r"""Self-hosted FLUX.1-dev + ControlNet-Union-Pro-2.0 (canny + depth) on Modal.

This is the production "Hero render" backend for the web app. It replaces the
fal-ai/flux-general proxy used in research (spike/run_e2b_registration.py) with a
self-hosted pair of HTTPS endpoints so the web app owns the model, the seed, and
the geometry-lock recipe end to end.

It ports the *proven* E2b recipe verbatim:
  - canny  = cv2.Canny(beauty, 70, 160)  UNION  instance-id pixel boundaries,
             at the exact ground-truth position. Pins openings / trim.
  - depth  = 1/99-percentile normalize of the depth buffer + 1px Gaussian blur.
             Pins massing.
  - A SINGLE Shakker-Labs FLUX.1-dev-ControlNet-Union-Pro-2.0 checkpoint drives
    BOTH controls via list args (canny mode 0 @0.8 end 0.85, depth mode 2 @0.5
    end 0.7), 32 steps, guidance 3.5. (Edge alignment 51.7% -> 98.5% within 2px.)

Endpoints (FastAPI, POST):
  - hero_render  — base render of a fresh capture (computes canny + depth server
                   side from the raw buffers, runs the dual-controlnet pass).
  - region_edit  — re-clad one region: a full controlnet pass with the region
                   prompt + SAME seed + SAME controls, composited ONLY through the
                   region mask over `base` so untouched pixels stay byte-stable.

Two tiny helpers are VENDORED (copied, not imported) from the spike package so the
Modal image needs nothing beyond the pinned wheels:
  - mask_png_from_ids  <- spike/multiview_apply.py  (dilate +1px, feather ~1px)
  - paste_tile         <- spike/composite.py        (PIL Image.composite)

This app is INDEPENDENT of spike/modal_app.py (which is frozen). It shares only
the Volume `arch-rendering-weights` and the secret `arch-spike`; it uses a
SEPARATE app name (`arch-rendering-flux`) and a SEPARATE image, so deploying it
never rebuilds the frozen app's container.

  Secret: the dedicated `arch-flux` Modal secret carries:
    HF_TOKEN            FLUX.1-dev is a GATED model on HuggingFace; the warm /
                        runtime download needs a token with access accepted at
                        https://huggingface.co/black-forest-labs/FLUX.1-dev
    HERO_SHARED_SECRET  shared secret the web app sends in the request BODY
                        (`body["secret"]`); both endpoints 401 on mismatch.

Deploy runbook (see spike/REPORTS/modal_flux.md for the full version):
    modal run    spike/modal_flux.py::warm_weights     # one-time weight prefetch
    modal deploy spike/modal_flux.py                    # publish both endpoints
    modal run    spike/modal_flux.py                    # local smoke (optional)
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Iterable

import modal

# --------------------------------------------------------------------------- #
# Config — GPU is a one-line const so it is trivially swappable.
# --------------------------------------------------------------------------- #
GPU = "A100-80GB"  # swap to "H100" (faster) or "A10G" (cheaper, slower, tight VRAM)

FLUX_REPO = "black-forest-labs/FLUX.1-dev"
UNION_REPO = "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0"

# Warm, specific default prompt — recovers terracotta siding + golden-hour light
# while the canny lock holds geometry (ported from run_e2b_registration.WARM_PROMPT).
WARM_PROMPT = (
    "A warm, photorealistic golden-hour architectural exterior photograph of a "
    "two-story craftsman house: terracotta red-painted wood lap siding, crisp "
    "white-painted trim and window casings, dark charcoal asphalt-shingle roof, "
    "white divided-lite windows, black metal porch railings, a covered front "
    "porch with white columns, concrete foundation and front steps, a green "
    "sloping lawn, rich saturated colours, warm low-angle sunlight with long "
    "soft shadows, clear blue sky, shot on a DSLR, high detail. "
    "Preserve every edge, window, muntin, trim line, roof plane and post exactly "
    "at its position and scale — the line drawing is binding."
)
DEFAULT_NEGATIVE = (
    "blurry, distorted, warped geometry, extra windows, missing windows, "
    "low quality, cartoon, painting, text, watermark"
)

# Dual-controlnet scales (E2b winner): canny pins openings/trim, depth pins massing.
DEFAULT_CANNY_SCALE = 0.8
DEFAULT_CANNY_END = 0.85
DEFAULT_DEPTH_SCALE = 0.5
DEFAULT_DEPTH_END = 0.7
DEFAULT_STEPS = 32
DEFAULT_GUIDANCE = 3.5
DEFAULT_SEED = 0
# true_cfg_scale > 1 turns on real classifier-free guidance so the NEGATIVE prompt
# actually applies (FLUX is guidance-distilled; the negative prompt is IGNORED at the
# 1.0 default). >1 roughly doubles inference time (two forward passes per step). The
# proven E2b fal recipe used real_cfg_scale 3.5, so 3.5 is the "strict" value.
DEFAULT_TRUE_CFG = 1.0

# FLUX's VAE downscales by 16 — width/height MUST be multiples of 16 or the pipeline
# errors. Round the requested size down to the nearest 16.
def _round16(n: int) -> int:
    return max(16, (int(n) // 16) * 16)

# ControlNet-Union control_mode ints (per Shakker-Labs Union-Pro-2.0): canny=0, depth=2.
CANNY_MODE = 0
DEPTH_MODE = 2

# --------------------------------------------------------------------------- #
# Image — SEPARATE from modal_app.py's frozen image (do NOT reuse it).
# --------------------------------------------------------------------------- #
flux_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "torchvision",
        extra_index_url="https://download.pytorch.org/whl/cu124",
    )
    .pip_install(
        "diffusers>=0.32",
        "transformers",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "protobuf",
        "Pillow",
        "numpy",
        "opencv-python-headless",
        "huggingface_hub",
    )
)

app = modal.App("arch-rendering-flux", image=flux_image)

# Shared with modal_app.py — same weights cache Volume, same secret name.
volume = modal.Volume.from_name("arch-rendering-weights", create_if_missing=True)
WEIGHTS_DIR = Path("/weights")
HF_CACHE = WEIGHTS_DIR / "hf-cache"

# Dedicated secret `arch-flux` carries HF_TOKEN (FLUX.1-dev is gated) +
# HERO_SHARED_SECRET (endpoint auth). Kept separate from `arch-spike` so it doesn't
# clobber that secret's GOOGLE_API_KEY (used by the frozen modal_app.py).
secret = modal.Secret.from_name("arch-flux")


# --------------------------------------------------------------------------- #
# base64 / PIL helpers (bare base64 — no `data:` prefix on the wire)
# --------------------------------------------------------------------------- #
def _b64(png_bytes: bytes) -> str:
    """Encode raw PNG bytes -> bare base64 string."""
    return base64.b64encode(png_bytes).decode("ascii")


def _unb64(s: str) -> bytes:
    """Decode a bare base64 string -> raw bytes. Tolerates an accidental
    `data:...;base64,` prefix so a sloppy caller still works."""
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _pil(b64: str):
    """Decode a bare base64 PNG -> PIL.Image."""
    from PIL import Image

    return Image.open(io.BytesIO(_unb64(b64)))


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# VENDORED helpers — copied (not imported) so the Modal image needs no spike pkg.
# --------------------------------------------------------------------------- #
# Source: spike/multiview_apply.py  (DILATE / FEATHER / mask_png_from_ids).
# Registration is tight post-E2b (98% of edges within 2px), so dilate only +1px to
# cover the anti-aliased ring, then feather ~1px so the composite hides hairline
# seams at trim boundaries.
DILATE = 3      # PIL MaxFilter window: +1px each side
FEATHER = 1.1   # Gaussian blur radius on the mask edge


def mask_png_from_ids(ids, region_ids: Iterable[int]) -> bytes:
    """Soft union mask for instance ids (+1px dilate, ~1px feather).
    VENDORED from spike/multiview_apply.py:mask_png_from_ids."""
    import numpy as np
    from PIL import Image, ImageFilter

    m = np.isin(ids, list(region_ids))
    img = Image.fromarray((m * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(DILATE)).filter(ImageFilter.GaussianBlur(FEATHER))
    return _png_bytes(img)


def paste_tile(base: bytes, mask: bytes, tile: bytes) -> bytes:
    """Composite `tile` onto `base` through grayscale `mask` (white=tile, black=base;
    soft edges blend). All PNG bytes in/out; output is RGB.
    VENDORED from spike/composite.py:paste_tile."""
    from PIL import Image

    base_img = Image.open(io.BytesIO(base)).convert("RGBA")
    tile_img = Image.open(io.BytesIO(tile)).convert("RGBA").resize(base_img.size)
    mask_img = Image.open(io.BytesIO(mask)).convert("L").resize(base_img.size)
    result = Image.composite(tile_img, base_img, mask_img)
    return _png_bytes(result.convert("RGB"))


# --------------------------------------------------------------------------- #
# Conditioning prep — ported from run_e2b_registration, now taking BYTES.
# --------------------------------------------------------------------------- #
def prep_depth(depth_png: bytes):
    """1/99-percentile normalize the depth buffer + 1px Gaussian blur -> PIL 'L'.
    Ported from run_e2b_registration.prep_depth (dir -> bytes).

    CONVENTION (verified against FLUX/MiDaS depth ControlNets — RunComfy + lllyasviel
    docs): the control image must be NEAR = WHITE, FAR = BLACK (closer = brighter).
    The web capture (lib/heroCapture.ts) already renders LINEAR eye-space depth with
    near=white, so this function only NORMALIZES — it does NOT invert. `hits` (d>0) is
    the in-scene mask; background (d==0) stays black (treated as far)."""
    import numpy as np
    from PIL import Image, ImageFilter

    d = np.array(Image.open(io.BytesIO(depth_png)).convert("L")).astype(float)
    hits = d > 0
    if not hits.any():
        # Degenerate (all-zero) depth: return a mid-grey plane so the pass still runs.
        return Image.fromarray(np.full(d.shape, 128, np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    lo, hi = np.percentile(d[hits], 1), np.percentile(d[hits], 99)
    n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    n[~hits] = 0.0
    return Image.fromarray((n * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))


def _decode_ids(ids_rgb_png: bytes):
    """Decode an RGB instance-id image to an int32 id array: id = r | (g << 8).
    (Matches the canvas capture's id encoding; b is unused / reserved.)"""
    import numpy as np
    from PIL import Image

    rgb = np.array(Image.open(io.BytesIO(ids_rgb_png)).convert("RGB")).astype(np.int32)
    return rgb[..., 0] | (rgb[..., 1] << 8)


def prep_canny(beauty_png: bytes, ids_rgb_png: bytes):
    """Canny(beauty) UNION instance-boundary edges -> PIL 'L' (exact GT lines).
    Ported from run_e2b_registration.prep_canny (dir -> bytes; ids decoded as
    r | g<<8 instead of read from a pre-decoded instance_ids.png)."""
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


# --------------------------------------------------------------------------- #
# warm_weights — one-time prefetch into the Volume (no GPU). Run via `modal run`.
# --------------------------------------------------------------------------- #
@app.function(volumes={str(WEIGHTS_DIR): volume}, secrets=[secret], timeout=3600)
def warm_weights():
    """Snapshot FLUX.1-dev + the Union ControlNet into /weights/hf-cache and commit
    the Volume so cold starts skip the download. Run ONCE:

        modal run spike/modal_flux.py::warm_weights
    """
    import os

    from huggingface_hub import snapshot_download

    HF_CACHE.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("[warm_weights] WARNING: HF_TOKEN not set — FLUX.1-dev is gated and "
              "the download will 401. Add HF_TOKEN to the `arch-spike` secret.")

    for repo in (FLUX_REPO, UNION_REPO):
        print(f"[warm_weights] snapshot_download {repo} ...")
        snapshot_download(repo_id=repo, cache_dir=str(HF_CACHE), token=token)
        print(f"[warm_weights]   done: {repo}")

    volume.commit()
    print(f"[warm_weights] committed Volume -> {HF_CACHE}")


# --------------------------------------------------------------------------- #
# HeroFlux — the GPU class. One warm pipe, two endpoints.
# --------------------------------------------------------------------------- #
@app.cls(
    gpu=GPU,
    volumes={str(WEIGHTS_DIR): volume},
    secrets=[secret],
    min_containers=0,       # scale to zero between sessions (no idle GPU spend)
    scaledown_window=300,   # keep the warm pipe ~5 min after the last request
    timeout=600,
)
class HeroFlux:
    @modal.enter()
    def load(self):
        """Build the FLUX + Union ControlNet pipeline once per container.

        A single FluxControlNetModel (the Union checkpoint) drives BOTH canny and
        depth; it is passed to FluxControlNetPipeline as the `controlnet`.
        """
        import os

        import torch
        from diffusers import FluxControlNetModel, FluxControlNetPipeline

        # Point HF + diffusers at the Volume cache so we reuse warm_weights' download.
        HF_CACHE.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(HF_CACHE))
        os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE))
        token = os.environ.get("HF_TOKEN")

        dtype = torch.bfloat16
        print(f"[HeroFlux] loading ControlNet-Union {UNION_REPO} ...")
        controlnet = FluxControlNetModel.from_pretrained(
            UNION_REPO, torch_dtype=dtype, cache_dir=str(HF_CACHE), token=token
        )
        print(f"[HeroFlux] loading FLUX pipeline {FLUX_REPO} ...")
        self.pipe = FluxControlNetPipeline.from_pretrained(
            FLUX_REPO,
            controlnet=controlnet,
            torch_dtype=dtype,
            cache_dir=str(HF_CACHE),
            token=token,
        ).to("cuda")
        print("[HeroFlux] pipeline ready on cuda")

    # ---- shared core: one dual-controlnet pass -> PIL image -------------------
    def _run_pipe(
        self,
        *,
        canny_pil,
        depth_pil,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: int,
        steps: int,
        guidance_scale: float,
        canny_scale: float,
        canny_end: float,
        depth_scale: float,
        depth_end: float,
        true_cfg_scale: float = DEFAULT_TRUE_CFG,
    ):
        """The verified diffusers call: one FluxControlNetModel, two controls via
        list args (canny=mode 0, depth=mode 2). `true_cfg_scale` > 1 enables the
        negative prompt (real CFG); == 1 ignores it (FLUX distilled guidance only)."""
        import torch

        img = self.pipe(
            prompt=prompt,
            prompt_2=prompt,
            negative_prompt=negative_prompt,
            true_cfg_scale=float(true_cfg_scale),
            control_image=[canny_pil, depth_pil],
            control_mode=[CANNY_MODE, DEPTH_MODE],          # canny=0, depth=2
            controlnet_conditioning_scale=[canny_scale, depth_scale],
            control_guidance_start=[0.0, 0.0],
            control_guidance_end=[canny_end, depth_end],
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=torch.Generator("cuda").manual_seed(int(seed)),
        ).images[0]
        return img

    def _conditioning(self, body: dict, width: int, height: int):
        """Build (canny_pil, depth_pil) at exactly (width, height).

        canny is computed SERVER-SIDE from beauty + ids_rgb unless the caller
        supplied a precomputed `canny` PNG; depth from the depth buffer.
        """
        beauty_b64 = body["beauty"]
        ids_b64 = body["ids_rgb"]
        depth_b64 = body["depth"]

        depth_pil = prep_depth(_unb64(depth_b64))
        if body.get("canny"):
            from PIL import Image

            canny_pil = Image.open(io.BytesIO(_unb64(body["canny"]))).convert("L")
        else:
            canny_pil = prep_canny(_unb64(beauty_b64), _unb64(ids_b64))

        # Controls must match the output grid exactly (no resize drift). Canny is a
        # hard binary edge map → NEAREST so the lines stay crisp (bilinear would blur
        # the lock); depth is continuous → bilinear (default) is correct.
        from PIL import Image as _Image

        if canny_pil.size != (width, height):
            canny_pil = canny_pil.resize((width, height), _Image.NEAREST)
        if depth_pil.size != (width, height):
            depth_pil = depth_pil.resize((width, height), _Image.BILINEAR)
        return canny_pil, depth_pil

    @staticmethod
    def _dims(body: dict, fallback_img) -> tuple[int, int]:
        """Output dimensions: explicit width/height if given, else the beauty size —
        rounded DOWN to a multiple of 16 (FLUX VAE constraint)."""
        w = body.get("width") or fallback_img.size[0]
        h = body.get("height") or fallback_img.size[1]
        return _round16(w), _round16(h)

    @staticmethod
    def _check_auth(body: dict):
        """Shared-secret auth. The secret travels in the JSON body (`body["secret"]`)
        — NOT a FastAPI Header — so the module never needs to import `fastapi` at the
        top level (it isn't in the local `modal deploy` env) and there's no header /
        query ambiguity. Fail-closed: a missing server secret refuses everything."""
        import os

        from fastapi import HTTPException

        expected = os.environ.get("HERO_SHARED_SECRET")
        if not expected:
            raise HTTPException(status_code=401, detail="HERO_SHARED_SECRET not configured")
        if body.get("secret") != expected:
            raise HTTPException(status_code=401, detail="bad secret")

    # ----------------------------------------------------------------------- #
    # Endpoint 1 — hero_render: base render of a fresh capture.
    # ----------------------------------------------------------------------- #
    @modal.fastapi_endpoint(method="POST")
    def hero_render(self, body: dict):
        """POST a capture's buffers + render params -> a photoreal base render.

        Request JSON (all images are BARE base64 PNG, no `data:` prefix):
          {
            "secret":          str,         # shared-secret auth (REQUIRED)
            "beauty":          <b64 png>,   # shaded viewport screenshot
            "depth":           <b64 png>,   # LINEAR depth, NEAR=white FAR=black
            "ids_rgb":         <b64 png>,   # instance ids as RGB (id = r | g<<8)
            "canny":           <b64 png>?,  # optional precomputed canny; else server-computed
            "prompt":          str?,        # default WARM_PROMPT
            "negative_prompt": str?,        # default DEFAULT_NEGATIVE
            "width":           int?,        # default beauty width  (rounded to /16)
            "height":          int?,        # default beauty height (rounded to /16)
            "seed":            int?,        # default 0
            "steps":           int?,        # default 32
            "guidance_scale":  float?,      # default 3.5
            "true_cfg_scale":  float?,      # default 1.0 (>1 enables the negative prompt)
            "canny_scale":     float?,      # default 0.8
            "canny_end":       float?,      # default 0.85
            "depth_scale":     float?,      # default 0.5
            "depth_end":       float?       # default 0.7
          }

        Response JSON: {"image": <b64 png>, "seed": int, "ms": int}
        """
        self._check_auth(body)
        return self._hero_core(body)

    @modal.method()
    def render_remote(self, body: dict) -> dict:
        """In-app (.remote) base render — used by the local `smoke` entrypoint to run
        ON the GPU. No HTTP auth (this is a trusted intra-app call)."""
        return self._hero_core(body)

    def _hero_core(self, body: dict) -> dict:
        t0 = time.monotonic()
        beauty_img = _pil(body["beauty"])
        width, height = self._dims(body, beauty_img)
        canny_pil, depth_pil = self._conditioning(body, width, height)

        seed = int(body.get("seed", DEFAULT_SEED))
        img = self._run_pipe(
            canny_pil=canny_pil,
            depth_pil=depth_pil,
            prompt=body.get("prompt") or WARM_PROMPT,
            negative_prompt=body.get("negative_prompt") or DEFAULT_NEGATIVE,
            width=width,
            height=height,
            seed=seed,
            steps=int(body.get("steps", DEFAULT_STEPS)),
            guidance_scale=float(body.get("guidance_scale", DEFAULT_GUIDANCE)),
            true_cfg_scale=float(body.get("true_cfg_scale", DEFAULT_TRUE_CFG)),
            canny_scale=float(body.get("canny_scale", DEFAULT_CANNY_SCALE)),
            canny_end=float(body.get("canny_end", DEFAULT_CANNY_END)),
            depth_scale=float(body.get("depth_scale", DEFAULT_DEPTH_SCALE)),
            depth_end=float(body.get("depth_end", DEFAULT_DEPTH_END)),
        )
        ms = int((time.monotonic() - t0) * 1000)
        print(f"[hero_render] {width}x{height} seed={seed} in {ms} ms")
        return {"image": _b64(_png_bytes(img)), "seed": seed, "ms": ms}

    # ----------------------------------------------------------------------- #
    # Endpoint 2 — region_edit: re-clad ONE region, byte-stable elsewhere.
    # ----------------------------------------------------------------------- #
    @modal.fastapi_endpoint(method="POST")
    def region_edit(self, body: dict):
        """POST a base frame + a region selection + a region prompt -> the base
        frame with ONLY that region re-rendered (untouched pixels == base, so the
        result is byte-stable outside the mask).

        v1 strategy: run a FULL dual-controlnet pass with the SAME seed and the
        SAME controls as the base render (so geometry + global lighting match),
        then composite ONLY the masked region over `base`. A true
        FluxControlNetInpaintPipeline (which only denoises inside the mask) is a
        v2 upgrade — it would be cheaper and avoid any global drift, but needs the
        inpaint pipeline class + a mask-aware call.

        Request JSON adds to the hero_render body (incl. `secret`):
          {
            ...all hero_render fields...,
            "base":       <b64 png>,        # the frame to edit into (required)
            "region_ids": [int, ...],       # instance ids to re-clad (required)
            "mask":       <b64 png>?        # optional explicit mask; else built from ids
          }
        `prompt` should describe the NEW material for the region.

        Response JSON: {"image": <b64 png full frame>, "mask": <b64 png>, "seed": int, "ms": int}
        """
        self._check_auth(body)
        return self._region_core(body)

    def _region_core(self, body: dict) -> dict:
        t0 = time.monotonic()

        base_png = _unb64(body["base"])
        beauty_img = _pil(body["beauty"])
        width, height = self._dims(body, beauty_img)
        canny_pil, depth_pil = self._conditioning(body, width, height)

        # Build the region mask: explicit if supplied, else from ids + region_ids.
        if body.get("mask"):
            mask_png = _unb64(body["mask"])
        else:
            ids = _decode_ids(_unb64(body["ids_rgb"]))
            mask_png = mask_png_from_ids(ids, body.get("region_ids", []))

        seed = int(body.get("seed", DEFAULT_SEED))
        img = self._run_pipe(
            canny_pil=canny_pil,
            depth_pil=depth_pil,
            prompt=body.get("prompt") or WARM_PROMPT,
            negative_prompt=body.get("negative_prompt") or DEFAULT_NEGATIVE,
            width=width,
            height=height,
            seed=seed,                                  # SAME seed as base render
            steps=int(body.get("steps", DEFAULT_STEPS)),
            guidance_scale=float(body.get("guidance_scale", DEFAULT_GUIDANCE)),
            true_cfg_scale=float(body.get("true_cfg_scale", DEFAULT_TRUE_CFG)),
            canny_scale=float(body.get("canny_scale", DEFAULT_CANNY_SCALE)),
            canny_end=float(body.get("canny_end", DEFAULT_CANNY_END)),
            depth_scale=float(body.get("depth_scale", DEFAULT_DEPTH_SCALE)),
            depth_end=float(body.get("depth_end", DEFAULT_DEPTH_END)),
        )
        edit_png = _png_bytes(img)
        # Composite ONLY the masked region over base -> untouched pixels stay base.
        final_png = paste_tile(base_png, mask_png, edit_png)
        ms = int((time.monotonic() - t0) * 1000)
        print(f"[region_edit] {width}x{height} seed={seed} ids={body.get('region_ids')} in {ms} ms")
        return {"image": _b64(final_png), "mask": _b64(mask_png), "seed": seed, "ms": ms}


# --------------------------------------------------------------------------- #
# smoke — local entrypoint. Base64s the buffers from spike/outputs/web3d_house/
# (if present) and calls hero_render via .remote, writing outputs/hero_smoke.png.
# --------------------------------------------------------------------------- #
@app.local_entrypoint()
def smoke():
    """Local smoke test. Run: `modal run spike/modal_flux.py`.

    Requires beauty.png + depth.png + instance_ids.png in spike/outputs/web3d_house/.
    If any is missing, prints a skip notice and exits cleanly (no GPU spend).
    """
    src = Path(__file__).parent / "outputs" / "web3d_house"
    beauty = src / "beauty.png"
    depth = src / "depth.png"
    ids = src / "instance_ids.png"

    missing = [p.name for p in (beauty, depth, ids) if not p.exists()]
    if missing:
        print(f"[smoke] skipping — {src} is missing {missing}. "
              f"Render a capture into that dir (beauty.png, depth.png, instance_ids.png) "
              f"and re-run `modal run spike/modal_flux.py`.")
        return

    body = {
        "beauty": _b64(beauty.read_bytes()),
        "depth": _b64(depth.read_bytes()),
        "ids_rgb": _b64(ids.read_bytes()),
        "prompt": WARM_PROMPT,
        "seed": 0,
    }

    # Run ON the GPU via the @modal.method (render_remote bypasses HTTP auth — it's a
    # trusted intra-app .remote call). The pipe loads once in @modal.enter().
    hero = HeroFlux()

    print("[smoke] cold call (container start + weight load + render) ...")
    t0 = time.monotonic()
    r1 = hero.render_remote.remote(body)
    cold_ms = int((time.monotonic() - t0) * 1000)

    out = Path(__file__).parent.parent / "outputs"
    out.mkdir(exist_ok=True)
    out_path = out / "hero_smoke.png"
    out_path.write_bytes(_unb64(r1["image"]))
    print(f"[smoke] cold {cold_ms} ms (pipe-reported {r1['ms']} ms) -> {out_path}")

    print("[smoke] warm call (pipe already loaded) ...")
    t0 = time.monotonic()
    r2 = hero.render_remote.remote(body)
    warm_ms = int((time.monotonic() - t0) * 1000)
    print(f"[smoke] warm {warm_ms} ms (pipe-reported {r2['ms']} ms)")
    print(f"[smoke] cold vs warm wall: {cold_ms} ms vs {warm_ms} ms")
