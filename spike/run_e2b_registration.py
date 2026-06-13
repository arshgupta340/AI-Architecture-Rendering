"""E2b — fix render↔mask registration with depth+canny multi-ControlNet.

E2 found depth ControlNet alone preserves massing but lets FLUX re-place
coplanar features (windows flush in a wall ≈ same depth), so ground-truth masks
don't land on the rendered openings (diagnosed via diag_facade_compare.png).

Fix: add a HARD edge control seeded from ground truth — Canny(beauty) ∪ instance
boundaries, at exact GT position — alongside depth, via fal flux-general
ControlNetUnion (FLUX.1-dev-ControlNet-Union-Pro-2.0). Canny pins openings/trim;
depth pins massing. Rendered at native 1504×656 (== mask grid; no resize drift).

Usage: spike\\.venv\\Scripts\\python.exe spike/run_e2b_registration.py --live [--canny 0.8 --depth 0.5]
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageFilter
import cv2

SPIKE = Path(__file__).parent
SRC = SPIKE / "outputs" / "e2_house_v2"
OUT = SRC / "renders"
UNION_PATH = "Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0"

STYLE = (
    "A photorealistic architectural exterior visualization of a two-story "
    "craftsman house: painted wood lap siding, white painted trim and window "
    "casings, dark asphalt shingle roof, divided-lite windows, black metal "
    "porch railing, concrete foundation and stairs, landscaped sloping lawn, "
    "soft late-afternoon sunlight, clear sky, professional photography."
)
PRESERVE = (
    "Preserve every edge, window, muntin, trim line, roof plane, and post "
    "exactly at its position and scale — the line drawing is binding."
)


def _data_uri(img: Image.Image, fmt="PNG") -> str:
    b = io.BytesIO()
    if fmt == "JPEG":
        img.save(b, "JPEG", quality=92)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def prep_depth() -> Image.Image:
    d = np.array(Image.open(SRC / "depth.png").convert("L")).astype(float)
    hits = d > 0
    lo, hi = np.percentile(d[hits], 1), np.percentile(d[hits], 99)
    n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    n[~hits] = 0.0
    return Image.fromarray((n * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))


def prep_canny() -> Image.Image:
    """Canny(beauty) OR instance-boundary edges — exact ground-truth lines."""
    beauty = np.array(Image.open(SRC / "beauty.png").convert("RGB"))
    edges = cv2.Canny(cv2.cvtColor(beauty, cv2.COLOR_RGB2GRAY), 70, 160) > 0
    inst = np.array(Image.open(SRC / "instance_ids.png")).astype(np.int32)
    # object boundary = id changes vs right/down neighbor
    bnd = np.zeros_like(inst, bool)
    bnd[:, :-1] |= inst[:, :-1] != inst[:, 1:]
    bnd[:-1, :] |= inst[:-1, :] != inst[1:, :]
    out = (edges | bnd).astype(np.uint8) * 255
    return Image.fromarray(out)


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


def run(canny_scale: float, depth_scale: float) -> bytes:
    depth_uri = _data_uri(prep_depth())
    canny_uri = _data_uri(prep_canny())
    return _fal({
        "prompt": STYLE + " " + PRESERVE,
        "image_size": {"width": 1504, "height": 656},
        "num_inference_steps": 30,
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
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--canny", type=float, default=0.8)
    ap.add_argument("--depth", type=float, default=0.5)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prep_depth().save(OUT / "_cond_depth.png")
    prep_canny().save(OUT / "_cond_canny.png")
    if not args.live:
        print("wrote conditioning images to", OUT, "(dry run)")
        return
    from dotenv import load_dotenv
    load_dotenv(SPIKE / ".env")
    tag = f"c{args.canny}_d{args.depth}".replace(".", "")
    print(f"[e2b] flux-general union canny={args.canny} depth={args.depth} ...")
    t0 = time.monotonic()
    data = run(args.canny, args.depth)
    p = OUT / f"depth_canny_{tag}.png"
    p.write_bytes(data)
    print(f"  ok in {time.monotonic()-t0:.1f}s -> {p.name} ({len(data):,} B)")


if __name__ == "__main__":
    main()
