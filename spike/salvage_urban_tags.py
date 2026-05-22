"""One-off salvage for T22's urban_exterior tag failure.

Originally this script implemented its own JSON-repair hook to recover
the malformed Gemini response (`{x, y, w, y}` instead of `{x, y, w, h}`).
After T23 that logic now lives in `spike/schemas.py:_bbox_pairs_hook` +
`TagRegionsResponse.parse_tolerant`, so this script is a thin wrapper
that:
  1. Reads spike/outputs/spike3/t22/urban_exterior/tags_raw.json
  2. Calls TagRegionsResponse.parse_tolerant (the same parser used by
     production paths now)
  3. Writes tags.json + tagged.png + updates meta.json with the
     salvage-stats produced by the parser

Kept around so the salvage is reproducible from raw_save_dir alone and
so future malformed-response incidents have a working template.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spike.schemas import TagRegionsResponse  # noqa: E402
from spike.test_vlm_tagging import _draw_regions  # noqa: E402

OUT_DIR = Path("spike/outputs/spike3/t22/urban_exterior")


def main() -> int:
    raw_path = OUT_DIR / "tags_raw.json"
    if not raw_path.exists():
        print(f"ERROR: {raw_path} not found.")
        return 1
    raw = raw_path.read_text(encoding="utf-8")
    response = TagRegionsResponse.parse_tolerant(raw)
    dropped = response.__dict__.get("_dropped_region_ids") or []

    print(f"salvaged regions:  {len(response.regions)}")
    print(f"dropped regions:   {len(dropped)}")
    for d in dropped:
        print(f"  - {d!r}")

    tags_path = OUT_DIR / "tags.json"
    tags_path.write_text(
        json.dumps(response.model_dump(), indent=2), encoding="utf-8"
    )
    print(f"wrote validated tags -> {tags_path}")

    render_bytes = (OUT_DIR / "render.png").read_bytes()
    tagged_bytes = _draw_regions(render_bytes, response)
    tagged_path = OUT_DIR / "tagged.png"
    tagged_path.write_bytes(tagged_bytes)
    print(f"wrote visualization  -> {tagged_path}")

    from PIL import Image
    rw, rh = Image.open(io.BytesIO(render_bytes)).size
    label_counts: dict[str, int] = {}
    for r in response.regions:
        label_counts[r.label] = label_counts.get(r.label, 0) + 1
    max_xy = (
        max((r.bbox.x + r.bbox.w for r in response.regions), default=0),
        max((r.bbox.y + r.bbox.h for r in response.regions), default=0),
    )
    meta = {
        "screenshot": "spike/test_assets/model_views/urban exterior.png",
        "render_size": [rw, rh],
        "region_count": len(response.regions),
        "label_counts": label_counts,
        "max_xy_norm": list(max_xy),
        "salvage_note": (
            "Recovered from Gemini's duplicate-`y` bbox bug via "
            "TagRegionsResponse.parse_tolerant. Bboxes shaped "
            "{x, y, w, y} are reinterpreted as {x, y, w, h=second_y}. "
            "The 'h' values are likely y2 (bottom-right y), so recovered "
            "bboxes may be over-tall; (x, y, w) and labels are valid. "
            "See wiki/DECISIONS.md#gemini-bbox-malformed-json."
        ),
        "dropped_region_ids": dropped,
        "render_cost_usd": 0.04,
        "tag_cost_usd": 0.02,
    }
    meta_path = OUT_DIR / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote meta           -> {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
