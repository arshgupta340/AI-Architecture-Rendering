r"""FLUX.2 hero backend (EXPERIMENTAL / high-quality) — geometry-locked, on Modal.

The switchable "experimental" sibling of `spike/modal_flux.py` (which serves the LIVE,
verified FLUX.1-dev + ControlNet-Union backend). Same browser contract — `/hero_render`
+ `/region_edit` + `/warm`, CORS ASGI, shared-secret in the body — so the web app's
Backend panel switches FLUX.1 ↔ FLUX.2 just by pointing at this app's URL.

Why this is a SEPARATE app (not a flag in modal_flux.py):
  • FLUX.2-dev is a **32B** rectified-flow transformer + a **Mistral-Small-3.2-24B**
    text encoder → BF16 needs ~64-110 GB VRAM ("requires an H200"); it does NOT fit
    cleanly on the A100-80GB that FLUX.1 uses. → GPU defaults to **H200 (141 GB)**.
  • FLUX.2's only depth/canny ControlNet today is **alibaba-pai/FLUX.2-dev-Fun-
    Controlnet-Union**, which runs through the **VideoX-Fun** framework (aigc-apps/
    VideoX-Fun), NOT diffusers' `FluxControlNetPipeline`. So the model-loading + the
    pipeline call differ from modal_flux.py and live in their own image.

Geometry lock: the Fun-Controlnet-Union takes ONE structural `control_image` per pass
(it's "union" = one checkpoint covering canny/depth/pose/HED/MLSD/inpaint, fed one
control at a time — a 260-ch context = 128 control + 4 mask + 128 inpaint). We feed our
proven **canny ∪ instance-id edges** map (the 98.5%-edge-alignment recipe) as the canny
control. region_edit is a **NATIVE inpaint** (mask + base image) — a real upgrade over
FLUX.1's full-pass-then-composite.

  Secret (shared `arch-flux`): HF_TOKEN (FLUX.2-dev is gated), HERO_SHARED_SECRET (auth).

================================  DEPLOY-GATED  ================================
This is NOT deployed/verified (FLUX.1 is the live one). Bringing it up costs real GPU
($-per-render is ~2-4× FLUX.1 + a large one-time ~70 GB weight download). Before you
deploy, see spike/REPORTS/flux2_feasibility.md, then:

    modal run    spike/modal_flux2.py::warm_weights   # one-time: prefetch FLUX.2 + ControlNet
    modal deploy spike/modal_flux2.py                 # publish the web endpoint

FIRST-DEPLOY VALIDATION (the only non-obvious part — like gsplat in modal_splat.py):
the VideoX-Fun model-loading block in `load()` and the `pipeline(...)` call are written
against the repo's `examples/flux2_fun/predict_t2i_control.py` (and its z_image analog).
The exact `videox_fun.*` import paths + loader names can drift between VideoX-Fun
revisions — confirm them against the cloned repo on the first deploy and adjust the
clearly-marked block; the Modal scaffolding / contract / conditioning around it is final.
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Iterable

import modal

# --------------------------------------------------------------------------- #
# Config — GPU + memory mode are one-line consts so they're trivially swappable.
# --------------------------------------------------------------------------- #
GPU = "H200"  # 141 GB → clean BF16. A100-80GB works only with GPU_MEMORY_MODE below.
# VideoX-Fun memory modes: "" (none, needs H200/B200), "model_cpu_offload",
# "model_cpu_offload_and_qfloat8" (float8 DiT → fits A100-80GB), "sequential_cpu_offload".
GPU_MEMORY_MODE = ""  # set to "model_cpu_offload_and_qfloat8" if you swap GPU to "A100-80GB".

FLUX2_REPO = "black-forest-labs/FLUX.2-dev"
FUN_CN_REPO = "alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union"
FUN_CN_FILE = "FLUX.2-dev-Fun-Controlnet-Union-2602.safetensors"  # the CFG-distilled (better) variant
VIDEOX_FUN_REPO = "https://github.com/aigc-apps/VideoX-Fun.git"
MODEL_NAME = "flux2-dev-fun-union"  # reported by /warm so the app shows which backend it's on

# Same warm/negative prompts + scales philosophy as FLUX.1 (see modal_flux.py). The Fun
# ControlNet's recommended control strength is 0.65–0.80 (per the model card), vs FLUX.1's
# canny scale; we default mid-range.
WARM_PROMPT = (
    "A warm, photorealistic golden-hour architectural exterior photograph of a "
    "two-story house: crisp materials, white-painted trim, charcoal roof, divided-lite "
    "windows, a covered porch, concrete steps, a green lawn, warm low sun, long soft "
    "shadows, clear sky, shot on a DSLR, high detail. Preserve every edge, window, "
    "muntin, trim line, roof plane and post exactly — the line drawing is binding."
)
DEFAULT_NEGATIVE = (
    "blurry, distorted, warped geometry, extra windows, missing windows, low quality, "
    "cartoon, painting, text, watermark"
)
DEFAULT_CONTROL_SCALE = 0.7   # control_context_scale; Fun-Union optimal range 0.65–0.80
DEFAULT_STEPS = 28
DEFAULT_GUIDANCE = 4.0        # FLUX.2 docs suggest ~4; 28 steps a good trade-off
DEFAULT_SEED = 0


def _round16(n: int) -> int:
    return max(16, (int(n) // 16) * 16)


# --------------------------------------------------------------------------- #
# Image — CUDA-devel base + a clone of VideoX-Fun and its requirements. The clone
# happens at build time so the repo's `videox_fun` package is importable. (Pinned to a
# commit on first successful deploy for reproducibility — left at main here.)
# --------------------------------------------------------------------------- #
WEIGHTS_DIR = Path("/weights")
HF_CACHE = WEIGHTS_DIR / "hf-cache"
VIDEOX_DIR = "/root/VideoX-Fun"

flux2_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "build-essential", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.4.1", "torchvision==0.19.1", index_url="https://download.pytorch.org/whl/cu124"
    )
    .run_commands(f"git clone --depth 1 {VIDEOX_FUN_REPO} {VIDEOX_DIR}")
    # VideoX-Fun's own deps (the repo ships a requirements.txt covering diffusers /
    # transformers / accelerate / safetensors pins it was tested with).
    .run_commands(f"pip install -r {VIDEOX_DIR}/requirements.txt || true")
    .pip_install(
        "transformers>=4.49.0", "accelerate>=1.1.0", "safetensors", "sentencepiece",
        "protobuf", "Pillow", "numpy<2", "opencv-python-headless", "huggingface_hub",
        "einops", "omegaconf",
    )
    .pip_install("fastapi[standard]")  # Modal 1.4+ needs FastAPI in the image for the ASGI app
    .env({"PYTHONPATH": VIDEOX_DIR})   # so `import videox_fun` resolves the cloned repo
)

app = modal.App("arch-rendering-flux2", image=flux2_image)
volume = modal.Volume.from_name("arch-rendering-weights", create_if_missing=True)
secret = modal.Secret.from_name("arch-flux")  # HF_TOKEN + HERO_SHARED_SECRET (shared with FLUX.1)


# --------------------------------------------------------------------------- #
# b64 / image helpers + conditioning. These MIRROR spike/modal_flux.py (the source of
# truth); vendored here rather than imported so deploying FLUX.2 never rebuilds / risks
# the live FLUX.1 app. Keep them in sync if the FLUX.1 recipe changes.
# --------------------------------------------------------------------------- #
def _unb64(s: str) -> bytes:
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _pil(b64: str):
    from PIL import Image

    return Image.open(io.BytesIO(_unb64(b64))).convert("RGB")


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _decode_ids(ids_rgb_png: bytes):
    """Unpack the per-pixel instance id = r | g<<8 from the ids_rgb PNG (b channel 0)."""
    import numpy as np
    from PIL import Image

    rgb = np.array(Image.open(io.BytesIO(ids_rgb_png)).convert("RGB"), dtype=np.uint32)
    return rgb[:, :, 0] | (rgb[:, :, 1] << 8)


def prep_canny(beauty_png: bytes, ids_rgb_png: bytes):
    """canny(beauty) ∪ instance-id boundaries → the geometry lock (same recipe as FLUX.1).
    Returns a 1-channel 'L' edge map (white edges on black)."""
    import cv2
    import numpy as np
    from PIL import Image

    beauty = np.array(Image.open(io.BytesIO(beauty_png)).convert("RGB"))
    edges = cv2.Canny(cv2.cvtColor(beauty, cv2.COLOR_RGB2GRAY), 70, 160) > 0
    inst = _decode_ids(ids_rgb_png)
    bnd = np.zeros_like(inst, bool)
    bnd[:, :-1] |= inst[:, :-1] != inst[:, 1:]
    bnd[:-1, :] |= inst[:-1, :] != inst[1:, :]
    return Image.fromarray(((edges | bnd).astype(np.uint8) * 255))


# Region mask (dilate +1px, ~1px feather) — mirrors modal_flux.py / multiview_apply.py.
DILATE = 3
FEATHER = 1.1


def mask_png_from_ids(ids, region_ids: Iterable[int]) -> bytes:
    import cv2
    import numpy as np
    from PIL import Image

    m = np.isin(ids, list(region_ids)).astype(np.uint8) * 255
    if DILATE:
        m = cv2.dilate(m, np.ones((DILATE, DILATE), np.uint8))
    img = Image.fromarray(m)
    if FEATHER:
        from PIL import ImageFilter

        img = img.filter(ImageFilter.GaussianBlur(FEATHER))
    return _png_bytes(img)


# --------------------------------------------------------------------------- #
# warm_weights — one-time prefetch into the Volume (no GPU). Run via `modal run`.
# --------------------------------------------------------------------------- #
@app.function(volumes={str(WEIGHTS_DIR): volume}, secrets=[secret], timeout=7200)
def warm_weights():
    """Snapshot FLUX.2-dev (~70 GB) + the Fun ControlNet (~8 GB) into /weights/hf-cache and
    commit the Volume so cold starts skip the (large) download.

        modal run spike/modal_flux2.py::warm_weights
    """
    import os

    from huggingface_hub import snapshot_download

    HF_CACHE.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("[warm_weights] WARNING: HF_TOKEN not set — FLUX.2-dev is GATED; the "
              "download will 401. Accept the license + add HF_TOKEN to the arch-flux secret.")

    print(f"[warm_weights] snapshot_download {FLUX2_REPO} (~70 GB, slow) ...")
    snapshot_download(repo_id=FLUX2_REPO, cache_dir=str(HF_CACHE), token=token)
    print(f"[warm_weights] snapshot_download {FUN_CN_REPO} ...")
    snapshot_download(repo_id=FUN_CN_REPO, cache_dir=str(HF_CACHE), token=token)

    volume.commit()
    print(f"[warm_weights] committed Volume -> {HF_CACHE}")


# --------------------------------------------------------------------------- #
# HeroFlux2 — the GPU class. One warm VideoX-Fun pipeline, three endpoints.
# --------------------------------------------------------------------------- #
@app.cls(
    gpu=GPU,
    volumes={str(WEIGHTS_DIR): volume},
    secrets=[secret],
    min_containers=0,       # scale to zero between sessions (no idle GPU spend)
    scaledown_window=300,   # keep the warm pipe ~5 min after the last request
    timeout=900,            # FLUX.2 is heavier; allow a longer cold start
)
class HeroFlux2:
    @modal.enter()
    def load(self):
        """Build the FLUX.2 + Fun-Controlnet-Union pipeline once per container.

        ┌─ FIRST-DEPLOY VALIDATION ────────────────────────────────────────────────┐
        │ This block uses VideoX-Fun's loaders + Flux2 control pipeline, written     │
        │ against examples/flux2_fun/predict_t2i_control.py (+ the z_image_fun        │
        │ analog). The `videox_fun.*` import paths / class names can drift between    │
        │ repo revisions — confirm against the cloned repo at /root/VideoX-Fun on the │
        │ first deploy and adjust ONLY this block. Everything else (contract, CORS,   │
        │ conditioning, auth) is final.                                               │
        └────────────────────────────────────────────────────────────────────────────┘
        """
        import os

        import torch

        HF_CACHE.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(HF_CACHE))
        os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE))
        token = os.environ.get("HF_TOKEN")
        self.dtype = torch.bfloat16
        self.device = "cuda"

        from huggingface_hub import snapshot_download

        # Resolve the on-Volume paths (warm_weights already downloaded these).
        flux2_dir = snapshot_download(FLUX2_REPO, cache_dir=str(HF_CACHE), token=token)
        cn_dir = snapshot_download(FUN_CN_REPO, cache_dir=str(HF_CACHE), token=token)
        cn_path = os.path.join(cn_dir, FUN_CN_FILE)

        # --- VideoX-Fun load (validate names on first deploy) ---------------------
        # Mirrors examples/flux2_fun/predict_t2i_control.py:
        from videox_fun.models import (  # type: ignore
            AutoencoderKLFlux2,
            Flux2Transformer2DModel,
        )
        from videox_fun.models.flux2_controlnet import (  # type: ignore
            load_flux2_controlnet_in_model,
        )
        from videox_fun.pipeline import Flux2ControlPipeline  # type: ignore
        from transformers import AutoTokenizer, Mistral3ForConditionalGeneration

        transformer = Flux2Transformer2DModel.from_pretrained(
            flux2_dir, subfolder="transformer", torch_dtype=self.dtype
        )
        # Inject the Fun ControlNet into the transformer (adds control to 4 double blocks).
        transformer = load_flux2_controlnet_in_model(transformer, cn_path, device=self.device)
        vae = AutoencoderKLFlux2.from_pretrained(flux2_dir, subfolder="vae", torch_dtype=self.dtype)
        text_encoder = Mistral3ForConditionalGeneration.from_pretrained(
            flux2_dir, subfolder="text_encoder", torch_dtype=self.dtype
        )
        tokenizer = AutoTokenizer.from_pretrained(flux2_dir, subfolder="tokenizer")
        from videox_fun.utils.fp8_optimization import convert_model_weight_to_float8  # type: ignore  # noqa: F401

        self.pipe = Flux2ControlPipeline(
            vae=vae, tokenizer=tokenizer, text_encoder=text_encoder, transformer=transformer,
        )
        # Memory mode for the chosen GPU (qfloat8 lets the 32B DiT fit on A100-80GB).
        if GPU_MEMORY_MODE == "model_cpu_offload_and_qfloat8":
            convert_model_weight_to_float8(transformer)
            self.pipe.enable_model_cpu_offload(device=self.device)
        elif GPU_MEMORY_MODE == "model_cpu_offload":
            self.pipe.enable_model_cpu_offload(device=self.device)
        elif GPU_MEMORY_MODE == "sequential_cpu_offload":
            self.pipe.enable_sequential_cpu_offload(device=self.device)
        else:
            self.pipe.to(self.device)  # H200/B200: full BF16 resident
        print(f"[HeroFlux2] pipeline ready on {self.device} (mem mode={GPU_MEMORY_MODE or 'none'})")

    # ---- shared core: one control pass (optionally inpaint) -> PIL image -------
    def _run(self, *, control_pil, prompt, negative_prompt, width, height, seed, steps,
             guidance_scale, control_scale, inpaint_pil=None, mask_pil=None):
        import torch

        gen = torch.Generator(device=self.device).manual_seed(int(seed))
        kwargs = dict(
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=height,
            width=width,
            generator=gen,
            guidance_scale=guidance_scale,
            control_image=control_pil,
            num_inference_steps=steps,
            control_context_scale=control_scale,
        )
        # Native inpaint path: pass the base image + mask (white = regenerate). For a
        # full t2i pass the VideoX-Fun example passes zeros / a full-white mask.
        if inpaint_pil is not None and mask_pil is not None:
            kwargs["image"] = inpaint_pil
            kwargs["mask_image"] = mask_pil
        return self.pipe(**kwargs).images[0]

    def _conditioning(self, body: dict, width: int, height: int):
        """Build the single canny ∪ id-edges control at (width, height), 3-channel RGB."""
        from PIL import Image as _Image

        if body.get("canny"):
            canny = _Image.open(io.BytesIO(_unb64(body["canny"]))).convert("L")
        else:
            canny = prep_canny(_unb64(body["beauty"]), _unb64(body["ids_rgb"]))
        if canny.size != (width, height):
            canny = canny.resize((width, height), _Image.NEAREST)
        return canny.convert("RGB")

    @staticmethod
    def _dims(body: dict, fallback_img):
        w = body.get("width") or fallback_img.size[0]
        h = body.get("height") or fallback_img.size[1]
        return _round16(w), _round16(h)

    @staticmethod
    def _check_auth(body: dict):
        import os

        from fastapi import HTTPException

        expected = os.environ.get("HERO_SHARED_SECRET")
        if not expected:
            raise HTTPException(status_code=401, detail="HERO_SHARED_SECRET not configured")
        if body.get("secret") != expected:
            raise HTTPException(status_code=401, detail="bad secret")

    # ---- /hero_render core: full geometry-locked render -----------------------
    def _hero_core(self, body: dict) -> dict:
        t0 = time.monotonic()
        beauty_img = _pil(body["beauty"])
        width, height = self._dims(body, beauty_img)
        control = self._conditioning(body, width, height)
        seed = int(body.get("seed", DEFAULT_SEED))
        img = self._run(
            control_pil=control,
            prompt=body.get("prompt") or WARM_PROMPT,
            negative_prompt=body.get("negative_prompt") or DEFAULT_NEGATIVE,
            width=width, height=height, seed=seed,
            steps=int(body.get("steps", DEFAULT_STEPS)),
            guidance_scale=float(body.get("guidance_scale", DEFAULT_GUIDANCE)),
            control_scale=float(body.get("control_scale", DEFAULT_CONTROL_SCALE)),
        )
        ms = int((time.monotonic() - t0) * 1000)
        print(f"[flux2 hero] {width}x{height} seed={seed} in {ms} ms")
        return {"image": _b64(_png_bytes(img)), "seed": seed, "ms": ms}

    # ---- /region_edit core: TRUE native inpaint (FLUX.2 advantage) ------------
    # Unlike FLUX.1 (full pass + composite), the Fun-Union runs a real inpaint: only the
    # masked region is regenerated, conditioned on the surrounding base pixels → seam-
    # consistent lighting. Body adds { base, region_ids:[int], mask? }.
    def _region_core(self, body: dict) -> dict:
        from PIL import Image as _Image

        t0 = time.monotonic()
        beauty_img = _pil(body["beauty"])
        width, height = self._dims(body, beauty_img)
        control = self._conditioning(body, width, height)
        base = _Image.open(io.BytesIO(_unb64(body["base"]))).convert("RGB").resize((width, height))

        if body.get("mask"):
            mask_png = _unb64(body["mask"])
        else:
            ids = _decode_ids(_unb64(body["ids_rgb"]))
            mask_png = mask_png_from_ids(ids, body.get("region_ids", []))
        mask = _Image.open(io.BytesIO(mask_png)).convert("L").resize((width, height))

        seed = int(body.get("seed", DEFAULT_SEED))
        img = self._run(
            control_pil=control,
            prompt=body.get("prompt") or WARM_PROMPT,
            negative_prompt=body.get("negative_prompt") or DEFAULT_NEGATIVE,
            width=width, height=height, seed=seed,
            steps=int(body.get("steps", DEFAULT_STEPS)),
            guidance_scale=float(body.get("guidance_scale", DEFAULT_GUIDANCE)),
            control_scale=float(body.get("control_scale", DEFAULT_CONTROL_SCALE)),
            inpaint_pil=base, mask_pil=mask,   # ← native inpaint
        )
        ms = int((time.monotonic() - t0) * 1000)
        print(f"[flux2 region] {width}x{height} seed={seed} ids={body.get('region_ids')} in {ms} ms")
        return {"image": _b64(_png_bytes(img)), "mask": _b64(mask_png), "seed": seed, "ms": ms}

    # ---- web: ONE CORS ASGI app, same routes/contract as modal_flux.py --------
    @modal.asgi_app()
    def web(self):
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse

        api = FastAPI()
        api.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )

        @api.exception_handler(Exception)
        async def _all_errors(_req: Request, exc: Exception):
            import traceback

            traceback.print_exc()
            return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

        @api.post("/hero_render")
        def hero_render(body: dict):
            self._check_auth(body)
            return self._hero_core(body)

        @api.post("/region_edit")
        def region_edit(body: dict):
            self._check_auth(body)
            return self._region_core(body)

        @api.post("/warm")
        def warm(body: dict):
            self._check_auth(body)
            return {"warm": True, "model": MODEL_NAME, "pipe_loaded": hasattr(self, "pipe")}

        return api


@app.local_entrypoint()
def info():
    """`modal run spike/modal_flux2.py` — prints the deploy hint (no GPU spend)."""
    print("FLUX.2 hero backend (EXPERIMENTAL, deploy-gated).")
    print(f"  GPU = {GPU};  memory mode = {GPU_MEMORY_MODE or 'none (full BF16)'}")
    print("  warm:   modal run    spike/modal_flux2.py::warm_weights   (~70 GB download)")
    print("  deploy: modal deploy spike/modal_flux2.py")
    print("  Then paste the …flux2-heroflux2-web.modal.run/{hero_render,region_edit} URLs")
    print("  into the app's Hero Backend panel (FLUX.2 preset). See spike/REPORTS/flux2_feasibility.md")
    print("  FIRST-DEPLOY: validate the VideoX-Fun loader block in HeroFlux2.load().")
