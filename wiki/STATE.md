---
type: state
updated: 2026-05-20
---

# Current State

> Overwrite this file at session end if the state has changed. Don't append — it's a snapshot, not a log. The log is [[SESSIONS]].

## Phase

**T21 done; Spike 3 gate passes on photoreal pair, partial on screenshot-only pairs.** T01–T21 complete. T22 (full production-shape eval on 4 new screenshots) is a budget-blocked follow-up.

## Branch

`overnight/spike-builder-2026-05-17`. Targets `renderer-bakeoff` after review; never direct to `main`.

## Spike status

| Spike | Status | Next |
|-------|--------|------|
| [[spikes/spike-1]] | rejected (historical) | — |
| [[spikes/spike-2]] | done (incumbent baseline) | replaced by Spike 2.5 |
| [[spikes/spike-2.5]] | B1: rubric written, manual scoring pending. B2: tightened sweep run, evaluation pending. B3: scaffolded, awaiting API keys. | acquire BFL / Magnific / Replicate / Recraft keys → run B3 |
| [[spikes/spike-3]] | T21 done: gate PASSES on (screenshot, photoreal render) pair (94 tight regions, all major categories hit); FAILS on raw-screenshot-only pairs. Prompt revision + coord-space fix landed. | T22: render 4 new screenshots via Nano Banana (~$0.16) then re-tag (~$0.04) to validate gate on production-shape sample of 5 |
| [[spikes/spike-4]] | scaffolded, end-to-end mock tests green | depends on Spike 2.5 winner + Modal auth ($0.35–0.70/run) |

## Cost ledger

**Running total: $0.06** ($0.01 T17 + $0.05 T21, 5 Gemini calls). User authorized the $0.01 cap overage for T21. See [cost_ledger.md](../spike/REPORTS/cost_ledger.md).

## Blocked / awaiting

- **T22 (full production-shape Spike 3 eval)** — ~$0.20 (4 × Nano Banana renders + 4 × Gemini tag) on top of current $0.06. Needs user OK.
- **B3 live run** — requires user to provide `BFL_API_KEY`, `MAGNIFIC_API_KEY`, `REPLICATE_API_TOKEN`, `RECRAFT_API_TOKEN` (see [PROVIDERS.md](../spike/PROVIDERS.md)).
- **Spike 4 live** — requires Spike 2.5 winner + Modal GPU authorization.

## Known issues

- **Mullion detection inconsistent.** T21 hit mullions on the traditional/interior dining pair (4 regions, first ever) but missed them on the complex-windows facade where mullions are the dominant feature. Prompt iteration needed.
- **Confidence field still flat-ish.** Now in 0.85–0.99 range instead of T17's flat 0.95, but variance is too narrow to use as a filter. Likely a Gemini 3 Pro limitation.
- **Coord-space bug:** RESOLVED. T21 added scaling helpers in both `test_vlm_tagging.py` and `end_to_end_edit.py`. Details: [[references/coordinate-systems]].
- **Wall bboxes too loose:** RESOLVED. T21 per-window bbox count went from 0 (T17) to 77 on the same render.
- **`modern interior.jpg` and `traditional exterior.jpg` filenames swapped** — the former is actually a modern exterior house view; the latter is a modern interior dining room. Rename when convenient.

## Recent commits

`3ccb1d0` T17 revise · `998ea84` T17 mark complete · `8f960de` modal Function.lookup → from_name · `b90e606` T20 mark complete · `17614dd` T20 end-to-end pytest. (T21 commits pending — implementation + mark-complete.)

## What to do next

1. Read [[ROADMAP]] for milestone-level priorities.
2. Read [[SESSIONS]] (newest entry) for what just happened (T21).
3. If picking up T22 or B3, get user authorization first (cost cap).
