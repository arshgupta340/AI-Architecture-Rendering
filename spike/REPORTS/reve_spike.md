# Reve Canvas Phase-0 validation spike

- **Task:** Validate Reve 2.x `extract_layout` → region edit → `render_layout` as the foundation for an architecture-native layer editor.
- **Status:** **Decisive negative — C2 kill gate failed. Do not build `apps/reve-canvas/`.**
- **Date:** 2026-07-15
- **Paid usage:** 320 credits = $0.4267 at the $10/7,500-credit pack rate (ledgered as four $0.11 estimated calls). Reve balance moved from 7,500 to 7,180 credits.

## Gate scorecard

| Criterion | Result | Evidence |
|---|---|---|
| **C1 — extraction sanity** | **FAIL (strict)** | Baseline exterior: 12/18 labels mapped (**66.7%**); shaded viewport: 7/10 (**70.0%**). The baseline exterior grouped the whole building as `<house 1>` and did not expose separate wall or roof regions, so the intended wall edit could not run. A targeted refinement prompt recovered roof + shingle-siding regions and reached 14/18 (**77.8%**), still below the required 80% matcher rate. The remaining misses (`porch`, `stairs`, `railing`, `shadow`) are mainly taxonomy aliases, but the unprompted wall/roof omission is a product-level extraction gap. |
| **C2 — geometry preservation** | **FAIL — KILL GATE** | The harness measured **7.1%** mean pixel change outside the edited wall bbox, above the <5% threshold. Reve also reframed a 1504×656 source (2.293:1) into a 5440×3072 output (1.771:1), shifted the composition, and did not visibly replace the dark shingle siding with travertine. |
| **C3 — client-deck quality** | **FAIL for the edit workflow** | The returned image is clean and high-resolution in isolation, but it does not deliver the requested material swap and does not preserve the supplied frame. That is not client-deck-safe for an element-aware architectural edit. |
| **C4 — five-edit stability** | **NOT RUN** | Stopped before five more paid renders because C2 is the designed kill gate. |
| **C5 — shaded-viewport photorealization** | **NOT RUN** | Stopped before further paid work after C2 failed. This criterion was non-killing, so it could not overturn the gate. |
| **C6 — RegionKey round-trip** | **PASS (one render)** | `wall.shingle-siding-1#002` returned verbatim through `render_layout`. |

## C2 visual finding

The source/output comparison shows a real product failure, not merely a noisy metric:

1. The output changes aspect ratio from ultrawide to 16:9 and reveals different surrounding content, so a user-provided camera frame is not stable.
2. The building is rescaled/repositioned within the canvas.
3. The requested wall prompt was changed to travertine, but the façade still reads as dark shingle siding.

The current `drift_outside_bbox` implementation resizes the 16:9 output directly to the source dimensions before comparison, so **7.1% should not be treated as a perfectly registered scientific measurement**; non-uniform resize can inflate it. This caveat does not rescue C2: the output-dimension change, visible reframing, and failed material substitution independently violate the criterion's no-warping/no-bleed intent.

Diagnostic artifacts:

- `spike/reve/outputs/S2_source_vs_output_contain.png` — undistorted, letterboxed source/output comparison.
- `spike/reve/outputs/S2_building_crops.png` — normalized building comparison.
- `spike/reve/outputs/S2_wall_travertine.png` — full 5440×3072 response image.
- `spike/reve/outputs/S2_wall_travertine_result.json` — measured C2/C6 result.

## Paid calls

| Call | Endpoint purpose | Credits | Est. USD | Request ID |
|---|---|---:|---:|---|
| S1 exterior | Extract baseline exterior layout | 80 | $0.1067 | `rsid-eab17bdd471aba2270b40fcb6b4efa6d` |
| S1 viewport | Extract shaded viewport layout | 80 | $0.1067 | `rsid-ca97bb06abf32e0978c0b12afa3e50c1` |
| S1 refined | Refine exterior into editable architectural regions | 80 | $0.1067 | `rsid-142e06376dcf27adc9aed7fa5e2d58e1` |
| S2 wall | Render keyed wall with travertine prompt | 80 | $0.1067 | `rsid-a725c33f1ca67bec45b7690a021df059` |

Raw response JSON was saved before parsing under `spike/reve/outputs/` for every successful call. The earlier HTTP 402 budget-exhausted attempt completed no call and spent zero credits.

## Decision

**STOP Reve Canvas.** The PRD requires C1 ∧ C2 before any app scaffolding, and both fail strictly; C2 is explicitly terminal. Do not create the Next.js/Supabase product or spend on S3–S6. Preserve the layout/taxonomy learnings for the mesh-first track, where geometry and semantic IDs come from the real 3D model.

Revisit only if Reve adds reliable source-dimension/aspect preservation plus genuinely region-confined editing, or exposes controls that demonstrate <5% outside-region drift on the same architectural fixtures.
