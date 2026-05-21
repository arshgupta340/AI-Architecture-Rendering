"""
Local driver for the `tag_regions` Modal function.

Default mode (`--dry-run`): loads a fixture `TagRegionsResponse` from
`spike/tests/fixtures/tag_regions_response.json` so this script can run
offline. Use this to iterate on the visualization without spending API budget.

Live mode (`--live`): looks up the deployed `tag_regions` Modal function
(`modal.Function.lookup("arch-rendering-spike", "tag_regions")`) and calls
`.remote(screenshot_bytes, render_bytes)`. This is local execution that
fans out to Modal — we do NOT deploy here.

In either mode, the script draws labeled bounding boxes on the render with
PIL and saves the result to `spike/outputs/spike3/tagged_<basename>.png`.

Examples:
    # offline, uses fixture
    python spike/test_vlm_tagging.py --input spike/outputs/spike2/render.png

    # live, hits Gemini 3 Pro via Modal
    python spike/test_vlm_tagging.py --live \\
        --input spike/outputs/spike2/render.png \\
        --screenshot spike/outputs/spike2/source.png
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Make `spike.schemas` importable when this script is run as
# `python spike/test_vlm_tagging.py` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spike.schemas import TagRegionsResponse  # noqa: E402


# Deterministic-ish color per label so eyeballing is easy.
_LABEL_COLORS: dict[str, tuple[int, int, int]] = {
    "wall": (255, 99, 71),
    "floor": (210, 180, 140),
    "ceiling": (176, 196, 222),
    "window": (30, 144, 255),
    "door": (255, 165, 0),
    "mullion": (138, 43, 226),
    "roof": (139, 69, 19),
    "ground": (160, 82, 45),
    "sky": (135, 206, 235),
    "vegetation": (60, 179, 113),
    "furniture": (218, 112, 214),
    "person": (255, 20, 147),
    "vehicle": (70, 130, 180),
}


def _load_fixture(path: Path) -> TagRegionsResponse:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TagRegionsResponse.model_validate(raw)


def _call_live(screenshot_bytes: bytes, render_bytes: bytes) -> TagRegionsResponse:
    # Import inside the function so module import works without modal auth.
    import modal

    fn = modal.Function.from_name("arch-rendering-spike", "tag_regions")
    result = fn.remote(screenshot_bytes, render_bytes)
    # Modal returns whatever the function returns. If it's already a
    # TagRegionsResponse we use it; otherwise validate from dict/json.
    import json as _json

    if isinstance(result, TagRegionsResponse):
        return result
    if isinstance(result, (str, bytes)):
        raw = _json.loads(result)
        # Gemini may return a bare list instead of {"regions": [...]}
        if isinstance(raw, list):
            raw = {"regions": raw}
        return TagRegionsResponse.model_validate(raw)
    if isinstance(result, list):
        return TagRegionsResponse.model_validate({"regions": result})
    return TagRegionsResponse.model_validate(result)


_NORMALIZED_MAX = 1000


def _scale_bbox_to_pixels(
    bbox_x: int, bbox_y: int, bbox_w: int, bbox_h: int,
    img_w: int, img_h: int,
) -> tuple[int, int, int, int]:
    """Convert a Gemini 0-1000 normalized bbox to pixel coords for img_w x img_h.

    Gemini 3 Pro returns spatial bboxes in normalized 0-1000 space regardless
    of the input image dimensions. The render is the authoritative coordinate
    space for downstream consumers (SAM2, inpainting), so we scale here.
    """
    sx = img_w / _NORMALIZED_MAX
    sy = img_h / _NORMALIZED_MAX
    px = int(round(bbox_x * sx))
    py = int(round(bbox_y * sy))
    pw = int(round(bbox_w * sx))
    ph = int(round(bbox_h * sy))
    return px, py, pw, ph


def _draw_regions(
    render_bytes: bytes, response: TagRegionsResponse
) -> bytes:
    img = Image.open(io.BytesIO(render_bytes)).convert("RGBA")
    img_w, img_h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    for region in response.regions:
        color = _LABEL_COLORS.get(region.label, (255, 255, 255))
        x, y, w, h = _scale_bbox_to_pixels(
            region.bbox.x, region.bbox.y, region.bbox.w, region.bbox.h,
            img_w, img_h,
        )
        # Translucent fill + opaque outline so dense regions stay readable.
        draw.rectangle(
            [x, y, x + w, y + h],
            outline=color + (255,),
            fill=color + (40,),
            width=2,
        )
        label_text = f"{region.id}:{region.label} {region.confidence:.2f}"
        # Text background for legibility.
        tx, ty = x + 4, max(0, y + 4)
        try:
            bbox_text = draw.textbbox((tx, ty), label_text, font=font)
        except AttributeError:
            # very old PIL fallback
            tw, th = draw.textsize(label_text, font=font)
            bbox_text = (tx, ty, tx + tw, ty + th)
        draw.rectangle(bbox_text, fill=(0, 0, 0, 180))
        draw.text((tx, ty), label_text, fill=(255, 255, 255, 255), font=font)

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    composed.save(buf, format="PNG")
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Visualize tag_regions output on a render.")
    p.add_argument(
        "--input",
        required=True,
        help="Path to the render PNG to annotate (and send to Gemini in --live).",
    )
    p.add_argument(
        "--screenshot",
        default=None,
        help=(
            "Path to the source 3D-model screenshot PNG. Required in --live mode; "
            "ignored in --dry-run."
        ),
    )
    p.add_argument(
        "--fixture",
        default=str(_REPO_ROOT / "spike" / "tests" / "fixtures" / "tag_regions_response.json"),
        help="Fixture JSON used when --dry-run (default: tests/fixtures/tag_regions_response.json).",
    )
    p.add_argument(
        "--output-dir",
        default=str(_REPO_ROOT / "spike" / "outputs" / "spike3"),
        help="Directory to write the annotated render into.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Load regions from the fixture instead of calling Modal/Gemini (default).",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Call the deployed `tag_regions` Modal function (hits Gemini 3 Pro).",
    )
    args = p.parse_args(argv)

    # Default to dry-run when neither flag is set.
    if not args.live and not args.dry_run:
        args.dry_run = True

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"--input render not found: {input_path}")
    render_bytes = input_path.read_bytes()

    if args.live:
        if args.screenshot is None:
            raise RuntimeError(
                "--screenshot is required in --live mode (the source 3D-model viewport)."
            )
        screenshot_path = Path(args.screenshot)
        if not screenshot_path.is_file():
            raise FileNotFoundError(f"--screenshot not found: {screenshot_path}")
        screenshot_bytes = screenshot_path.read_bytes()
        print(
            f"[test_vlm_tagging] LIVE: tag_regions("
            f"{screenshot_path.name}, {input_path.name})"
        )
        response = _call_live(screenshot_bytes, render_bytes)
    else:
        fixture_path = Path(args.fixture)
        if not fixture_path.is_file():
            raise FileNotFoundError(f"--fixture not found: {fixture_path}")
        print(f"[test_vlm_tagging] DRY-RUN: loading fixture {fixture_path}")
        response = _load_fixture(fixture_path)

    print(f"[test_vlm_tagging] {len(response.regions)} regions:")
    for r in response.regions:
        parent = f" parent={r.parent_id}" if r.parent_id else ""
        print(
            f"    {r.id}: {r.label:<10} bbox=({r.bbox.x},{r.bbox.y},"
            f"{r.bbox.w},{r.bbox.h}) conf={r.confidence:.2f}{parent}"
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tagged_{input_path.stem}.png"
    out_path.write_bytes(_draw_regions(render_bytes, response))
    print(f"[test_vlm_tagging] wrote {out_path}")

    if args.live:
        import json as _json
        json_path = out_dir / f"tagged_{input_path.stem}.json"
        json_path.write_text(
            _json.dumps(response.model_dump(), indent=2), encoding="utf-8"
        )
        print(f"[test_vlm_tagging] wrote {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
