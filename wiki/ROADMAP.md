---
type: roadmap
updated: 2026-05-19
---

# Roadmap

Near-term and medium-term milestones with entry/exit criteria. Alternates inline so we don't have to re-derive them.

The authoritative live task board is still [spike/TASKS.md](../spike/TASKS.md). This page is the *strategic* roadmap — milestones, not tasks.

---

## M1 — Spike 3 gate evaluation (T21)

**Goal:** Decide whether Gemini 3 Pro tagging is good enough to drive Spike 4's material-swap UX.

**Entry:** T17 smoke test pass (done, 2026-05-19). Coordinate-space fix in place.

**Work:**
1. Fix coordinate-space handling (Gemini's 0–1000 → pixel rescale) in `test_vlm_tagging.py:_draw_regions` and `end_to_end_edit.py`. See [[references/coordinate-systems]].
2. Revise `tag_regions` prompt in `modal_app.py` — tighter per-element bboxes, clarify `parent_id` is containment not overlap, forbid inventing elements like "door inside a window".
3. Acquire 4 additional diverse test screenshots (modern interior, traditional exterior, mixed materials, urban exterior w/ trees/cars/people).
4. Run live tagger on all 5; score each manually against the gate.

**Exit gate:** ≥80% of major elements (wall, window, mullion, floor, ceiling, door) correctly labeled with tight, pixel-accurate bboxes on ≥4/5 screenshots.

**Cost:** ~$0.05 (5 × $0.01 Gemini calls). **Brings cumulative to $0.06 — exceeds session cap; needs user authorization.**

**Alternates:**
- If can't get 5 diverse screenshots, run on 3 (the existing render + 2 new) — narrower gate, faster feedback.
- If prompt revision fails to fix wall-bbox looseness, fall back to per-mullion / per-window-pane granularity (smaller, easier-to-label units) and rebuild "wall" by subtraction.

**Fallback if gate fails:** see [[STRATEGY#Q2]] — per-region click-confirmation UX, or color-based seed segmentation fallback.

---

## M2 — Spike 2.5 B3 live bake-off

**Goal:** Pick the production renderer.

**Entry:** M1 doesn't strictly block this — they're parallelizable. But user needs to provide API keys.

**Work:**
1. Acquire keys: `BFL_API_KEY`, `MAGNIFIC_API_KEY`, `REPLICATE_API_TOKEN`, `RECRAFT_API_TOKEN` (also `GOOGLE_API_KEY` for the incumbent Nano Banana path). See [PROVIDERS.md](../spike/PROVIDERS.md) for signup links.
2. Run `spike/compare_renderers.py --input <screenshot>` on `building.png` plus ≥1 second test asset. Save outputs under `spike/outputs/spike2_5/b3/`.
3. Manual scoring against rubric — critical failure count first, photorealism (1–10) second.
4. Update `wiki/spikes/spike-2.5.md` § B3 with results + chosen winner.

**Exit gate:** one renderer with zero critical failures + manual photorealism ≥7/10 on both test images.

**Cost:** ~$3–5 for the full run (8 renderers × 2 screenshots × per-call costs). **Needs explicit user authorization.**

**Alternates:**
- If multiple renderers tie, run a tie-breaker on 2 additional screenshots before deciding.
- If all renderers fail the gate, see [[STRATEGY#Q1]] — hybrid two-pass, or accept-and-correct UX.
- If the user's budget is tight, run a $1 subset (3 cheapest challengers) first; only escalate to the full 8 if results warrant.

---

## M3 — End-to-end live edit (Spike 4)

**Goal:** Demonstrate the full pipeline working live on one screenshot: shaded screenshot → render → tag → segment → swap material → composite.

**Entry:** M1 + M2 both passed. Renderer and tagger both production-ready. Modal GPU usage authorized by the user.

**Work:**
1. Wire the selected production renderer (M2 winner) into `end_to_end_edit.py`.
2. One live run on `building.png` swapping a wall to travertine.
3. Visual inspection — does it look right? Do non-wall regions stay untouched?
4. Write up findings; identify the next bottleneck (likely material library size, or SAM2 mask quality, or composite blending).

**Exit gate:** subjective — does the result feel like the product hypothesis? If yes, move toward UI work and plugin scaffolding (web MVP per [master plan](../docs/plans/master-plan.md)).

**Cost:** ~$0.50/run live (per `end_to_end_edit.py` estimate) + Modal GPU spend ($0.35–0.70). **Needs authorization.**

**Alternates:**
- If results are close but blending is poor, iterate on `composite.py` (alpha edges, color-match correction) without re-running the full pipeline.
- If SAM2 masks from VLM bboxes are too loose, add a refinement pass (point prompts from bbox center, or click-to-refine UX).

---

## Beyond M3 (sketches, not commitments)

- **Material library seeding** — ambientCG ingest script, swatch tile generation. Currently a placeholder in the master plan.
- **Layer/undo data model** — non-destructive region→material assignments. Paper-design only today.
- **Web canvas MVP** — Next.js + Konva per the master plan stack. Don't start before M3.
- **Host plugins** — Rhino → SketchUp → Revit → Forma. Each is its own scope.

See the [master plan](../docs/plans/master-plan.md) for the full long-tail.
