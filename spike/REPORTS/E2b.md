# E2b — Render↔mask registration fix (depth + canny multi-ControlNet)

- **Trigger:** User found the canvas prototype's masking inaccurate — brick lands over windows, pillar edits smudge. Diagnosed to render/mask misregistration, not a UI bug.
- **Status:** **FIXED.** GT-edge alignment 51.7% → **98.5% within 2px** (median drift 1.91px → 0.95px). Brick now lands on walls only; windows and porch posts stay sharp. Wired into the prototype.
- **Cost:** ~$0.20 (E2b render $0.075 + brick validation $0.06 + travertine demo asset $0.06). Ledger ≈ $2.54.
- **Date:** 2026-06-12

## Root cause (diagnosed, not guessed)

`beauty.png` and `instance_ids.png` come from the same atomic capture, so the masks align **perfectly** with the beauty pass (control overlay confirmed). The displayed base, however, was the E2 `flux_depth` render — and **depth ControlNet cannot pin coplanar features**: a window flush in a wall has ~the same depth as the wall, so FLUX invented opening positions, drifting them 5–25px. The mask is registered to true geometry; the image drifted from it → masking "wall" cut window-holes where the *real* windows are, not the *rendered* ones → brick over rendered windows, posts offset → "smudge". Evidence: `spike/outputs/e2_house/diag_facade_compare.png` (control top vs drift bottom).

Secondary: masks 1514×659 (aspect 2.2974) vs render 1504×656 (2.2927) → progressive resize drift.

## Fix

1. **Re-capture at native 1504×656** (FLUX snaps to /16; 1504=94·16, 656=41·16). Masks now share the render's exact pixel grid — zero resize drift. Done via `rhino_capture.capture(..., camera=hero)` after `vp.Size = (1504,656)` → `spike/outputs/e2_house_v2/` (90.5% decode).
2. **Hard edge lock**: render with fal `flux-general` **ControlNetUnion** = canny@0.8 (start 0–0.85) + depth@0.5 (start 0–0.7), at 1504×656. The canny control is a *ground-truth* line drawing — `Canny(beauty) ∪ instance-boundaries` — so every window/muntin/trim/post line is pinned at its exact geometric position. Script: `spike/run_e2b_registration.py`.

## Result (`edge_align` metric: GT-edge → nearest render-edge)

| render | median px | ≤2px | ≤1px |
|---|---|---|---|
| OLD flux_depth (depth only) | 1.91 | 51.7% | 38.9% |
| **NEW depth+canny union** | **0.95** | **98.5%** | **91.7%** |

Live brick-on-walls on the new base (`val_brick_window_check.png`, `val_facade_zoom.png`): brick confined to walls, window casings/glass clean, porch posts sharp white. App-path highlight (`apps/canvas-prototype/verify_wall_highlight_v2_zoom.png`) confirms wall selection excludes windows.

## Wired into the prototype

- `prepare_data.py` → sources `e2_house_v2`, base = the depth+canny `base_render.png`; also clears the layer cache on refresh (cache key is content-independent — stale-layer trap).
- `server.py` no-spend travertine path → `e2_house_v2/travertine_walls_v2.png` (aligned). Live path unchanged (FLUX.2 Edit on aligned base + paste_tile). 62 tests green; API smoke + regeneration confirmed.

## Polish + feather (resolved, same session)

- **Warmth recovered for free, no re-drift.** The gray look was the *prompt*, not the model — I'd never specified siding colour, so flux-dev defaulted to gray. A warm, specific prompt (terracotta lap siding, golden-hour light, saturated) on the *same* canny@0.8+depth@0.5 lock → `renders/warm_w1.png`, now the canonical `base_render.png`. Edge alignment held: **98.2% within 2px** (vs 98.5% gray — statistically identical). No second-stage img2img needed, so zero re-drift risk. The two-stage low-denoise polish idea is therefore dropped as unnecessary.
- **Edge feather added.** `server._mask_png` now dilates only +1px (was +2px — registration is tight enough) then Gaussian-feathers ~1.1px; `paste_tile`'s `Image.composite` blends the soft alpha, hiding hairline seams at trim boundaries (`feather_compare.png`). Feather is now polish, not a crutch.

## Remaining follow-ups

- Bake `out_size` into `rhino_capture.capture()` so the native-size capture is explicit, not a manual `vp.Size` set before the call.
- flux-dev union photorealism has a ceiling; if a warmer/sharper base is wanted later, re-evaluate a flux-pro multi-ControlNet path if/when fal exposes one (their `flux-pro/v1/canny` queue was dead in E2).
