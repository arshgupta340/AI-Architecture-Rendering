"""B3 multi-renderer bake-off driver.

Instantiates every renderer in `spike/renderers/` whose required env var is
present, fans them out sequentially on a single screenshot, and assembles:

  - `spike/outputs/spike2_5/b3/<renderer_name>.png`             raw renders
  - `spike/outputs/spike2_5/b3/comparison_grid.png`             labeled grid
  - `spike/outputs/spike2_5/b3/overlays_grid.png`               edge overlays
  - `spike/outputs/spike2_5/b3/scores.csv`                      rubric template

Default behavior with no provider env vars set: prints a manifest of which
renderers would run, writes nothing, exits 0. This lets the architect dry-run
locally tomorrow without firing any HTTP.

Usage:
  python spike/compare_renderers.py --input <screenshot.png>
  python spike/compare_renderers.py --input <screenshot.png> --seed 42 \\
      --style "warm afternoon light, urban context, photorealistic exterior"
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

# Load spike/.env so renderer env vars (BFL_API_KEY, REPLICATE_API_TOKEN,
# RECRAFT_API_TOKEN, MAGNIFIC_API_KEY, GOOGLE_API_KEY) are picked up without
# requiring the user to source it in their shell first. Shell env still wins
# over .env values, matching run_spike.py's behavior.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Reuse B1's labeled-grid / overlay helpers so the visual style stays
# consistent across spike phases. Path bootstrap: this file may be run via
# `python spike/compare_renderers.py` from the repo root, in which case
# `spike/` isn't on sys.path. Insert it so `run_b1_baseline` and
# `renderers.*` both resolve.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from run_b1_baseline import (  # noqa: E402 -- after sys.path tweak
    build_grid,
    extract_edges,
    label_image,
    make_overlay,
)

# Import every renderer. Module-load is network-free by contract.
from spike.renderers.base import Renderer  # noqa: E402
from spike.renderers.flux_bfl import Flux2ProRenderer, FluxFillProRenderer  # noqa: E402
from spike.renderers.magnific import MagnificMysticRenderer  # noqa: E402
from spike.renderers.nano_banana import NanoBananaProRenderer  # noqa: E402
from spike.renderers.recraft import RecraftV3Renderer  # noqa: E402
from spike.renderers.replicate_models import (  # noqa: E402
    FluxCannyProReplicateRenderer,
    FluxDepthProReplicateRenderer,
    HiDreamE1Renderer,
    QwenImageEditRenderer,
)

# Order here drives the order in the grid + CSV.
ALL_RENDERER_CLASSES: tuple[type[Renderer], ...] = (
    NanoBananaProRenderer,
    Flux2ProRenderer,
    FluxFillProRenderer,
    FluxCannyProReplicateRenderer,
    FluxDepthProReplicateRenderer,
    MagnificMysticRenderer,
    RecraftV3Renderer,
    QwenImageEditRenderer,
    HiDreamE1Renderer,
)

DEFAULT_STYLE = (
    "warm afternoon light, urban context, photorealistic exterior, "
    "mixed-use building"
)

# Rubric columns mirror B1's scoring_rubric.json so the architect can fill
# this in with the same vocabulary. Left blank by the driver.
SCORE_COLUMNS = (
    "renderer",
    "provider",
    "cost_per_call_usd",
    "status",            # "ok" / "error" / "skipped"
    "elapsed_s",
    "output_file",
    "critical_failures",
    "high_failures",
    "medium_failures",
    "low_failures",
    "photorealism_1_to_10",
    "material_believability_1_to_10",
    "lighting_coherence_1_to_10",
    "silhouette_iou",
    "edge_density_delta",
    "notes",
)


def _available_renderers() -> list[Renderer]:
    """Return one instance per renderer class whose env var is set."""
    live: list[Renderer] = []
    for cls in ALL_RENDERER_CLASSES:
        if os.environ.get(cls.env_var):
            live.append(cls())
    return live


def _manifest_line(cls: type[Renderer]) -> str:
    present = bool(os.environ.get(cls.env_var))
    flag = "LIVE" if present else "skip"
    return (
        f"  [{flag}] {cls.name:<24} provider={cls.provider:<10} "
        f"env={cls.env_var:<22} cost~${cls.cost_per_call_usd:.3f}"
    )


def _print_manifest(renderers_in_order: tuple[type[Renderer], ...]) -> None:
    print("[b3] Renderer manifest:")
    for cls in renderers_in_order:
        print(_manifest_line(cls))


def _save_csv_template(
    out_path: Path,
    rows: list[dict[str, object]],
) -> None:
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCORE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in SCORE_COLUMNS})


def main() -> int:
    ap = argparse.ArgumentParser(description="Spike 2.5/B3 bake-off driver.")
    ap.add_argument(
        "--input",
        required=True,
        type=str,
        help="Path to the source screenshot (PNG).",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed passed to renderers that accept one (default: 42).",
    )
    ap.add_argument(
        "--style",
        type=str,
        default=DEFAULT_STYLE,
        help="Style prompt sent to every renderer.",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default="spike/outputs/spike2_5/b3",
        help="Output directory (default: spike/outputs/spike2_5/b3).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the renderer manifest and exit without firing any HTTP. "
            "Use this to verify .env wiring without spending."
        ),
    )
    args = ap.parse_args()

    src_path = Path(args.input)
    if not src_path.is_file():
        print(f"[b3] ERROR: input not found: {src_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)

    # Always print the manifest first. If nothing is live, exit 0 without
    # creating any files — this is the safe dry-run default.
    _print_manifest(ALL_RENDERER_CLASSES)
    live = _available_renderers()
    if not live:
        print(
            "\n[b3] No provider env vars set. Nothing to render. "
            "Exiting without writing outputs."
        )
        return 0

    if args.dry_run:
        print(
            f"\n[b3] --dry-run: would fire {len(live)} renderer(s) "
            f"({', '.join(r.name for r in live)}). No HTTP made. Exiting."
        )
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    src_bytes = src_path.read_bytes()
    src_img = Image.open(io.BytesIO(src_bytes)).convert("RGB")
    print(
        f"\n[b3] Input: {src_path} ({src_img.size[0]}x{src_img.size[1]}, "
        f"{len(src_bytes):,} bytes)"
    )
    print(f"[b3] Live renderers: {', '.join(r.name for r in live)}")

    edges_img = extract_edges(src_img)

    raw_panels: list[Image.Image] = [label_image(src_img, "SOURCE")]
    overlay_panels: list[Image.Image] = [label_image(src_img, "SOURCE")]
    rows: list[dict[str, object]] = []

    for r in live:
        print(f"\n[b3] -> {r.name} ...")
        row: dict[str, object] = {
            "renderer": r.name,
            "provider": r.provider,
            "cost_per_call_usd": r.cost_per_call_usd,
        }
        t0 = time.monotonic()
        try:
            render_bytes = r.render(src_path, args.style, seed=args.seed)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"[b3]    FAILED in {elapsed:.1f}s: {exc!r}")
            traceback.print_exc()
            row["status"] = "error"
            row["elapsed_s"] = f"{elapsed:.2f}"
            row["notes"] = repr(exc)
            rows.append(row)
            continue

        elapsed = time.monotonic() - t0
        out_path = out_dir / f"{r.name}.png"
        out_path.write_bytes(render_bytes)
        print(f"[b3]    ok in {elapsed:.1f}s -> {out_path}")

        render_img = Image.open(io.BytesIO(render_bytes)).convert("RGB")
        overlay_img = make_overlay(edges_img, render_img)
        raw_panels.append(label_image(render_img, r.name))
        overlay_panels.append(label_image(overlay_img, f"{r.name} (edges)"))

        row["status"] = "ok"
        row["elapsed_s"] = f"{elapsed:.2f}"
        row["output_file"] = str(out_path)
        rows.append(row)

    # Build the two grids only if at least one renderer succeeded.
    successes = [row for row in rows if row.get("status") == "ok"]
    if successes:
        cols = len(raw_panels)
        comparison = build_grid(raw_panels, cols=cols)
        overlays = build_grid(overlay_panels, cols=cols)
        comparison_path = out_dir / "comparison_grid.png"
        overlays_path = out_dir / "overlays_grid.png"
        comparison.save(comparison_path)
        overlays.save(overlays_path)
        print(f"\n[b3] Comparison grid -> {comparison_path}")
        print(f"[b3] Overlay grid    -> {overlays_path}")
    else:
        print("\n[b3] No successful renders; skipping grids.")

    scores_path = out_dir / "scores.csv"
    _save_csv_template(scores_path, rows)
    print(f"[b3] Scores template -> {scores_path}")
    print(
        "\n[b3] DONE. Next step: open the grids, fill in scores.csv per row "
        "with failure counts and 1-10 subjective scores, then pick the top "
        "two renderers for Spike 3 region-edit experiments."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
