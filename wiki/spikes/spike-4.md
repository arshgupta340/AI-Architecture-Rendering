---
type: spike
status: T24 + T25 done — pipeline integration PASSES on two inpainter backends. FLUX Fill (Replicate) preferred at $0.05/call native-res. Material conditioning gap (no IP-Adapter) is the last v1 inpainter piece.
budget: ~$0.10/run with FLUX (warm cache, segment + flux_fill_replicate); ~$0.45/run with SD Inpaint
gate: subjective — does the result feel like the product hypothesis? — pipeline integration: PASSES
---

# Spike 4 — End-to-end edit pipeline

**Status:** T24 + T25 complete. Pipeline runs end-to-end with either inpainter backend; FLUX Fill Pro via Replicate is the better one (8× cheaper than SD Inpaint, native resolution rather than 512×512). Material conditioning is still text-only on both backends — that's the IP-Adapter-shaped hole the v1 inpainter will need to fill.

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

## T25 — FLUX Fill (Replicate) as a second apply_material backend (DONE 2026-05-22)

Full write-up: [`REPORTS/T25.md`](../../spike/REPORTS/T25.md).

- Added `--inpainter {sd_inpaint, flux_fill_replicate}` to `spike/end_to_end_edit.py`. Default is `sd_inpaint` so T20 + T24 paths are unchanged.
- FLUX path calls `black-forest-labs/flux-fill-pro` on Replicate directly (image + mask + text prompt). Encoded as base64 data URLs, polled to completion, downloaded.
- Separate cache scope per inpainter (`tile` vs `tile_flux`) preserves T24's SD cache.
- 4 new pytest tests; full suite 52/52 green.
- Live test on the same (screenshot, region=wall, material=travertine) as T24. FLUX cost: $0.05; SD cost: $0.40. FLUX tile: 1259×848 native; SD tile: 512×512 forced.
- Visible result on the masked wall: FLUX dramatically beats SD on resolution + edge fidelity (window cuts and balcony framing stay crisp); both still produce "cream wall" rather than distinctive travertine because the swatch isn't conditioning the output.

### T25 verdict

- ✅ **Inpainter integration**: two backends wired, dispatcher tested, cache scoping correct.
- ✅ **Resolution + edge fidelity**: FLUX is the right call. The 512×512 SD round-trip was destroying detail; FLUX preserves it.
- ❌ **Material conditioning**: still text-only. IP-Adapter is the next required step. Recorded as a follow-up in the report.

## T24 — first live run (DONE 2026-05-22)

Full write-up: [`REPORTS/T24.md`](../../spike/REPORTS/T24.md).

- Pre-populated render + tags cache from existing on-disk artifacts (T21 pair 1) → free, no Nano Banana or Gemini calls.
- Ran `end_to_end_edit.py --live` with `--screenshot spike/outputs/spike2/source.png --region-label wall --material spike/test_assets/travertine.jpeg`.
- All 6 stages completed: render (cached) → tag (cached) → pick wall_1 (conf 0.95) → SAM2 segment (mask 8.2% coverage) → SD Inpaint apply_material → paste_tile composite.
- Output: `spike/outputs/spike4/first_live/edit_result.png` (1.6 MB, 1259×848). Mask + tile preserved alongside.
- Cost: $0.05 SAM2 + $0.40 SD Inpaint = $0.45.
- Result: pipeline works end-to-end. Travertine swap is *applied* but doesn't *look* like travertine — SD Inpaint 1.5 has no material conditioning. Expected per master plan.

## What's NOT blocking anymore

- ~~Renderer not yet chosen~~ — Nano Banana Pro is the de facto Spike 4 renderer; bake-off still pending on B3 but doesn't gate Spike 4 integration.
- ~~Tagger gate not passed~~ — T22 cleared the production-shape gate; T23 defended the parser.
- ~~Modal authorization~~ — granted for T24.

## Still relevant concerns

- **SAM2 mask quality from VLM bboxes.** wall_1 bbox started at y=0 (included sky). SAM2 correctly excluded the sky from the mask, but a tighter bbox would help. Prompt iteration TBD.
- **Material conditioning.** SD Inpaint 1.5 doesn't use the swatch image — only the material *name* string. v1 needs FLUX Fill + IP-Adapter to actually transfer travertine's appearance from `travertine.jpeg`.
- **Resolution ceiling.** SD Inpaint downsamples to 512×512. v1 needs native-resolution inpainting or tiling.
- **Composite blending.** No seam artifacts observed at the wall edges on this run. Tune later if other regions surface them.
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
