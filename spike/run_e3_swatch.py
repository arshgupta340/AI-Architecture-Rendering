"""E3 — swatch-conditioning shootout on the E2 flux_depth render (house frame).

The "does travertine read as travertine" experiment, run on aligned tier-1 data:
base = the depth-conditioned render (registers with ground truth), mask = the
house wall semantic mask from the host, swatch = spike/test_assets/travertine.jpeg.

Candidates:
  a) fill_text       — FLUX Fill [pro], text-only "travertine" (control, = T25 behavior)
  b) general_ip      — flux-general/inpainting + IP-Adapter conditioned on the swatch
  c) flux2_multiref  — FLUX.2 [pro] Edit, [render, swatch] multi-reference
  d) kontext_multi   — FLUX Kontext [max] multi, [render, swatch]

Gate: a blind viewer names the material. Whole-image editors (c/d) additionally
audited for alignment damage outside the mask.

Usage: spike\\.venv\\Scripts\\python.exe spike/run_e3_swatch.py --live [--only name]
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
from PIL import Image, ImageDraw, ImageFilter

SPIKE = Path(__file__).parent
SRC = SPIKE / "outputs" / "e2_house"
OUT = SPIKE / "outputs" / "e3_swatch"
SWATCH = SPIKE / "test_assets" / "travertine.jpeg"

PROMPT_TEXT = (
    "Replace the painted wood lap siding of the house walls with honed "
    "travertine stone cladding: beige cream natural stone with subtle "
    "horizontal veining and visible coursing joints. Keep lighting, shadows, "
    "trim, windows, roof, and everything else exactly unchanged."
)


def _data_uri(img, fmt: str = "PNG") -> str:
    if isinstance(img, (str, Path)):
        img = Image.open(img).convert("RGB")
    b = BytesIO()
    if fmt == "JPEG":
        img.save(b, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def wall_mask() -> Image.Image:
    """Ground-truth wall mask (semantic 'wall'), slightly dilated."""
    sys.path.insert(0, str(SPIKE))
    from host_probe_rhino import mask_for
    m = mask_for(SRC, lambda rec: rec["semantic"] == "wall")
    img = Image.fromarray((m * 255).astype(np.uint8))
    return img.filter(ImageFilter.MaxFilter(5))  # ~2px dilation


def _fal_call(endpoint: str, payload: dict, timeout_s: int = 400) -> bytes:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY not set")
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post(f"https://queue.fal.run/{endpoint}", headers=headers,
                      json=payload, timeout=60)
    r.raise_for_status()
    sub = r.json()
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        s = requests.get(sub["status_url"], headers=headers, timeout=30).json()
        if s["status"] == "COMPLETED":
            out = requests.get(sub["response_url"], headers=headers, timeout=30).json()
            if "images" not in out:
                raise RuntimeError(f"{endpoint} unexpected response: {json.dumps(out)[:600]}")
            url = out["images"][0]["url"]
            if url.startswith("data:"):
                return base64.b64decode(url.split(",", 1)[1])
            return requests.get(url, timeout=120).content
        if s["status"] in ("FAILED", "ERROR"):
            raise RuntimeError(f"{endpoint} failed: {s}")
        time.sleep(2)
    raise RuntimeError(f"{endpoint} timed out")


def base_render_uri():
    return _data_uri(SRC / "renders" / "flux_depth.png", fmt="JPEG")


def run_fill_text() -> bytes:
    return _fal_call("fal-ai/flux-pro/v1/fill", {
        "prompt": PROMPT_TEXT,
        "image_url": base_render_uri(),
        "mask_url": _data_uri(wall_mask()),
        "output_format": "png",
        "safety_tolerance": "5",
    })


def run_general_ip() -> bytes:
    return _fal_call("fal-ai/flux-general/inpainting", {
        "prompt": PROMPT_TEXT,
        "image_url": base_render_uri(),
        "mask_url": _data_uri(wall_mask()),
        "strength": 0.92,
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "output_format": "png",
        "ip_adapters": [{
            "path": "XLabs-AI/flux-ip-adapter",
            "weight_name": "ip_adapter.safetensors",
            "image_encoder_path": "openai/clip-vit-large-patch14",
            "image_url": _data_uri(SWATCH, fmt="JPEG"),
            "scale": 0.75,
        }],
    })


def run_flux2_multiref() -> bytes:
    return _fal_call("fal-ai/flux-2-pro/edit", {
        "prompt": ("Apply the stone material shown in the second image to the "
                   "exterior wall siding of the house in the first image. Only the "
                   "wall siding changes; windows, trim, roof, railing, stairs, "
                   "ground, lighting, and camera stay exactly identical."),
        "image_urls": [base_render_uri(), _data_uri(SWATCH)],
        "output_format": "png",
        "safety_tolerance": "5",
    })


def run_kontext_multi() -> bytes:
    return _fal_call("fal-ai/flux-pro/kontext/max/multi", {
        "prompt": ("Apply the stone material from the second image to the house "
                   "wall siding in the first image. Keep windows, trim, roof, and "
                   "everything else exactly unchanged."),
        "image_urls": [base_render_uri(), _data_uri(SWATCH)],
        "output_format": "png",
        "safety_tolerance": "5",
    })


CANDIDATES = {
    "fill_text": (run_fill_text, 0.05),
    "general_ip": (run_general_ip, 0.08),
    "flux2_multiref": (run_flux2_multiref, 0.06),
    "kontext_multi": (run_kontext_multi, 0.08),
}


def build_grid():
    base = Image.open(SRC / "renders" / "flux_depth.png").convert("RGB")
    sw = Image.open(SWATCH).convert("RGB")
    panels = [("base render", base), ("swatch", sw)]
    for name in CANDIDATES:
        p = OUT / f"{name}.png"
        if p.exists():
            panels.append((name, Image.open(p).convert("RGB")))
    w, h = 752, 328
    cols = 3
    rows = (len(panels) + cols - 1) // cols
    grid = Image.new("RGB", (cols * w, rows * (h + 26)), (18, 18, 18))
    d = ImageDraw.Draw(grid)
    for i, (name, im) in enumerate(panels):
        x, y = (i % cols) * w, (i // cols) * (h + 26)
        grid.paste(im.resize((w, h)), (x, y + 26))
        d.text((x + 8, y + 5), name, fill=(255, 255, 255))
    grid.save(OUT / "e3_comparison_grid.png")
    print("e3_comparison_grid.png saved")


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
    wall_mask().save(OUT / "_wall_mask.png")
    total = 0.0
    for name, (fn, cost) in CANDIDATES.items():
        if args.only and name != args.only:
            continue
        print(f"[e3] {name} (~${cost:.2f}) ...")
        try:
            t0 = time.monotonic()
            data = fn()
            (OUT / f"{name}.png").write_bytes(data)
            total += cost
            print(f"  ok in {time.monotonic()-t0:.1f}s ({len(data):,} B)")
        except Exception as e:
            print(f"  FAILED: {e}")
    build_grid()
    print(f"[e3] est. spend: ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
