from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

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


def _bbox_pairs_hook(pairs: list[tuple[str, Any]]) -> dict:
    """JSON `object_pairs_hook` that repairs Gemini's malformed bbox shape.

    Background: Gemini 3 Pro intermittently returns bboxes as
    `{"x": 499, "y": 361, "w": 25, "y": 425}` — duplicate `y` key, no `h`.
    Standard JSON parsing drops the first key on duplicates, so pydantic
    sees `{x, y, w}` and rejects the region. We preserve the duplicate via
    `object_pairs_hook` and promote the second `y` to `h`.

    The second `y` may actually be `y2` (bottom-right y) rather than `h`
    (height); in that case the recovered bbox is over-tall but the (x, y, w)
    portion is still valid for label coverage. See
    wiki/DECISIONS.md#gemini-bbox-malformed-json.
    """
    keys = [k for k, _ in pairs]
    if keys == ["x", "y", "w", "y"]:
        x, y, w, y2 = (v for _, v in pairs)
        return {"x": x, "y": y, "w": w, "h": y2}
    return dict(pairs)


def save_raw_response(
    out_dir: Path, raw: Any, *, filename: str = "tags_raw.json"
) -> Path:
    """Persist a Gemini response BEFORE pydantic validation.

    Schema validation is best-effort; data loss on schema failure is not
    acceptable when each call costs money. Callers in production paths
    must use this before attempting validation so a malformed response
    can still be inspected and salvaged after the fact.

    Returns the path written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / filename
    if isinstance(raw, bytes):
        raw_path.write_text(raw.decode("utf-8"), encoding="utf-8")
    elif isinstance(raw, str):
        raw_path.write_text(raw, encoding="utf-8")
    else:
        # list / dict / pydantic instance — serialize as JSON with a
        # default=str fallback so anything exotic still lands on disk.
        raw_path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    return raw_path


class TagRegionsResponse(BaseModel):
    """Top-level response shape for the `tag_regions` Modal function."""

    regions: list[Region]

    @classmethod
    def parse_tolerant(cls, raw: Any) -> "TagRegionsResponse":
        """Validate a Gemini tag_regions response, tolerating known bugs.

        Handles:
          - `TagRegionsResponse` instance (returned as-is)
          - `dict` with `regions` key (validated)
          - `list` (wrapped in `{"regions": ...}`)
          - `str`/`bytes` JSON of either of the above
          - Malformed bboxes with duplicate `y` keys (repaired via
            `_bbox_pairs_hook`)
          - Regions whose bbox is too damaged to repair (skipped with the
            list of dropped IDs available via the raised error)
        """
        if isinstance(raw, cls):
            return raw

        # Decode JSON text using the repair hook so duplicate-`y` bboxes
        # arrive as `{x, y, w, h}` rather than `{x, y, w}`.
        if isinstance(raw, (str, bytes)):
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            parsed = json.loads(text, object_pairs_hook=_bbox_pairs_hook)
        else:
            parsed = raw

        # Normalize to a `{"regions": [...]}` shape. Gemini sometimes
        # returns a bare list when response_schema is absent.
        if isinstance(parsed, list):
            payload: dict[str, Any] = {"regions": parsed}
        elif isinstance(parsed, dict) and "regions" in parsed:
            payload = parsed
        else:
            payload = {"regions": [parsed] if isinstance(parsed, dict) else []}

        # Drop regions whose bbox is still missing required fields even
        # after the repair hook. We prefer to lose a few unrecoverable
        # regions over rejecting the entire response.
        regions_in = payload.get("regions", []) or []
        regions_out: list[Any] = []
        dropped: list[str] = []
        for r in regions_in:
            if not isinstance(r, dict):
                regions_out.append(r)
                continue
            bbox = r.get("bbox")
            if isinstance(bbox, dict) and not all(k in bbox for k in ("x", "y", "w", "h")):
                dropped.append(str(r.get("id", "<no-id>")))
                continue
            regions_out.append(r)
        payload = {"regions": regions_out}
        response = cls.model_validate(payload)
        # Stash the list of dropped region IDs on the instance as a
        # private attribute the caller can inspect if it wants to log
        # them. Pydantic v2 ignores unknown attrs on instances by
        # default; setting via __dict__ keeps it out of model_dump.
        response.__dict__["_dropped_region_ids"] = dropped
        return response
