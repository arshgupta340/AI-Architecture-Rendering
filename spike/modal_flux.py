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
# Identity reported by /warm so the app can show which backend it's pinned to. The
# FLUX.2 path is a SEPARATE app (spike/modal_flux2.py, H200 + VideoX-Fun) reachable at
# its own URL — the app's Backend panel switches between the two by URL preset.
MODEL_NAME = "flux1-dev-union"
# Experiment B: an IP-Adapter so multi-view renders can inherit the HERO view's
# materials/lighting (a "reference image" condition) on top of the geometry lock. XLabs
# FLUX IP-Adapter + CLIP-L encoder.
#   ⚠️ CONFIRMED INERT on the PINNED diffusers 0.32.2: `FluxControlNetPipeline` has no
#   `load_ip_adapter` (the FLUX IP-Adapter mixin was added to the PLAIN FluxPipeline first;
#   the ControlNet variant got it in a later release). So this path stays GUARDED + inert
#   (has_ip=False → geometry-only) until diffusers is bumped to a version where the
#   ControlNet pipeline includes the IP-Adapter mixin — a bump that must re-verify the
#   multi-controlnet base. Also note: the XLabs adapter is documented to need real CFG,
#   which 0.32.2's ControlNet pipeline also lacks. See spike/REPORTS/modal_flux.md.
IP_ADAPTER_REPO = "XLabs-AI/flux-ip-adapter"
IP_ADAPTER_WEIGHT = "ip_adapter.safetensors"
IP_IMAGE_ENCODER = "openai/clip-vit-large-patch14"

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
        # Pinned to a known-good FLUX-ControlNet combo (unpinned pulled diffusers 0.38 /
        # transformers 5.x / hf_hub 1.x — too new, risks breaking the FLUX text encoders).
        "diffusers==0.32.2",
        "transformers==4.49.0",
        "accelerate==1.1.1",
        "huggingface_hub==0.26.5",
        "safetensors>=0.4.5",
        "sentencepiece>=0.2",
        "protobuf>=4",
        "Pillow>=10",
        "numpy<2",
        "opencv-python-headless>=4.9",
        # Modal 1.4+ no longer auto-installs FastAPI for @modal.fastapi_endpoint.
        "fastapi[standard]",
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

    for repo in (FLUX_REPO, UNION_REPO, IP_ADAPTER_REPO, IP_IMAGE_ENCODER):
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

        The Union checkpoint drives BOTH canny + depth. To pass TWO control images on
        diffusers 0.32.2 we wrap the single Union model in a FluxMultiControlNetModel
        referenced TWICE ([cn, cn]) — passing a bare list of 2 control images to a
        single FluxControlNetModel makes 0.32.2 batch them (latent-shape mismatch:
        "shape [...] invalid for input of size 2x"). The multi-wrapper tells the
        pipeline there are 2 distinct conditions (mode 0 = canny, mode 2 = depth).
        """
        import os

        import torch
        from diffusers import FluxControlNetModel, FluxControlNetPipeline, FluxMultiControlNetModel

        # Point HF + diffusers at the Volume cache so we reuse warm_weights' download.
        HF_CACHE.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(HF_CACHE))
        os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE))
        token = os.environ.get("HF_TOKEN")

        dtype = torch.bfloat16
        print(f"[HeroFlux] loading ControlNet-Union {UNION_REPO} ...")
        union = FluxControlNetModel.from_pretrained(
            UNION_REPO, torch_dtype=dtype, cache_dir=str(HF_CACHE), token=token
        )
        controlnet = FluxMultiControlNetModel([union, union])  # [canny-mode, depth-mode]
        print(f"[HeroFlux] loading FLUX pipeline {FLUX_REPO} ...")
        self.pipe = FluxControlNetPipeline.from_pretrained(
            FLUX_REPO,
            controlnet=controlnet,
            torch_dtype=dtype,
            cache_dir=str(HF_CACHE),
            token=token,
        ).to("cuda")
        print("[HeroFlux] pipeline ready on cuda")

        # Experiment B (GUARDED): load the XLabs FLUX IP-Adapter so a reference image can
        # carry materials/lighting across views. If anything here fails (version, weights,
        # the ControlNet pipeline not wiring ip_adapter_image on 0.32.2), we log it and the
        # base geometry-locked render is COMPLETELY unaffected.
        self.has_ip = False
        try:
            self.pipe.load_ip_adapter(
                IP_ADAPTER_REPO,
                weight_name=IP_ADAPTER_WEIGHT,
                image_encoder_pretrained_model_name_or_path=IP_IMAGE_ENCODER,
            )
            import inspect

            self.has_ip = "ip_adapter_image" in inspect.signature(self.pipe.__call__).parameters
            print(f"[HeroFlux] IP-Adapter loaded; ControlNet pipe accepts ip_adapter_image={self.has_ip}")
        except Exception as e:  # noqa: BLE001 — IP-Adapter is opt-in; never fatal
            print(f"[HeroFlux] IP-Adapter unavailable ({type(e).__name__}: {e}) — base render unaffected")

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
        ref_pil=None,            # Experiment B: reference image (the hero view) for the IP-Adapter
        ip_scale: float = 0.0,   # 0 = off (geometry-only); ~0.6 = balanced material carry-over
    ):
        """One FluxControlNetModel, two controls via list args (canny=mode 0,
        depth=mode 2). `negative_prompt` + `true_cfg_scale` only exist on newer
        FluxControlNetPipeline (>0.32.2) — added ONLY if the installed diffusers
        supports them, so the negative prompt activates after a diffusers bump without
        crashing the pinned version (0.32.2 raises TypeError otherwise)."""
        import inspect

        import torch

        kwargs = dict(
            prompt=prompt,
            prompt_2=prompt,
            control_image=[canny_pil, depth_pil],
            control_mode=[CANNY_MODE, DEPTH_MODE],          # canny=0, depth=2
            controlnet_conditioning_scale=[canny_scale, depth_scale],
            control_guidance_start=[0.0, 0.0],
            control_guidance_end=[canny_end, depth_end],
            width=width,
            height=height,
        )
        _sig = inspect.signature(self.pipe.__call__).parameters
        if true_cfg_scale and true_cfg_scale > 1 and "true_cfg_scale" in _sig and "negative_prompt" in _sig:
            kwargs["negative_prompt"] = negative_prompt
            kwargs["true_cfg_scale"] = float(true_cfg_scale)

        # Experiment B: condition on the hero reference image via the IP-Adapter (only if it
        # loaded AND this pipeline build accepts ip_adapter_image AND a ref + scale are given).
        if ref_pil is not None and ip_scale and getattr(self, "has_ip", False) and "ip_adapter_image" in _sig:
            self.pipe.set_ip_adapter_scale(float(ip_scale))
            kwargs["ip_adapter_image"] = ref_pil
        elif getattr(self, "has_ip", False):
            self.pipe.set_ip_adapter_scale(0.0)  # ensure the adapter is inert when not used

        img = self.pipe(
            **kwargs,
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
        # FLUX ControlNet expects 3-channel RGB control images (prep_* produce 1-ch 'L'
        # → "expected input to have 3 channels, but got 1" otherwise).
        return canny_pil.convert("RGB"), depth_pil.convert("RGB")

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
    # Web — ONE ASGI app (FastAPI + CORSMiddleware) serving both routes.
    #
    # Why not two @modal.fastapi_endpoint methods: Modal's per-endpoint decorator
    # CORS-es the OPTIONS preflight but NOT the actual function response, so a browser
    # cross-origin POST gets a response with no Access-Control-Allow-Origin and the
    # fetch fails ("Failed to fetch"). A real FastAPI app + CORSMiddleware adds CORS to
    # EVERY response (incl. 401/500), which is what the browser needs.
    #
    # Routes (secret in the JSON body):
    #   POST /hero_render  { secret, beauty, depth, ids_rgb, canny?, prompt?,
    #     negative_prompt?, width?, height?, seed?, steps?, guidance_scale?,
    #     true_cfg_scale?, canny_scale?, canny_end?, depth_scale?, depth_end? }
    #       -> { image: <b64 png>, seed, ms }    (depth is LINEAR, NEAR=white FAR=black;
    #          ids_rgb packs id=r|g<<8; canny is computed server-side if omitted)
    #   POST /region_edit  { ...hero_render fields, base, region_ids:[int], mask? }
    #       -> { image: <b64 full frame>, mask, seed, ms }   (region composited over
    #          `base` with the SAME seed/controls → byte-stable outside the mask)
    # ----------------------------------------------------------------------- #
    @modal.asgi_app()
    def web(self):
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse

        api = FastAPI()
        api.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )

        # Return a CORS'd JSON error for ANY unhandled exception — otherwise an
        # unhandled 500 bypasses CORSMiddleware and the browser sees only an opaque
        # "Failed to fetch" instead of the real error message.
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

        # Cheap keep-alive: hitting ANY route resets the container's scaledown timer,
        # so the app's "keep GPU warm" toggle can ping this every ~4 min to avoid the
        # ~40-60 s cold start during an active editing session — WITHOUT paying for a
        # full render. Confirms the pipe is resident so the client can show "warm".
        @api.post("/warm")
        def warm(body: dict):
            self._check_auth(body)
            return {"warm": True, "model": MODEL_NAME, "pipe_loaded": hasattr(self, "pipe")}

        return api

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
        # Experiment B: an optional reference image (the hero view) + IP-Adapter scale.
        ref_pil = _pil(body["ref_image"]).convert("RGB") if body.get("ref_image") else None
        ip_scale = float(body.get("ip_scale", 0.0))
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
            ref_pil=ref_pil,
            ip_scale=ip_scale,
        )
        ms = int((time.monotonic() - t0) * 1000)
        print(f"[hero_render] {width}x{height} seed={seed} ip={ip_scale if ref_pil else 0} in {ms} ms")
        return {"image": _b64(_png_bytes(img)), "seed": seed, "ms": ms, "ip_used": bool(ref_pil and ip_scale and getattr(self, 'has_ip', False))}

    # ----------------------------------------------------------------------- #
    # region_edit core — served by the POST /region_edit route in web(). v1 strategy:
    # run a FULL dual-controlnet pass (SAME seed + controls as the base, so geometry +
    # global lighting match), then composite ONLY the masked region over `base` so
    # untouched pixels == base (byte-stable). A true FluxControlNetInpaintPipeline is a
    # v2 upgrade. Body adds { base, region_ids:[int], mask? } to the hero_render fields.
    # ----------------------------------------------------------------------- #
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
