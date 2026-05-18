"""
Spike 2 — Nano Banana Pro line-work fidelity test.

Usage:
  python test_linework_fidelity.py path/to/linework.png
  python test_linework_fidelity.py path/to/linework.pdf
  python test_linework_fidelity.py path/to/linework.png --style "warm evening light, cozy interior"

Reads a perspective line drawing (PNG or PDF), sends it to render_from_linework()
on Modal, and saves:
  - outputs/spike2/render.png       — the photorealistic render
  - outputs/spike2/overlay.png      — line work overlaid on render (alpha-blended)
  - outputs/spike2/sidebyside.png   — input | render | overlay, side-by-side

Visual inspection of overlay.png answers the spike's question:
  Did Nano Banana Pro preserve the line geometry?

PDF handling: rasterizes page 1 at 200 DPI to a PNG before sending.
"""

import argparse
import io
import sys
from pathlib import Path

# Run inside the Python 3.12 venv (.venv\Scripts\activate)
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageChops


def load_linework(path: Path) -> tuple[bytes, str]:
    """Returns (PNG bytes, mime_type). Rasterizes PDFs."""
    if path.suffix.lower() == ".pdf":
        try:
            from pdf2image import convert_from_path
        except ImportError:
            sys.exit("PDF input requires pdf2image: `pip install pdf2image` "
                     "(and Poppler installed on the system).")
        pages = convert_from_path(str(path), dpi=200, first_page=1, last_page=1)
        if not pages:
            sys.exit(f"Could not rasterize PDF: {path}")
        buf = io.BytesIO()
        pages[0].save(buf, format="PNG")
        return buf.getvalue(), "image/png"
    elif path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return path.read_bytes(), f"image/{path.suffix.lower().lstrip('.')}".replace("jpg", "jpeg")
    else:
        sys.exit(f"Unsupported file type: {path.suffix}. Use PNG, JPG, or PDF.")


def make_overlay(linework: Image.Image, render: Image.Image) -> Image.Image:
    """
    Overlay the line work on top of the render. Lines should align with edges
    in the render. Misalignment = Nano Banana Pro hallucinated geometry.
    """
    if linework.size != render.size:
        linework = linework.resize(render.size)

    # Convert line work to RGBA with transparent background.
    # Assume dark lines on light background: dark pixels → opaque red,
    # light pixels → transparent.
    lw_gray = linework.convert("L")
    alpha = Image.eval(lw_gray, lambda px: 255 - px)  # invert: dark → opaque
    red_lines = Image.new("RGBA", linework.size, (255, 30, 30, 0))
    red_lines.putalpha(alpha)

    overlay = render.convert("RGBA").copy()
    overlay.alpha_composite(red_lines)
    return overlay.convert("RGB")


def make_sidebyside(linework: Image.Image, render: Image.Image, overlay: Image.Image) -> Image.Image:
    h = max(linework.height, render.height, overlay.height)
    def fit(img):
        ratio = h / img.height
        return img.resize((int(img.width * ratio), h))
    panels = [fit(linework.convert("RGB")), fit(render), fit(overlay)]
    total_w = sum(p.width for p in panels) + 20
    sbs = Image.new("RGB", (total_w, h), (240, 240, 240))
    x = 0
    for p in panels:
        sbs.paste(p, (x, 0))
        x += p.width + 10
    return sbs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("linework_path", type=str, help="PNG, JPG, or PDF perspective line drawing")
    ap.add_argument("--style", type=str, default="modern interior, natural daylight",
                    help="Render style prompt (materials/lighting only — does NOT change geometry)")
    args = ap.parse_args()

    path = Path(args.linework_path)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    out_dir = Path("outputs/spike2")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[spike2] Loading line work: {path}")
    linework_bytes, mime = load_linework(path)
    print(f"[spike2] {len(linework_bytes):,} bytes, mime={mime}")

    print(f"[spike2] Calling Nano Banana Pro via Modal...")
    import modal
    fn = modal.Function.from_name("arch-rendering-spike", "render_from_linework")
    render_bytes = fn.remote(linework_bytes, args.style, mime)

    render_path = out_dir / "render.png"
    render_path.write_bytes(render_bytes)
    print(f"[spike2] -> {render_path}")

    # Build overlay + side-by-side visualizations
    linework_img = Image.open(io.BytesIO(linework_bytes))
    render_img = Image.open(io.BytesIO(render_bytes))

    overlay_img = make_overlay(linework_img, render_img)
    overlay_path = out_dir / "overlay.png"
    overlay_img.save(overlay_path)
    print(f"[spike2] -> {overlay_path}  (red lines = original; should align with edges in the render)")

    sbs_img = make_sidebyside(linework_img, render_img, overlay_img)
    sbs_path = out_dir / "sidebyside.png"
    sbs_img.save(sbs_path)
    print(f"[spike2] -> {sbs_path}")

    print("\n[spike2] Open the overlay and judge visually:")
    print("  If red lines hug the edges of objects in the render -> Nano Banana preserves geometry.")
    print("  If red lines float off / contradict the render -> need FLUX + ControlNet fallback.")


if __name__ == "__main__":
    main()
