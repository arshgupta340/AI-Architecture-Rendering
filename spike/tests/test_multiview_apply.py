"""Mock tests for spike/multiview_apply.py — the "one swatch -> all views" engine.

Every fal call is mocked (`multiview_apply.flux2_edit`), so this never touches the
network. The composites and the A2 neutralization are real PIL/numpy, so the
assertions on layer geometry and call ordering are genuine.

Covers:
  1. lock_strategy branches by material class (raw for smooth, neutral for textured).
  2. apply_to_views runs the anchor first, then locks each other view (call order).
  3. The neutral strategy passes a THIRD reference that is NOT the raw anchor frame
     (i.e. neutralize_wall actually transformed it); the raw strategy passes the
     anchor frame itself.
  4. Cost accounting: 1 anchor + (N-1) locks; on_cost fires once per billable call.
  5. anchor_precomputed skips the anchor fal call (the no-spend path) and the cost
     drops accordingly.
  6. A view with no matching regions is skipped (no fal call, base frame returned).
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from spike import multiview_apply
from spike.multiview_apply import View, apply_to_views, lock_strategy


# --------------------------------------------------------------------------- #
# fixtures — two tiny synthetic views of the "same building"
# --------------------------------------------------------------------------- #
def _png(color, size=(16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _ids_array(h=16, w=16):
    """Instance-id grid: id 1 = wall (top half), id 2 = trim (bottom strip), 0 = bg."""
    ids = np.zeros((h, w), np.uint16)
    ids[0:8, :] = 1       # wall
    ids[8:10, :] = 2      # trim (white-ish, used as the illuminant probe)
    return ids


def _regions():
    return {"1": {"semantic": "wall"}, "2": {"semantic": "trim"}}


@pytest.fixture
def anchor_view():
    return View("hero", _png((150, 90, 60)), _ids_array(), _regions())


@pytest.fixture
def front_view():
    return View("front", _png((140, 95, 70)), _ids_array(), _regions())


@pytest.fixture
def swatch_path(tmp_path: Path) -> Path:
    p = tmp_path / "red_brick.png"
    Image.new("RGB", (32, 32), (150, 60, 45)).save(p)
    return p


# --------------------------------------------------------------------------- #
# 1. strategy branching
# --------------------------------------------------------------------------- #
def test_lock_strategy_branches_by_material():
    assert lock_strategy("travertine") == "raw"
    assert lock_strategy("white_stucco") == "raw"
    assert lock_strategy("red_brick") == "neutral"
    assert lock_strategy("charcoal_seam") == "neutral"
    # unknown material defaults to the safe (neutral) lock
    assert lock_strategy("mystery_material") == "neutral"


# --------------------------------------------------------------------------- #
# 2 + 3 + 4. anchor-first ordering, reference choice, cost
# --------------------------------------------------------------------------- #
def test_apply_to_views_neutral_order_and_reference(anchor_view, front_view, swatch_path):
    calls = []  # (n_refs, third_ref_bytes_or_None)

    def fake_edit(uris, prompt, timeout_s=420):
        calls.append((len(uris), uris[2] if len(uris) > 2 else None))
        # echo a distinct solid frame so composites are real
        return _png((10, 20, 30))

    costs = []
    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        res = apply_to_views(
            anchor=anchor_view, others=[front_view], swatch_name="red_brick",
            swatch_path=swatch_path, material_desc="red clay brick",
            region_semantic="wall", on_cost=lambda c, l: costs.append((c, l)))

    # red_brick -> neutral strategy
    assert res["strategy"] == "neutral"
    # call order: anchor edit first (2 refs), then the lock (3 refs)
    assert [c[0] for c in calls] == [2, 3]
    # the lock's third reference is the NEUTRALIZED wall, which must differ from the
    # raw anchor-edit frame (neutralize_wall transformed it)
    raw_anchor_uri = multiview_apply._uri(res["anchor"]["final_png"])
    third_ref = calls[1][1]
    assert third_ref is not None and third_ref != raw_anchor_uri
    # cost: 1 anchor + 1 lock = 2 * $0.06; two billable calls logged
    assert res["cost"] == pytest.approx(0.12)
    assert len(costs) == 2
    # both views produced a final frame at the base size
    assert Image.open(io.BytesIO(res["anchor"]["final_png"])).size == (16, 16)
    assert res["views"][0]["view_id"] == "front"
    assert Image.open(io.BytesIO(res["views"][0]["final_png"])).size == (16, 16)


def test_apply_to_views_raw_passes_anchor_frame(anchor_view, front_view, swatch_path):
    """Smooth material -> raw lock: the 3rd reference IS the anchor frame (no neutralize)."""
    third_refs = []

    def fake_edit(uris, prompt, timeout_s=420):
        if len(uris) > 2:
            third_refs.append(uris[2])
        return _png((5, 5, 5))

    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        res = apply_to_views(
            anchor=anchor_view, others=[front_view], swatch_name="travertine",
            swatch_path=swatch_path, material_desc="honed travertine",
            region_semantic="wall")

    assert res["strategy"] == "raw"
    # raw lock feeds the materialized anchor frame itself as the reference
    assert third_refs == [multiview_apply._uri(res["anchor"]["final_png"])]


# --------------------------------------------------------------------------- #
# 5. precomputed anchor -> no anchor fal call, lower cost
# --------------------------------------------------------------------------- #
def test_precomputed_anchor_skips_anchor_call(anchor_view, front_view, swatch_path):
    n_calls = 0

    def fake_edit(uris, prompt, timeout_s=420):
        nonlocal n_calls
        n_calls += 1
        # precomputed anchor path must only ever issue the (N-1) lock calls (3 refs)
        assert len(uris) == 3
        return _png((0, 0, 0))

    precomp = _png((222, 200, 170))
    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        res = apply_to_views(
            anchor=anchor_view, others=[front_view], swatch_name="travertine",
            swatch_path=swatch_path, material_desc="honed travertine",
            region_semantic="wall", anchor_precomputed=precomp)

    assert n_calls == 1                       # only the single lock call
    assert res["anchor"]["cost"] == 0.0       # anchor was free
    assert res["cost"] == pytest.approx(0.06)


# --------------------------------------------------------------------------- #
# 6. view with no matching regions is skipped
# --------------------------------------------------------------------------- #
def test_view_without_semantic_is_skipped(anchor_view, swatch_path):
    # a third view that has NO wall regions (only trim)
    no_wall = View("side", _png((100, 100, 100)),
                   np.full((16, 16), 2, np.uint16), {"2": {"semantic": "trim"}})

    def fake_edit(uris, prompt, timeout_s=420):
        return _png((1, 2, 3))

    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        res = apply_to_views(
            anchor=anchor_view, others=[no_wall], swatch_name="red_brick",
            swatch_path=swatch_path, material_desc="red clay brick",
            region_semantic="wall")

    side = next(v for v in res["views"] if v["view_id"] == "side")
    assert side["skipped"] is True
    assert side["region_ids"] == []
    # only the anchor edit was billed (the skipped view costs nothing)
    assert res["cost"] == pytest.approx(0.06)


def test_neutralize_wall_changes_pixels_and_keeps_size(anchor_view):
    """neutralize_wall returns a different, still-decodable PNG (white-balance +
    luminance flatten actually ran)."""
    edit = _png((150, 90, 60))
    out = multiview_apply.neutralize_wall(edit, anchor_view.ids, [1], illuminant=None)
    assert out != edit
    img = Image.open(io.BytesIO(out))
    assert img.mode == "RGB" and img.size[0] > 0
