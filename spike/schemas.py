from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class BBox(BaseModel):
    """Axis-aligned bounding box in pixel coordinates of the render.

    `x, y` is the top-left corner; `w, h` are width and height.
    """

    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)


class Region(BaseModel):
    """A single labeled region returned by the VLM tagger.

    `parent_id` is set when the region is logically contained within another
    region (e.g., a mullion inside a window). `confidence` is the model's
    self-reported score in [0, 1].
    """

    # Allowed label vocabulary the VLM is constrained to. Anything else
    # should be rejected at parse time so downstream code can trust the value.
    LABELS: ClassVar[tuple[str, ...]] = (
        "wall",
        "floor",
        "ceiling",
        "window",
        "door",
        "mullion",
        "roof",
        "ground",
        "sky",
        "vegetation",
        "furniture",
        "person",
        "vehicle",
    )

    id: str
    label: str
    bbox: BBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    parent_id: str | None = None

    @field_validator("label")
    @classmethod
    def _label_in_vocab(cls, v: str) -> str:
        if v not in cls.LABELS:
            raise ValueError(
                f"label {v!r} not in allowed vocabulary {cls.LABELS!r}"
            )
        return v


class TagRegionsResponse(BaseModel):
    """Top-level response shape for the `tag_regions` Modal function."""

    regions: list[Region]
