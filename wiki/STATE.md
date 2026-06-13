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

## Registration fix (2026-06-12, E2b) — masking now accurate

User found the canvas masks didn't land on the rendered elements (brick over windows, smudged pillars). Root cause: depth-only ControlNet can't pin coplanar openings, so the `flux_depth` base drifted 5–25px from the GT masks (which are registered to the beauty geometry). Fix: re-capture at native **1504×656** (`spike/outputs/e2_house_v2/`, no resize drift) + render with **depth+canny ControlNetUnion** where canny = a ground-truth line drawing (`Canny(beauty) ∪ instance-boundaries`). GT-edge alignment **51.7% → 98.5% within 2px**. Brick lands on walls only; windows/posts sharp. Prototype repointed to v2; layer cache auto-clears on `prepare_data`. [REPORTS/E2b.md](../spike/REPORTS/E2b.md). **Production render recipe updated: depth+canny union, not depth alone.** Polish (same session): warm-prompt base (`warm_w1.png`) recovers the terracotta/golden-hour look while holding **98.2%** edge align (warmth was a prompt fix, no second-stage, no re-drift); `server._mask_png` now +1px dilate + ~1.1px Gaussian feather for soft composite seams.

## P3.3 — capture→canvas wiring DONE (2026-06-12)

"Click Capture in Rhino → canvas updates" is wired end to end, validated live on a *fresh camera view* (decode 92.9%, 98.5% edge align). Rhino-side `rhino_capture.capture_and_send()` POSTs the bundle to the server's `POST /api/ingest`, which runs `ingest.build_project` (decode → `render_locked` warm depth+canny render → `write_web_project`); the canvas polls `GET /api/version` (base.png mtime) every 3s and auto-reloads, clearing the now-stale layer stack ("● synced" in the header). Reusable `render_locked()` now carries the warm prompt (was inline). Robustness from the live run: (a) `rhino_capture` forces flat-unlit white-reference shading; (b) **a long-idle/heavily-churned Rhino session can return a dim white-reference pass → garbage masks; the pipeline now rejects any capture decoding <50% before spending on the render**, and a fresh model reopen restores 90%+. Canvas currently restored to the known-good e2_house_v2 hero project.

## Capture repeatability ROOT-CAUSED + fixed (2026-06-13, P3.3-fix `0f49c7a`)

The "only the first capture per doc-open decodes; the rest → 0.3%" bug was **not** session/GL degradation — it was the bare `view.CaptureToBitmap(size)` overload returning a **stale default-lit frame** in a headless/MCP viewport (proved: byte-identical across display modes, fg median 157==background). Fix: white/ID passes now use `CaptureToBitmap(size, displayModeDescription)` (`_capture_idmode`) → fg median 191, ~97% decode. **`capture()` is now idempotent in-session — no reopen needed.** Added a white-pass brightness health gate (`MIN_LIGHT_PASS_MEDIAN=180`, raises instead of returning garbage) + optional `doc_path` retry. 69 tests. **Reverses the old E1 note** (corrected in `host_probe_rhino.py` finding #5). Independently re-validated: 2 captures, one session, different cameras → 90.5% & 92.9%.

## Multi-view material lock validated (2026-06-13, M4 `2cfbc55`)

Anchor-reference technique (`spike/run_multiview_lock.py`): edit the anchor view, then feed its edited result as a 3rd FLUX.2 Edit reference when editing other views. **Travertine: wall ΔE-to-anchor 7.43 (naive) → 4.14 (locked), −44% — clean win.** Red brick **backfired** (21.62 vs 8.25): the anchor's baked golden-hour shadows + differing camera-relative sun direction inject wrong lighting. **Finding: color-dominated materials lock cleanly; texture/shadow-heavy materials need lighting normalized first.** $0.38. Report: [multiview.md](../spike/REPORTS/multiview.md).

## What to do next

1. Build the real Grasshopper "Send to Canvas" component around `capture_and_send` (in-session capture is now reliable — multi-view capture from one Rhino session works). The `<50%` ingest guard + in-Rhino health gate are belt-and-suspenders.
2. Multi-view lock v2: normalize lighting before the anchor-lock (neutral relight, or soften the prompt to "same material *type/tone*") so textured materials (brick) lock too. Then wire multi-view into the canvas (one swatch → all views).
3. Material library: tile-scale prompt hints; more real swatches (ambientCG ingest).
4. Tier-2 follow-ups (lower priority): E5 re-score on the photoreal render; Revit add-in scoping.
