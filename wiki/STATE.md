---
type: state
updated: 2026-06-12
---

# Current State

> Overwrite this file at session end if the state has changed. Don't append — it's a snapshot, not a log. The log is [[SESSIONS]].

## Phase

**Plugin-first pivot decided (2026-06-12).** Foundational pressure test complete (four research tracks). New architecture: two tiers — host plugins exporting ground truth (beauty/ID-mask/depth/objects.json; tag+segment stages deleted) as primary, the screenshot pipeline as universal fallback. Master plan rewritten to v2; research doc suite created. Next: experiment ladder E1–E6 ([docs/plans/experiments.md](../docs/plans/experiments.md)), starting with the $0 Rhino MCP extraction probe.

## Branch

`overnight/spike-builder-2026-05-17`. Targets `renderer-bakeoff` after review; never direct to `main`. (Pivot docs are committed here too; consider a fresh branch name at next merge point.)

## Plan of record

- [docs/plans/master-plan.md](../docs/plans/master-plan.md) — **v2** (two-tier plugin-first architecture).
- [docs/plans/experiments.md](../docs/plans/experiments.md) — E1–E6 ladder with gates; ~$10–15 of a **$50 user-authorized budget**.
- Research: [host-integration](../docs/plans/research/host-integration.md) · [generative-stack](../docs/plans/research/generative-stack.md) · [competitive-landscape](../docs/plans/research/competitive-landscape.md).
- Pivot rationale: [[DECISIONS#plugin-first-pivot]].

## Spike status (v1 pipeline — now the tier-2 fallback)

| Spike | Status | Disposition under v2 |
|-------|--------|----------------------|
| [[spikes/spike-1]] | rejected (historical) | — |
| [[spikes/spike-2]] | done | baseline data reused |
| [[spikes/spike-2.5]] | B3 partial (2 renderers ran; BFL endpoints deprecated upstream) | superseded by E2 render shootout (fal.ai-routed) |
| [[spikes/spike-3]] | done (gate 4/5) | tier-2 only; stack to be upgraded per E4/E5 (Florence-2→SAM 3 vs Vision-Banana-style probe) |
| [[spikes/spike-4]] | done (pipeline proven, material conditioning weak) | harness reused for E3 swatch shootout (warm T24 cache) |

## Experiment ladder status

- **E1 — PASSED ($0, 2026-06-12).** Rhino MCP probe on the real SFUrban model: 93.1% of object pixels decode exactly; 257 mullion instances with pixel-accurate masks at 2–4px (the class Gemini scored zero on in T21); true z-buffer captured. Required white-reference second pass + atomic capture. [REPORTS/E1.md](../spike/REPORTS/E1.md), decoder `spike/host_probe_rhino.py`.
- **E6 — PASSED ($0, 2026-06-12).** Single ground-truth wall instance → `composite.paste_tile` → exact-instance edit, zero leakage; tag+segment deleted. Evidence `spike/outputs/e1_rhino_probe/e6_sidebyside.png`.
- **E2 — PASSED (~$0.40).** New house model (kCs_SampleHouseProject, CSI layers). True-z-buffer FLUX depth ControlNet is the only candidate that registers pixel-for-pixel; criterion locked: geometry preservation = mask registration. [REPORTS/E2.md](../spike/REPORTS/E2.md).
- **E3 — PASSED (~$0.30).** Production recipe locked: FLUX.2 Edit multi-ref(render, swatch) + composite through host mask = travertine that reads as travertine at $0.06/swap. MatSwap contingency not needed for v1. [REPORTS/E3.md](../spike/REPORTS/E3.md).
- **E4 — decisive negative ($0.13):** prompted Nano Banana segmentation drifts geometrically (mullion IoU 0.003); Veras's edge is the non-public tuning. [REPORTS/E4.md](../spike/REPORTS/E4.md).
- **E5 — ran (~$0.50):** hosted Grounded-SAM not edit-grade on raw screenshots (mullion IoU 0.02); re-test on photoreal render pending. [REPORTS/E5.md](../spike/REPORTS/E5.md).
- **LADDER COMPLETE.** Total phase spend ≈ $2.22 of $50. Next: Phase 3 — Grasshopper capture component + layer-model canvas prototype.

## Cost ledger

**Running total: ≈ $2.22** ($0.89 pre-pivot + E2 $0.40 + E3 $0.30 + E4 $0.13 + E5 ~$0.50). Phase budget $50, authorized 2026-06-11. See [cost_ledger.md](../spike/REPORTS/cost_ledger.md).

## Blocked / awaiting

- Nothing blocked. `FAL_KEY` in place; Rhino MCP works; ladder complete.
- Deferred: E5 re-score on photoreal render; fal canny endpoint dead (multi-ControlNet via `flux-general` if needed); `FAL_KEY` placeholder + fal paragraph still to add to `.env.example`/`PROVIDERS.md`.

## Known issues (carried forward, tier-2 relevant)

- Material conditioning text-only (E3 addresses); mullion detection inconsistent (E4/E5 address); Gemini malformed-bbox defense in place ([[DECISIONS#gemini-bbox-malformed-json]]); confidence flat; `modern interior.jpg`/`traditional exterior.jpg` filenames swapped.

## Competitive watch

- Veras v4.5 Smart Selection runs on **Vision Banana** (DeepMind, non-public) — watch the [Gemini API changelog](https://ai.google.dev/gemini-api/docs/changelog) for a public endpoint.
- Veras ships every 4–6 weeks; est. 6–12 months from closing the swatch+layers gap.

## Phase 3 — first deliverables BUILT (2026-06-12, two parallel agents)

- **P3.1 — `spike/rhino_capture.py`** (+ README + tests): the proven atomic capture as a production module; CSI/keyword semantic rules auto-sniffed; r-plane ID extension to 140k objects; live-verified 90.5% decode; doc state fully restored. Suite: 62 tests green.
- **P3.2 — `apps/canvas-prototype/`**: the product loop in a browser on real data — hover/click regions, swatch library, apply → RGBA layer (FLUX.2 Edit + paste_tile; travertine no-spend demo path), layer stack with eye-toggle (≈14ms redraw), replace-not-stack, localStorage persistence. 22/22 API checks; live brick call proved the paid path ($0.06). Run: `spike\.venv\Scripts\python.exe apps/canvas-prototype/server.py` → http://localhost:8765 (first run: `prepare_data.py`).

## What to do next

1. Wire P3.1 → P3.2 directly: capture POSTs straight into the canvas server (`/api/capture`), making "click Capture in Rhino → canvas opens" one motion.
2. Material library: tile-scale prompt hints; 2px mask feather on composite seams; more real swatches (ambientCG ingest).
3. Multi-view material lock (M4): capture 2–3 views of the house, same swatch + per-view masks, check consistency (anchor-reference technique).
4. Tier-2 follow-ups (lower priority): E5 re-score on the photoreal render; Revit add-in scoping.
