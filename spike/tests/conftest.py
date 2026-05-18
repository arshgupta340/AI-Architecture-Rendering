"""Shared pytest fixtures for the spike test suite."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image


def _make_tiny_png(color: tuple[int, int, int] = (200, 100, 50)) -> bytes:
    """8x8 solid-color PNG generated in-memory via PIL."""
    img = Image.new("RGB", (8, 8), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def tiny_png_bytes() -> bytes:
    """Raw bytes of an 8x8 solid-color PNG."""
    return _make_tiny_png()


@pytest.fixture
def tiny_png(tmp_path: Path, tiny_png_bytes: bytes) -> Path:
    """An 8x8 solid-color PNG written to a tmp_path-scoped file."""
    p = tmp_path / "screenshot.png"
    p.write_bytes(tiny_png_bytes)
    return p


@pytest.fixture
def another_tiny_png(tmp_path: Path) -> bytes:
    """A second tiny PNG with a different color — used as the fake render output."""
    return _make_tiny_png(color=(20, 220, 80))
