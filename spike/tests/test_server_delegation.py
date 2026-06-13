"""Consolidation guard: the canvas server's single-view /api/apply_material must
DELEGATE to the shared multiview_apply engine instead of duplicating the mask +
edit + composite logic. These tests pin that the two paths share one source of truth
so they cannot silently drift apart again.

`apps/canvas-prototype/server.py` imports the engine under the bare name
`multiview_apply` (it inserts `spike/` on sys.path), so the canonical engine object
is `server.multiview_apply` — that is what the assertions compare against.

Importing the server module is side-effect-free: `_load_project()` and the HTTP
server only run under `__main__`/`main()`. No network is touched; the one live-path
test stubs `multiview_apply.flux2_edit`.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SERVER_PY = REPO / "apps" / "canvas-prototype" / "server.py"


def _load_server():
    """Import apps/canvas-prototype/server.py by path (it is not on a package path).

    server.py and its sibling ingest.py expect spike/ and their own dir on sys.path
    (the same insertions main() relies on when run as a script)."""
    for p in (REPO / "spike", SERVER_PY.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("canvas_server", SERVER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server():
    return _load_server()


# --------------------------------------------------------------------------- #
# 1. SWATCH_PROMPTS has exactly one definition; the server re-exports the engine's.
# --------------------------------------------------------------------------- #
def test_server_sources_swatch_prompts_from_engine(server):
    assert server.SWATCH_PROMPTS is server.multiview_apply.SWATCH_PROMPTS


def test_swatch_prompts_strings_unchanged(server):
    # The exact material text must survive the move into the engine.
    assert server.SWATCH_PROMPTS == {
        "travertine": "honed travertine stone cladding",
        "red_brick": "red clay brick in running bond courses with mortar joints",
        "charcoal_seam": "charcoal standing-seam metal cladding with vertical seams",
        "white_stucco": "smooth white stucco render",
        "weathered_cedar": "weathered cedar board siding",
    }


# --------------------------------------------------------------------------- #
# helpers to drive apply_material against tiny in-memory project state
# --------------------------------------------------------------------------- #
def _png(color, size=(16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _wire_project(server, tmp_path: Path, monkeypatch):
    """Point the server's module globals at a tiny synthetic single-view project so
    apply_material runs without disk/network. id 1 = wall (top half)."""
    ids = np.zeros((16, 16), np.uint16)
    ids[0:8, :] = 1
    monkeypatch.setattr(server, "_ids", ids, raising=False)
    monkeypatch.setattr(server, "_regions", {"regions": {"1": {"semantic": "wall"}}}, raising=False)
    monkeypatch.setattr(server, "_base_png", _png((140, 95, 70)), raising=False)
    monkeypatch.setattr(server, "_live_calls", 0, raising=False)
    layers = tmp_path / "layers"
    monkeypatch.setattr(server, "LAYERS", layers, raising=False)
    # a swatch file the server can resolve
    sw = tmp_path / "swatches"
    sw.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (150, 60, 45)).save(sw / "red_brick.png")
    monkeypatch.setattr(server, "_swatch_path", lambda name: sw / f"{name}.png", raising=False)
    return layers


def test_apply_material_live_path_goes_through_materialize_view(server, tmp_path, monkeypatch):
    """The single-view live path must call multiview_apply.materialize_view (the shared
    engine), bill exactly one budget unit, and return the documented JSON shape."""
    _wire_project(server, tmp_path, monkeypatch)
    monkeypatch.setenv("FAL_KEY", "test-key")  # unlock the live branch

    seen = {}
    real_materialize = server.multiview_apply.materialize_view

    def spy_materialize(view, **kw):
        seen.update(view_id=view.id, region_ids=kw["region_ids"],
                    target=kw.get("target"), precomputed=kw.get("precomputed"))
        return real_materialize(view, **kw)

    with patch.object(server.multiview_apply, "flux2_edit",
                      side_effect=lambda *a, **k: _png((10, 20, 30))), \
         patch.object(server.multiview_apply, "materialize_view", side_effect=spy_materialize):
        out = server.apply_material({"region_ids": [1], "swatch": "red_brick"})

    # delegated to the shared engine with the server-computed target, live (no precomp)
    assert seen["view_id"] == "canvas"
    assert seen["region_ids"] == [1]
    assert seen["target"] == "wall"
    assert seen["precomputed"] is None
    # exactly one live budget unit consumed
    assert server._live_calls == 1
    # JSON contract unchanged (keys + types the canvas JS reads)
    assert set(out) == {"layer_id", "image_url", "cost_est", "live", "cached"}
    assert out["live"] is True and out["cached"] is False
    assert out["cost_est"] == server.COST_PER_CALL
    assert isinstance(out["layer_id"], str) and out["image_url"].endswith(".png")


def test_apply_material_budget_guard_raises_when_exhausted(server, tmp_path, monkeypatch):
    """The MAX_LIVE_CALLS guard still trips with no live call made when the budget is
    already spent (delegation must not weaken the guard)."""
    _wire_project(server, tmp_path, monkeypatch)
    monkeypatch.setenv("FAL_KEY", "test-key")
    monkeypatch.setattr(server, "_live_calls", server.MAX_LIVE_CALLS, raising=False)

    with patch.object(server.multiview_apply, "flux2_edit",
                      side_effect=AssertionError("no fal call when budget exhausted")):
        with pytest.raises(RuntimeError, match="budget guard"):
            server.apply_material({"region_ids": [1], "swatch": "red_brick"})
    assert server._live_calls == server.MAX_LIVE_CALLS  # unchanged
