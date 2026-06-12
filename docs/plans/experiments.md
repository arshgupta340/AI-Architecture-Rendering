# Experiment Ladder — validating the plugin-first pivot

> Created 2026-06-12. Budget: **$50 user-authorized for this phase** (ladder uses ~$10–15; MatSwap contingency may use more). Every live call logged in [cost_ledger.md](../../spike/REPORTS/cost_ledger.md). Each gate decides the next step — do not run ahead of a failed gate without a decision.

Status legend: `[ ]` pending · `[~]` in progress · `[x]` passed gate · `[!]` failed gate / blocked

## The ladder

### [x] E1 — Rhino native-extraction probe ($0) — KEYSTONE → [report](../../spike/REPORTS/E1.md)
Via the connected Rhino MCP (`run_python` / `run_csharp` / `get_viewport_image`), from a real model:
export `beauty.png`, `depth.png` (ZBufferCapture → GrayscaleDib, then linearize), `id_mask.png`
(per-object flat color via conduit override or temporary material swap; AA off; transparency→0),
`objects.json` (id → layer/material/name), `camera.json`.

- **Gate:** pixel-accurate masks including thin mullions at 1:1 zoom; depth map usable after normalization.
- **Risks:** Rhino 8 `DrawMeshShaded` conduit regressions; viewport-res cap on depth.
- **Artifacts:** `spike/outputs/e1_rhino_probe/` + `spike/host_probe_rhino.py`.

### [ ] E2 — Render conditioning shootout (~$3) — needs `FAL_KEY`
Same scene through: (a) true-depth+Canny via fal `flux-general`; (b) FLUX.2 [pro] Edit i2i; (c) Nano Banana Pro i2i (control). Score with the B1 rubric / `spike/scoring.py` — critical-failure count first.

- **Gate:** ≥1 candidate with zero critical failures (invented windows, transformed corners, mass changes).
- **Prereq:** E1 depth map; `FAL_KEY` added to `spike/.env` (placeholder in `.env.example`, paragraph in `PROVIDERS.md`); fal renderer clients in `spike/renderers/` with respx-mocked tests.

### [ ] E3 — Swatch-conditioning shootout (~$3) — warm T24 cache
The "does travertine read as travertine" experiment: (a) FLUX.2 Edit multi-ref (render + region + swatch); (b) FLUX Kontext + swatch; (c) fal `flux-general` inpaint + IP-Adapter; (d) FLUX Fill text-only (control, exists from T25).

- **Gate:** a blind viewer names the material from the result.
- **On failure:** stand up **MatSwap** on Modal (pre-authorized contingency; takes true normals from the plugin path).

### [x] E4 — Vision-Banana-style probe ($0.13) — decisive negative → [report](../../spike/REPORTS/E4.md)
Prompt public `gemini-3-pro-image-preview` with color-coded segmentation instructions ("walls pure blue [0,0,255], windows pure yellow [255,255,0], mullions pure red [255,0,0]…") on the T21 renders; decode colors → masks (`spike/probe_vision_banana.py`).

- **Score:** mask IoU vs E1 ground truth; side-by-side vs T21 Gemini-bbox results.
- **Purpose:** intelligence on the approach Veras ships (they use the non-public tuned variant); decides whether prompting the base model is a viable tier-2 shortcut.

### [x] E5 — Fallback tagging upgrade (~$0.50) — ran; re-test on photoreal post-E2 → [report](../../spike/REPORTS/E5.md)
Florence-2 → SAM 3 on the same renders. Acid test: the `complex windows` mullion-grid facade (T21: 69 windows, 0 mullions from Gemini).

- **Decision output:** pick the tier-2 stack from E4 vs E5 results.

### [x] E6 — ID-mask end-to-end ($0) — PASSED (see result log)
Feed an E1 ground-truth mask directly into the existing `spike/composite.py` + apply-material path, bypassing tag+segment.

- **Gate:** edit quality ≥ the T24/T25 SAM2-mask runs → proves stage deletion on the plugin tier.

## After the ladder (Phase 3, separate sessions)

1. Rhino capture plugin proper (Grasshopper component fast path 3–5 days; full .rhp ~2 weeks).
2. Layer/data-model + canvas prototype on E1's real ground-truth exports.
3. Revit add-in → SketchUp → multi-view material lock (anchor-reference technique).

## Result log

*(append one line per executed experiment: date, spend, gate result, link to artifacts)*

- **2026-06-12 — E5 — ~$0.50 — ran (raw-screenshot case).** Grounded-SAM on Replicate: mullion IoU 0.02 / recall 0.47 (coarse blobs), wall/glass missed, door query crashes. Better than E4 on mullions, far from edit-grade. Domain mismatch (photo-trained detector, CAD-shaded input) dominates — re-run on E2's photoreal render before tier-2 verdict. [REPORTS/E5.md](../../spike/REPORTS/E5.md).
- **2026-06-12 — E4 — $0.13 — DECISIVE NEGATIVE.** Prompted Nano Banana Pro produces a semantically coherent but geometrically redrawn segmentation (buildings shifted/rescaled; mullion IoU 0.003 vs E1 ground truth). Vision Banana's value is the instruction tuning, which is non-public — tier 2 must be discriminative (E5). [REPORTS/E4.md](../../spike/REPORTS/E4.md).
- **2026-06-12 — E6 — $0 — GATE PASSED.** Largest wall instance from E1's `instance_ids.png` (`mask_for(semantic=='wall')`, 2,162px, single GUID on `ENSCAPE::EXTERIOR WALL::CONCRETE PANELS`) fed directly into `composite.paste_tile` with a travertine tile — exact-instance edit, zero leakage onto mullions/neighbors, tag+segment stages bypassed entirely. Evidence: `spike/outputs/e1_rhino_probe/e6_sidebyside.png`.
- **2026-06-12 — E1 — $0 — GATE PASSED.** 93.1% of object pixels decode exactly; 257 mullion instances with pixel-accurate masks at 2–4px; true z-buffer captured. Required a white-reference second pass (Rhino's "unlit" mode still applies a 0.7-slope headlight) and atomic capture. Real model: SFUrban. Artifacts: `spike/outputs/e1_rhino_probe/`, decoder `spike/host_probe_rhino.py`, [REPORTS/E1.md](../../spike/REPORTS/E1.md).
