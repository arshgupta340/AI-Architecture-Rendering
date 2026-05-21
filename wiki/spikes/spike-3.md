---
type: spike
status: T22 done — production-shape gate PASSES on 4/5 pairs (1 strong pass, 3 pass, 1 partial). Spike 4 integration unblocked.
budget: $0.27 spent on Spike 3 (T17 $0.01 + T21 $0.05 + T22 $0.21). Plus $0.04 B3-PREP unintended, not Spike 3.
gate: ≥80% of major elements correctly labeled with tight pixel-accurate bboxes on ≥4/5 diverse screenshots
---

# Spike 3 — VLM region tagging (Gemini 3 Pro)

**Status:** T22 complete. Production-shape gate **PASSES** on 4 of 5 pairs (modern_interior PASS, traditional_exterior STRONG PASS — hit all 6 categories, urban_exterior PASS-with-caveat, complex_windows PARTIAL on mullions). The T21 hypothesis ([[DECISIONS#tag-regions-needs-photoreal]]) was empirically confirmed: urban_exterior went from 0 windows (T21 screenshot-only) to 10 windows (T22 photoreal pair) on the same screenshot. New finding from T22: Gemini 3 Pro can return malformed bbox JSON with duplicate `y` keys — [[DECISIONS#gemini-bbox-malformed-json]]. Spike 4 integration can proceed.

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

## T22 — production-shape gate eval (DONE 2026-05-20)

Full write-up: [`REPORTS/T22.md`](../../spike/REPORTS/T22.md).

Did exactly what was proposed: rendered the 4 new screenshots through Nano Banana Pro, ran `tag_regions` on each (screenshot, render) pair, scored against the gate. Cost: $0.21 ($0.16 renders + $0.04 tags + $0.01 retry).

### T22 vs T21 — same screenshots, with and without photoreal context

| Image | T21 (screenshot-only) | T22 (photoreal pair) | Δ |
|---|---|---|---|
| modern_interior | 31 regions, no door | 27 regions, +ground/sky | similar |
| traditional_exterior | 16, 4 mullions, no door, 3 furniture | 25, 5 mullions, 1 door, 11 furniture | photoreal added: door, +8 furniture, +1 mullion |
| **urban_exterior** | 25, **0 windows** | 47, **10 windows**, 10 vegetation | photoreal unblocked window detection |
| complex_windows | 97, 69 windows, no roof | 118, 103 windows, 6 roofs | more windows + roof + context |

The urban_exterior row is the decisive proof of [[DECISIONS#tag-regions-needs-photoreal]]: same screenshot, same prompt, different input image, completely different categorical outcome on windows.

### T22 results vs gate

| # | Image | Verdict |
|---|---|---|
| 1 | T21 carry-over (spike2 photoreal) | PASS |
| 2 | modern_interior | PASS |
| 3 | traditional_exterior | **STRONG PASS** (all 6 categories) |
| 4 | urban_exterior | PASS-with-caveat (Gemini JSON bug, salvaged) |
| 5 | complex_windows | PARTIAL (mullion miss on dense grid) |

### New finding from T22 — Gemini bbox JSON malformation

On urban_exterior (2/2 attempts), Gemini returned `{"x": 499, "y": 361, "w": 25, "y": 425}` — duplicate `y` keys, no `h`. Standard JSON parsing drops the first key on duplicates → pydantic saw `{x, y, w}` → 37 validation errors. Reproducible. Salvaged via `spike/salvage_urban_tags.py` (custom JSON object_pairs_hook). 44 of 47 regions recovered. Decision recorded as [[DECISIONS#gemini-bbox-malformed-json]].

## Follow-ups (after T22)

- **T23 candidate (no API cost):** promote `_save_raw_response` + tolerant JSON parser from `spike/run_t22.py` and `spike/salvage_urban_tags.py` into `spike/test_vlm_tagging.py:_call_live`. Prevents future paid-data loss.
- **Mullion-on-grid prompt iteration** (~$0.01 per attempt on complex_windows). Low-cost optimization.
- Spike 4 integration unblocked — `tag_regions` output on real photoreal renders is good enough to drive SAM2 + material swap on 4 of 5 image types.

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
