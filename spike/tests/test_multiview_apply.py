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
            region_semantic="wall", generative=True,
            on_cost=lambda c, l: costs.append((c, l)))

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
            region_semantic="wall", generative=True)

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
            region_semantic="wall", anchor_precomputed=precomp, generative=True)

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
            region_semantic="wall", generative=True)

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


# --------------------------------------------------------------------------- #
# materialize_view — the single-view stage shared by both server paths
# --------------------------------------------------------------------------- #
def test_materialize_view_live_bills_once_and_composites(anchor_view, swatch_path):
    """Live materialize: one flux2_edit ([base, swatch] = 2 refs), one on_cost at
    COST_EDIT, a composited frame at base size, and the mask is returned for reuse."""
    calls = []
    costs = []

    def fake_edit(uris, prompt, timeout_s=420):
        calls.append(len(uris))
        return _png((10, 20, 30))

    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        mat = multiview_apply.materialize_view(
            anchor_view, swatch_name="red_brick", swatch_path=swatch_path,
            material_desc="red clay brick", region_ids=[1], generative=True,
            on_cost=lambda c, l: costs.append((c, l)))

    assert calls == [2]                                   # base + swatch, no lock ref
    assert costs and costs[0][0] == multiview_apply.COST_EDIT
    assert mat["cost"] == multiview_apply.COST_EDIT
    assert mat["region_ids"] == [1]
    assert Image.open(io.BytesIO(mat["final_png"])).size == (16, 16)
    # mask_png is the SAME bytes mask_png_from_ids would build for these ids
    assert mat["mask_png"] == multiview_apply.mask_png_from_ids(anchor_view.ids, [1])


def test_materialize_view_precomputed_is_free_and_makes_no_call(anchor_view, swatch_path):
    """Precomputed (no-spend) materialize: zero flux2_edit calls, zero cost, no
    on_cost firing, and the precomputed bytes are what get composited."""
    n_calls = 0

    def fake_edit(uris, prompt, timeout_s=420):
        nonlocal n_calls
        n_calls += 1
        return _png((0, 0, 0))

    costs = []
    precomp = _png((222, 200, 170))
    with patch.object(multiview_apply, "flux2_edit", side_effect=fake_edit):
        mat = multiview_apply.materialize_view(
            anchor_view, swatch_name="travertine", swatch_path=swatch_path,
            material_desc="honed travertine", region_ids=[1], precomputed=precomp,
            on_cost=lambda c, l: costs.append((c, l)))

    assert n_calls == 0
    assert costs == []
    assert mat["cost"] == 0.0
    assert mat["edit_png"] == precomp


def test_apply_to_views_anchor_uses_materialize_view(anchor_view, front_view, swatch_path):
    """The multi-view anchor stage is materialize_view: patching materialize_view to a
    sentinel proves apply_to_views routes its anchor through that one shared function."""
    sentinel_final = _png((7, 7, 7))
    seen = {}

    def fake_materialize(view, **kw):
        seen.update(view_id=view.id, region_ids=kw["region_ids"],
                    precomputed=kw.get("precomputed"))
        return {"final_png": sentinel_final, "edit_png": sentinel_final,
                "mask_png": multiview_apply.mask_png_from_ids(view.ids, kw["region_ids"]),
                "region_ids": kw["region_ids"], "cost": 0.0}

    # lock calls (the OTHER views) still go through flux2_edit; only the anchor is
    # materialize_view, so stub flux2_edit too to stay offline.
    with patch.object(multiview_apply, "materialize_view", side_effect=fake_materialize), \
         patch.object(multiview_apply, "flux2_edit", side_effect=lambda *a, **k: _png((1, 1, 1))):
        res = multiview_apply.apply_to_views(
            anchor=anchor_view, others=[front_view], swatch_name="travertine",
            swatch_path=swatch_path, material_desc="honed travertine",
            region_semantic="wall", generative=True)

    assert seen["view_id"] == "hero"          # the anchor view was materialized
    assert seen["region_ids"] == [1]          # the wall ids
    assert res["anchor"]["final_png"] == sentinel_final


# --------------------------------------------------------------------------- #
# proxy (default) — deterministic projection: instant, $0, no model call
# --------------------------------------------------------------------------- #
def test_project_material_recolours_region_only(anchor_view, swatch_path):
    """project_material returns a full-frame PNG at base size whose region pixels take
    the swatch colour (a red-brick swatch over the wall -> reddish wall)."""
    out = multiview_apply.project_material(
        anchor_view.base_png, anchor_view.ids, [1], swatch_path)
    img = Image.open(io.BytesIO(out)).convert("RGB")
    assert img.size == (16, 16)
    wall = np.asarray(img)[0:8].reshape(-1, 3).mean(0)   # top half = wall
    assert wall[0] > wall[2] + 20                         # R clearly > B (brick swatch)


def test_materialize_view_proxy_default_is_free_and_makes_no_call(anchor_view, swatch_path):
    """Default (generative=False) materialize: zero flux2_edit calls, zero cost, a
    composited frame at base size, and the shared mask returned."""
    with patch.object(multiview_apply, "flux2_edit",
                      side_effect=AssertionError("proxy must not call flux2_edit")):
        mat = multiview_apply.materialize_view(
            anchor_view, swatch_name="white_stucco", swatch_path=swatch_path,
            material_desc="white stucco", region_ids=[1])
    assert mat["cost"] == 0.0
    assert mat["region_ids"] == [1]
    assert Image.open(io.BytesIO(mat["final_png"])).size == (16, 16)
    assert mat["mask_png"] == multiview_apply.mask_png_from_ids(anchor_view.ids, [1])


def test_apply_to_views_proxy_default_all_views_free(anchor_view, front_view, swatch_path):
    """Default apply_to_views projects every view deterministically: strategy 'proxy',
    no flux2_edit calls, zero cost, both views composited (consistency is automatic)."""
    with patch.object(multiview_apply, "flux2_edit",
                      side_effect=AssertionError("proxy must not call flux2_edit")):
        res = apply_to_views(
            anchor=anchor_view, others=[front_view], swatch_name="red_brick",
            swatch_path=swatch_path, material_desc="red clay brick",
            region_semantic="wall")
    assert res["strategy"] == "proxy"
    assert res["cost"] == 0.0 and res["anchor"]["cost"] == 0.0
    assert res["views"][0]["view_id"] == "front" and res["views"][0]["cost"] == 0.0
    assert Image.open(io.BytesIO(res["views"][0]["final_png"])).size == (16, 16)
