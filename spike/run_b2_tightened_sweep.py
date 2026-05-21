"""B2 tightened-prompt sweep: prompt-on vs prompt-off at the same B1 seeds.

Runs Nano Banana Pro with `TIGHTENED_CONSTRAINTS` injected via
extra_constraints at the same 4 seeds B1 used (42, 100, 200, 300). Builds a
2-row comparison grid against B1 so each seed can be graded side by side.

Outputs (all under outputs/spike2_5/b2/):
  - nb_seed_<N>_tightened.png         renders with tightened constraints
  - nb_seed_<N>_tightened_overlay.png Canny edges of source overlaid in red
  - comparison_vs_b1.png              top row = B1 (no constraints),
                                      bottom row = B2 (tightened)

Run from the spike/ directory:
  spike\\.venv\\Scripts\\python.exe run_b2_tightened_sweep.py \\
      test_assets/model_views/building.png
"""

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

# Reuse B1 helpers for edge extraction, overlays, labels, grid building.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_b1_baseline import build_grid, extract_edges, label_image, make_overlay  # noqa: E402
from run_b2_variants import TIGHTENED_CONSTRAINTS  # noqa: E402


STYLE = (
    "warm afternoon light, urban context, photorealistic exterior, "
    "mixed-use building"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot_path", type=str,
                    help="PNG model viewport screenshot")
    ap.add_argument("--seeds", type=str, default="42,100,200,300",
                    help="Comma-separated seed list (default: 42,100,200,300)")
    ap.add_argument("--b1-dir", type=str, default="outputs/spike2_5/b1",
                    help="Where the B1 overlays live (for the comparison row)")
    args = ap.parse_args()

    src_path = Path(args.screenshot_path)
    if not src_path.exists():
        sys.exit(f"File not found: {src_path}")

    seeds = [int(s) for s in args.seeds.split(",")]
    out_dir = Path("outputs/spike2_5/b2")
    out_dir.mkdir(parents=True, exist_ok=True)
    b1_dir = Path(args.b1_dir)

    src_bytes = src_path.read_bytes()
    src_img = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    print(f"[b2-sweep] Input: {src_path} "
          f"({src_img.size[0]}x{src_img.size[1]}, {len(src_bytes):,} bytes)")
    print(f"[b2-sweep] Seeds: {seeds}")
    print(f"[b2-sweep] Tightened constraints:\n  {TIGHTENED_CONSTRAINTS}\n")

    edges_img = extract_edges(src_img)

    import modal
    fn = modal.Function.from_name("arch-rendering-spike", "render_from_model_view")
    mime = "image/png" if src_path.suffix.lower() == ".png" else "image/jpeg"

    b1_panels = [label_image(src_img, "SOURCE")]
    b2_panels = [label_image(src_img, "SOURCE")]

    for seed in seeds:
        # Reuse existing B1 overlay for the top row.
        b1_overlay_path = b1_dir / f"nb_seed_{seed}_overlay.png"
        if b1_overlay_path.exists():
            b1_img = Image.open(b1_overlay_path).convert("RGB")
            b1_panels.append(label_image(b1_img, f"B1 seed={seed}"))
        else:
            print(f"[b2-sweep] WARNING: missing {b1_overlay_path}; using gray placeholder")
            placeholder = Image.new("RGB", src_img.size, (200, 200, 200))
            b1_panels.append(label_image(placeholder, f"B1 seed={seed} (missing)"))

        print(f"[b2-sweep] Rendering seed={seed} with tightened constraints...")
        render_bytes = fn.remote(src_bytes, STYLE, mime, seed, TIGHTENED_CONSTRAINTS)
        render_path = out_dir / f"nb_seed_{seed}_tightened.png"
        render_path.write_bytes(render_bytes)
        print(f"[b2-sweep]   -> {render_path}")

        render_img = Image.open(io.BytesIO(render_bytes)).convert("RGB")
        overlay_img = make_overlay(edges_img, render_img)
        overlay_path = out_dir / f"nb_seed_{seed}_tightened_overlay.png"
        overlay_img.save(overlay_path)
        print(f"[b2-sweep]   -> {overlay_path}")

        b2_panels.append(label_image(overlay_img, f"B2 seed={seed} (tightened)"))

    # 2-row grid: top = B1 row, bottom = B2 row.
    b1_row = build_grid(b1_panels)
    b2_row = build_grid(b2_panels)
    w = max(b1_row.width, b2_row.width)
    gap = 20
    h = b1_row.height + b2_row.height + gap
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(b1_row, (0, 0))
    canvas.paste(b2_row, (0, b1_row.height + gap))
    grid_path = out_dir / "comparison_vs_b1.png"
    canvas.save(grid_path)
    print(f"\n[b2-sweep] Comparison grid -> {grid_path}")
    print("\n[b2-sweep] DONE. Next step:")
    print(f"  1. Open {grid_path}")
    print( "     top row    = B1 (no extra constraints)")
    print( "     bottom row = B2 (tightened: 'right facade has 0 windows', etc.)")
    print( "  2. For each seed, check if the invented windows and corner")
    print( "     wraparound disappeared.")
    print( "  3. If clean -> advance to Spike 3. If not -> escalate to B3.")


if __name__ == "__main__":
    main()
