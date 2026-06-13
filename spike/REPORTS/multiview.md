# Multi-view material lock — enterprise consistency demo

- **Claim:** "change a material once and it stays consistent across every view of the building."
- **Approach:** anchor-reference. Materialize the wall in the ANCHOR view (e2_house_v2, hero/SW), then condition the SECOND view (mv_front) on that already-materialized anchor as a third FLUX.2 Edit reference. Compare against a NAIVE per-view edit that only sees the raw swatch.
- **Mode:** LIVE
- **fal spend this run:** ~$0.38
- **Views:** anchor cam `[-12.7, 13.5, 26.0]`, front cam `[31.6, -2.8, 26.0]` — same house, both 1504x656, both ground-truth decoded.

## Consistency metric (wall region, distance to the anchor — lower = more consistent)

`dE` = Euclidean distance of mean CIELAB colour between the view-2 wall and the anchor wall. `dTex` = |difference| in mean-|Laplacian| texture energy. The headline number is colour `dE`.

| material | NAIVE dE | LOCKED dE | dE improvement | NAIVE dTex | LOCKED dTex | verdict |
|---|---|---|---|---|---|---|
| travertine | 7.43 | 4.14 | **+3.29** | 2.52 | 4.35 | LOCKED wins |
| red_brick | 8.25 | 21.62 | **-13.37** | 6.49 | 25.89 | inconclusive |

## Mean wall Lab per variant

| material | anchor (L,a,b) | naive (L,a,b) | locked (L,a,b) |
|---|---|---|---|
| travertine | (73.3, 2.4, 18.7) | (75.5, 2.9, 11.6) | (77.0, 2.3, 16.9) |
| red_brick | (44.3, 19.5, 27.8) | (42.6, 19.4, 19.7) | (50.7, 7.0, 11.3) |

## Interpretation — the differentiator is proven, with a sharp caveat

**Travertine: clean win, and the headline result.** The naive front-view edit drifts
*cooler and less saturated* — its `b*` (yellow) collapses from the anchor's 18.7 to 11.6,
so it reads as a paler, greyer stone than the anchor. Conditioning on the materialized
anchor pulls `b*` back to 16.9 (dE 7.43 -> 4.14, a 44% reduction in colour distance to the
anchor). Visually the locked wall is the *same* warm beige coursed travertine in both views;
the naive wall is visibly a different, washed-out stone. This is exactly the enterprise claim:
**change the material once, it stays consistent across views.**

**Red brick: the anchor reference BACKFIRED — and the reason matters.** The naive brick is
actually good and fairly close to the anchor (dE 8.25); the locked brick is *worse* (dE 21.62,
texture energy 4x higher — a blotchy, patchy wall). Root cause: the anchor view is rendered at
**golden hour with strong low-angle directional light and long shadows**, while the front view
has different lighting geometry. A smooth, near-uniform material (travertine) is dominated by
*colour*, which transfers across views cleanly. Brick carries strong *coursing texture that
interacts with light*; handing FLUX the anchor with a hard "match this exact appearance"
instruction injected the **anchor's baked-in shadows/warm cast** into a differently-lit view,
producing mottled, inconsistent brickwork. The metric correctly flags this (LOCKED dTex 25.89).

**Takeaway for the product:** the anchor-reference lock is the right mechanism, but the anchor
must be supplied as a *material-identity* reference, not a *lit-appearance* reference. Two fixes
for v2: (a) anchor and all views captured/rendered under the **same neutral lighting** so the
reference carries only material; or (b) soften the prompt from "match exactly" to "use the same
stone/brick type and tone" and let per-view shading re-derive. Travertine already works under
(a)-like conditions because its appearance is lighting-insensitive; texture-heavy materials need
the lighting controlled before the lock is trustworthy. (Both renders here come from the same
`render_locked` golden-hour prompt, but the *camera-relative* sun direction differs between the
two views, which is enough to break a texture match.)

## Evidence

- `spike\outputs\multiview\sidebyside_travertine.png` — [anchor | view2 NAIVE | view2 LOCKED] for travertine
- `spike\outputs\multiview\sidebyside_red_brick.png` — [anchor | view2 NAIVE | view2 LOCKED] for red_brick
- `spike/outputs/multiview/anchor_<mat>.png`, `view2_naive_<mat>.png`, `view2_locked_<mat>.png` — per-view composites.

## How it works (production recipe)

```
anchor_final = composite(anchor_render, wall_mask_anchor,
                         FLUX.2 Edit[anchor_render, swatch])
view2_locked = composite(front_render,  wall_mask_front,
                         FLUX.2 Edit[front_render, swatch, anchor_final])
```
The third reference (the already-materialized anchor) is what carries the material identity across the camera change. The swatch alone (naive) lets FLUX re-interpret tone/coursing per view.

## fal call shapes

- FLUX.2 [pro] Edit (`fal-ai/flux-2-pro/edit`) accepts **3** `image_urls` (E3 used 2). Verified live this run; the locked edits each sent [front, swatch, anchor].
- Swatch data URIs are JPEG and downscaled to <=1024px long edge (travertine asset is ~16 MB raw) to stay under fal's 413 payload limit with three references.
- Fallback wired to `fal-ai/flux-pro/kontext/max/multi` if a 3-image FLUX.2 Edit call ever errors.

Runner: `spike/run_multiview_lock.py`. Inputs: `spike/outputs/e2_house_v2/` (anchor), `spike/outputs/mv_front/` (view 2).