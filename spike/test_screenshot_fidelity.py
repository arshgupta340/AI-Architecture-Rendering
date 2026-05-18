"""
Spike 2 — Nano Banana Pro geometry-fidelity test for model viewport screenshots.

Usage:
  python test_screenshot_fidelity.py path/to/screenshot.png
  python test_screenshot_fidelity.py path/to/screenshot.png --style "warm dusk light, urban context"

Reads a 3D-model viewport screenshot (shaded display from Rhino/SKP/Revit),
sends it to render_from_model_view() on Modal, and saves diagnostics:
  - outputs/spike2/source.png    — input screenshot (copy)
  - outputs/spike2/render.png    — Nano Banana Pro photoreal render
  - outputs/spike2/edges.png     — Canny edges of the source
  - outputs/spike2/overlay.png   — edges overlaid in red on the render
                                   (alignment = geometry preserved)
  - outputs/spike2/sidebyside.png — source | render | overlay
"""

import argparse
import io
import sys
from pathlib import Path

from PIL import Image
import numpy as np
import cv2


def extract_edges(image: Image.Image, low: int = 60, high: int = 180) -> Image.Image:
    """Canny edge detection. Returns a grayscale image: white = edge, black = none."""
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, low, high)
    return Image.fromarray(edges)


def make_overlay(edges: Image.Image, render: Image.Image) -> Image.Image:
    """Red edges (from source) on top of the render. Misalignment = geometry drift."""
    if edges.size != render.size:
        edges = edges.resize(render.size)

    red = Image.new("RGBA", render.size, (255, 30, 30, 0))
    red.putalpha(edges.convert("L"))  # alpha = edge intensity → opaque red where edges exist

    composed = render.convert("RGBA").copy()
    composed.alpha_composite(red)
    return composed.convert("RGB")


def make_sidebyside(*panels: Image.Image) -> Image.Image:
    h = max(p.height for p in panels)
    def fit(img):
        ratio = h / img.height
        return img.convert("RGB").resize((int(img.width * ratio), h))
    sized = [fit(p) for p in panels]
    total_w = sum(p.width for p in sized) + 10 * (len(sized) - 1)
    canvas = Image.new("RGB", (total_w, h), (240, 240, 240))
    x = 0
    for p in sized:
        canvas.paste(p, (x, 0))
        x += p.width + 10
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot_path", type=str, help="PNG viewport screenshot from Rhino/SKP/Revit")
    ap.add_argument("--style", type=str,
                    default="modern materials, natural daylight, professional architectural render",
                    help="Render style hint (materials/lighting only — must NOT change geometry)")
    args = ap.parse_args()

    src_path = Path(args.screenshot_path)
    if not src_path.exists():
        sys.exit(f"File not found: {src_path}")

    out_dir = Path("outputs/spike2")
    out_dir.mkdir(parents=True, exist_ok=True)

    src_bytes = src_path.read_bytes()
    src_img = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    print(f"[spike2] Input: {src_path}  ({src_img.size[0]}x{src_img.size[1]}, {len(src_bytes):,} bytes)")

    # Save a copy of the source for the side-by-side
    (out_dir / "source.png").write_bytes(src_bytes)

    # Extract Canny edges before calling the model — used as the fidelity diagnostic
    print("[spike2] Extracting Canny edges from source...")
    edges_img = extract_edges(src_img)
    edges_img.save(out_dir / "edges.png")
    print(f"[spike2] -> {out_dir / 'edges.png'}")

    # Call Modal
    mime = "image/png" if src_path.suffix.lower() in (".png", ".pdf") else "image/jpeg"
    print(f"[spike2] Calling Nano Banana Pro via Modal (mime={mime})...")
    import modal
    fn = modal.Function.from_name("arch-rendering-spike", "render_from_model_view")
    render_bytes = fn.remote(src_bytes, args.style, mime)

    (out_dir / "render.png").write_bytes(render_bytes)
    print(f"[spike2] -> {out_dir / 'render.png'}")

    render_img = Image.open(io.BytesIO(render_bytes)).convert("RGB")

    # Overlay
    overlay_img = make_overlay(edges_img, render_img)
    overlay_img.save(out_dir / "overlay.png")
    print(f"[spike2] -> {out_dir / 'overlay.png'}  (red = source edges; should align with render edges)")

    # Side by side
    sbs = make_sidebyside(src_img, render_img, overlay_img)
    sbs.save(out_dir / "sidebyside.png")
    print(f"[spike2] -> {out_dir / 'sidebyside.png'}")

    print("\n[spike2] Open overlay.png. Verdict:")
    print("  Red edges hug edges in the render -> Nano Banana Pro preserves geometry. CONTINUE.")
    print("  Red edges float off / contradict the render -> need FLUX + ControlNet fallback.")


if __name__ == "__main__":
    main()
