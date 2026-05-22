"""Tests for spike/schemas.py (T23).

Focus: the defensive helpers that make production tag_regions callers
robust to Gemini's known output bugs:

  - `save_raw_response`: persists the response BEFORE pydantic validation
    so a schema failure never costs us paid data.
  - `TagRegionsResponse.parse_tolerant`: alternate constructor that
    handles clean responses, bare-list responses, dict input, str/bytes
    JSON, AND the duplicate-`y`-key bbox malformation surfaced by T22.

The duplicate-`y` test uses the exact shape Gemini produced on
urban_exterior so future regressions on the parser are caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spike.schemas import (
    BBox,
    Region,
    TagRegionsResponse,
    _bbox_pairs_hook,
    save_raw_response,
)


# --------------------------------------------------------------------------- #
# save_raw_response                                                           #
# --------------------------------------------------------------------------- #


def test_save_raw_response_writes_str_verbatim(tmp_path: Path) -> None:
    raw_text = '[{"id":"r1","label":"wall","bbox":{"x":0,"y":0,"w":10,"h":10}}]'
    out = save_raw_response(tmp_path, raw_text)
    assert out.exists() and out.name == "tags_raw.json"
    assert out.read_text(encoding="utf-8") == raw_text


def test_save_raw_response_decodes_bytes(tmp_path: Path) -> None:
    raw_bytes = b'{"regions": []}'
    out = save_raw_response(tmp_path, raw_bytes)
    assert out.read_text(encoding="utf-8") == '{"regions": []}'


def test_save_raw_response_serializes_object(tmp_path: Path) -> None:
    raw_obj = {"regions": [{"id": "r1", "label": "wall"}]}
    out = save_raw_response(tmp_path, raw_obj)
    assert json.loads(out.read_text(encoding="utf-8")) == raw_obj


def test_save_raw_response_creates_missing_dir(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    out = save_raw_response(nested, "hi", filename="my_raw.json")
    assert out.parent == nested
    assert out.name == "my_raw.json"
    assert out.read_text(encoding="utf-8") == "hi"


# --------------------------------------------------------------------------- #
# _bbox_pairs_hook (used during JSON decode)                                  #
# --------------------------------------------------------------------------- #


def test_pairs_hook_repairs_duplicate_y_key() -> None:
    # Exactly the shape Gemini produced on urban_exterior.
    pairs = [("x", 499), ("y", 361), ("w", 25), ("y", 425)]
    assert _bbox_pairs_hook(pairs) == {"x": 499, "y": 361, "w": 25, "h": 425}


def test_pairs_hook_leaves_clean_bbox_alone() -> None:
    pairs = [("x", 0), ("y", 0), ("w", 100), ("h", 50)]
    assert _bbox_pairs_hook(pairs) == {"x": 0, "y": 0, "w": 100, "h": 50}


def test_pairs_hook_leaves_non_bbox_dicts_alone() -> None:
    region_pairs = [("id", "r1"), ("label", "wall"), ("bbox", {}), ("confidence", 0.9)]
    assert _bbox_pairs_hook(region_pairs) == {
        "id": "r1", "label": "wall", "bbox": {}, "confidence": 0.9,
    }


# --------------------------------------------------------------------------- #
# TagRegionsResponse.parse_tolerant                                           #
# --------------------------------------------------------------------------- #


_GOOD_BBOX = {"x": 10, "y": 20, "w": 30, "h": 40}


def _good_region(rid: str = "r1", label: str = "wall") -> dict:
    return {"id": rid, "label": label, "bbox": dict(_GOOD_BBOX), "confidence": 0.9}


def test_parse_tolerant_passes_through_existing_instance() -> None:
    r = Region(id="r1", label="wall", bbox=BBox(**_GOOD_BBOX), confidence=0.9)
    inst = TagRegionsResponse(regions=[r])
    assert TagRegionsResponse.parse_tolerant(inst) is inst


def test_parse_tolerant_handles_dict_with_regions_key() -> None:
    payload = {"regions": [_good_region()]}
    out = TagRegionsResponse.parse_tolerant(payload)
    assert len(out.regions) == 1 and out.regions[0].id == "r1"


def test_parse_tolerant_handles_bare_list_dict() -> None:
    out = TagRegionsResponse.parse_tolerant([_good_region("a"), _good_region("b")])
    assert [r.id for r in out.regions] == ["a", "b"]


def test_parse_tolerant_handles_json_str_with_regions_key() -> None:
    payload = json.dumps({"regions": [_good_region()]})
    out = TagRegionsResponse.parse_tolerant(payload)
    assert len(out.regions) == 1


def test_parse_tolerant_handles_json_str_bare_list() -> None:
    payload = json.dumps([_good_region()])
    out = TagRegionsResponse.parse_tolerant(payload)
    assert len(out.regions) == 1


def test_parse_tolerant_handles_bytes_input() -> None:
    payload = json.dumps({"regions": [_good_region()]}).encode("utf-8")
    out = TagRegionsResponse.parse_tolerant(payload)
    assert len(out.regions) == 1


def test_parse_tolerant_recovers_duplicate_y_bbox() -> None:
    """T22 regression: Gemini's `{x, y, w, y}` malformation must round-trip."""
    # Hand-built JSON with duplicate 'y' key. json.dumps can't produce this,
    # so we string-concatenate.
    raw = (
        '[{"id":"r1","label":"wall","bbox":'
        '{"x":499,"y":361,"w":25,"y":425},'
        '"confidence":0.9}]'
    )
    out = TagRegionsResponse.parse_tolerant(raw)
    assert len(out.regions) == 1
    bbox = out.regions[0].bbox
    assert (bbox.x, bbox.y, bbox.w, bbox.h) == (499, 361, 25, 425)


def test_parse_tolerant_drops_unrecoverable_bbox_but_keeps_response() -> None:
    """A region with `{x, y}` only must be dropped, not abort the whole response."""
    raw = (
        '[{"id":"good","label":"wall","bbox":'
        '{"x":0,"y":0,"w":10,"h":10},"confidence":0.9},'
        '{"id":"bad","label":"vegetation","bbox":'
        '{"x":10,"y":20},"confidence":0.5}]'
    )
    out = TagRegionsResponse.parse_tolerant(raw)
    assert [r.id for r in out.regions] == ["good"]
    dropped = out.__dict__.get("_dropped_region_ids")
    assert dropped == ["bad"]


def test_parse_tolerant_mixed_clean_and_malformed_regions() -> None:
    """Some regions clean, some duplicate-y; both should land in the response."""
    raw = (
        '['
        '{"id":"sky","label":"sky","bbox":'
        '{"x":0,"y":0,"w":1000,"h":284},"confidence":1.0},'
        '{"id":"veg1","label":"vegetation","bbox":'
        '{"x":499,"y":361,"w":25,"y":425},"confidence":0.8}'
        ']'
    )
    out = TagRegionsResponse.parse_tolerant(raw)
    assert [r.id for r in out.regions] == ["sky", "veg1"]
    assert out.regions[1].bbox.h == 425


def test_parse_tolerant_empty_dropped_when_response_is_clean() -> None:
    out = TagRegionsResponse.parse_tolerant([_good_region()])
    assert out.__dict__.get("_dropped_region_ids") == []


def test_parse_tolerant_rejects_invalid_label() -> None:
    """parse_tolerant must still enforce the label vocabulary."""
    raw = json.dumps([{
        "id": "r1", "label": "spaceship",
        "bbox": _GOOD_BBOX, "confidence": 0.9,
    }])
    with pytest.raises(Exception):
        TagRegionsResponse.parse_tolerant(raw)
