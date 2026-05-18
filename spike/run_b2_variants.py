"""B2 prompt-variant driver for Nano Banana Pro.

Four variant configs that each try to address spike-2 failures via a *cheap*
intervention (prompt / resolution / multi-pass), without changing the
underlying renderer. The architect picks the best B2 variant before
escalating to the full multi-renderer bake-off in B3.

Variants
--------
1. ``tightened_prompt``         — Inject explicit, geometry-pinning
                                  constraints into ``extra_constraints`` so
                                  Nano Banana stops inventing windows / wrap-
                                  around corners.
2. ``higher_res``               — Resize the input screenshot to a 1920px
                                  long edge before sending. The render
                                  function is the same; only the pixel
                                  budget for the model changes.
3. ``multi_region_annotated``   — Tightened prompt PLUS per-facade callouts
                                  describing what each region of the model
                                  is supposed to be.
4. ``multi_pass``               — Two-call pipeline: first NB render ->
                                  Gemini-3-Pro tags regions and counts
                                  elements -> second NB render with
                                  count-derived constraints.

Modes
-----
- Default ``--dry-run``: prints the exact arguments each variant *would*
  send (prompt, extra_constraints, image dimensions, mime type, seed) and
  writes nothing. Zero network. Safe to run any time.
- ``--live`` (requires ``GOOGLE_API_KEY``): looks up the Modal function and
  executes each variant for real. Outputs land in
  ``spike/outputs/spike2_5/b2/<variant>.png``. Cost is roughly $0.04 per
  Nano-Banana call, so a full live run is ~$0.16 (or ~$0.20 with the
  multi-pass variant's two NB calls + one Gemini tagging call).

Usage
-----
    python spike/run_b2_variants.py --input test_assets/model_views/x.png
    python spike/run_b2_variants.py --input ... --variant tightened_prompt
    python spike/run_b2_variants.py --input ... --live --seed 42
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image


# ---------------------------------------------------------------------------
# Defaults — kept here so dry-run output is self-documenting.
# ---------------------------------------------------------------------------

DEFAULT_STYLE = (
    "warm afternoon light, urban context, photorealistic exterior, "
    "mixed-use building"
)

# Tightened constraints derived from the recurring spike-2 failures: invented
# windows on blank facades, wrap-around glazing at corners, fabricated
# mullion grids on the distant facade. These are intentionally negative /
# count-pinning so the model has less room to hallucinate.
TIGHTENED_CONSTRAINTS = (
    "The right facade has zero windows; do not add any. "
    "The corner is recessed, not wrapping — do not extend glazing around it. "
    "Mullion patterns must match the input exactly; do not invent new "
    "subdivisions. Window count per facade must equal what the input shows."
)

# Per-facade annotations layered on top of TIGHTENED_CONSTRAINTS for
# variant (c). Architect can edit these to match the specific input.
MULTI_REGION_ANNOTATIONS = (
    "Per-facade callouts: "
    "(1) Front (south) facade: regular punched-window grid as shown, "
    "ground-floor retail glazing. "
    "(2) Right (east) facade: solid masonry, zero openings. "
    "(3) Left (west) facade: narrow service openings only, no curtain wall. "
    "(4) Rear facade: same window rhythm as front, no balconies. "
    "(5) Roof: flat parapet, no penthouse, no rooftop equipment unless "
    "shown in the input."
)

# Multi-pass first-call instructions: ask Gemini-3-Pro to enumerate regions
# AND counts. The driver parses these counts and reuses them as constraints
# in the second NB call.
MULTI_PASS_TAG_PROMPT = (
    "Look at this architectural model screenshot and the photorealistic "
    "render of it. List each facade region you can identify and, for each, "
    "the integer count of distinct windows, doors, and balconies. Return "
    "JSON: {regions: [{label, window_count, door_count, balcony_count}]}."
)


HIGHER_RES_LONG_EDGE = 1920


# Modal app + function names must match `spike/modal_app.py`.
_MODAL_APP_NAME = "arch-rendering-spike"
_MODAL_FN_NAME = "render_from_model_view"


# ---------------------------------------------------------------------------
# Variant config — a thin record of everything the live run would send.
# ---------------------------------------------------------------------------


@dataclass
class VariantCall:
    """One Nano-Banana call planned by a variant.

    ``image_path`` is the on-disk path of the (possibly resized) input that
    would be sent. In dry-run mode we never write the resized file; we just
    note the intended size in ``image_size``.
    """

    style_prompt: str
    extra_constraints: str
    image_path: Path
    image_size: tuple[int, int]
    mime_type: str = "image/png"
    note: str = ""


@dataclass
class Variant:
    name: str
    description: str
    calls: list[VariantCall] = field(default_factory=list)
    # Optional non-NB calls (e.g. multi-pass uses one Gemini tagging call).
    aux_calls: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Variant builders — each takes the raw screenshot path + style and produces
# a Variant record. Pure / no network.
# ---------------------------------------------------------------------------


def _open_rgb(path: Path) -> Image.Image:
    return Image.open(io.BytesIO(path.read_bytes())).convert("RGB")


def _resize_long_edge(img: Image.Image, long_edge: int) -> Image.Image:
    w, h = img.size
    if max(w, h) >= long_edge:
        return img
    ratio = long_edge / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


def build_tightened(screenshot: Path, style: str) -> Variant:
    img = _open_rgb(screenshot)
    return Variant(
        name="tightened_prompt",
        description=(
            "Inject explicit constraints (window counts, corner recess, "
            "mullion rules) into extra_constraints; everything else "
            "matches the baseline call."
        ),
        calls=[
            VariantCall(
                style_prompt=style,
                extra_constraints=TIGHTENED_CONSTRAINTS,
                image_path=screenshot,
                image_size=img.size,
                note="single-call variant, no resize",
            )
        ],
    )


def build_higher_res(screenshot: Path, style: str, out_dir: Path) -> Variant:
    img = _open_rgb(screenshot)
    resized = _resize_long_edge(img, HIGHER_RES_LONG_EDGE)
    # In dry-run mode the resized file isn't written; the live runner writes
    # it under out_dir before sending. We record the *intended* target path.
    target_path = out_dir / f"{screenshot.stem}__1920.png"
    return Variant(
        name="higher_res",
        description=(
            f"Resize input long-edge to {HIGHER_RES_LONG_EDGE}px before "
            "sending; same prompt as baseline."
        ),
        calls=[
            VariantCall(
                style_prompt=style,
                extra_constraints="",
                image_path=target_path,
                image_size=resized.size,
                note=(
                    f"input {img.size[0]}x{img.size[1]} -> resized to "
                    f"{resized.size[0]}x{resized.size[1]}"
                ),
            )
        ],
    )


def build_multi_region(screenshot: Path, style: str) -> Variant:
    img = _open_rgb(screenshot)
    combined = TIGHTENED_CONSTRAINTS + " " + MULTI_REGION_ANNOTATIONS
    return Variant(
        name="multi_region_annotated",
        description=(
            "Tightened constraints plus per-facade callouts describing what "
            "each region is supposed to be."
        ),
        calls=[
            VariantCall(
                style_prompt=style,
                extra_constraints=combined,
                image_path=screenshot,
                image_size=img.size,
                note="single-call variant, no resize",
            )
        ],
    )


def build_multi_pass(screenshot: Path, style: str) -> Variant:
    img = _open_rgb(screenshot)
    # First call uses the tightened prompt to give the tagger something
    # coherent to count. Second call mirrors the tightened call but with
    # extra_constraints rewritten from the tagger's counts.
    first = VariantCall(
        style_prompt=style,
        extra_constraints=TIGHTENED_CONSTRAINTS,
        image_path=screenshot,
        image_size=img.size,
        note="pass 1: NB render with tightened prompt",
    )
    second = VariantCall(
        style_prompt=style,
        extra_constraints=(
            TIGHTENED_CONSTRAINTS
            + " (counts pinned by pass-1 tagger — see aux_calls)"
        ),
        image_path=screenshot,
        image_size=img.size,
        note="pass 2: NB render with count-derived constraints",
    )
    return Variant(
        name="multi_pass",
        description=(
            "Two NB calls bracketing a Gemini-3-Pro region/count tagging "
            "step. Pass 2's extra_constraints are rewritten from pass 1's "
            "counts before sending."
        ),
        calls=[first, second],
        aux_calls=[
            "gemini-3-pro-preview structured tagging "
            f"(prompt: {MULTI_PASS_TAG_PROMPT!r})"
        ],
    )


VARIANT_BUILDERS = {
    "tightened_prompt": build_tightened,
    "higher_res": build_higher_res,
    "multi_region_annotated": build_multi_region,
    "multi_pass": build_multi_pass,
}


# ---------------------------------------------------------------------------
# Dry-run printer — the only thing the agent / architect normally sees.
# ---------------------------------------------------------------------------


def print_variant(variant: Variant) -> None:
    print(f"\n=== variant: {variant.name} ===")
    print(f"  description: {variant.description}")
    for i, call in enumerate(variant.calls, 1):
        print(f"  call {i}:")
        print(f"    image_path:        {call.image_path}")
        print(f"    image_size:        {call.image_size[0]}x{call.image_size[1]}")
        print(f"    mime_type:         {call.mime_type}")
        print(f"    style_prompt:      {call.style_prompt!r}")
        print(f"    extra_constraints: {call.extra_constraints!r}")
        if call.note:
            print(f"    note:              {call.note}")
    for aux in variant.aux_calls:
        print(f"  aux call: {aux}")


# ---------------------------------------------------------------------------
# Live runner — only reached behind --live AND GOOGLE_API_KEY.
# ---------------------------------------------------------------------------


def run_variant_live(
    variant: Variant,
    screenshot: Path,
    out_dir: Path,
    seed: int | None,
) -> Path:
    """Execute a variant's call sequence. Returns the final output PNG path.

    Only call this when ``--live`` was passed and ``GOOGLE_API_KEY`` is set.
    Network and money are spent here.
    """
    import modal  # lazy — keeps dry-run import-clean without modal auth.

    out_dir.mkdir(parents=True, exist_ok=True)

    # For higher_res, materialize the resized PNG to the target path now.
    if variant.name == "higher_res":
        img = _resize_long_edge(_open_rgb(screenshot), HIGHER_RES_LONG_EDGE)
        target = variant.calls[0].image_path
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, format="PNG")

    fn = modal.Function.lookup(_MODAL_APP_NAME, _MODAL_FN_NAME)

    last_bytes: bytes | None = None
    for idx, call in enumerate(variant.calls, 1):
        image_bytes = call.image_path.read_bytes()
        print(f"[b2:{variant.name}] call {idx}/{len(variant.calls)} -> Modal…")
        result = fn.remote(
            image_bytes=image_bytes,
            style_prompt=call.style_prompt,
            mime_type=call.mime_type,
            seed=seed,
            extra_constraints=call.extra_constraints,
        )
        if not isinstance(result, (bytes, bytearray)):
            raise RuntimeError(
                f"render_from_model_view returned {type(result).__name__}, "
                "expected bytes"
            )
        last_bytes = bytes(result)
        intermediate_path = out_dir / f"{variant.name}__call{idx}.png"
        intermediate_path.write_bytes(last_bytes)
        print(f"[b2:{variant.name}]   -> {intermediate_path}")

    final = out_dir / f"{variant.name}.png"
    assert last_bytes is not None
    final.write_bytes(last_bytes)
    print(f"[b2:{variant.name}] FINAL -> {final}")
    return final


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True,
                    help="PNG model viewport screenshot")
    ap.add_argument(
        "--variant",
        choices=sorted(VARIANT_BUILDERS.keys()),
        action="append",
        help=(
            "Variant to run; may be passed multiple times. Default: all "
            "four variants."
        ),
    )
    ap.add_argument("--style", default=DEFAULT_STYLE,
                    help="Style prompt fragment (default: see source)")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed for reproducibility (live mode only)")
    ap.add_argument("--out-dir", type=Path,
                    default=Path("spike/outputs/spike2_5/b2"),
                    help="Where to write live-mode outputs")
    ap.add_argument("--live", action="store_true",
                    help="Actually call Modal / Gemini. Requires GOOGLE_API_KEY.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Force dry-run mode (default when --live is absent)")
    args = ap.parse_args()

    screenshot: Path = args.input
    if not screenshot.is_file():
        print(f"error: input not found: {screenshot}", file=sys.stderr)
        return 2

    selected = args.variant or sorted(VARIANT_BUILDERS.keys())
    live = args.live and not args.dry_run

    if live and not os.environ.get("GOOGLE_API_KEY"):
        print(
            "error: --live requires GOOGLE_API_KEY in the environment.",
            file=sys.stderr,
        )
        return 2

    # Build all variants up-front so dry-run output and live execution see
    # the same plan.
    variants: list[Variant] = []
    for name in selected:
        builder = VARIANT_BUILDERS[name]
        if name == "higher_res":
            v = builder(screenshot, args.style, args.out_dir)
        else:
            v = builder(screenshot, args.style)
        variants.append(v)

    print(f"[b2] input: {screenshot}")
    print(f"[b2] mode:  {'LIVE' if live else 'dry-run'}")
    print(f"[b2] variants: {', '.join(v.name for v in variants)}")
    if live:
        est_calls = sum(len(v.calls) for v in variants)
        print(f"[b2] estimated cost: ~${est_calls * 0.04:.2f} "
              f"({est_calls} NB calls)")

    for v in variants:
        print_variant(v)

    if not live:
        print("\n[b2] dry-run complete — no network calls made.")
        return 0

    print("\n[b2] executing live calls…")
    for v in variants:
        run_variant_live(v, screenshot, args.out_dir, args.seed)
    print("\n[b2] all variants done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
