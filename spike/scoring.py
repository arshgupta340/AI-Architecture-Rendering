"""Bake-off scoring helpers — pure CV (no network).

Functions here grade a candidate render against the source model-view screenshot
on three axes:

  * silhouette_iou        — does the render keep the building's overall mass?
  * edge_density_delta    — does the render keep roughly the same amount of
                            edge detail (windows, mullions, panel lines)?
  * count_windows         — stub: would ask Gemini 3 Pro for a structured
                            window count; gated behind GOOGLE_API_KEY and
                            never invoked from this module.

Canny / overlay primitives are imported from `run_b1_baseline.py` so the
parameters stay consistent with the B1 baseline rubric. If that import path
breaks (e.g., the file moves), the local `_canny` fallback kicks in with the
same default thresholds.
"""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PIL import Image

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Canny — reuse run_b1_baseline.extract_edges when importable, else fall back
# ---------------------------------------------------------------------------

try:
    # Same low/high thresholds (60/180) as the B1 baseline rubric.
    from run_b1_baseline import extract_edges as _b1_extract_edges  # type: ignore[import-not-found]
except Exception:
    _b1_extract_edges = None


def _canny(img: Image.Image, low: int = 60, high: int = 180) -> np.ndarray:
    """Return Canny edges as a uint8 ndarray (0 / 255)."""
    if _b1_extract_edges is not None:
        return np.array(_b1_extract_edges(img).convert("L"))
    arr = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.Canny(blurred, low, high)


def _decode(img_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def _match_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Resize b to match a's size if they differ — keeps IoU math honest."""
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    return a, b


# ---------------------------------------------------------------------------
# Silhouette IoU
# ---------------------------------------------------------------------------

def _silhouette_mask(img: Image.Image) -> np.ndarray:
    """Derive a binary foreground mask via Canny + flood-fill from the corners.

    The model-view screenshot is a shaded perspective on a near-uniform
    background (white sky, neutral ground). Flood-filling from each of the four
    image corners on the inverted Canny edges paints the background; whatever
    is left unfilled is the foreground silhouette (the building + anything
    fully enclosed by edges).
    """
    edges = _canny(img)

    # Dilate edges slightly so flood-fill can't squeeze through 1-pixel gaps
    # in the Canny output.
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.dilate(edges, kernel, iterations=1)

    # Build a 1-pixel-border mask required by cv2.floodFill.
    h, w = closed.shape
    flood = closed.copy()
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)

    # Treat edges as walls (255 = stop). Flood-fill the background (0 -> 128)
    # starting from each corner. Corners that already sit on an edge are
    # skipped — the next pixel inward usually isn't.
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        sx, sy = seed
        if flood[sy, sx] == 0:
            cv2.floodFill(flood, ff_mask, (sx, sy), 128)

    # Foreground = anything that's neither an edge (255) nor flooded bg (128).
    fg = (flood == 0).astype(np.uint8)
    return fg


def silhouette_iou(img_a: bytes, img_b: bytes) -> float:
    """Intersection-over-Union of the two derived foreground silhouettes."""
    a_img = _decode(img_a)
    b_img = _decode(img_b)
    a_img, b_img = _match_size(a_img, b_img)

    a_mask = _silhouette_mask(a_img)
    b_mask = _silhouette_mask(b_img)

    inter = np.logical_and(a_mask, b_mask).sum()
    union = np.logical_or(a_mask, b_mask).sum()
    if union == 0:
        return 0.0
    return float(inter) / float(union)


# ---------------------------------------------------------------------------
# Edge density delta
# ---------------------------------------------------------------------------

def edge_density_delta(
    img_a: bytes,
    img_b: bytes,
    region_bbox: tuple[int, int, int, int] | None = None,
) -> float:
    """Ratio of Canny edge pixel counts between b and a.

    Returns `count(canny(b)) / count(canny(a))`. Values near 1.0 mean the
    render kept roughly the same edge density as the source; <<1 means edges
    were smoothed away (style drift); >>1 means edges were invented
    (hallucinated detail).

    If `region_bbox=(x, y, w, h)` is given, both images are cropped to that
    box first — useful for scoring per-facade fidelity without the sky
    contaminating the ratio.
    """
    a_img = _decode(img_a)
    b_img = _decode(img_b)
    a_img, b_img = _match_size(a_img, b_img)

    if region_bbox is not None:
        x, y, w, h = region_bbox
        if w <= 0 or h <= 0:
            raise ValueError(f"region_bbox w/h must be positive, got w={w}, h={h}")
        box = (x, y, x + w, y + h)
        a_img = a_img.crop(box)
        b_img = b_img.crop(box)

    a_edges = _canny(a_img)
    b_edges = _canny(b_img)

    a_count = int((a_edges > 0).sum())
    b_count = int((b_edges > 0).sum())

    if a_count == 0:
        return float("inf") if b_count > 0 else 1.0
    return b_count / a_count


# ---------------------------------------------------------------------------
# Window-count stub — gated behind GOOGLE_API_KEY, never invoked here
# ---------------------------------------------------------------------------

def count_windows(render_bytes: bytes) -> int:
    """Count distinct window openings in a render via Gemini 3 Pro.

    Stub: this is the call site the B3 driver will use, but the actual API
    call is deferred to T14/T17. We env-gate here so a caller that wires this
    in by accident on a key-less machine fails loudly with the same error
    message every other renderer uses.

    Implementation plan (do NOT run from here):
      1. Build `types.Part.from_bytes(data=render_bytes, mime_type="image/png")`.
      2. `client.models.generate_content(model="gemini-3-pro-preview", ...)`
         with `config.response_mime_type="application/json"` and a
         response_schema of `{"window_count": int}`.
      3. Parse `response.parsed.window_count` and return it.

    Returning a sentinel `-1` would silently corrupt the scoring CSV, so we
    raise instead. The driver in T08 should catch this and write 'n/a' to the
    CSV when no key is present.
    """
    if not render_bytes:
        raise ValueError("render_bytes is empty")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY not set")
    raise NotImplementedError(
        "count_windows is a stub — wire this to the tag_regions Modal "
        "function from T14 once it lands. Do not call Gemini directly from "
        "the scoring module; the bake-off driver should batch VLM calls."
    )
