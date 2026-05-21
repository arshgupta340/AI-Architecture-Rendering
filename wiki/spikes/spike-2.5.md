---
type: spike
status: in-progress (B1 scoring pending, B2 sweep pending, B3 awaiting API keys)
budget: $0.12 (B1) + $0.50 (B2) + $3–5 (B3)
gate: zero critical failures + ≥7/10 manual photorealism on the winner
---

# Spike 2.5 — Multi-renderer bake-off

**Status:** scaffolding done (T01–T12). B1 outputs generated, B2 tightened-prompt sweep run, B3 awaiting user API keys. **Gate not yet decided.**

## Goal

Replace or validate the [[spike-2]] incumbent (Nano Banana Pro). Spike 2 hit ~90% macro alignment but produced critical-severity failures (invented windows, corner wraparounds). We need a renderer with **zero critical failures** at acceptable cost.

## Approach

Three phases, ordered by cost: characterize → cheap-fix → bake-off. Cheapest information first. See [[DECISIONS#b-cascade]].

```
B1 ($0.12)        B2 ($0.50)         B3 ($3–5)
characterize  →   try cheap fixes →  compare 8 candidates
the failure       on the incumbent   pick the winner
mode
```

---

## B1 — Baseline Characterization

**Goal:** Is the Nano Banana failure deterministic (prompt issue) or stochastic (model randomness)? This sets the cost-of-fix expectation.

**Method:** Run Nano Banana Pro on `building.png` four times at seeds 42 / 100 / 200 / 300. Build comparison grid + Canny-edge overlays. Manual scoring against a rubric for: silhouette IoU, edge density delta, invented-element count, mullion correctness.

**Code:** `spike/run_b1_baseline.py`.

**Outputs:** `spike/outputs/spike2_5/b1/` — `nb_seed_*.png`, `nb_seed_*_overlay.png`, `comparison_grid.png`, `scoring_rubric.json`.

**Status:** seed renders + overlays generated. **Manual scoring pending** — `scoring_rubric.json` is the template; architect fills it in. Initial qualitative read: failures vary by seed → mostly stochastic, but the *types* of failure are consistent (invented windows, corner wraparounds appear across seeds).

**Implication:** if failure is stochastic, B2 cheap fixes have a real chance of working. If it were deterministic to the prompt, we'd already need B3.

---

## B2 — Cheap Interventions

**Goal:** Can we eliminate critical failures *without changing renderer*?

**Method:** Four prompt-level variants, all on Nano Banana Pro:

1. **`tightened_prompt`** — inject hard geometry-pinning constraints into the prompt.
2. **`higher_res`** — resize input to 1920px long edge before sending.
3. **`multi_region_annotated`** — tightened prompt + per-facade region callouts.
4. **`multi_pass`** — first NB render → Gemini tags elements → second NB render with count-derived constraints (e.g., "preserve exactly N windows on the left facade").

Default `--dry-run` prints what each call would send. `--live` is opt-in and gated on `GOOGLE_API_KEY`.

**Code:** `spike/run_b2_variants.py`. Subsidiary sweep: `spike/run_b2_tightened_sweep.py`.

**Outputs:** `spike/outputs/spike2_5/b2/` (tightened variant), `spike/outputs/spike2_5/b2_v1_constraints_only/` (constraints-only subset).

**Status:** tightened-prompt sweep run; **evaluation pending**. Other three variants written but not run live (budget conservation). Comparison-vs-B1 grids generated for the variants that ran.

**Implication if B2 succeeds:** we keep Nano Banana, save B3 budget, and Spike 4 plugs into the incumbent.

**Implication if B2 fails:** escalate to B3.

---

## B3 — Multi-Renderer Bake-Off

**Goal:** Compare every candidate renderer on the same input and pick the winner.

**Field (8 candidates):**

| Class | Backend | Env | $/call | Why in the field |
|-------|---------|-----|--------|------------------|
| `NanoBananaProRenderer` | Gemini 2.5 FI / Modal | `GOOGLE_API_KEY` | $0.039 | Incumbent, best B2 variant. |
| `FluxCannyProRenderer` | BFL | `BFL_API_KEY` | $0.05 | Server-side Canny conditioning — strong geometry preservation. |
| `FluxKontextProRenderer` | BFL | `BFL_API_KEY` | $0.05 | Instruction-edit variant. |
| `MagnificMysticRenderer` | Magnific | `MAGNIFIC_API_KEY` | $0.10 | Strong arch-viz prior. |
| `QwenImageEditRenderer` | Replicate | `REPLICATE_API_TOKEN` | $0.03 | Instruction-based, good layout preservation. |
| `HiDreamE1Renderer` | Replicate | `REPLICATE_API_TOKEN` | $0.04 | Geometry-friendly instruction-edit. |
| `RecraftV3Renderer` | Recraft native | `RECRAFT_API_TOKEN` | $0.04 | — |
| `RecraftV3ReplicateRenderer` | Replicate | `REPLICATE_API_TOKEN` | $0.04 | Same model, different backend for latency/quality comparison. |

**Method:** `spike/compare_renderers.py --input <screenshot>` fans out to every renderer whose env is set, saves outputs under `spike/outputs/spike2_5/b3/<renderer>.png`, builds comparison + overlay grids, emits `scores.csv` for manual scoring.

**Default behavior with no keys set:** prints a manifest of what *would* run, writes nothing.

**Status:** scaffolding complete (T08), all 8 renderer classes implemented + mock-tested (T02–T06, T11). **Awaiting user to acquire API keys** — see [PROVIDERS.md](../../spike/PROVIDERS.md) for signup links. No live B3 runs yet.

**Exit gate:** one renderer with zero critical failures + manual photorealism ≥7/10 on ≥2 test images.

**Fallback if gate fails:** see [[STRATEGY#Q1]] — hybrid two-pass, or accept-and-correct UX.

---

## Scoring

Pure-CV scoring helpers in `spike/scoring.py`:

- `silhouette_iou(img_a, img_b)` — Canny + flood-fill silhouette IoU.
- `edge_density_delta(img_a, img_b, region_bbox=None)` — edge-pixel ratio comparison.
- `count_windows(render_bytes)` — Gemini-based stub, env-gated, not invoked in pure CV pass.

Manual rubric fields (in `scoring_rubric.json` template): silhouette IoU, invented-element count, mullion correctness, lighting plausibility, material plausibility, photorealism 1–10.

## Open questions

- Will the cheap B2 fixes actually reduce critical failures? Pending manual eval.
- If B3 produces a tie, what's the tie-breaker? Likely cost-per-call.
- Is one screenshot enough for B3, or do we need ≥2? Current plan says ≥2.

## See also

- [[spike-2]] — what motivated this spike.
- [[DECISIONS#empirical-bake-off]], [[DECISIONS#b-cascade]] — strategy decisions.
- [[ROADMAP#M2]] — what triggers the B3 live run.
- [Task board T01–T12](../../spike/TASKS.md) — granular task status.
