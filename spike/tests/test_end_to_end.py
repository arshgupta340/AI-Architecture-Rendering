"""End-to-end pipeline mock test for `spike/end_to_end_edit.py` (T20).

The driver under test orchestrates four Modal functions plus a local
composite step:

    render_from_model_view -> tag_regions -> segment -> apply_material
                                                      -> paste_tile (local)

Each Modal function is reached via `modal.Function.from_name("arch-rendering-spike",
<fn_name>)`. We mock that lookup so every "remote" call is in fact a
predictable in-process stub. The composite step uses a real PIL call against
mock bytes, so the assertion that the final output is non-empty PNG bytes is
genuine, not stubbed.

Assertions cover:

1. The five pipeline stages run in the documented order.
2. Each stage is invoked exactly once with the inputs we expect.
3. `_pick_region` selects the right region by label + confidence
   (deterministic tie-break on id).
4. The final composite is non-empty bytes and parses as PNG.

The disk cache (`spike.cache.get_or_compute`) is redirected to a `tmp_path`
scoped directory via monkeypatching `_CACHE_ROOT`, so the test never touches
the real `spike/.cache/` and never sees stale entries from prior runs.
"""

from __future__ import annotations

import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from spike import end_to_end_edit
from spike.schemas import BBox, Region, TagRegionsResponse


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


# Render size is 1000x1000 so that normalized 0-1000 bbox coords map 1:1 to
# pixel coords through end_to_end_edit._bbox_norm_to_pixels. This keeps the
# fixture values readable and lets the segment() mock assert on the same
# (x, y, w, h) numbers the fixture declares.
_RENDER_SIZE = (1000, 1000)


def _solid_png(color: tuple[int, int, int], size: tuple[int, int] = _RENDER_SIZE) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mask_png(size: tuple[int, int] = _RENDER_SIZE) -> bytes:
    """Grayscale mask with a white rectangle in the center."""
    img = Image.new("L", size, color=0)
    w, h = size
    # Paint a white square in the middle -> the tile shows through there.
    x0, y0 = w // 4, h // 4
    x1, y1 = 3 * w // 4, 3 * h // 4
    for x in range(x0, x1):
        for y in range(y0, y1):
            img.putpixel((x, y), 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fake_render_bytes() -> bytes:
    return _solid_png((180, 60, 60))


@pytest.fixture
def fake_mask_bytes() -> bytes:
    return _mask_png()


@pytest.fixture
def fake_tile_bytes() -> bytes:
    return _solid_png((40, 200, 90))


@pytest.fixture
def fake_tag_response() -> TagRegionsResponse:
    """Two walls (so confidence tie-break matters), one window, one floor."""
    return TagRegionsResponse(
        regions=[
            Region(id="r1", label="wall", bbox=BBox(x=0, y=0, w=10, h=10), confidence=0.6),
            # Highest-confidence wall, this is the one _pick_region should choose.
            Region(id="r2", label="wall", bbox=BBox(x=20, y=5, w=15, h=20), confidence=0.92),
            Region(id="r3", label="window", bbox=BBox(x=40, y=40, w=8, h=8), confidence=0.85),
            Region(id="r4", label="floor", bbox=BBox(x=0, y=50, w=64, h=14), confidence=0.7),
        ]
    )


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect the disk cache to a tmp dir so the test is hermetic."""
    cache_root = tmp_path / "cache"
    monkeypatch.setattr("spike.cache._CACHE_ROOT", cache_root)
    return cache_root


@pytest.fixture
def screenshot_file(tmp_path) -> Path:
    p = tmp_path / "screenshot.png"
    p.write_bytes(_solid_png((220, 220, 220)))
    return p


@pytest.fixture
def material_file(tmp_path) -> Path:
    p = tmp_path / "travertine_tile.jpg"
    # Contents irrelevant; the driver only uses the file stem as material name.
    p.write_bytes(b"not-really-a-jpg")
    return p


# --------------------------------------------------------------------------- #
# Pure-function: _pick_region                                                 #
# --------------------------------------------------------------------------- #


def test_pick_region_chooses_highest_confidence(fake_tag_response):
    """When two regions share a label, the higher-confidence one wins."""
    picked = end_to_end_edit._pick_region(fake_tag_response, "wall")
    assert picked.id == "r2"
    assert picked.confidence == pytest.approx(0.92)


def test_pick_region_tie_break_by_id():
    """Equal confidence -> id sort order decides (deterministic)."""
    resp = TagRegionsResponse(
        regions=[
            Region(id="r9", label="wall", bbox=BBox(x=0, y=0, w=1, h=1), confidence=0.8),
            Region(id="r1", label="wall", bbox=BBox(x=0, y=0, w=1, h=1), confidence=0.8),
            Region(id="r5", label="wall", bbox=BBox(x=0, y=0, w=1, h=1), confidence=0.8),
        ]
    )
    picked = end_to_end_edit._pick_region(resp, "wall")
    assert picked.id == "r1"


def test_pick_region_missing_label_raises(fake_tag_response):
    with pytest.raises(RuntimeError, match="No region with label"):
        end_to_end_edit._pick_region(fake_tag_response, "vehicle")


def test_pick_region_unknown_vocab_raises(fake_tag_response):
    with pytest.raises(ValueError, match="not in allowed vocabulary"):
        end_to_end_edit._pick_region(fake_tag_response, "spaceship")


# --------------------------------------------------------------------------- #
# Full pipeline (all Modal calls mocked)                                      #
# --------------------------------------------------------------------------- #


def test_end_to_end_pipeline_mocked(
    isolated_cache,
    screenshot_file,
    material_file,
    fake_render_bytes,
    fake_mask_bytes,
    fake_tile_bytes,
    fake_tag_response,
    tmp_path,
):
    """The whole pipeline runs end-to-end against mock Modal functions.

    Asserts (in roughly the order they fire):
      - render_from_model_view called first, with screenshot bytes + style prompt
      - tag_regions called second, with screenshot + the render output
      - _pick_region picked the highest-confidence wall (r2)
      - segment called with bbox dict matching r2's bbox
      - apply_material called with render bytes, mask bytes, and material name
        derived from the file stem
      - paste_tile produced non-empty PNG bytes that parse as a real image
      - call order recorded across all four stubs is exactly: render, tag,
        segment, apply_material
    """
    call_log: list[str] = []

    # --- per-function stubs ------------------------------------------------

    def render_remote(*args, **kwargs):
        call_log.append("render_from_model_view")
        # The driver passes positional args: (screenshot_bytes, style_prompt)
        assert args[0] == screenshot_file.read_bytes()
        assert isinstance(args[1], str) and len(args[1]) > 0
        return fake_render_bytes

    def tag_remote(*args, **kwargs):
        call_log.append("tag_regions")
        # Positional: (screenshot_bytes, render_bytes)
        assert args[0] == screenshot_file.read_bytes()
        assert args[1] == fake_render_bytes
        return fake_tag_response

    def segment_remote(*args, **kwargs):
        call_log.append("segment")
        # Driver: fn.remote(render_bytes, prompt={...})
        assert args[0] == fake_render_bytes
        prompt = kwargs["prompt"]
        # Expect the bbox of the highest-confidence wall (r2).
        assert prompt == {"type": "bbox", "x": 20, "y": 5, "w": 15, "h": 20}
        return fake_mask_bytes

    def apply_material_remote(*args, **kwargs):
        call_log.append("apply_material")
        # Driver: fn.remote(render_bytes, mask_bytes, material_name)
        assert args[0] == fake_render_bytes
        assert args[1] == fake_mask_bytes
        # Material name derived from the file stem with underscores -> spaces.
        assert args[2] == "travertine tile"
        return fake_tile_bytes

    fake_fns = {
        "render_from_model_view": MagicMock(remote=MagicMock(side_effect=render_remote)),
        "tag_regions": MagicMock(remote=MagicMock(side_effect=tag_remote)),
        "segment": MagicMock(remote=MagicMock(side_effect=segment_remote)),
        "apply_material": MagicMock(remote=MagicMock(side_effect=apply_material_remote)),
    }

    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()

    def lookup(app_name, fn_name):
        assert app_name == "arch-rendering-spike"
        assert fn_name in fake_fns, f"unexpected Modal lookup: {fn_name}"
        return fake_fns[fn_name]

    fake_modal.Function.from_name = MagicMock(side_effect=lookup)

    output_path = tmp_path / "out" / "edit_result.png"

    # --- run -------------------------------------------------------------------

    with patch.dict(sys.modules, {"modal": fake_modal}):
        exit_code = end_to_end_edit.main(
            [
                "--live",
                "--screenshot", str(screenshot_file),
                "--region-label", "wall",
                "--material", str(material_file),
                "--style-prompt", "warm afternoon studio render",
                "--output", str(output_path),
            ]
        )

    assert exit_code == 0

    # --- ordering --------------------------------------------------------------
    # Each Modal function is called exactly once.
    assert call_log == [
        "render_from_model_view",
        "tag_regions",
        "segment",
        "apply_material",
    ]
    for name, fn in fake_fns.items():
        assert fn.remote.call_count == 1, f"{name} called {fn.remote.call_count}x"

    # --- output ----------------------------------------------------------------
    assert output_path.exists(), "driver did not write the composite output"
    result_bytes = output_path.read_bytes()
    assert isinstance(result_bytes, bytes)
    assert len(result_bytes) > 0, "composite output was empty"
    # Validate it actually decodes as a PNG with the expected base size.
    out_img = Image.open(io.BytesIO(result_bytes))
    out_img.load()
    assert out_img.format == "PNG"
    assert out_img.size == _RENDER_SIZE  # matches fake_render_bytes


def test_end_to_end_picks_window_not_wall(
    isolated_cache,
    screenshot_file,
    material_file,
    fake_render_bytes,
    fake_mask_bytes,
    fake_tile_bytes,
    fake_tag_response,
    tmp_path,
):
    """Changing --region-label routes segment() to a different bbox."""
    seen_bboxes: list[dict] = []

    def render_remote(*a, **kw):
        return fake_render_bytes

    def tag_remote(*a, **kw):
        return fake_tag_response

    def segment_remote(*args, **kwargs):
        seen_bboxes.append(kwargs["prompt"])
        return fake_mask_bytes

    def apply_material_remote(*a, **kw):
        return fake_tile_bytes

    fake_fns = {
        "render_from_model_view": MagicMock(remote=MagicMock(side_effect=render_remote)),
        "tag_regions": MagicMock(remote=MagicMock(side_effect=tag_remote)),
        "segment": MagicMock(remote=MagicMock(side_effect=segment_remote)),
        "apply_material": MagicMock(remote=MagicMock(side_effect=apply_material_remote)),
    }

    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(side_effect=lambda app, fn: fake_fns[fn])

    output_path = tmp_path / "out" / "window_edit.png"

    with patch.dict(sys.modules, {"modal": fake_modal}):
        rc = end_to_end_edit.main(
            [
                "--live",
                "--screenshot", str(screenshot_file),
                "--region-label", "window",
                "--material", str(material_file),
                "--output", str(output_path),
            ]
        )

    assert rc == 0
    # The window region (r3) has bbox (40,40,8,8).
    assert seen_bboxes == [{"type": "bbox", "x": 40, "y": 40, "w": 8, "h": 8}]
    assert output_path.exists()


def test_end_to_end_dry_run_makes_no_modal_calls(
    screenshot_file, material_file, capsys
):
    """Default --dry-run path must not import or call modal at all."""
    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(
        side_effect=AssertionError("dry-run must not call modal.Function.from_name")
    )

    with patch.dict(sys.modules, {"modal": fake_modal}):
        rc = end_to_end_edit.main(
            [
                "--dry-run",
                "--screenshot", str(screenshot_file),
                "--region-label", "wall",
                "--material", str(material_file),
            ]
        )

    assert rc == 0
    fake_modal.Function.from_name.assert_not_called()
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "ESTIMATED COST PER LIVE RUN" in out


def test_end_to_end_unknown_label_short_circuits(
    screenshot_file, material_file
):
    """--region-label outside the allowed vocab fails before any Modal call."""
    fake_modal = types.ModuleType("modal")
    fake_modal.Function = MagicMock()
    fake_modal.Function.from_name = MagicMock(
        side_effect=AssertionError("must not call modal on a bad label")
    )

    with patch.dict(sys.modules, {"modal": fake_modal}):
        with pytest.raises(ValueError, match="not in"):
            end_to_end_edit.main(
                [
                    "--live",
                    "--screenshot", str(screenshot_file),
                    "--region-label", "spaceship",
                    "--material", str(material_file),
                ]
            )

    fake_modal.Function.from_name.assert_not_called()
