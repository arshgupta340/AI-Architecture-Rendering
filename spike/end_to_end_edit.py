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
import os
import sys
import time
from pathlib import Path

# Make `spike.*` importable when this script is run as
# `python spike/end_to_end_edit.py` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spike import cache, composite as composite_mod  # noqa: E402
from spike.schemas import Region, TagRegionsResponse, save_raw_response  # noqa: E402

# Load spike/.env so renderer/inpainter env vars (REPLICATE_API_TOKEN,
# GOOGLE_API_KEY, etc.) are picked up without the user sourcing first.
# Shell env wins over .env values, matching compare_renderers.py's behavior.
try:
    from dotenv import load_dotenv as _load_dotenv  # noqa: E402

    _load_dotenv(_REPO_ROOT / "spike" / ".env")
except ImportError:
    # python-dotenv not installed — fine in test envs that set env directly.
    pass


# Rough per-call costs in USD. Used only for the printed cost estimate before
# a live run; the real authoritative ledger is `spike/REPORTS/cost_ledger.md`.
# These are upper-bound estimates so a sleepy architect is never surprised.
# Per-inpainter cost — apply_material is the one stage with a choice. The
# rest are the same regardless of inpainter.
_INPAINTER_COSTS_USD = {
    "sd_inpaint": 0.40,         # Stable Diffusion 1.5 Inpainting on Modal A10G, ~60s incl. cold start
    "flux_fill_replicate": 0.05,  # black-forest-labs/flux-fill-pro via Replicate
}
_COST_ESTIMATE_USD = {
    "render_from_model_view": 0.04,   # Nano Banana Pro image gen
    "tag_regions": 0.02,              # Gemini 3 Pro structured output
    "segment": 0.05,                  # SAM2 on A10G, ~30s cold
    "apply_material": _INPAINTER_COSTS_USD["sd_inpaint"],  # default; rewritten per --inpainter
    "paste_tile": 0.0,                # local CPU
}
_COST_TOTAL_ESTIMATE = sum(_COST_ESTIMATE_USD.values())  # ~$0.51 (SD default)


# Replicate endpoint for flux-fill-pro. Inlined here rather than reusing the
# B3 FluxFillProRenderer class because (a) the renderer takes a file path
# and we have bytes in memory, (b) Spike 4 needs to pass a mask while B3
# fires without one. Cleanest path is a direct API call in this file.
_REPLICATE_BASE = "https://api.replicate.com/v1"
_FLUX_FILL_PRO_PATH = "models/black-forest-labs/flux-fill-pro/predictions"
_REPLICATE_POLL_INTERVAL_S = 2.0
_REPLICATE_POLL_TIMEOUT_S = 300.0


def _short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# Gemini 3 Pro returns spatial bboxes in normalized 0-1000 space regardless of
# input image dimensions. SAM2 needs pixel coordinates of the render, so we
# rescale here. Keep in sync with spike/test_vlm_tagging.py:_scale_bbox_to_pixels.
_NORMALIZED_MAX = 1000


def _render_pixel_size(render_bytes: bytes) -> tuple[int, int]:
    import io as _io
    from PIL import Image as _Image

    with _Image.open(_io.BytesIO(render_bytes)) as im:
        return im.size  # (w, h)


def _bbox_norm_to_pixels(
    region: Region, img_w: int, img_h: int
) -> tuple[int, int, int, int]:
    sx = img_w / _NORMALIZED_MAX
    sy = img_h / _NORMALIZED_MAX
    px = int(round(region.bbox.x * sx))
    py = int(round(region.bbox.y * sy))
    pw = int(round(region.bbox.w * sx))
    ph = int(round(region.bbox.h * sy))
    return px, py, pw, ph


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
    *,
    inpainter: str = "sd_inpaint",
) -> None:
    apply_cost = _INPAINTER_COSTS_USD[inpainter]
    other_cost = sum(v for k, v in _COST_ESTIMATE_USD.items() if k != "apply_material")
    total_cost = other_cost + apply_cost
    print("=" * 72)
    print("end_to_end_edit.py -- DRY RUN (no network, no Modal calls)")
    print("=" * 72)
    print(f"  screenshot:    {screenshot_path}")
    print(f"  region label:  {region_label}")
    print(f"  material:      {material_path}")
    print(f"  style prompt:  {style_prompt!r}")
    print(f"  output:        {output_path}")
    print(f"  inpainter:     {inpainter}")
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
    print(f"  5. apply_material via {inpainter}")
    print(f"       est ${apply_cost:.2f}")
    if inpainter == "sd_inpaint":
        print("       -> tile_bytes (cached at scope=tile)")
    else:
        print("       -> tile_bytes (cached at scope=tile_flux); needs REPLICATE_API_TOKEN")
    print("  6. paste_tile(render_bytes, mask_bytes, tile_bytes) [local]")
    print("       -> final composite PNG -> output path")
    print("")
    print(f"ESTIMATED COST PER LIVE RUN: ~${total_cost:.2f} USD")
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
    *,
    raw_save_dir: Path | None = None,
) -> TagRegionsResponse:
    """Tag regions on (screenshot, render); save raw before validation.

    Cache stores canonical post-tolerant-parse JSON. The raw response is
    persisted to `raw_save_dir/tags_raw.json` (when given) on every cache
    miss, before any validation — so a future Gemini-output bug can be
    salvaged offline without re-spending the API call.
    """
    key = f"tags_{_short_hash(screenshot_bytes)}_{_short_hash(render_bytes)}"

    def _compute() -> bytes:
        fn = _modal_lookup("tag_regions")
        result = fn.remote(screenshot_bytes, render_bytes)
        if raw_save_dir is not None:
            save_raw_response(raw_save_dir, result)
        response = TagRegionsResponse.parse_tolerant(result)
        return response.model_dump_json().encode("utf-8")

    raw = cache.get_or_compute(key, _compute, scope="tags")
    return TagRegionsResponse.model_validate_json(raw)


def _run_segment_bbox(
    render_bytes: bytes,
    region: Region,
) -> bytes:
    img_w, img_h = _render_pixel_size(render_bytes)
    px, py, pw, ph = _bbox_norm_to_pixels(region, img_w, img_h)
    key = (
        f"mask_{_short_hash(render_bytes)}_"
        f"{px}_{py}_{pw}_{ph}"
    )

    def _compute() -> bytes:
        fn = _modal_lookup("segment")
        prompt = {"type": "bbox", "x": px, "y": py, "w": pw, "h": ph}
        return fn.remote(render_bytes, prompt=prompt)

    return cache.get_or_compute(key, _compute, scope="mask")


def _flux_prompt_for_material(material_name: str) -> str:
    """Material prompt used for the Replicate FLUX Fill path.

    Kept structurally similar to modal_app.apply_material's SD prompt so
    differences between outputs reflect the model, not the prompt.
    """
    return (
        f"photorealistic {material_name} wall surface, architectural facade, "
        "natural daylight, sharp surface texture, high material detail, "
        "professional architectural photography"
    )


def _apply_material_via_replicate_flux_fill(
    render_bytes: bytes,
    mask_bytes: bytes,
    material_name: str,
) -> bytes:
    """Call black-forest-labs/flux-fill-pro on Replicate with image + mask.

    Replicate accepts inputs as base64 data URLs, so no upload step is
    needed. The poll loop matches the shape used by
    spike/renderers/replicate_models.py (which is also tested there).
    Returns the inpainted image bytes at the input's native resolution.
    """
    import base64

    import requests

    api_key = os.environ.get("REPLICATE_API_TOKEN")
    if not api_key:
        raise RuntimeError("REPLICATE_API_TOKEN not set")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    image_data_url = "data:image/png;base64," + base64.b64encode(render_bytes).decode("ascii")
    mask_data_url = "data:image/png;base64," + base64.b64encode(mask_bytes).decode("ascii")
    prompt = _flux_prompt_for_material(material_name)

    submit_url = f"{_REPLICATE_BASE}/{_FLUX_FILL_PRO_PATH}"
    body = {
        "input": {
            "image": image_data_url,
            "mask": mask_data_url,
            "prompt": prompt,
            "output_format": "png",
            "safety_tolerance": 2,
        }
    }
    submit = requests.post(submit_url, json=body, headers=headers, timeout=30)
    submit.raise_for_status()
    submit_body = submit.json()
    poll_url = (submit_body.get("urls") or {}).get("get")
    if not poll_url:
        pred_id = submit_body.get("id")
        if not pred_id:
            raise RuntimeError(
                f"Replicate submit returned no poll url or id: {submit_body!r}"
            )
        poll_url = f"{_REPLICATE_BASE}/predictions/{pred_id}"

    deadline = time.monotonic() + _REPLICATE_POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        resp = requests.get(poll_url, headers=headers, timeout=30)
        resp.raise_for_status()
        st = resp.json()
        status = st.get("status")
        if status == "succeeded":
            output = st.get("output")
            if isinstance(output, str):
                output_url = output
            elif isinstance(output, list) and output and isinstance(output[0], str):
                output_url = output[0]
            else:
                raise RuntimeError(f"flux-fill-pro output not a URL: {output!r}")
            dl = requests.get(output_url, timeout=60)
            dl.raise_for_status()
            return dl.content
        if status in {"failed", "canceled"}:
            raise RuntimeError(
                f"flux-fill-pro prediction {status}: error={st.get('error')!r}"
            )
        time.sleep(_REPLICATE_POLL_INTERVAL_S)
    raise RuntimeError(
        f"flux-fill-pro polling timed out after {_REPLICATE_POLL_TIMEOUT_S}s"
    )


def _run_apply_material(
    render_bytes: bytes,
    mask_bytes: bytes,
    material_name: str,
    *,
    inpainter: str = "sd_inpaint",
) -> bytes:
    """Dispatch to the chosen inpainter. Cache scope differs per inpainter
    so outputs don't collide (e.g., re-running T24's SD tile via FLUX would
    otherwise overwrite the cached SD result and vice versa).
    """
    if inpainter == "sd_inpaint":
        scope = "tile"
        key = (
            f"tile_{_short_hash(render_bytes)}_"
            f"{_short_hash(mask_bytes)}_{material_name}"
        )

        def _compute() -> bytes:
            fn = _modal_lookup("apply_material")
            return fn.remote(render_bytes, mask_bytes, material_name)

    elif inpainter == "flux_fill_replicate":
        scope = "tile_flux"
        key = (
            f"tile_flux_{_short_hash(render_bytes)}_"
            f"{_short_hash(mask_bytes)}_{material_name}"
        )

        def _compute() -> bytes:
            return _apply_material_via_replicate_flux_fill(
                render_bytes, mask_bytes, material_name
            )

    else:
        raise ValueError(
            f"unknown --inpainter {inpainter!r}; expected one of "
            f"{sorted(_INPAINTER_COSTS_USD)!r}"
        )

    return cache.get_or_compute(key, _compute, scope=scope)


def _run_live(
    screenshot_path: Path,
    region_label: str,
    material_path: Path,
    style_prompt: str,
    output_path: Path,
    *,
    inpainter: str = "sd_inpaint",
) -> None:
    apply_cost = _INPAINTER_COSTS_USD[inpainter]
    other_cost = sum(v for k, v in _COST_ESTIMATE_USD.items() if k != "apply_material")
    est_total = other_cost + apply_cost
    print(
        f"[end_to_end_edit] LIVE run — inpainter={inpainter!r}, "
        f"est ~${est_total:.2f} (apply_material ~${apply_cost:.2f})"
    )
    print(f"[end_to_end_edit] cache scope: spike/.cache/{{render,tags,mask,tile,tile_flux}}/")
    screenshot_bytes = screenshot_path.read_bytes()
    # We use the material file *name* (stem) as the material prompt token. Neither
    # SD Inpaint 1.5 nor flux-fill-pro (without IP-Adapter) takes the swatch image
    # as conditioning; both read only the material name. Full image-conditioned
    # material transfer needs IP-Adapter, which lives outside this driver.
    material_name = material_path.stem.replace("_", " ")

    print("[1/6] render_from_model_view …")
    render_bytes = _run_render(screenshot_bytes, style_prompt)
    print(f"      render: {len(render_bytes):,} bytes")

    print("[2/6] tag_regions …")
    raw_save_dir = output_path.parent
    tags = _run_tag_regions(
        screenshot_bytes, render_bytes, raw_save_dir=raw_save_dir
    )
    dropped = tags.__dict__.get("_dropped_region_ids") or []
    extra = f" ({len(dropped)} dropped: {dropped})" if dropped else ""
    print(f"      regions: {len(tags.regions)}{extra}")

    print(f"[3/6] pick region label={region_label!r} …")
    region = _pick_region(tags, region_label)
    img_w, img_h = _render_pixel_size(render_bytes)
    px, py, pw, ph = _bbox_norm_to_pixels(region, img_w, img_h)
    print(
        f"      picked {region.id} ({region.label}) "
        f"bbox_norm=({region.bbox.x},{region.bbox.y},{region.bbox.w},{region.bbox.h}) "
        f"bbox_px=({px},{py},{pw},{ph}) on {img_w}x{img_h} render "
        f"conf={region.confidence:.2f}"
    )

    print("[4/6] segment (bbox) …")
    mask_bytes = _run_segment_bbox(render_bytes, region)
    print(f"      mask: {len(mask_bytes):,} bytes")

    print(f"[5/6] apply_material name={material_name!r} via {inpainter} …")
    tile_bytes = _run_apply_material(
        render_bytes, mask_bytes, material_name, inpainter=inpainter
    )
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
    p.add_argument(
        "--inpainter",
        default="sd_inpaint",
        choices=sorted(_INPAINTER_COSTS_USD),
        help=(
            "Which apply_material backend to use. "
            "'sd_inpaint' is the Modal-hosted Stable Diffusion 1.5 inpaint "
            "(~$0.40/call, 512x512 native). "
            "'flux_fill_replicate' is black-forest-labs/flux-fill-pro on "
            "Replicate (~$0.05/call, native resolution; needs REPLICATE_API_TOKEN)."
        ),
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
            inpainter=args.inpainter,
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
        inpainter=args.inpainter,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
