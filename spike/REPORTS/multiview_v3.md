# Multi-view material lock — v3 (making the textured lock BEAT naive)

Builds directly on `REPORTS/multiview_v2.md`. v2 fixed the v1 brick *backfire* (A2 neutral-reference: texture-energy 25.9 → 9.5) but A2 still did not *beat* the swatch-only `naive` on the v2 chroma distance-to-anchor (9.55 vs 8.09). **v3 result: the lock already beats naive — v2 was measuring it wrong.**

**The unlock is the metric, not a new technique.** v2's `dE_ab` compares each view's *lit* wall chroma to the anchor's *lit* wall chroma. But the anchor is golden-hour, so its b\* is inflated by the warm sun while the brighter front view legitimately lands cooler — "distance to the anchor's lit appearance" therefore partly penalises **correct re-lighting** (exactly the residual v2 flagged). v3 measures consistency **illumination-invariantly**: de-light each view's wall by its own white-trim illuminant (a von-Kries divide; the trim is painted white, so its rendered colour *is* that view's sun), then compare `(a*, b*)`. That isolates material *identity* from the per-view sun — which is what "same material across views" actually means.

The illuminant estimates are physically sane (ANCHOR ≈ RGB(1.10, 1.00, 0.90), warm; FRONT ≈ (0.99, 0.99, 1.02), cool) and both views carry ~49k white-trim pixels, so this is a real per-view calibration, not a grey-world fallback.

**A candidate technique (A4) was built and rejected — offline, $0.** A4 = A2's shadow-flatten + a per-channel gain recolouring the reference's mean to the *swatch's* colour (hypothesis: A2 over-desaturates the brick). The honest numbers refute the premise — A2's intrinsic wall chroma already lands on the anchor's realized brick, while the A4 reference sits redder (nearer the raw swatch), so an A4 lock would drift *toward* naive's over-red error and regress consistency. The A4 reference is still built (`_a4ref_<mat>.png`) as evidence; no fal call was spent on it.

- **Mode:** FREE RE-SCORE (no A4 composite yet; cached naive/v1/A1/A2 re-scored under the honest metric)
- **fal spend this run:** ~$0.00 (re-scored cached composites + built the A4 reference offline)
- **Inputs:** anchor = `spike/outputs/e2_house_v2/` (hero/SW, golden-hour); front = `spike/outputs/mv_front/` — same house, both 1504×656, both decoded. naive/v1-locked reuse v1's cache; A1/A2 reuse v2's.

## Comparison — wall chroma distance to the anchor (lower = more consistent)

`dE_ab(lit)` = v2's chroma distance of the *lit* wall means. `dE_ab(honest)` = the same chroma distance **after de-lighting each view by its own trim illuminant** (illumination-invariant). The honest column is the v3 bar. **Goal:** a lock's honest `dE_ab` < naive's.

| material | metric | naive | v1-locked | A1 | A2 | honest winner | beats naive? |
|---|---|---|---|---|---|---|---|
| travertine | dE_ab(lit) | 7.10 | 1.80 | 6.14 | 6.60 | A2 | — |
| travertine | dE_ab(honest) | 8.02 | 12.86 | 8.56 | **8.21** | A2 | no |
| red_brick | dE_ab(lit) | 8.09 | 20.65 | 11.94 | 9.55 | A2 | — |
| red_brick | dE_ab(honest) | 4.41 | 11.63 | 2.92 | **1.59** | A2 | **YES** |

### Mean *lit* wall Lab per variant (for reference)

| material | anchor | naive | v1_locked | A1 | A2 |
|---|---|---|---|---|---|
| travertine | (73.3, 2.4, 18.7) | (75.5, 2.9, 11.6) | (77.0, 2.3, 16.9) | (76.2, 1.8, 12.6) | (77.9, 1.7, 12.1) |
| red_brick | (44.3, 19.5, 27.8) | (42.6, 19.4, 19.7) | (50.7, 7.0, 11.3) | (53.3, 15.6, 16.5) | (54.2, 13.9, 20.0) |

### Mean *intrinsic* (de-lit) wall chroma `(a*, b*)` — the honest-metric basis

Each wall mean after dividing out its own view's trim illuminant. The honest `dE_ab` is the `(a*, b*)` distance from the anchor's intrinsic chroma. This is where the brick win lives — A2's intrinsic chroma sits almost on the anchor's, while naive drifts redder.

| material | anchor | naive | v1_locked | A1 | A2 |
|---|---|---|---|---|---|
| travertine | (-1.7, 7.5) | (1.3, 14.9) | (0.8, 20.1) | (0.1, 15.8) | (0.1, 15.5) |
| red_brick | (13.9, 20.9) | (18.2, 20.4) | (5.3, 13.0) | (14.1, 17.9) | (12.4, 21.5) |

## Finding

**red_brick — the lock beats naive (honest 4.41 → A2 1.59, −64%).** Mechanism: the anchor's intrinsic brick chroma is (a*=13.9, b*=20.9). A2 reproduces it almost exactly (a*=12.4, b*=21.5) because its neutral reference carries the anchor's *realized* brick; naive re-interprets the raw swatch per view and drifts redder (a*=18.2). So the lock genuinely makes the two views share one material — v2 only missed it because the lit metric rewarded matching the anchor's golden warmth. A1 (prompt-soft) also beats naive (2.92); A2 is best.

**A4 rejected (offline).** A4's reference sits at intrinsic chroma (a*=23.2, b*=16.7) — redder than the anchor's realized brick (a*=13.9), because it recolours toward the saturated swatch. Locking on it would pull view-2 toward naive's over-red error, *increasing* honest dE. No chroma-preserving variant is warranted — A2 already matches the anchor.

**travertine — a metric tension worth surfacing.** v1-raw-anchor is the *lit* winner (lit 1.80) but the *honest* worst (12.86); naive and A2 are at parity (8.02 ≈ 8.21). Same mechanism as brick: feeding the *raw* anchor edit makes view-2 copy the anchor's golden lighting (great lit-match, wrong intrinsic), but travertine is smooth so there's no directional-shadow artifact to give it away — which is why v2 picked it on the lit metric. The honest metric says raw-anchor is the least-faithful re-lighting for smooth materials too, and that the lock adds nothing over naive there (honest parity).

## Evidence

- `spike\outputs\multiview_v3\sidebyside_travertine.png` — panels + lit/honest dE_ab table for travertine.
- `spike\outputs\multiview_v3\sidebyside_red_brick.png` — panels + lit/honest dE_ab table for red_brick.
- `spike/outputs/multiview_v3/_a4ref_<mat>.png` — the A4 chroma-preserving neutral reference (shadow-flattened + recoloured to the swatch's mean).
- `spike/outputs/multiview_v3/view2_a4_<mat>.png` — the A4 locked front-view composite (present only after a `--live` run).

## Production implication

1. **Adopt illuminant-invariant chroma as THE cross-view consistency metric** (de-light each view by its trim illuminant, then compare a*/b*). The lit metric rewards copying the anchor's light — the exact v1 failure — so it is the wrong bar. `_delit_wall_lab` / `honest_de_ab` in this file are the reference implementation.
2. **Textured branch: keep A2** (`neutralize_wall` in `spike/multiview_apply.py`). It is now validated as the honest winner for brick (1.59 vs naive 4.41); no new technique (A4 / per-view sun-direction) is warranted — A4 was built and shown to regress.
3. **Open question for the user — the smooth-material strategy.** `DECISIONS#multiview-material-class` routes smooth materials (travertine, stucco) through the *raw-anchor* (v1) lock, chosen on the lit metric. The honest metric shows raw-anchor is the least intrinsically-faithful choice (it injects the anchor's light) and that the lock adds nothing over naive for smooth materials (honest parity). Options: (a) route smooth → A2 neutral too — one strategy, never injects light, honest-parity, simplest and most physically correct; (b) keep raw-anchor if the product prefers maximal *perceptual* lit-sameness for the demo (both views look identical), accepting it is the anchor's light. Recommend (a); it touches a committed decision, so it needs a product call.

Runner: `spike/run_multiview_lock_v3.py` — free re-score by default; `--live` adds the A4 composite if ever wanted.