---
type: spike
status: scaffolded (T18–T20 done); awaiting live runs
budget: ~$0.50/run (+ Modal GPU $0.35–0.70)
gate: subjective — does the result feel like the product hypothesis?
---

# Spike 4 — End-to-end edit pipeline

**Status:** scaffolding complete (T18–T20). Mock tests green. **No live runs yet.** Blocked on [[spike-2.5]] renderer pick + [[spike-3]] gate pass + Modal authorization.

## Hypothesis

Chaining the per-step results from earlier spikes — render → tag → segment → apply material → composite — produces a single material-swap that feels like the product hypothesis: an architect clicks a wall, picks travertine, and the wall surface re-renders coherently while everything else stays untouched.

## Pipeline

```
screenshot ──► render_from_model_view ──► tag_regions ──► (pick region by label)
                                                              │
                                                              ▼
                                                          segment (bbox prompt)
                                                              │
                                                              ▼
                                                        apply_material (FLUX Fill / SD Inpaint)
                                                              │
                                                              ▼
                                                        composite (alpha-aware paste)
                                                              │
                                                              ▼
                                                          final image
```

## Driver

`spike/end_to_end_edit.py`:

```
--screenshot <path>        input model-viewport screenshot
--region-label <label>     e.g. "wall"
--material <path>          path to swatch tile
[--dry-run]                default; prints call graph, no spend
[--live]                   actually invoke Modal
```

Default `--dry-run` prints the call graph; `--live` warns with cost estimate (~$0.50) before invoking.

## Building blocks (all built)

- **`spike/cache.py`** — `get_or_compute(key, fn, scope)` with disk persistence under `spike/.cache/<scope>/<key>.bin`. Avoid re-running expensive Modal calls during iteration.
- **`spike/composite.py`** — `paste_tile(base, mask, tile) -> bytes`. Alpha-aware PIL composite. Reuses idioms from `modal_app.py:composite()`.
- **`spike/modal_app.py`** — `render_from_model_view`, `tag_regions`, `segment` (point or bbox), `apply_material` (SD Inpainting + material conditioning).

## Tests (T20)

`spike/tests/test_end_to_end.py` mocks every Modal function. Asserts:

- Calls happen in pipeline order.
- Region matching picks the correct region by label.
- Output composite is non-empty PNG bytes.

Cache is redirected to `tmp_path` so tests don't poison the real cache.

## What's blocking the live run

1. **Renderer not yet chosen.** [[spike-2.5]] B3 must produce a winner first.
2. **Tagger gate not passed.** [[spike-3]] T21 must succeed (coord fix + ≥4/5 screenshots scoring) before SAM2 gets usable bboxes from real tagger output.
3. **Modal authorization.** GPU spend is $0.35–0.70/run plus ~$0.50 in API calls. Outside the $0.05 session cap.

## Known concerns for the live run

- **SAM2 mask quality from VLM bboxes.** Loose bboxes (per T17 Issue C) → SAM2 segments whatever's most salient inside the box → could grab the wrong thing. Mitigation: improve tagger first (T21), or add a point-prompt refinement step.
- **Composite blending.** Material seams at region boundaries may need feathering / color-matching. `composite.py` is a starting point; tune after the first real run shows the failure mode.
- **Region overlap.** If two regions overlap (e.g., a mullion inside a window), material applied to "window" must not also paint over the mullion. The pipeline currently picks one region; multi-region applies are future work.

## Success looks like

Subjective gate: when an architect (real user, not the developer) looks at the result and says "yes, that's what I asked for." No invented walls. No bleed across regions. Lighting consistent with the rest of the render.

## What follows a successful Spike 4

See [[ROADMAP#M3]] and beyond. Next-bottleneck candidates: material library size, layer/undo data model, web canvas MVP, plugin scaffolding.

## See also

- [Master plan § Pipeline](../../docs/plans/master-plan.md).
- [[spike-2.5]] — provides the renderer.
- [[spike-3]] — provides the tagger.
- [Task board T18–T20](../../spike/TASKS.md).
