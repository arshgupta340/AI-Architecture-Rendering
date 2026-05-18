"""
B1: Characterize spike 2 failures.

Runs Nano Banana Pro 4 times on the same input screenshot at different seeds
to separate deterministic failures (always present) from stochastic ones
(seed-dependent). Builds a comparison grid and a rubric template the user
fills in.

Outputs (all in outputs/spike2_5/b1/):
  - nb_seed_<N>.png         (4 raw renders)
  - nb_seed_<N>_overlay.png (each with Canny edges of source overlaid in red)
  - comparison_grid.png     (5x1: source + 4 renders with overlays)
  - scoring_rubric.json     (template — user fills in per-render scores)

Usage:
  python run_b1_baseline.py test_assets/model_views/building.png
  python run_b1_baseline.py test_assets/model_views/building.png --seeds 42,100,200,300
"""

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2


def extract_edges(image: Image.Image, low: int = 60, high: int = 180) -> Image.Image:
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, low, high)
    return Image.fromarray(edges)


def make_overlay(edges: Image.Image, render: Image.Image) -> Image.Image:
    if edges.size != render.size:
        edges = edges.resize(render.size)
    red = Image.new("RGBA", render.size, (255, 30, 30, 0))
    red.putalpha(edges.convert("L"))
    composed = render.convert("RGBA").copy()
    composed.alpha_composite(red)
    return composed.convert("RGB")


def label_image(img: Image.Image, text: str, height: int = 40) -> Image.Image:
    """Add a labeled banner above an image."""
    w, h = img.size
    out = Image.new("RGB", (w, h + height), (245, 245, 245))
    out.paste(img, (0, height))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((12, 8), text, fill=(40, 40, 40), font=font)
    return out


def build_grid(panels: list[Image.Image], cols: int = 5) -> Image.Image:
    """Stack labeled panels into a horizontal grid."""
    h = max(p.height for p in panels)
    def fit(img):
        ratio = h / img.height
        return img.resize((int(img.width * ratio), h))
    sized = [fit(p) for p in panels]
    total_w = sum(p.width for p in sized) + 10 * (len(sized) - 1)
    canvas = Image.new("RGB", (total_w, h), (255, 255, 255))
    x = 0
    for p in sized:
        canvas.paste(p, (x, 0))
        x += p.width + 10
    return canvas


def make_rubric_template(seeds: list[int], output_path: Path) -> None:
    """Write a JSON rubric the architect fills in per-render."""
    rubric = {
        "_instructions": (
            "Score each render below by tagging every observed failure. Use the "
            "categories defined in the plan: Type (Invention/Omission/Displacement/"
            "Transformation/StyleDrift), Location (FrameEdge/Distant/Repetitive/"
            "Ambiguous/CoreMass), Severity (Critical/High/Medium/Low). Then "
            "subjectively score Photorealism, Material believability, and Lighting "
            "coherence on 1-10. The 'critical_failures' field is what gates a "
            "renderer in/out of consideration."
        ),
        "_severity_definitions": {
            "Critical": "Changes building footprint, story count, window grid — architect rejects",
            "High": "Proportions, mullion patterns, or other visible geometric deviation",
            "Medium": "Material/glass tint/color choices — meant to change",
            "Low": "Shadows, sky, foreground vegetation — not part of design"
        },
        "renders": {
            f"nb_seed_{s}": {
                "render_file": f"outputs/spike2_5/b1/nb_seed_{s}.png",
                "overlay_file": f"outputs/spike2_5/b1/nb_seed_{s}_overlay.png",
                "failures": [
                    # Example entry — replace with actual observed failures:
                    # {"type": "Invention", "location": "CoreMass",
                    #  "severity": "Critical", "note": "added 6 windows on right facade"}
                ],
                "critical_failure_count": 0,
                "high_failure_count": 0,
                "medium_failure_count": 0,
                "low_failure_count": 0,
                "photorealism_1_to_10": None,
                "material_believability_1_to_10": None,
                "lighting_coherence_1_to_10": None,
                "notes": ""
            }
            for s in seeds
        },
        "_summary": {
            "deterministic_failures": "list failures that appear across ALL seeds (model limitation, not stochastic)",
            "stochastic_failures": "list failures that vary by seed (potentially fixable with seed selection)",
            "verdict": "advance / iterate-prompt / escalate-to-bake-off"
        }
    }
    output_path.write_text(json.dumps(rubric, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot_path", type=str, help="PNG model viewport screenshot")
    ap.add_argument("--seeds", type=str, default="42,100,200,300",
                    help="Comma-separated seed list (default: 42,100,200,300)")
    ap.add_argument("--style", type=str,
                    default="warm afternoon light, urban context, photorealistic exterior, mixed-use building",
                    help="Render style hint")
    args = ap.parse_args()

    src_path = Path(args.screenshot_path)
    if not src_path.exists():
        sys.exit(f"File not found: {src_path}")

    seeds = [int(s) for s in args.seeds.split(",")]

    out_dir = Path("outputs/spike2_5/b1")
    out_dir.mkdir(parents=True, exist_ok=True)

    src_bytes = src_path.read_bytes()
    src_img = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    print(f"[b1] Input: {src_path} ({src_img.size[0]}x{src_img.size[1]}, {len(src_bytes):,} bytes)")

    edges_img = extract_edges(src_img)
    edges_img.save(out_dir / "edges.png")

    import modal
    fn = modal.Function.from_name("arch-rendering-spike", "render_from_model_view")
    mime = "image/png" if src_path.suffix.lower() == ".png" else "image/jpeg"

    panels = [label_image(src_img, "SOURCE")]

    for seed in seeds:
        print(f"\n[b1] Rendering at seed={seed}...")
        render_bytes = fn.remote(src_bytes, args.style, mime, seed, "")
        render_path = out_dir / f"nb_seed_{seed}.png"
        render_path.write_bytes(render_bytes)
        print(f"[b1]   -> {render_path}")

        render_img = Image.open(io.BytesIO(render_bytes)).convert("RGB")
        overlay_img = make_overlay(edges_img, render_img)
        overlay_path = out_dir / f"nb_seed_{seed}_overlay.png"
        overlay_img.save(overlay_path)
        print(f"[b1]   -> {overlay_path}")

        panels.append(label_image(overlay_img, f"seed={seed} (edges overlaid)"))

    grid = build_grid(panels)
    grid_path = out_dir / "comparison_grid.png"
    grid.save(grid_path)
    print(f"\n[b1] Comparison grid -> {grid_path}")

    rubric_path = out_dir / "scoring_rubric.json"
    make_rubric_template(seeds, rubric_path)
    print(f"[b1] Rubric template -> {rubric_path}")

    print("\n[b1] DONE. Next step:")
    print(f"  1. Open {grid_path} and compare all 4 seeds side by side.")
    print(f"  2. Fill in {rubric_path} with failure tags + subjective scores per render.")
    print(f"  3. In _summary, list which failures are deterministic (across all seeds) vs stochastic.")
    print(f"  4. Verdict: 'advance' / 'iterate-prompt' / 'escalate-to-bake-off'.")


if __name__ == "__main__":
    main()
