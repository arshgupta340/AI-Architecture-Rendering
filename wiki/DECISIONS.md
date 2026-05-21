---
type: log
updated: 2026-05-19
---

# Decision Log

Append-only. **Newest at top.** One entry per non-obvious or non-reversible choice — what we picked, what we considered, why.

Each entry follows the same shape so it can be scanned in 15 seconds:

```
## YYYY-MM-DD — <decision title>           {anchor: kebab-case-title}
**Decision:** the choice, in one sentence.
**Context:** what prompted it.
**Alternatives considered:** 1–3 bullets, briefly.
**Reasoning:** why this over the alternatives.
**Revisit if:** what would invalidate this.
```

---

## 2026-05-20 — Defend against Gemini malformed bbox JSON; never lose paid data to schema validation {#gemini-bbox-malformed-json}

**Decision:** Wherever we call `tag_regions` (or any Gemini structured-output call), the caller must persist the raw response *before* attempting pydantic validation, and must use a tolerant JSON parser that handles known model output bugs (currently: duplicate `y` keys in bboxes). Schema validation is best-effort; data loss on schema failure is not acceptable.

**Context:** T22 ran `tag_regions` on 4 new (screenshot, photoreal_render) pairs. 3 of 4 returned clean schema. On urban_exterior, every bbox came back as `{"x": 499, "y": 361, "w": 25, "y": 425}` — duplicate `y` key, no `h`. JSON parsers silently drop the first key on duplicates, so pydantic saw `{x, y, w}` and threw 37 validation errors. Reproducible on a $0.01 retry (same screenshot, same render, same prompt → same malformation). 47 regions worth of paid data would have been lost if the raw response hadn't been saved. The `spike/salvage_urban_tags.py` script recovered 44 of 47 via `json.loads(..., object_pairs_hook=...)` that promotes the second `y` to `h`.

**Alternatives considered:**
- Trust schema validation and re-call on failure — rejected; the malformation is reproducible, so retries waste money without recovering data.
- Rewrite the `tag_regions` prompt to avoid the bug — uncertain whether it would help (we don't know what's triggering it on this specific image), and risks regressing the cases that already work.
- Accept the loss as a one-off — rejected; with $0.01 per Gemini call, every paid response is data that future eval and prompt iteration depends on. Schema failures will recur as the model evolves.

**Reasoning:** Save raw, then attempt validation, then attempt tolerant repair, then surface. Cost: a few lines of code and a small disk overhead per call. Benefit: never throw away paid data because of a schema mismatch.

**Revisit if:** Gemini stops producing the duplicate-key malformation entirely (in which case we still want the safety net); or we discover the malformation has a meaning other than "duplicate key" (e.g., maybe the second `y` is actually `y2` not `h`, in which case the salvage hook's interpretation needs revision).

---

## 2026-05-20 — tag_regions requires the photoreal render, not a raw screenshot {#tag-regions-needs-photoreal}

**Decision:** `tag_regions` is only invoked on `(screenshot, photoreal_render)` pairs in production. Calling it on a raw 3D-model screenshot alone (e.g., for a pre-render preview) is not supported by Gemini 3 Pro at the quality level the Spike 4 pipeline needs.

**Context:** T21 ran the revised `tag_regions` prompt on 5 images: pair 1 was the existing T17 (screenshot, render) pair; pairs 2–5 were 4 new screenshots passed as both screenshot and render (budget would not stretch to ~$0.20 of Nano Banana renders for the 4 new shots). Pair 1 cleanly cleared the Spike 3 gate with 94 tight regions including 77 per-window bboxes. Pair 4 (urban exterior screenshot) returned 25 regions and **zero windows** despite the screenshot showing many visible bright-blue window blocks. Pair 5 (complex-windows screenshot) returned 97 regions but zero mullions despite the entire facade being a mullion grid.

**Alternatives considered:**
- Make `tag_regions` accept a single-image mode (cheaper for previews) — rejected because it underperforms badly on raw screenshots; supporting a degraded mode invites users into a UX they will then judge the product on.
- Accept the screenshot-only quality and design the UI to mask it — rejected; the whole point of the Photoshop-for-Architects UX is clean per-element masks for material swap, and "missed every window" is a categorical failure for that UX.

**Reasoning:** The photoreal render gives Gemini the visual context it needs to distinguish glazing (translucent, reflective) from solid wall, mullion (thin frame) from wall strip, and door (passage) from balcony glazing. Without that context the model treats the screenshot's color blocks too literally and produces categorical misses. Spike 4's pipeline already runs render before tagging, so this decision matches what the production flow does anyway — it makes the constraint explicit.

**Revisit if:** Gemini 4 / next-gen VLM lifts performance on raw screenshots; or we add a single-image preview mode and find a prompt variant that doesn't degrade. T22 will provide a real production-shape benchmark on the 4 new screenshots.

---

## 2026-05-19 — Knowledge wiki as single source of truth {#wiki-ssot}

**Decision:** Stand up `wiki/` at repo root as the project's SSOT. Plain markdown, Obsidian-friendly. Existing docs (`docs/plans/`, `spike/TASKS.md`, `spike/REPORTS/`, `spike/PROVIDERS.md`) stay where they are and the wiki links to them. Every chat appends to [[SESSIONS]] at session end; non-obvious choices also append here.

**Context:** Project knowledge was scattered. New agents re-derived "what is B1?", "Photoshop or VLM?", "what's blocked?" every session. No decision log existed.

**Alternatives considered:**
- Consolidate everything under `docs/wiki/` — breaks existing links and rewrites history references.
- Full Obsidian vault with `.obsidian/` committed — clutters git, only helps Obsidian users.
- Skip wiki, just improve `CLAUDE.md` — doesn't solve the "where do decisions live" gap.

**Reasoning:** Lowest churn (nothing existing breaks) + Obsidian-friendly without forcing Obsidian on anyone + cross-linking avoids duplication that would go stale.

**Revisit if:** wiki turns into another stale corner. The session-log protocol in `CLAUDE.md` is what keeps it alive — if it stops being followed, the wiki will rot.

---

## 2026-05-19 — Coordinate-space rescaling is owned by the *consumer*, not the model {#coord-space-consumer}

**Decision:** Treat Gemini 3 Pro's normalized 0–1000 bbox output as the source of truth. Local code (`test_vlm_tagging.py:_draw_regions`, `end_to_end_edit.py` before SAM2) rescales to pixel space.

**Context:** T17 smoke test revealed Gemini returns bboxes in 0–1000 normalized space regardless of input image dimensions. Drawing code was treating them as pixel coords; every bbox was drawn at ~79% width / ~118% height.

**Alternatives considered:**
- Instruct Gemini to return pixel coords directly. VLMs often ignore this instruction.
- Override the schema to enforce pixel ranges. Same problem — the model normalizes anyway.

**Reasoning:** Trust the model's documented behavior (0–1000 is the standard VLM spatial output). Rescaling on the client side is deterministic and testable; relying on prompt compliance is not.

**Revisit if:** Gemini changes its default spatial output convention, or we switch tagger to a model that emits pixel coords natively.

See [[references/coordinate-systems]] and the T17 report.

---

## 2026-05-17 — Overnight scaffolding via constrained subagent {#overnight-scaffolding}

**Decision:** Build Spike 2.5/3/4 scaffolding overnight via the `spike-builder` subagent. Agent allowed to edit only `spike/**`, allowed git status/diff/add/commit (no push/reset/rebase/merge), zero network calls except a single T17 Gemini smoke test (~$0.01). Hard $0.05 cap.

**Context:** 20 tasks of scaffolding (renderer clients, scoring, drivers, tests) would have taken multiple manual sessions. Subagent with tight boundaries can ship it in one night.

**Alternatives considered:**
- Manual session-by-session implementation. Slower, but more oversight per step.
- Less-constrained agent. Higher risk of unwanted edits outside `spike/` or premature live API calls.

**Reasoning:** Tight boundaries (edit scope, git ops, network) plus per-task report contract keeps blast radius small. Bills only $0.01 for the entire run.

**Revisit if:** subagent produces poor-quality scaffolding (it didn't — T01–T20 all passed), or if we ever need to repeat this for another spike phase.

See `docs/plans/overnight-spike-builder.md`.

---

## 2026-05-15 — Branch model: overnight → renderer-bakeoff → main {#branch-model}

**Decision:** Overnight work goes on `overnight/spike-builder-2026-05-17`. Merges into `renderer-bakeoff` only after user review. `main` is sacred — never direct-commit, never force-push, never `--no-verify`, never `--amend` on shared history.

**Context:** Multi-day scaffolding work with an autonomous agent. Need a quarantine branch.

**Alternatives considered:**
- Direct to `renderer-bakeoff`. Less isolation if the agent makes a mistake.
- PR-based workflow. Adds friction for a solo developer.

**Reasoning:** Branch-of-a-branch gives a review checkpoint without the GitHub PR overhead.

**Revisit if:** team grows beyond solo dev (need real PR workflow), or scaffolding phase ends.

---

## 2026-05-10 — B1 → B2 → B3 cascade before any GPU spend {#b-cascade}

**Decision:** Order Spike 2.5 work by cost. B1 (characterize Nano Banana failures, ~$0.12) → B2 (try cheap prompt fixes, ~$0.50) → B3 (multi-renderer bake-off, ~$3–5). Each phase has a clear gate; only escalate if the prior phase doesn't resolve the issue.

**Context:** Spike 2 showed Nano Banana has critical failures. We could (a) jump straight to a multi-renderer bake-off and burn $3–5 on the first try, or (b) characterize the failure mode and try cheap fixes first.

**Alternatives considered:**
- Jump to B3 immediately. Faster but expensive if a B2-style fix would have sufficed.
- Skip B1, go to B2. Lose the deterministic-vs-stochastic question.

**Reasoning:** Cheapest information first. B1 tells us if the failure is even fixable in-renderer; B2 tries the cheapest fix; B3 is the expensive escape hatch.

**Revisit if:** B1/B2 are taking longer than expected (sunk-cost trap — be willing to skip ahead).

---

## 2026-04 — Empirical multi-renderer bake-off, not a single renderer bet {#empirical-bake-off}

**Decision:** Spike 2.5 B3 evaluates 8 renderer candidates (Nano Banana Pro, FLUX Canny Pro, FLUX Kontext Pro, Magnific Mystic, Qwen-Image-Edit, HiDream-E1, Recraft V3 native, Recraft V3 via Replicate) on the same input and picks by score, rather than committing to one based on first impressions.

**Context:** Spike 2 showed Nano Banana Pro at ~90% macro alignment but with critical-severity failures (invented windows, corner wraparounds altering building mass). Picking the next renderer without comparison would just repeat the gamble.

**Alternatives considered:**
- Bet on FLUX Canny Pro because of its explicit edge-conditioning. Single point of failure if it doesn't generalize.
- Bet on Magnific because of its arch-viz reputation. Highest per-call cost, hard to justify without comparison.
- Bet on whichever model "looked best" on a casual test. Confirmation bias.

**Reasoning:** Empirical comparison on the same input with the same rubric is the only honest way to choose. The cost ($3–5 for one round) is much smaller than committing to the wrong renderer for months.

**Revisit if:** B3 finishes and one renderer is a clear winner (then this decision retires). Or if a new renderer arrives that we'd want to add to the field.

---

## 2026-04 — VLM (Gemini 3 Pro) for region tagging, not color-coded mask passes {#vlm-tagging}

**Decision:** Use a Vision-Language Model on the *render* to identify regions (wall / window / mullion / door / floor / ceiling / etc.). Do not bake material IDs or color codes into the 3D model.

**Context:** Need to know which region the user clicked. Two options: (a) tag the render with a VLM, (b) ask the host application (Rhino / SketchUp / Revit) to render a per-material-ID color pass alongside the shaded screenshot.

**Alternatives considered:**
- **Color-coded mask passes.** Requires plugin work per host, and the encoding (one color per region) bakes geometry assumptions into the input. Doesn't generalize across renderers either — different renderers can blur or fail to preserve color discontinuities.
- **Manual mask drawing.** Defeats the "click a wall" UX hypothesis.

**Reasoning:** VLM reads pixels, so it generalizes across hosts and renderers. The architect already gives us a screenshot — no extra rendering step required from their tool. Cost is ~$0.01/tag, acceptable.

**Revisit if:** VLM tagging quality remains poor after T21 prompt revision + 5-screenshot eval. See [[STRATEGY#Q2]] for fallback options.

---

## 2026-03 — Shaded model viewport screenshot as primary input (not line drawings) {#shaded-screenshot-input}

**Decision:** Input to the pipeline is a *shaded* viewport screenshot from the architect's 3D modeling tool — not a line drawing, axonometric, or pure wireframe.

**Context:** Multiple input formats are possible from 3D modelers. Need to pick one.

**Alternatives considered:**
- **Pure line drawings (axon / hidden-line).** Gives geometry but no surface or material cues.
- **Materials-only render (matte shaded).** Loses lighting cues.
- **Photorealistic render from the host.** Defeats the purpose — we're trying to *produce* photorealism downstream.

**Reasoning:** Shaded screenshots carry both geometry edges *and* color discontinuities. The renderer gets geometry to preserve; the VLM gets region boundary hints. One input, two downstream uses.

**Revisit if:** real-world architect workflows produce a different default input that we want to support natively.

---

## 2026-02 — Dropped text-to-image + click-segmentation (Spike 1 pivot) {#dropped-text-to-image}

**Decision:** Killed the original architecture: user prompts a text-to-image model to generate a building, then clicks elements in the resulting image to identify them. Replaced with: user provides a 3D-model viewport screenshot, we re-render it preserving geometry, then a VLM tags regions.

**Context:** Spike 1 tried the text-to-image + click-segmentation flow. Two compounding generative steps kept failing — the model invented geometry that was then hard for downstream segmentation to identify.

**Alternatives considered:**
- Keep text-to-image but with better prompts. The compounding-error problem is structural; prompt tuning doesn't fix it.
- Text-to-image with a separate "redraw to fix" pass. More compounding.

**Reasoning:** Architects don't think in prompts — they already have geometry from their 3D model. Anchoring the input to that geometry eliminates one whole class of compounding failures. The renderer's job becomes "preserve this geometry, just change the surface treatment" — a much more constrained problem.

**Revisit if:** text-to-image models reach a quality where they preserve a sketched layout precisely (we'd still probably prefer the model-anchored flow, but it stops being categorically required).

---
