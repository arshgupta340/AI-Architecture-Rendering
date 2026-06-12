"""E2 — render conditioning shootout on the house frame (spike/outputs/e2_house).

Candidates, all driven by the same geometry-preservation prompt:
  a) flux_depth   — fal-ai/flux-pro/v1/depth with the TRUE z-buffer from Rhino
  b) flux_canny   — fal-ai/flux-pro/v1/canny with Canny edges from the beauty pass
  c) flux2_edit   — fal-ai/flux-2-pro/edit i2i on the beauty pass
  d) nano_banana  — nano-banana-pro-preview i2i control (current baseline)

Outputs to spike/outputs/e2_house/renders/ + comparison_grid.png.
Gate: at least one candidate with zero critical failures (invented windows,
moved openings, changed massing). Costs ~$0.05-0.13 per call, logged in ledger.

Usage:
  spike\\.venv\\Scripts\\python.exe spike/run_e2_shootout.py --live [--only name]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

SPIKE = Path(__file__).parent
SRC = SPIKE / "outputs" / "e2_house"
OUT = SRC / "renders"

STYLE = (
    "A photorealistic architectural exterior visualization of a two-story "
    "craftsman house: painted wood lap siding, white painted trim and window "
    "casings, dark asphalt shingle roof, divided-lite windows, black metal "
    "porch railing, concrete foundation and stairs, landscaped sloping lawn, "
    "soft late-afternoon sunlight, clear sky, professional photography."
)

PRESERVE = (
    "PRESERVE GEOMETRY EXACTLY: every edge, corner, opening, window placement, "
    "muntin grid, roof plane, and structural detail must remain in the same "
    "position, scale, and proportion. Do not move, add, or delete any "
    "architectural element. The input geometry is binding."
)


def _data_uri(img: Image.Image) -> str:
    b = BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def prep_depth() -> Image.Image:
    """Normalize the Rhino z-buffer for ControlNet: stretch hit-range, slight blur."""
    from PIL import ImageFilter
    d = np.array(Image.open(SRC / "depth.png").convert("L")).astype(float)
    hits = d > 0
    lo, hi = np.percentile(d[hits], 1), np.percentile(d[hits], 99)
    n = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    n[~hits] = 0.0
    img = Image.fromarray((n * 255).astype(np.uint8))
    return img.filter(ImageFilter.GaussianBlur(1.2))


def prep_canny() -> Image.Image:
    import cv2
    g = cv2.cvtColor(np.array(Image.open(SRC / "beauty.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(g, 80, 180)
    return Image.fromarray(edges)


def _fal_call(endpoint: str, payload: dict, timeout_s: int = 300) -> bytes:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY not set")
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post(f"https://queue.fal.run/{endpoint}", headers=headers,
                      json=payload, timeout=60)
    r.raise_for_status()
    sub = r.json()
    status_url, response_url = sub["status_url"], sub["response_url"]
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        s = requests.get(status_url, headers=headers, timeout=30).json()
        if s["status"] == "COMPLETED":
            out = requests.get(response_url, headers=headers, timeout=30).json()
            if "images" not in out:
                raise RuntimeError(f"{endpoint} unexpected response: {json.dumps(out)[:800]}")
            url = out["images"][0]["url"]
            if url.startswith("data:"):
                return base64.b64decode(url.split(",", 1)[1])
            return requests.get(url, timeout=120).content
        if s["status"] in ("FAILED", "ERROR"):
            raise RuntimeError(f"{endpoint} failed: {s}")
        time.sleep(2)
    raise RuntimeError(f"{endpoint} timed out")


def run_flux_depth() -> bytes:
    return _fal_call("fal-ai/flux-pro/v1/depth", {
        "prompt": STYLE + " " + PRESERVE,
        "control_image_url": _data_uri(prep_depth()),
        "guidance_scale": 15,
        "num_inference_steps": 28,
        "output_format": "png",
        "safety_tolerance": "5",
    })


def run_flux_canny() -> bytes:
    return _fal_call("fal-ai/flux-pro/v1/canny", {
        "prompt": STYLE + " " + PRESERVE,
        "control_image_url": _data_uri(prep_canny()),
        "guidance_scale": 20,
        "num_inference_steps": 28,
        "output_format": "png",
        "safety_tolerance": "5",
    })


def run_flux2_edit() -> bytes:
    return _fal_call("fal-ai/flux-2-pro/edit", {
        "prompt": ("Convert this shaded 3D-model viewport screenshot into a "
                   "photorealistic architectural visualization. " + STYLE + " " + PRESERVE),
        "image_urls": [_data_uri(Image.open(SRC / "beauty.png").convert("RGB"))],
        "output_format": "png",
        "safety_tolerance": "5",
    })


def run_nano_banana() -> bytes:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    src = (SRC / "beauty.png").read_bytes()
    resp = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[
            types.Part.from_bytes(data=src, mime_type="image/png"),
            ("This is a 3D-model viewport screenshot. Render it as a "
             "photorealistic architectural visualization. " + PRESERVE + " " + STYLE),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data
    raise RuntimeError("no image in nano banana response")


CANDIDATES = {
    "flux_depth": (run_flux_depth, 0.05),
    "flux_canny": (run_flux_canny, 0.05),
    "flux2_edit": (run_flux2_edit, 0.06),
    "nano_banana": (run_nano_banana, 0.13),
}


def build_grid():
    panels = [("input", Image.open(SRC / "beauty.png").convert("RGB"))]
    for name in CANDIDATES:
        p = OUT / f"{name}.png"
        if p.exists():
            panels.append((name, Image.open(p).convert("RGB")))
    w, h = 760, 428
    cols = 3
    rows = (len(panels) + cols - 1) // cols
    grid = Image.new("RGB", (cols * w, rows * (h + 26)), (20, 20, 20))
    d = ImageDraw.Draw(grid)
    for i, (name, im) in enumerate(panels):
        x, y = (i % cols) * w, (i // cols) * (h + 26)
        grid.paste(im.resize((w, h)), (x, y + 26))
        d.text((x + 8, y + 5), name, fill=(255, 255, 255))
    grid.save(SRC / "comparison_grid.png")
    print("comparison_grid.png saved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    if not args.live:
        print(__doc__)
        return 0
    from dotenv import load_dotenv
    load_dotenv(SPIKE / ".env")
    OUT.mkdir(parents=True, exist_ok=True)
    # save conditioning inputs for the record
    prep_depth().save(OUT / "_cond_depth.png")
    prep_canny().save(OUT / "_cond_canny.png")
    total = 0.0
    for name, (fn, cost) in CANDIDATES.items():
        if args.only and name != args.only:
            continue
        print(f"[e2] {name} (~${cost:.2f}) ...")
        try:
            t0 = time.monotonic()
            data = fn()
            (OUT / f"{name}.png").write_bytes(data)
            total += cost
            print(f"  ok in {time.monotonic()-t0:.1f}s -> {name}.png ({len(data):,} B)")
        except Exception as e:
            print(f"  FAILED: {e}")
    build_grid()
    print(f"[e2] est. total spend this run: ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
