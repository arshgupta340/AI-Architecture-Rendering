"""One-off salvage script for T22's urban_exterior tag failure.

Background: Gemini 3 Pro returned bboxes with duplicate "y" keys
(`{"x": 499, "y": 361, "w": 25, "y": 425}` instead of `{x, y, w, h}`).
Standard JSON parsers silently drop the first key on duplicates, so
pydantic saw bboxes missing `h`. Reproducible: same failure on retry.

This script:
  1. Reads spike/outputs/spike3/t22/urban_exterior/tags_raw.json
  2. Uses json.loads with object_pairs_hook to preserve key collisions
  3. For each bbox dict, if there are two "y" entries, treats the second
     as `h` (the model's intent was clearly xywh; the second "y" was a
     typo)
  4. Validates via TagRegionsResponse and writes:
       - tags.json (validated, schema-clean)
       - tagged.png (visualization with rescaled pixel bboxes)
  5. Documents what was salvaged vs dropped

No API calls. Idempotent. Safe to re-run.
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


def _bbox_hook(pairs: list[tuple[str, object]]) -> dict:
    """object_pairs_hook that promotes a duplicate 'y' to 'h' for bbox dicts."""
    keys = [k for k, _ in pairs]
    if keys == ["x", "y", "w", "y"]:
        x, y, w, y2 = (v for _, v in pairs)
        return {"x": x, "y": y, "w": w, "h": y2}
    if keys == ["x", "y"] and len(pairs) == 2:
        # Region 34 in the original had only x,y — we can't salvage that.
        return {"x": pairs[0][1], "y": pairs[1][1]}
    return dict(pairs)


def main() -> int:
    raw_path = OUT_DIR / "tags_raw.json"
    if not raw_path.exists():
        print(f"ERROR: {raw_path} not found.")
        return 1
    raw = raw_path.read_text(encoding="utf-8")
    parsed = json.loads(raw, object_pairs_hook=_bbox_hook)
    # Top-level was a list of region dicts (bare-list response).
    if isinstance(parsed, list):
        regions_raw = parsed
    else:
        regions_raw = parsed.get("regions", [])

    salvaged: list[dict] = []
    dropped: list[dict] = []
    for region in regions_raw:
        bbox = region.get("bbox", {})
        if all(k in bbox for k in ("x", "y", "w", "h")):
            salvaged.append(region)
        else:
            dropped.append({"id": region.get("id"), "label": region.get("label"), "bbox": bbox})

    print(f"input regions:    {len(regions_raw)}")
    print(f"salvaged (xywh):  {len(salvaged)}")
    print(f"dropped (broken): {len(dropped)}")
    for d in dropped:
        print(f"  - {d['id']!r} ({d['label']!r}): bbox={d['bbox']}")

    response = TagRegionsResponse.model_validate({"regions": salvaged})
    tags_path = OUT_DIR / "tags.json"
    tags_path.write_text(json.dumps(response.model_dump(), indent=2), encoding="utf-8")
    print(f"wrote validated tags -> {tags_path}")

    render_bytes = (OUT_DIR / "render.png").read_bytes()
    tagged_bytes = _draw_regions(render_bytes, response)
    tagged_path = OUT_DIR / "tagged.png"
    tagged_path.write_bytes(tagged_bytes)
    print(f"wrote visualization  -> {tagged_path}")

    # Meta — write similar shape as run_t22.py.
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
            "Original Gemini response had malformed bboxes with duplicate 'y' "
            "keys instead of 'h'. Salvaged via custom JSON object_pairs_hook "
            "treating the second 'y' as 'h'. Dropped any region whose bbox "
            "still lacked w or h after that fix."
        ),
        "dropped_region_ids": [d["id"] for d in dropped],
        "render_cost_usd": 0.04,
        "tag_cost_usd": 0.02,  # 2 attempts during T22
    }
    meta_path = OUT_DIR / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote meta           -> {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
