"""
Alpha-aware compositing helpers for the end-to-end edit pipeline.

The Modal app already has a `composite()` function (see
`spike/modal_app.py:composite`) that pastes a re-textured tile back over
the base render using a binary segmentation mask. This module exposes the
same idea as a pure-local function with a cleaner signature suitable for
the T19 driver:

    paste_tile(base, mask, tile) -> bytes

`base` and `tile` are RGB(A) PNG bytes; `mask` is a grayscale PNG (white =
keep the tile, black = keep the base; soft-edge masks blend smoothly).
"""

from __future__ import annotations

import io


def paste_tile(base: bytes, mask: bytes, tile: bytes) -> bytes:
    """
    Composite `tile` onto `base` using `mask` as the alpha source.

    All three inputs are PNG-encoded bytes. The output is PNG-encoded bytes
    of an RGB image (we drop the alpha channel on save so downstream tools
    that don't expect alpha don't get surprised).

    `tile` and `mask` are resized to `base.size` before compositing. This
    matches the existing `modal_app.composite()` behavior — SD-Inpainting
    produces a 512x512 tile while the base render is typically larger, and
    we want the result at the base resolution.
    """
    from PIL import Image

    base_img = Image.open(io.BytesIO(base)).convert("RGBA")
    tile_img = Image.open(io.BytesIO(tile)).convert("RGBA").resize(base_img.size)
    mask_img = Image.open(io.BytesIO(mask)).convert("L").resize(base_img.size)

    # Image.composite picks per-pixel: where mask==255 use tile, where mask==0
    # use base, intermediate values blend linearly. That gives us free soft
    # edges if SAM2 returns a non-binary mask.
    result = Image.composite(tile_img, base_img, mask_img)

    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
