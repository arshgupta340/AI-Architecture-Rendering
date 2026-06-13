r"""Reusable "one swatch -> all views" material lock (Part B engine).

This is the production-shaped, parameterized version of the winning v2 pipeline
(spike/run_multiview_lock_v2.py). The canvas server calls apply_to_views(); the
v2 research script and tests can call the same primitives.

Pipeline ("anchor first, then lock the rest"):
  1. ANCHOR view: FLUX.2 Edit [anchor_render, swatch] -> composite through the
     anchor wall mask. This is the materialized anchor (== the existing single-view
     /api/apply_material result, so a cached anchor layer is reused for free).
  2. Build the lock REFERENCE from the anchor edit, per material class:
       - smooth / colour-dominated (travertine, stucco, painted): the RAW anchor
         edit (v1 lock — best for these; appearance is lighting-insensitive).
       - textured / shadow-interacting (brick, seam metal, cedar): a lighting-
         NEUTRALIZED crop of the anchor wall (A2 — trim-calibrated white-balance +
         luminance flatten). Transfers coursing + intrinsic colour without the
         anchor's baked golden-hour sun, which is what made v1 backfire on brick.
  3. Each OTHER view: FLUX.2 Edit [view_render, swatch, reference] with a prompt
     matched to the class -> composite through that view's wall mask.

Costs: 1 anchor edit + (N-1) view edits, each ~$0.06 (FLUX.2 [pro] Edit). The
anchor edit is skipped when a cached anchor layer is supplied (e.g. the no-spend
travertine path). Every call is surfaced via the `on_cost` callback so the server
can budget-guard and log.

Reuses (never reimplements): run_e3_swatch._fal_call/_data_uri, composite.paste_tile,
and the neutralization is the same trim-calibrated WB + luminance-flatten as v2.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, ImageFilter

import composite
from run_e3_swatch import _data_uri, _fal_call

# Material class -> lock strategy. Smooth/colour-dominated transfer cleanly from the
# raw (lit) anchor; textured/shadow-interacting need the reference neutralized first.
SMOOTH_MATERIALS = {"travertine", "white_stucco"}            # raw-anchor (v1) lock
TEXTURED_MATERIALS = {"red_brick", "charcoal_seam", "weathered_cedar"}  # A2 neutral lock

COST_EDIT = 0.06   # FLUX.2 [pro] Edit, measured in E3


def lock_strategy(swatch: str) -> str:
    """'raw' (v1 raw-anchor lock) or 'neutral' (A2). Defaults to neutral (safer:
    A2 is never worse than the swatch alone, per REPORTS/multiview_v2.md)."""
    if swatch in SMOOTH_MATERIALS:
        return "raw"
    return "neutral"


# --------------------------------------------------------------------------- #
# masks + payload helpers (mirror server.py / v2 exactly)
# --------------------------------------------------------------------------- #
DILATE = 3
FEATHER = 1.1


def mask_png_from_ids(ids: np.ndarray, region_ids: Iterable[int]) -> bytes:
    """Soft union mask for instance ids (+1px dilate, ~1px feather) — same as
    apps/canvas-prototype/server.py:_mask_png so composites match the product."""
    m = np.isin(ids, list(region_ids))
    img = Image.fromarray((m * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(DILATE)).filter(ImageFilter.GaussianBlur(FEATHER))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _swatch_uri(path: Path, max_side: int = 1024) -> str:
    """JPEG data URI of a swatch, long edge capped so 3-image payloads stay < 413."""
    img = Image.open(path).convert("RGB")
    if max(img.size) > max_side:
        s = max_side / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)))
    return _data_uri(img, fmt="JPEG")


def _uri(png: bytes) -> str:
    return _data_uri(Image.open(io.BytesIO(png)).convert("RGB"), fmt="JPEG")


def flux2_edit(image_uris: list[str], prompt: str, timeout_s: int = 420) -> bytes:
    """FLUX.2 [pro] Edit with N references (E3 winner; verified to accept 3)."""
    payload = {"prompt": prompt, "image_urls": image_uris,
               "output_format": "png", "safety_tolerance": "5"}
    try:
        return _fal_call("fal-ai/flux-2-pro/edit", payload, timeout_s=timeout_s)
    except Exception:
        if len(image_uris) <= 2:
            raise
        return _fal_call("fal-ai/flux-pro/kontext/max/multi", payload, timeout_s=timeout_s)


# --------------------------------------------------------------------------- #
# A2 neutralization (trim-calibrated WB + luminance flatten) — parameterized
# --------------------------------------------------------------------------- #
def neutralize_wall(anchor_edit: bytes, anchor_ids: np.ndarray, wall_ids: Iterable[int],
                    illuminant: np.ndarray | None) -> bytes:
    """Crop the wall region of the materialized anchor and strip its baked lighting.

    illuminant: normalized RGB of the anchor's white trim (cast == golden-hour
    illuminant). If None, grey-world over the wall is used as a fallback.
    """
    arr = np.array(Image.open(io.BytesIO(anchor_edit)).convert("RGB")).astype(np.float32)
    m = np.isin(anchor_ids, list(wall_ids))
    if not m.any():
        return anchor_edit
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = arr[y0:y1, x0:x1].copy()
    mcrop = m[y0:y1, x0:x1]

    if illuminant is None:
        illuminant = crop[mcrop].mean(axis=0)
        illuminant = illuminant / max(float(illuminant.mean()), 1e-3)
    crop = crop / illuminant[None, None, :]

    lum = 0.2126 * crop[..., 0] + 0.7152 * crop[..., 1] + 0.0722 * crop[..., 2]
    blur = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(60))).astype(np.float32)
    tgt = float(lum[mcrop].mean())
    crop = crop * (tgt / np.clip(blur, 1e-3, None))[..., None]

    out = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def trim_illuminant(base_render: bytes, ids: np.ndarray, trim_ids: Iterable[int]) -> np.ndarray | None:
    """Normalized illuminant from the white-painted trim of a view; None if no trim."""
    tids = list(trim_ids)
    if not tids:
        return None
    m = np.isin(ids, tids)
    if m.sum() < 50:
        return None
    base = np.array(Image.open(io.BytesIO(base_render)).convert("RGB")).astype(np.float32)
    mean = base[m].mean(axis=0)
    return mean / max(float(mean.mean()), 1e-3)


# --------------------------------------------------------------------------- #
# prompts
# --------------------------------------------------------------------------- #
def anchor_prompt(material_desc: str, target: str) -> str:
    return (f"Apply the {material_desc} material shown in the second image to the "
            f"{target} surfaces of the building in the first image. Only those surfaces "
            f"change; windows, trim, roof, ground, lighting and camera stay exactly "
            f"identical.")


def lock_prompt(material_desc: str, target: str, strategy: str) -> str:
    if strategy == "neutral":
        return (f"Apply {material_desc} to the {target} surfaces of the building in the "
                f"first image. The third image is a flat, evenly-lit sample of the EXACT "
                f"material already applied to the same building — match its colour, tone, "
                f"coursing scale and texture precisely so the views read as the identical "
                f"material, but light it naturally for THIS view. The second image is the "
                f"raw material swatch. Only those surfaces change; windows, trim, roof, "
                f"ground, lighting and camera stay exactly identical.")
    # raw (v1) lock
    return (f"Apply {material_desc} to the {target} surfaces of the building in the first "
            f"image. The third image shows the SAME building already clad in this exact "
            f"material from another camera angle — match that material's colour, tone, "
            f"coursing scale and texture precisely so the two views read as the identical "
            f"material. The second image is the raw material swatch. Only those surfaces "
            f"change; windows, trim, roof, ground, lighting and camera stay exactly "
            f"identical.")


# --------------------------------------------------------------------------- #
# the engine
# --------------------------------------------------------------------------- #
class View:
    """One view's loaded data (a small DTO the server fills from disk)."""
    def __init__(self, vid: str, base_png: bytes, ids: np.ndarray, regions: dict):
        self.id = vid
        self.base_png = base_png
        self.ids = ids
        self.regions = regions     # {str(id): {"semantic", ...}}

    def ids_for_semantic(self, semantic: str) -> list[int]:
        return sorted(int(k) for k, r in self.regions.items() if r.get("semantic") == semantic)

    def ids_for_trim(self) -> list[int]:
        return self.ids_for_semantic("trim")


def apply_to_views(
    *, anchor: View, others: list[View], swatch_name: str, swatch_path: Path,
    material_desc: str, region_semantic: str | None = None,
    anchor_region_ids: list[int] | None = None,
    anchor_precomputed: bytes | None = None,
    on_cost: Callable[[float, str], None] | None = None,
) -> dict:
    """Run the winning lock across the anchor + all other views.

    Selection is by `region_semantic` (propagates across views via the shared
    semantic) OR explicit `anchor_region_ids` (then other views use the same ids
    that exist in them). Returns:
        {"strategy", "anchor": {"view_id","final_png","region_ids","cost"},
         "views": [{"view_id","final_png","region_ids","cost"}], "cost"}
    `final_png` is the full composited RGB frame for that view.

    `anchor_precomputed`: if given, used as the anchor's materialized edit instead of
    a live FLUX call (the no-spend travertine path). `on_cost(cost, label)` fires per
    billable call so the caller can budget-guard.
    """
    strategy = lock_strategy(swatch_name)
    target = region_semantic or "wall"

    def cost(c: float, label: str):
        if on_cost:
            on_cost(c, label)

    def ids_for(view: View) -> list[int]:
        if region_semantic is not None:
            return view.ids_for_semantic(region_semantic)
        # explicit ids: keep the ones that actually exist in this view
        present = set(int(k) for k in view.regions)
        return sorted(i for i in (anchor_region_ids or []) if i in present)

    # ---- 1. anchor ----
    a_ids = ids_for(anchor)
    if not a_ids:
        raise ValueError(f"anchor view '{anchor.id}' has no regions for {target}")
    a_mask = mask_png_from_ids(anchor.ids, a_ids)
    if anchor_precomputed is not None:
        anchor_final = composite.paste_tile(anchor.base_png, a_mask, anchor_precomputed)
        anchor_edit_full = anchor_precomputed
    else:
        cost(COST_EDIT, f"anchor {swatch_name}->{target} ({anchor.id})")
        edit = flux2_edit([_uri(anchor.base_png), _swatch_uri(swatch_path)],
                          anchor_prompt(material_desc, target))
        anchor_final = composite.paste_tile(anchor.base_png, a_mask, edit)
        anchor_edit_full = edit

    # ---- 2. build the lock reference from the anchor ----
    if strategy == "neutral":
        illum = trim_illuminant(anchor.base_png, anchor.ids, anchor.ids_for_trim())
        reference = neutralize_wall(anchor_final, anchor.ids, a_ids, illum)
    else:
        reference = anchor_final
    ref_uri = _uri(reference)

    # ---- 3. lock each other view ----
    view_results = []
    total = (0.0 if anchor_precomputed is not None else COST_EDIT)
    for v in others:
        v_ids = ids_for(v)
        if not v_ids:
            view_results.append({"view_id": v.id, "final_png": v.base_png,
                                 "region_ids": [], "cost": 0.0, "skipped": True})
            continue
        v_mask = mask_png_from_ids(v.ids, v_ids)
        cost(COST_EDIT, f"lock {swatch_name}->{target} ({v.id}, {strategy})")
        edit = flux2_edit([_uri(v.base_png), _swatch_uri(swatch_path), ref_uri],
                          lock_prompt(material_desc, target, strategy))
        v_final = composite.paste_tile(v.base_png, v_mask, edit)
        view_results.append({"view_id": v.id, "final_png": v_final,
                            "region_ids": v_ids, "cost": COST_EDIT, "skipped": False})
        total += COST_EDIT

    return {
        "strategy": strategy,
        "anchor": {"view_id": anchor.id, "final_png": anchor_final,
                   "region_ids": a_ids,
                   "cost": 0.0 if anchor_precomputed is not None else COST_EDIT,
                   "reference_png": reference},
        "views": view_results,
        "cost": round(total, 2),
    }
