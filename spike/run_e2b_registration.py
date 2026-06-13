"""E2b — geometry-locked render: depth+canny multi-ControlNet, warm prompt.

E2 found depth ControlNet alone preserves massing but lets FLUX re-place
coplanar features (windows flush in a wall ≈ same depth), so ground-truth masks
don't land on the rendered openings. Fix: a HARD edge control seeded from ground
truth — Canny(beauty) ∪ instance boundaries, at exact GT position — alongside
depth, via fal flux-general ControlNetUnion (FLUX.1-dev-ControlNet-Union-Pro-2.0).
Canny pins openings/trim, depth pins massing. Rendered at the capture's native
size (== mask grid; no resize drift). Edge alignment: 51.7% → 98.5% within 2px.

`render_locked(src_dir)` is the reusable production render step (warm prompt,
canny@0.8 + depth@0.5). It is called by the capture→canvas pipeline
(apps/canvas-prototype/ingest.py) and by the CLI below.

Usage: spike\\.venv\\Scripts\\python.exe spike/run_e2b_registration.py --live [--src DIR] [--canny 0.8 --depth 0.5]
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageFilter
import cv2

SPIKE = Path(__file__).parent
SRC = SPIKE / "outputs" / "e2_house_v2"          # CLI default
UNION_PATH = "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0"

# Warm, specific prompt — recovers terracotta siding + golden-hour light while
# the canny lock holds geometry (validated: warmth costs ~0 alignment, E2b).
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


def _data_uri(img: Image.Image, fmt="PNG") -> str:
    b = io.BytesIO()
    if fmt == "JPEG":
        img.save(b, "JPEG", quality=92)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def prep_depth(src: Path = SRC) -> Image.Image:
    d = np.array(Image.open(Path(src) / "depth.png").convert("L")).astype(float)
    hits = d > 0
    lo, hi = np.percentile(d[hits], 1), np.percentile(d[hits], 99)
    n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    n[~hits] = 0.0
    return Image.fromarray((n * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))


def prep_canny(src: Path = SRC) -> Image.Image:
    """Canny(beauty) OR instance-boundary edges — exact ground-truth lines.

    Requires instance_ids.png (run host_probe_rhino.decode on the capture first).
    """
    src = Path(src)
    beauty = np.array(Image.open(src / "beauty.png").convert("RGB"))
    edges = cv2.Canny(cv2.cvtColor(beauty, cv2.COLOR_RGB2GRAY), 70, 160) > 0
    inst = np.array(Image.open(src / "instance_ids.png")).astype(np.int32)
    bnd = np.zeros_like(inst, bool)
    bnd[:, :-1] |= inst[:, :-1] != inst[:, 1:]
    bnd[:-1, :] |= inst[:-1, :] != inst[1:, :]
    return Image.fromarray(((edges | bnd).astype(np.uint8) * 255))


def _fal(payload, timeout_s=420) -> bytes:
    key = os.environ["FAL_KEY"]
    h = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post("https://queue.fal.run/fal-ai/flux-general", headers=h, json=payload, timeout=60)
    r.raise_for_status()
    sub = r.json()
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        s = requests.get(sub["status_url"], headers=h, timeout=30).json()
        if s["status"] == "COMPLETED":
            out = requests.get(sub["response_url"], headers=h, timeout=30).json()
            if "images" not in out:
                raise RuntimeError(f"no images: {json.dumps(out)[:600]}")
            url = out["images"][0]["url"]
            return (base64.b64decode(url.split(",", 1)[1]) if url.startswith("data:")
                    else requests.get(url, timeout=120).content)
        if s["status"] in ("FAILED", "ERROR"):
            raise RuntimeError(f"failed: {s}")
        time.sleep(2)
    raise RuntimeError("timed out")


def render_locked(src: Path = SRC, canny_scale: float = 0.8, depth_scale: float = 0.5,
                  prompt: str = WARM_PROMPT, timeout_s: int = 420) -> bytes:
    """Geometry-locked, warm photoreal render of a capture dir. Returns PNG bytes.

    Renders at the capture's native pixel size (read from camera.json), so the
    output shares the ground-truth mask grid exactly.
    """
    src = Path(src)
    cam = json.loads((src / "camera.json").read_text())
    w, h = cam["size_px"]
    depth_uri = _data_uri(prep_depth(src))
    canny_uri = _data_uri(prep_canny(src))
    return _fal({
        "prompt": prompt,
        "image_size": {"width": int(w), "height": int(h)},
        "num_inference_steps": 32,
        "guidance_scale": 3.5,
        "real_cfg_scale": 3.5,
        "output_format": "png",
        "enable_safety_checker": False,
        "controlnet_unions": [{
            "path": UNION_PATH,
            "controls": [
                {"control_mode": "canny", "control_image_url": canny_uri,
                 "conditioning_scale": canny_scale, "start_percentage": 0, "end_percentage": 0.85},
                {"control_mode": "depth", "control_image_url": depth_uri,
                 "conditioning_scale": depth_scale, "start_percentage": 0, "end_percentage": 0.7},
            ],
        }],
    }, timeout_s=timeout_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--canny", type=float, default=0.8)
    ap.add_argument("--depth", type=float, default=0.5)
    args = ap.parse_args()
    src = Path(args.src)
    out = src / "renders"
    out.mkdir(parents=True, exist_ok=True)
    prep_depth(src).save(out / "_cond_depth.png")
    prep_canny(src).save(out / "_cond_canny.png")
    if not args.live:
        print("wrote conditioning images to", out, "(dry run)")
        return
    from dotenv import load_dotenv
    load_dotenv(SPIKE / ".env")
    print(f"[e2b] flux-general union canny={args.canny} depth={args.depth} ...")
    t0 = time.monotonic()
    data = render_locked(src, args.canny, args.depth)
    p = out / "base_render.png"
    p.write_bytes(data)
    print(f"  ok in {time.monotonic()-t0:.1f}s -> {p} ({len(data):,} B)")


if __name__ == "__main__":
    main()
