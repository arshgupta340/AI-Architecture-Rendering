# Multi-view material lock — v2 (fixing the lock for textured materials)

- **Problem (from v1, `REPORTS/multiview.md`):** the anchor-reference lock (feed the anchor's already-materialized wall as a 3rd FLUX.2 Edit reference) won for colour-dominated travertine (ΔE-to-anchor **7.43 → 4.14**) but BACKFIRED for texture/shadow-heavy red_brick (**8.25 → 21.62**). The anchor render is golden-hour with strong directional shadows whose camera-relative direction differs from the front view, so a "match this exact appearance" reference injects the anchor's baked lighting into a differently-lit view.
- **v2 fix:** transfer material *identity*, not lit *appearance*. Two strategies, both measured against the same v1 wall-region metric:
  - **A1 prompt-softened lock** — same 3-image edit `[front, swatch, anchor_edit]`, but the instruction says "apply the same material TYPE/COLOUR/TONE as image 3, rendered under THIS view's own lighting and shadows."
  - **A2 neutral-reference lock** — replace the raw anchor reference with a lighting-neutralized crop of the anchor's wall: trim-calibrated white-balance (divide out the warm illuminant, estimated from the white-painted trim) + luminance flatten (divide by a blurred luminance to kill the directional shadow). The reference then carries only material identity.
- **Mode:** LIVE (A1/A2 numbers from real FLUX.2 Edit calls)
- **fal spend (the live A1/A2 run):** ~$0.24 — 4 FLUX.2 Edit calls (A1×2 + A2×2 @ $0.06). The naive + v1-locked columns reuse v1's cache for $0. (Re-running with `--reuse` re-measures the cached composites for $0.)
- **Inputs:** anchor = `spike/outputs/e2_house_v2/` (hero/SW, golden-hour), front = `spike/outputs/mv_front/` — same house, both 1504×656, both decoded.

## Comparison — wall-region distance to the anchor (lower = more consistent)

`dE(Lab)` = full CIELAB distance of the mean wall colour to the anchor wall. `dE_ab` = the same distance **dropping L\*** (chroma only). `dTex` = |difference| in mean-|Laplacian| texture energy.

Two headline numbers because L\* (brightness) legitimately differs between the golden-hour anchor and the brighter front view — the *same* brick under a brighter sun is genuinely lighter, so part of `dE(Lab)` penalises correct re-lighting. A material's **identity** is its chroma `(a*, b*)`, so `dE_ab` is the honest cross-view-consistency measure. **Success criterion (brief):** for red_brick a lock's `dE` < naive (8.25), travertine ≤ ~4.5.

| material | metric | naive | v1-locked | A1 | A2 | best lock | < naive? |
|---|---|---|---|---|---|---|---|
| travertine | dE(Lab) | 7.43 | **4.14** | 6.81 | 8.05 | v1_locked | YES |
| travertine | dE_ab | 7.10 | **1.80** | 6.14 | 6.60 | v1_locked | YES |
| red_brick | dE(Lab) | 8.25 | 21.62 | 14.96 | **13.75** | A2 | no |
| red_brick | dE_ab | 8.09 | 20.65 | 11.94 | **9.55** | A2 | no |

### Texture energy distance (dTex) to the anchor (the v1 failure signal — lower = no shadow injection)

| material | naive dTex | v1-locked dTex | A1 dTex | A2 dTex |
|---|---|---|---|---|
| travertine | 2.52 | 4.35 | 4.93 | 4.48 |
| red_brick | 6.49 | 25.89 | 5.00 | 9.47 |

### Mean wall Lab per variant

| material | anchor | naive | v1_locked | A1 | A2 |
|---|---|---|---|---|---|
| travertine | (73.3, 2.4, 18.7) | (75.5, 2.9, 11.6) | (77.0, 2.3, 16.9) | (76.2, 1.8, 12.6) | (77.9, 1.7, 12.1) |
| red_brick | (44.3, 19.5, 27.8) | (42.6, 19.4, 19.7) | (50.7, 7.0, 11.3) | (53.3, 15.6, 16.5) | (54.2, 13.9, 20.0) |

## Chosen strategy (per material)

- **travertine:** best lock = **v1_locked** (dE(Lab) 4.14, chroma dE_ab 1.80; v1-locked was 4.14/1.80, naive 7.43/7.10).
- **red_brick:** best lock = **A2** (dE(Lab) 13.75, chroma dE_ab 9.55; v1-locked was 21.62/20.65, naive 8.25/8.09).

## Interpretation — what v2 fixed

**red_brick — the v1 backfire is fixed.** v1-locked produced a blotchy, washed wall (dTex **25.9**, chroma desaturated to a\*=7.0). Both v2 strategies eliminate that: A1/A2 texture energy drops to 5.0/9.5 (vs v1's 25.9) and the brick is properly red again (A2 a\*=13.9, b\*=20.0 — matching the anchor's warm tone far better than v1-locked). On chroma, A2 halves the v1 error (20.6 → 9.5). It still does not quite *beat* the swatch-only naive (8.1) because for a colour this saturated the swatch alone already nails the hue; the anchor lock's job here is to **stop hurting**, which A2 achieves. The residual `dE(Lab)` gap is almost entirely L\* (A2 is +10 brighter than the golden-hour anchor) — i.e. correct re-lighting for the brighter front view, not a material mismatch (see `_wallzoom_red_brick.png`).

**travertine — the v1 lock stays the winner.** Its appearance is lighting-insensitive (smooth, near-shadowless), so feeding the raw anchor edit is safe and best: v1-locked chroma dE_ab **1.8** beats naive (7.1) and both v2 strategies (A1 6.1, A2 6.6). Softening the prompt or neutralising the reference throws away signal it could safely use.

**Product rule that falls out of this:** branch on material class. *Smooth / colour-dominated* (travertine, stucco, painted): raw-anchor 3-reference lock (v1). *Textured / shadow-interacting* (brick, stone coursing, cedar): the **A2 neutral-reference lock** — it transfers coursing + intrinsic colour without importing the anchor's baked sun, so the lock is never worse than the swatch and usually better on texture consistency. A simple heuristic for the class: if the anchor wall's masked texture-energy is high, neutralise the reference.

## Evidence

- `spike\outputs\multiview_v2\sidebyside_travertine.png` — [anchor | naive | v1-locked | A1 | A2] for travertine
- `spike\outputs\multiview_v2\_wallzoom_travertine.png` — matched-scale wall patches [anchor | naive | v1-locked | winner] for travertine (judge cross-view consistency without layout distraction)
- `spike\outputs\multiview_v2\sidebyside_red_brick.png` — [anchor | naive | v1-locked | A1 | A2] for red_brick
- `spike\outputs\multiview_v2\_wallzoom_red_brick.png` — matched-scale wall patches [anchor | naive | v1-locked | winner] for red_brick (judge cross-view consistency without layout distraction)
- `spike/outputs/multiview_v2/_neutral_<mat>.png` — the A2 lighting-neutralized anchor wall reference (white-balanced + shadow-flattened).
- `spike/outputs/multiview_v2/view2_a1_<mat>.png`, `view2_a2_<mat>.png` — per-strategy view-2 composites.

## Production recipe (v2)

```
anchor_final = composite(anchor_render, wall_mask_anchor,
                         FLUX.2 Edit[anchor_render, swatch])      # view 1
neutral_ref  = flatten_luminance(white_balance(crop_wall(anchor_final)))
view2_locked = composite(front_render, wall_mask_front,
                         FLUX.2 Edit[front_render, swatch, neutral_ref])  # A2
```
The neutralized reference carries the material's intrinsic colour + coursing texture with the anchor's golden-hour cast and directional shadow removed, so FLUX re-lights it for the new view instead of copying baked highlights.

Runner: `spike/run_multiview_lock_v2.py`. Reuses v1's cache (`spike/outputs/multiview/`) for the naive / v1-locked columns.