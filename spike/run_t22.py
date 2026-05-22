"""T22 — production-shape Spike 3 gate evaluation.

For each of the 4 new test screenshots:
  1. Call `render_from_model_view` (Nano Banana Pro) — produces a photoreal
     render that PRESERVES the screenshot's geometry.
  2. Call `tag_regions` (Gemini 3 Pro) on the (screenshot, render) pair —
     produces a TagRegionsResponse with normalized 0-1000 bboxes.
  3. Draw labeled bboxes on the render (rescaled to pixel coords) and save.

Outputs land in `spike/outputs/spike3/t22/<stem>/`:
    - render.png        — photoreal render
    - tagged.png        — render with bboxes overlaid
    - tags.json         — raw TagRegionsResponse
    - meta.json         — image dims + region counts + label histogram

Cost: ~$0.05 per screenshot ($0.04 Nano Banana + $0.01 Gemini) × 4 = ~$0.20.

Run from repo root:
    spike/.venv/Scripts/python.exe spike/run_t22.py --live
or dry-run (default; lists planned work, no API calls):
    spike/.venv/Scripts/python.exe spike/run_t22.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make spike.* importable when run from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spike.schemas import TagRegionsResponse, save_raw_response  # noqa: E402
from spike.test_vlm_tagging import _draw_regions  # noqa: E402

SCREENSHOTS = [
    Path("spike/test_assets/model_views/modern interior.jpg"),
    Path("spike/test_assets/model_views/traditional exterior.jpg"),
    Path("spike/test_assets/model_views/urban exterior.png"),
    Path("spike/test_assets/model_views/complex windows - Copy.png"),
]
OUT_ROOT = Path("spike/outputs/spike3/t22")

_RENDER_COST_USD = 0.04  # Nano Banana Pro per image
_TAG_COST_USD = 0.01     # Gemini 3 Pro per call


def _slugify(stem: str) -> str:
    return stem.replace(" ", "_").replace("-_Copy", "").lower()


def _run_one(screenshot_path: Path, *, reuse_render: bool = False) -> dict:
    import modal
    from PIL import Image
    import io

    slug = _slugify(screenshot_path.stem)
    out_dir = OUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    screenshot_bytes = screenshot_path.read_bytes()
    mime = "image/jpeg" if screenshot_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    render_path = out_dir / "render.png"

    # ---- 1. Render (skip if --reuse-render and render.png exists) ----
    if reuse_render and render_path.exists():
        render_bytes = render_path.read_bytes()
        rw, rh = Image.open(io.BytesIO(render_bytes)).size
        print(f"  [1/3] render reused -> {render_path} ({rw}x{rh})")
    else:
        print(f"  [1/3] render_from_model_view -> Nano Banana Pro ...")
        render_fn = modal.Function.from_name("arch-rendering-spike", "render_from_model_view")
        render_bytes = render_fn.remote(screenshot_bytes, mime_type=mime)
        render_path.write_bytes(render_bytes)
        rw, rh = Image.open(io.BytesIO(render_bytes)).size
        print(f"        render saved -> {render_path} ({rw}x{rh}, {len(render_bytes):,} bytes)")

    # ---- 2. Tag ----
    print(f"  [2/3] tag_regions -> Gemini 3 Pro ...")
    tag_fn = modal.Function.from_name("arch-rendering-spike", "tag_regions")
    raw = tag_fn.remote(screenshot_bytes, render_bytes, screenshot_mime=mime, render_mime="image/png")
    raw_path = save_raw_response(out_dir, raw)
    print(f"        raw response saved -> {raw_path}")
    tags = TagRegionsResponse.parse_tolerant(raw)
    dropped = tags.__dict__.get("_dropped_region_ids") or []
    if dropped:
        print(f"        tolerant-parse dropped {len(dropped)} region(s): {dropped}")
    tags_path = out_dir / "tags.json"
    tags_path.write_text(json.dumps(tags.model_dump(), indent=2), encoding="utf-8")
    print(f"        {len(tags.regions)} regions -> {tags_path}")

    # ---- 3. Visualize ----
    print(f"  [3/3] draw bboxes (scaled to pixel coords) ...")
    tagged_bytes = _draw_regions(render_bytes, tags)
    tagged_path = out_dir / "tagged.png"
    tagged_path.write_bytes(tagged_bytes)
    print(f"        tagged saved -> {tagged_path}")

    # ---- Meta ----
    label_counts: dict[str, int] = {}
    for r in tags.regions:
        label_counts[r.label] = label_counts.get(r.label, 0) + 1
    max_xy = (
        max((r.bbox.x + r.bbox.w for r in tags.regions), default=0),
        max((r.bbox.y + r.bbox.h for r in tags.regions), default=0),
    )
    meta = {
        "screenshot": str(screenshot_path),
        "render_size": [rw, rh],
        "region_count": len(tags.regions),
        "label_counts": label_counts,
        "max_xy_norm": list(max_xy),
        "render_cost_usd": _RENDER_COST_USD,
        "tag_cost_usd": _TAG_COST_USD,
    }
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="T22 - production-shape Spike 3 gate eval.")
    p.add_argument("--live", action="store_true", help="Actually invoke Modal. Default is dry-run.")
    p.add_argument("--only", default=None, help="Run only this slug (e.g. 'urban_exterior').")
    p.add_argument("--reuse-render", action="store_true", help="If render.png exists, skip the render call and re-tag only.")
    args = p.parse_args(argv)

    targets = SCREENSHOTS
    if args.only:
        targets = [s for s in SCREENSHOTS if _slugify(s.stem) == args.only]
        if not targets:
            print(f"--only {args.only!r} did not match any screenshot. Slugs available: "
                  f"{[_slugify(s.stem) for s in SCREENSHOTS]}")
            return 2

    print(f"T22 plan: {len(targets)} screenshot(s) × (render + tag)")
    for s in targets:
        marker = "OK" if s.exists() else "MISSING"
        print(f"  [{marker}] {s}")
    per_call = (0 if args.reuse_render else _RENDER_COST_USD) + _TAG_COST_USD
    total = len(targets) * per_call
    bits = []
    if not args.reuse_render:
        bits.append(f"{_RENDER_COST_USD:.2f} render")
    bits.append(f"{_TAG_COST_USD:.2f} tag")
    print(f"Estimated cost: ~${total:.2f} ({' + '.join(bits)}, × {len(targets)})")

    if not args.live:
        print("\n(dry-run; re-run with --live to actually invoke Modal)")
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    metas: list[dict] = []
    for i, s in enumerate(targets, start=1):
        if not s.exists():
            print(f"\n[{i}/{len(targets)}] SKIP (missing): {s}")
            continue
        print(f"\n[{i}/{len(targets)}] {s.name}")
        try:
            metas.append(_run_one(s, reuse_render=args.reuse_render))
        except Exception as e:
            print(f"        FAILED: {type(e).__name__}: {e}")
            metas.append({"screenshot": str(s), "error": f"{type(e).__name__}: {e}"})

    summary_path = OUT_ROOT / "summary.json"
    summary_path.write_text(json.dumps({"runs": metas}, indent=2), encoding="utf-8")
    print(f"\nT22 complete. Summary -> {summary_path}")
    print(f"Per-screenshot outputs under {OUT_ROOT}/<slug>/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
