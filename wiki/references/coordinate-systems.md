---
type: reference
updated: 2026-05-19
---

# Coordinate systems

Three coordinate spaces exist in the pipeline. The bug that turned up in T17 was treating them as interchangeable. This page documents which space each component speaks.

## The three spaces

### 1. Input pixel space (native)

The screenshot's actual dimensions, e.g. `1259 × 848`.

Used by:
- The user's UI (clicks).
- SAM2 prompts (it accepts pixel `(x, y)` and bbox `(x, y, w, h)`).
- PIL drawing / composite operations.
- Final output rendering.

### 2. Gemini normalized 0–1000

Gemini 3 Pro returns bboxes with `x, y, w, h` values in `[0, 1000]` regardless of input image dimensions. This is standard VLM behavior — every major VLM normalizes spatial output to a fixed range.

Confirmed by T17: render was `1259 × 848`, but the largest `x + w` was ~1000 and the largest `y + h` was ~1000. Examples:

- `r31 "ground": (x=0, y=709, w=1000, h=291)` — right edge `x=1000`, bottom `y=1000`.
- `r9 "wall": (x=778, w=222)` — right edge `x=1000`.

If you treat these as pixels of a `1259 × 848` image, every bbox is drawn at `1000/1259 ≈ 79%` of its true width and `1000/848 ≈ 118%` of its true height (i.e., bottoms extend past the image).

### 3. SAM2 prompt space

Pixel coordinates of the image being segmented. Same as space (1).

## The conversion

**From Gemini 0–1000 to pixel:**

```python
def rescale_bbox_from_gemini(bbox, image_width, image_height):
    return BBox(
        x=int(bbox.x * image_width / 1000),
        y=int(bbox.y * image_height / 1000),
        w=int(bbox.w * image_width / 1000),
        h=int(bbox.h * image_height / 1000),
    )
```

Apply this **once, at the boundary** where Gemini output enters local code. Don't propagate the 0–1000 space deeper.

## Where the rescale must happen

- **`spike/test_vlm_tagging.py:_draw_regions`** — before drawing bboxes onto the render.
- **`spike/end_to_end_edit.py`** — before passing bbox to SAM2 (`segment(image, {"type":"bbox", ...})`).
- **Any future consumer** of `tag_regions` output — same rule.

## Why we rescale client-side instead of prompting Gemini to emit pixels

See [[DECISIONS#coord-space-consumer]]. Short version: VLMs often ignore "use pixel coordinates" instructions and normalize anyway. Trusting the documented model behavior (0–1000) and rescaling deterministically on the client side is safer than depending on prompt compliance.

## What to verify when adding a new consumer

1. What image dimensions is the consumer operating on? (Get `image.size` from PIL.)
2. Is the bbox in space (1) or space (2)? (If it came directly from `tag_regions`, it's (2).)
3. Apply the rescale exactly once before using.
4. Write a unit test with a known-size fixture image and an off-axis bbox to catch regressions.

## See also

- T17 report `REPORTS/T17.md` Issue A — where this was discovered.
- [[spike-3]] — the spike this affects.
- [[ROADMAP#M1]] — T21 fixes this in the affected code paths.
- [[DECISIONS#coord-space-consumer]] — the architectural decision.
