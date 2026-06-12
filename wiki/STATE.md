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
- E2 (render shootout, ~$3, **needs FAL_KEY from user**) → E3 (swatch shootout, ~$3) pending.
- E4 (Vision-Banana-style probe, ~$1, GOOGLE_API_KEY available) and E5 (Florence-2→SAM 3, ~$1) runnable next.

## Cost ledger

**Running total: $0.89** (unchanged this session — research + docs only). New phase budget: $50 authorized 2026-06-11. See [cost_ledger.md](../spike/REPORTS/cost_ledger.md).

## Blocked / awaiting

- **E2/E3** — need `FAL_KEY` from user (fal.ai account; PROVIDERS.md to gain a fal paragraph during E2 setup).
- **E1** — needs Rhino running with the MCP bridge + a real model open.

## Known issues (carried forward, tier-2 relevant)

- Material conditioning text-only (E3 addresses); mullion detection inconsistent (E4/E5 address); Gemini malformed-bbox defense in place ([[DECISIONS#gemini-bbox-malformed-json]]); confidence flat; `modern interior.jpg`/`traditional exterior.jpg` filenames swapped.

## Competitive watch

- Veras v4.5 Smart Selection runs on **Vision Banana** (DeepMind, non-public) — watch the [Gemini API changelog](https://ai.google.dev/gemini-api/docs/changelog) for a public endpoint.
- Veras ships every 4–6 weeks; est. 6–12 months from closing the swatch+layers gap.

## What to do next

1. Run **E1** (Rhino MCP extraction probe) — $0, proves the keystone.
2. User: create fal.ai account, put `FAL_KEY` in `spike/.env` → unblocks E2/E3.
3. E4/E5 afterward; E6 once E1 masks exist.
