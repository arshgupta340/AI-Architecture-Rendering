"""
End-to-end edit driver for the Photoshop-for-Architects spike.

Pipeline (Spike 4, T19):

    screenshot.png  -> render_from_model_view -> render bytes
                                  |
                                  v
                            tag_regions -> TagRegionsResponse
                                  |
                                  v
                   pick region matching --region-label
                                  |
                                  v
                        segment (bbox mode) -> mask bytes
                                  |
                                  v
                          apply_material -> tile bytes
                                  |
                                  v
                          paste_tile (local) -> final composite

Default mode is `--dry-run`: prints the call graph + estimated cost without
invoking anything. `--live` looks up each Modal function via
`modal.Function.lookup("arch-rendering-spike", ...)` and executes the pipeline
locally (the heavy work runs on Modal). Intermediate artifacts are cached on
disk via `spike.cache.get_or_compute` so iterative dev does not re-spend on
unchanged stages.

Example:

    python spike/end_to_end_edit.py --dry-run \\
        --screenshot spike/outputs/spike2/source.png \\
        --region-label wall \\
        --material assets/materials/travertine.jpg
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# Make `spike.*` importable when this script is run as
# `python spike/end_to_end_edit.py` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spike import cache, composite as composite_mod  # noqa: E402
from spike.schemas import Region, TagRegionsResponse  # noqa: E402


# Rough per-call costs in USD. Used only for the printed cost estimate before
# a live run; the real authoritative ledger is `spike/REPORTS/cost_ledger.md`.
# These are upper-bound estimates so a sleepy architect is never surprised.
_COST_ESTIMATE_USD = {
    "render_from_model_view": 0.04,   # Nano Banana Pro image gen
    "tag_regions": 0.02,              # Gemini 3 Pro structured output
    "segment": 0.05,                  # SAM2 on A10G, ~30s cold
    "apply_material": 0.40,           # SD Inpaint on A10G, ~60s incl. cold start
    "paste_tile": 0.0,                # local CPU
}
_COST_TOTAL_ESTIMATE = sum(_COST_ESTIMATE_USD.values())  # ~$0.51


def _short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _pick_region(
    response: TagRegionsResponse, label: str
) -> Region:
    """Pick the highest-confidence region matching `label`.

    Raises a clear error if no region matches — we do not silently fall back
    to a different label because that would let downstream edits hit the
    wrong part of the image without the user noticing.
    """
    if label not in Region.LABELS:
        raise ValueError(
            f"--region-label {label!r} not in allowed vocabulary "
            f"{Region.LABELS!r}"
        )
    matches = [r for r in response.regions if r.label == label]
    if not matches:
        available = sorted({r.label for r in response.regions})
        raise RuntimeError(
            f"No region with label {label!r} in tag_regions response. "
            f"Available labels: {available}"
        )
    # Highest confidence wins; ties broken by region id for determinism.
    matches.sort(key=lambda r: (-r.confidence, r.id))
    return matches[0]


def _print_call_graph(
    screenshot_path: Path,
    region_label: str,
    material_path: Path,
    style_prompt: str,
    output_path: Path,
) -> None:
    print("=" * 72)
    print("end_to_end_edit.py -- DRY RUN (no network, no Modal calls)")
    print("=" * 72)
    print(f"  screenshot:    {screenshot_path}")
    print(f"  region label:  {region_label}")
    print(f"  material:      {material_path}")
    print(f"  style prompt:  {style_prompt!r}")
    print(f"  output:        {output_path}")
    print("")
    print("Pipeline:")
    print("  1. render_from_model_view(screenshot_bytes, style_prompt)")
    print(f"       est ${_COST_ESTIMATE_USD['render_from_model_view']:.2f}")
    print("       -> render_bytes (cached by sha256(screenshot+prompt))")
    print("  2. tag_regions(screenshot_bytes, render_bytes)")
    print(f"       est ${_COST_ESTIMATE_USD['tag_regions']:.2f}")
    print("       -> TagRegionsResponse (cached by sha256(screenshot+render))")
    print(f"  3. pick region with label={region_label!r}, max confidence")
    print("  4. segment(render_bytes, prompt={'type':'bbox', ...})")
    print(f"       est ${_COST_ESTIMATE_USD['segment']:.2f}")
    print("       -> mask_bytes (cached by sha256(render+bbox))")
    print("  5. apply_material(render_bytes, mask_bytes, material_name)")
    print(f"       est ${_COST_ESTIMATE_USD['apply_material']:.2f}")
    print("       -> tile_bytes (cached by sha256(render+mask+material))")
    print("  6. paste_tile(render_bytes, mask_bytes, tile_bytes) [local]")
    print("       -> final composite PNG -> output path")
    print("")
    print(f"ESTIMATED COST PER LIVE RUN: ~${_COST_TOTAL_ESTIMATE:.2f} USD")
    print("Re-run with --live to actually execute. Cached stages cost $0.")
    print("=" * 72)


def _modal_lookup(fn_name: str):
    """Lazy import + lookup of a Modal function by name in our app.

    Importing modal at module top would force every dry-run to require modal
    auth; doing it here keeps the dry-run path zero-dependency.
    """
    import modal

    return modal.Function.from_name("arch-rendering-spike", fn_name)


def _run_render(
    screenshot_bytes: bytes,
    style_prompt: str,
) -> bytes:
    key = f"render_{_short_hash(screenshot_bytes)}_{_short_hash(style_prompt.encode())}"

    def _compute() -> bytes:
        fn = _modal_lookup("render_from_model_view")
        return fn.remote(screenshot_bytes, style_prompt)

    return cache.get_or_compute(key, _compute, scope="render")


def _run_tag_regions(
    screenshot_bytes: bytes,
    render_bytes: bytes,
) -> TagRegionsResponse:
    key = f"tags_{_short_hash(screenshot_bytes)}_{_short_hash(render_bytes)}"

    def _compute() -> bytes:
        fn = _modal_lookup("tag_regions")
        result = fn.remote(screenshot_bytes, render_bytes)
        # Cache as JSON bytes so cache stays bytes-only (see cache.py contract).
        if isinstance(result, TagRegionsResponse):
            return result.model_dump_json().encode("utf-8")
        if isinstance(result, (str, bytes)):
            # Already JSON; validate then re-serialize for canonical form.
            return TagRegionsResponse.model_validate_json(result).model_dump_json().encode("utf-8")
        return TagRegionsResponse.model_validate(result).model_dump_json().encode("utf-8")

    raw = cache.get_or_compute(key, _compute, scope="tags")
    return TagRegionsResponse.model_validate_json(raw)


def _run_segment_bbox(
    render_bytes: bytes,
    region: Region,
) -> bytes:
    bbox = region.bbox
    key = (
        f"mask_{_short_hash(render_bytes)}_"
        f"{bbox.x}_{bbox.y}_{bbox.w}_{bbox.h}"
    )

    def _compute() -> bytes:
        fn = _modal_lookup("segment")
        prompt = {"type": "bbox", "x": bbox.x, "y": bbox.y, "w": bbox.w, "h": bbox.h}
        return fn.remote(render_bytes, prompt=prompt)

    return cache.get_or_compute(key, _compute, scope="mask")


def _run_apply_material(
    render_bytes: bytes,
    mask_bytes: bytes,
    material_name: str,
) -> bytes:
    key = (
        f"tile_{_short_hash(render_bytes)}_"
        f"{_short_hash(mask_bytes)}_{material_name}"
    )

    def _compute() -> bytes:
        fn = _modal_lookup("apply_material")
        return fn.remote(render_bytes, mask_bytes, material_name)

    return cache.get_or_compute(key, _compute, scope="tile")


def _run_live(
    screenshot_path: Path,
    region_label: str,
    material_path: Path,
    style_prompt: str,
    output_path: Path,
) -> None:
    print(f"[end_to_end_edit] LIVE run — estimated cost ~${_COST_TOTAL_ESTIMATE:.2f}")
    print(f"[end_to_end_edit] cache scope: spike/.cache/{{render,tags,mask,tile}}/")
    screenshot_bytes = screenshot_path.read_bytes()
    # We use the material file *name* (stem) as the material prompt token for
    # apply_material — the Modal function takes a material_name string, not a
    # swatch image (SD Inpaint isn't material-conditioned in the spike). The
    # swatch path is preserved so v1 can switch to FLUX Fill + IP-Adapter.
    material_name = material_path.stem.replace("_", " ")

    print("[1/6] render_from_model_view …")
    render_bytes = _run_render(screenshot_bytes, style_prompt)
    print(f"      render: {len(render_bytes):,} bytes")

    print("[2/6] tag_regions …")
    tags = _run_tag_regions(screenshot_bytes, render_bytes)
    print(f"      regions: {len(tags.regions)}")

    print(f"[3/6] pick region label={region_label!r} …")
    region = _pick_region(tags, region_label)
    bbox = region.bbox
    print(
        f"      picked {region.id} ({region.label}) "
        f"bbox=({bbox.x},{bbox.y},{bbox.w},{bbox.h}) "
        f"conf={region.confidence:.2f}"
    )

    print("[4/6] segment (bbox) …")
    mask_bytes = _run_segment_bbox(render_bytes, region)
    print(f"      mask: {len(mask_bytes):,} bytes")

    print(f"[5/6] apply_material name={material_name!r} …")
    tile_bytes = _run_apply_material(render_bytes, mask_bytes, material_name)
    print(f"      tile: {len(tile_bytes):,} bytes")

    print("[6/6] paste_tile (local) …")
    result_bytes = composite_mod.paste_tile(render_bytes, mask_bytes, tile_bytes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result_bytes)
    print(f"[end_to_end_edit] wrote {output_path} ({len(result_bytes):,} bytes)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="End-to-end edit pipeline: screenshot → render → tag → segment → re-texture → composite."
    )
    p.add_argument(
        "--screenshot",
        required=True,
        help="Path to the source 3D-model viewport screenshot (PNG).",
    )
    p.add_argument(
        "--region-label",
        required=True,
        help=f"Which region to re-texture. One of {list(Region.LABELS)}.",
    )
    p.add_argument(
        "--material",
        required=True,
        help=(
            "Path to a material swatch image. The file stem (e.g., "
            "'travertine' from 'travertine.jpg') is used as the material "
            "prompt token for SD Inpaint."
        ),
    )
    p.add_argument(
        "--style-prompt",
        default="modern materials, natural daylight, professional architectural render",
        help="Style prompt passed to render_from_model_view.",
    )
    p.add_argument(
        "--output",
        default=str(_REPO_ROOT / "spike" / "outputs" / "spike4" / "edit_result.png"),
        help="Where to write the final composite PNG.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the call graph + cost estimate; do not invoke anything (default).",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Actually execute the pipeline via modal.Function.lookup.",
    )
    args = p.parse_args(argv)

    if not args.live and not args.dry_run:
        args.dry_run = True

    screenshot_path = Path(args.screenshot)
    material_path = Path(args.material)
    output_path = Path(args.output)

    # Validate label up front so a typo doesn't waste a render + tag call
    # before we discover it.
    if args.region_label not in Region.LABELS:
        raise ValueError(
            f"--region-label {args.region_label!r} not in {list(Region.LABELS)}"
        )

    if args.dry_run:
        # In dry-run we tolerate missing paths so the call graph can be
        # printed before any inputs exist (useful for planning).
        if not screenshot_path.exists():
            print(f"[dry-run] note: --screenshot {screenshot_path} does not exist yet.")
        if not material_path.exists():
            print(f"[dry-run] note: --material {material_path} does not exist yet.")
        _print_call_graph(
            screenshot_path=screenshot_path,
            region_label=args.region_label,
            material_path=material_path,
            style_prompt=args.style_prompt,
            output_path=output_path,
        )
        return 0

    # Live mode: inputs must exist.
    if not screenshot_path.is_file():
        raise FileNotFoundError(f"--screenshot not found: {screenshot_path}")
    if not material_path.is_file():
        raise FileNotFoundError(f"--material not found: {material_path}")

    _run_live(
        screenshot_path=screenshot_path,
        region_label=args.region_label,
        material_path=material_path,
        style_prompt=args.style_prompt,
        output_path=output_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
