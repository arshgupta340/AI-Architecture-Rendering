r"""Scene-bake: train a 3D Gaussian Splat from posed renders, on Modal.

The "convert our scene → splat" backend for the web app. The browser
(apps/web3d-prototype/src/lib/splatBake.ts) orbits the camera through ~42 posed
views, renders each, and POSTs the images + a nerfstudio `transforms.json` here.
Because we KNOW the exact camera poses (three.js -Z forward == nerfstudio/OpenGL),
there is NO COLMAP / structure-from-motion step — we feed the poses straight to
nerfstudio `splatfacto`, train, export a `.ply`, and hand it back. The browser then
renders it with @sparkjsdev/spark as a photoreal backdrop.

Training is long (~15-25 min), so the HTTP endpoint SPAWNs the training function and
returns a `job_id`; the client polls the same endpoint with `{job_id}` until the
`.ply` is ready. Apache-2.0 stack (nerfstudio + gsplat), commercial-safe.

  Secret keys (on the shared `arch-flux` Modal secret): HERO_SHARED_SECRET (auth).

Deploy runbook (see spike/REPORTS/modal_flux.md §splat):
    modal deploy spike/modal_splat.py          # publish the bake endpoint
  Then paste the `…splatbake-web.modal.run/bake` URL into the app's Splat panel.

NOTE: the IMAGE BUILD (CUDA devel + nerfstudio + gsplat JIT) is the part to verify on
your first `modal deploy` — gsplat compiles CUDA kernels. If the build is flaky, pin
gsplat to a prebuilt wheel for the CUDA/torch combo (see the commented alt below).
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

import modal

GPU = "A100-80GB"  # swap to "H100" for faster training

# CUDA *devel* base (nvcc present) so gsplat can build its kernels. nerfstudio pulls a
# compatible gsplat; torch is installed against cu121 to match the base toolkit.
splat_image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "build-essential", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install("torch==2.1.2", "torchvision==0.16.2", index_url="https://download.pytorch.org/whl/cu121")
    .pip_install("ninja")
    .pip_install("nerfstudio==1.1.5")  # pulls a matching gsplat; splatfacto lives here
    .pip_install("fastapi[standard]")  # Modal 1.4+ requires FastAPI for @modal.fastapi_endpoint
    .env({"TORCH_CUDA_ARCH_LIST": "8.0;9.0"})  # A100=8.0, H100=9.0
)

app = modal.App("arch-rendering-splatbake", image=splat_image)
volume = modal.Volume.from_name("arch-rendering-weights", create_if_missing=True)
secret = modal.Secret.from_name("arch-flux")  # HERO_SHARED_SECRET (shared with modal_flux)


def _unb64(s: str) -> bytes:
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


# --------------------------------------------------------------------------- #
# train — the heavy GPU job (spawned async by the endpoint).
# --------------------------------------------------------------------------- #
@app.function(gpu=GPU, timeout=3600, volumes={"/cache": volume})
def train(transforms: dict, images: list[dict], iterations: int = 20000) -> str:
    """Write the posed dataset, run `ns-train splatfacto`, export + return a .ply (b64)."""
    import json
    import shutil
    import subprocess
    import tempfile

    work = Path(tempfile.mkdtemp(prefix="bake_"))
    data = work / "data"
    (data / "images").mkdir(parents=True, exist_ok=True)
    for im in images:
        (data / "images" / im["name"]).write_bytes(_unb64(im["b64"]))
    (data / "transforms.json").write_text(json.dumps(transforms))

    out = work / "out"
    print(f"[train] {len(images)} views, {iterations} iters → splatfacto")
    subprocess.run(
        [
            "ns-train", "splatfacto",
            "--data", str(data),
            "--output-dir", str(out),
            "--max-num-iterations", str(int(iterations)),
            "--viewer.quit-on-train-completion", "True",
            "--pipeline.model.cull-alpha-thresh", "0.005",
            # Synthetic, perfect poses + no SfM point cloud → random init.
            "nerfstudio-data", "--orientation-method", "none", "--center-method", "none",
            "--auto-scale-poses", "False",
        ],
        check=True,
    )

    # Find the trained config, export the gaussian splat .ply.
    configs = list(out.rglob("config.yml"))
    if not configs:
        raise RuntimeError("training produced no config.yml")
    config = sorted(configs, key=lambda p: p.stat().st_mtime)[-1]
    ply_dir = work / "ply"
    ply_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["ns-export", "gaussian-splat", "--load-config", str(config), "--output-dir", str(ply_dir)],
        check=True,
    )
    plys = list(ply_dir.rglob("*.ply"))
    if not plys:
        raise RuntimeError("export produced no .ply")
    ply_bytes = plys[0].read_bytes()
    print(f"[train] exported {plys[0].name} ({len(ply_bytes)/1e6:.1f} MB)")
    shutil.rmtree(work, ignore_errors=True)
    return _b64(ply_bytes)


def _check_auth(body: dict):
    import os

    from fastapi import HTTPException

    expected = os.environ.get("HERO_SHARED_SECRET")
    if not expected:
        raise HTTPException(status_code=401, detail="HERO_SHARED_SECRET not configured")
    if body.get("secret") != expected:
        raise HTTPException(status_code=401, detail="bad secret")


# --------------------------------------------------------------------------- #
# web — ONE ASGI app (FastAPI + CORSMiddleware) serving POST /bake. A real FastAPI
#       app is needed because the browser POSTs cross-origin: Modal's per-endpoint
#       decorator only CORS-es the OPTIONS preflight, not the response, so the fetch
#       fails. POST /bake: start (transforms present) → spawn + {job_id}; poll
#       ({job_id} only) → {job_id} (training) | {ply_b64} (done).
# --------------------------------------------------------------------------- #
@app.function(secrets=[secret], timeout=120)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    api = FastAPI()
    api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @api.exception_handler(Exception)
    async def _err(_r: Request, exc: Exception):
        import traceback

        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

    @api.post("/bake")
    def bake(body: dict):
        _check_auth(body)
        # Poll path.
        if body.get("job_id") and not body.get("transforms"):
            call = modal.functions.FunctionCall.from_id(body["job_id"])
            try:
                return {"ply_b64": call.get(timeout=0)}
            except TimeoutError:
                return {"job_id": body["job_id"]}
            except Exception as e:  # noqa: BLE001 — surface training failures to the client
                raise HTTPException(status_code=500, detail=f"training failed: {e}")
        # Start path.
        transforms = body.get("transforms")
        images = body.get("images")
        if not transforms or not images:
            raise HTTPException(status_code=400, detail="need transforms + images to start a bake")
        call = train.spawn(transforms, images, int(body.get("iterations", 20000)))
        return {"job_id": call.object_id}

    return api


@app.local_entrypoint()
def info():
    """`modal run spike/modal_splat.py` — prints the deploy hint (no GPU spend)."""
    print("Deploy with:  modal deploy spike/modal_splat.py")
    print("Then paste the  …splatbake-web.modal.run/bake  URL into the app's Splat panel (source: Bake).")
    print(f"GPU = {GPU};  training ~15-25 min for ~42 views @ 20k iters.")
    print("Build risk: gsplat CUDA kernels compile in the image — watch the first deploy.")
