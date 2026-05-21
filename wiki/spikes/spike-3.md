---
type: spike
status: T21 done — gate PASSES on photoreal pair, FAILS on raw-screenshot pairs; T22 follow-up to test 4 new screenshots in production shape pending budget
budget: $0.06 spent (T17 $0.01 + T21 $0.05). T22 would add ~$0.20.
gate: ≥80% of major elements correctly labeled with tight pixel-accurate bboxes on ≥4/5 diverse screenshots
---

# Spike 3 — VLM region tagging (Gemini 3 Pro)

**Status:** T21 complete. Gate **passes** on the (screenshot, photoreal render) pair (94 tight regions, all major label categories hit, 77 per-window bboxes vs T17's 0). Gate **fails** on raw-screenshot-only pairs — most starkly, the urban exterior screenshot returned zero windows despite having many visible blue-block window markings. Key finding: see [[DECISIONS#tag-regions-needs-photoreal]]. T22 (run Nano Banana on the 4 new screenshots, then re-tag) is the path to validate the gate on a full production-shape sample.

## Hypothesis

Gemini 3 Pro, given the screenshot + the render together, can tag every region in the render with a semantic label (wall / window / mullion / door / floor / ceiling / etc.) and a bounding box, producing a `Region[]` good enough to drive SAM2 → Spike 4's material-swap UX.

## Why a VLM and not color-coded masks

See [[DECISIONS#vlm-tagging]]. Short version: color-coded mask passes bake assumptions into the host (Rhino / SketchUp / Revit each differ) and don't survive a re-render. A VLM reads pixels and generalizes.

## Schema

`spike/schemas.py`:

```python
class BBox: x, y, w, h: int
class Region: id, label, bbox, confidence, parent_id  # LABELS = {wall, floor, ceiling, window, door, mullion, roof, ground, sky, vegetation, furniture, person, vehicle}
class TagRegionsResponse: regions: list[Region]
```

`parent_id` encodes geometric containment (e.g., a mullion inside a window). T17 found the model sometimes uses it for spatial overlap instead — see Issue E below.

## What was done (T13–T17)

- **T13** — schemas.
- **T14** — `tag_regions()` Modal function. Calls `gemini-3-pro-preview` with structured-output config.
- **T15** — `segment()` refactored to accept either point or bbox prompts (SAM2 supports both natively).
- **T16** — driver `spike/test_vlm_tagging.py` with `--dry-run` (fixture-loaded) and `--live` modes.
- **T17** — one live call against `building.png` + Spike 2 render. Cost $0.01. Schema parsed. 49 regions returned. Visualization saved.

## T17 findings — smoke test passed, gate FAILED

See [`REPORTS/T17.md`](../../spike/REPORTS/T17.md) for the full write-up. Summary:

### Issue A — Coordinate space (blocking)

Gemini 3 Pro returns bboxes in **normalized 0–1000 space**, not pixel coordinates. Render is 1259×848; bboxes max out at x≈1000, y≈1000. Visualization code (`_draw_regions`) treats these as raw pixels — bboxes drawn at ~79% width / ~118% height. SAM2 would receive equally wrong prompts.

**Fix:** rescale on the client side. See [[references/coordinate-systems]] and [[DECISIONS#coord-space-consumer]].

### Issue B — Confidence field is unusable

All 49 regions returned `confidence=0.95`. Flat → not informative → can't filter.

### Issue C — "Wall" bboxes too loose

`r1 "wall"` covered an entire right facade *including* the neighboring building's windows and balconies. As a SAM2 prompt, this is useless — SAM2 would segment whichever salient thing is inside the box.

### Issue D — Some "door" labels are wrong

Several "door" regions were actually balcony glazing on neighboring buildings, or balcony elements on upper floors of the main building.

### Issue E — Hierarchy semantics confused

One "door" was tagged with `parent_id` pointing to a "window" — geometrically incoherent. Model is using parent-child to encode spatial *overlap*, not *containment*.

## What this means

T17 is a **smoke test pass** (pipeline runs, schema validates, plausible labels for major categories) but **not a Spike 3 gate pass.** The gate requires usable bboxes on ≥4/5 diverse screenshots.

## T21 — proper gate evaluation (DONE 2026-05-20)

All four pieces of T21 work landed. Full write-up: [`REPORTS/T21.md`](../../spike/REPORTS/T21.md).

1. **Coordinate fix:** SHIPPED. `_scale_bbox_to_pixels` in `spike/test_vlm_tagging.py` and `_bbox_norm_to_pixels` in `spike/end_to_end_edit.py`. Both kept symmetric. SAM2 prompts now receive correct pixel coords.
2. **Prompt revision:** SHIPPED. `tag_regions` in `spike/modal_app.py` was rewritten with explicit 0–1000 coord declaration, tight-bbox-per-element rules, strict `parent_id` semantics (containment, not overlap), label discipline (door ≠ balcony glazing, mullion only when visible), and primary-building focus.
3. **Multi-image eval:** PARTIAL. Ran 5 Gemini calls within the $0.05 authorized budget. Pair 1 = existing (screenshot, photoreal render) pair from T17. Pairs 2–5 = 4 new screenshots passed as both screenshot and render (full production-shape eval would have needed +$0.20 for Nano Banana renders, beyond budget).
4. **Manual scoring:** SHIPPED. `spike/outputs/spike3/t21/scored_rubric.json` + the report.

### T21 results

| Image | Verdict | Notes |
|---|---|---|
| `render.png` (photoreal pair) | **PASS** | 94 regions, 77 per-window bboxes (vs 0 in T17), all major categories hit |
| `modern interior.jpg` (actually modern exterior — filename wrong) | PARTIAL | 31 regions, undercount on windows |
| `traditional exterior.jpg` (actually modern interior dining — filename wrong) | **PASS** | 16 regions, **first successful mullion detection** (4 mullions) |
| `urban exterior.png` | **FAIL** | 25 regions, **zero windows** — model couldn't read color-block windows without photoreal context |
| `complex windows - Copy.png` | PARTIAL | 97 regions (69 windows) but zero mullions on a facade that's mostly mullions |

### T17 → T21 issue movement

| Issue | T17 | T21 |
|---|---|---|
| A — Coord-space 0–1000 vs pixel | bug | FIXED (consumer-side scaling in two places) |
| B — Confidence flat 0.95 | flat | UNCHANGED (now 0.85–0.99 but variance too narrow to filter) |
| C — Wall bboxes per-facade, too loose | bug | FIXED (per-window bbox count 0 → 77 on same render) |
| D — Doors mislabeled as balcony glazing | bug | FIXED (none reproduced) |
| E — `parent_id` used as "overlap" | bug | FIXED (no invalid parent chains) |

## T22 — production-shape gate eval (proposed, ~$0.20)

The decisive insight from T21 is [[DECISIONS#tag-regions-needs-photoreal]] — raw screenshots aren't good enough. T22 would close the gate by:

1. Run `render_from_model_view` on each of the 4 new screenshots (~$0.16 = 4 × $0.04 Nano Banana).
2. Re-tag each (screenshot, render) pair via the deployed Modal `tag_regions` (~$0.04 = 4 × $0.01).
3. Score against the gate; predicted PASS on most or all based on the pair-1 finding.

Needs ~$0.20 additional authorization on top of the current $0.06.

## Fallback if T21 also fails

See [[STRATEGY#Q2]]:

- Per-region click-confirmation UX (tagger surfaces candidates, user picks).
- Color-based seed segmentation + VLM only labels.
- Swap tagger (GPT-5V or Claude vision).

## See also

- [`REPORTS/T17.md`](../../spike/REPORTS/T17.md) — full smoke-test write-up.
- `spike/outputs/spike3/smoke_test.json` — raw 49-region response.
- `spike/outputs/spike3/tagged_render.png` — visualization (in wrong coord space; see Issue A).
- [[references/coordinate-systems]].
