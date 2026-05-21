---
type: spike
status: done (incumbent baseline; superseded by spike-2.5)
budget: ~$0.04/render
gate: ~90% macro alignment, no critical failures
---

# Spike 2 — Screenshot-to-render fidelity (Nano Banana Pro baseline)

**Status:** done. Established the incumbent. Critical failures motivated [[spike-2.5]].

## Hypothesis

A shaded viewport screenshot from the architect's 3D tool, fed to Gemini 2.5 Flash Image ("Nano Banana Pro") with a geometry-preservation prompt, will produce a photorealistic render that preserves the building's mass, window layout, and major surface boundaries.

## What was done

- Set up Modal function `render_from_model_view` calling Gemini 2.5 Flash Image with the screenshot + a tight geometry-pinning prompt.
- Ran on `spike/test_assets/model_views/building.png` at a baseline seed.
- Output: `spike/outputs/spike2/render.png`. Also computed Canny-edge overlays vs source for manual inspection.

## What we found

- **Macro alignment ~90%.** Overall building silhouette, window grid, floor count usually preserved.
- **Critical-severity failures** — a non-trivial fraction of renders:
  - **Invented windows.** Extra window introduced where the screenshot showed solid wall.
  - **Corner wraparounds.** Volumes wrapping around a corner in a way the screenshot doesn't show, changing the building mass.
  - **Mullion inconsistency.** Vertical mullions occasionally missing or doubled.
- **Lighting plausible.** Where geometry was preserved, the lighting / material choice usually looked photoreal.
- **Stochasticity.** Same prompt, different seeds gave noticeably different failure modes — failures aren't deterministic to the prompt, which matters for the cheap-fixes question in [[spike-2.5#B1]].

## Why this isn't good enough

Critical failures change the *building*, not just the *render*. An architect using this in production would need to manually inspect every render for invented geometry — defeating the "click and re-render" UX. We need a renderer that produces zero critical failures, not just an average score.

## What this informed

- **[[spike-2.5]]** — characterize the failure mode (B1), try cheap fixes on the incumbent (B2), compare against challengers (B3).
- **[[DECISIONS#empirical-bake-off]]** — don't bet on a single replacement; run a comparison.
- **Failure taxonomy** in [[GLOSSARY]] (critical / high / medium / low).

## Artifacts

- Code: `spike/modal_app.py` (`render_from_model_view` function), prompt embedded in that function.
- Outputs: `spike/outputs/spike2/render.png`, source + edge overlays in same folder.

## See also

- [Master plan § Renderer fidelity risk](../../docs/plans/master-plan.md).
- [[spike-2.5]] — the bake-off that's now choosing the production renderer.
