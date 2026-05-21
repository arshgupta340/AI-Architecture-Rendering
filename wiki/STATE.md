---
type: state
updated: 2026-05-20
---

# Current State

> Overwrite this file at session end if the state has changed. Don't append — it's a snapshot, not a log. The log is [[SESSIONS]].

## Phase

**Spike 3 gate PASSES on production-shape eval (T22 done).** Spike 4 integration unblocked. Spike 2.5 still pending eval + B3 keys.

## Branch

`overnight/spike-builder-2026-05-17`. Targets `renderer-bakeoff` after review; never direct to `main`.

## Spike status

| Spike | Status | Next |
|-------|--------|------|
| [[spikes/spike-1]] | rejected (historical) | — |
| [[spikes/spike-2]] | done (incumbent baseline) | replaced by Spike 2.5 |
| [[spikes/spike-2.5]] | B1: rubric written, manual scoring pending. B2: tightened sweep run + 2 variant directories committed, evaluation pending. B3: scaffolded, awaiting API keys. | acquire BFL / Magnific / Replicate / Recraft keys → run B3 |
| [[spikes/spike-3]] | T22 done: production-shape gate PASSES on 4/5 pairs (1 strong pass, 3 pass, 1 partial — mullion miss on dense grid). Urban_exterior surfaced a Gemini JSON malformation bug; salvaged. | Optional T23: promote raw-response saving + tolerant parser into test_vlm_tagging.py (no API cost). Optional mullion-on-grid prompt iteration (~$0.01). Otherwise integrate into Spike 4. |
| [[spikes/spike-4]] | scaffolded, end-to-end mock tests green | depends on Spike 2.5 winner + Modal GPU authorization ($0.35–0.70/run) |

## Cost ledger

**Running total: $0.31.** Breakdown:
- $0.01 T17 smoke test
- $0.05 T21 (5 Gemini tag calls)
- $0.04 B3-PREP (unintended Nano Banana from compare_renderers.py manifest mode)
- $0.21 T22 (4 Nano Banana renders + 4 Gemini tags + 1 retry)

T21 and T22 spend was user-authorized. T22 retry ($0.01) also user-authorized for reproducibility confirmation. B3-PREP was unintended. See [cost_ledger.md](../spike/REPORTS/cost_ledger.md).

## Blocked / awaiting

- **B3 live run** — requires user to provide `BFL_API_KEY`, `MAGNIFIC_API_KEY`, `REPLICATE_API_TOKEN`, `RECRAFT_API_TOKEN` (see [PROVIDERS.md](../spike/PROVIDERS.md)). Nano Banana panel for B3 already saved (from the B3-PREP unintended call) at `spike/outputs/spike2_5/b3/nano_banana_pro.png`.
- **Spike 4 live** — requires Spike 2.5 winner + Modal GPU authorization.

## Known issues

- **Gemini bbox malformation** (NEW from T22): on certain images (urban_exterior reproduced 2/2 times), Gemini returns `{x, y, w, y}` with duplicate `y` keys instead of `{x, y, w, h}`. Recoverable via `spike/salvage_urban_tags.py`. Decision: [[DECISIONS#gemini-bbox-malformed-json]].
- **Mullion detection inconsistent.** Hit on traditional/interior dining (5 mullions in T22); missed on complex_windows tower (0 mullions in both T21 and T22). Photoreal vs screenshot mode doesn't fix it — it's a prompt issue.
- **Confidence field still flat-ish.** 0.85–0.99 range. Cannot be used as filter. Likely a Gemini 3 Pro limitation.
- **`modern interior.jpg` / `traditional exterior.jpg` filenames swapped** — the former is actually a modern exterior house view; the latter is a modern interior dining room. Rename when convenient.

## Recent commits

`4238de3` .claude settings · `97f3bb2` spike2.5/B2 outputs · `81c9524` docs+wiki bootstrap · `ddd0ac4` [T21] mark complete · `e02a7b8` [T21] prompt revision + 5-image eval · `3ccb1d0` [T17] revise. (T22 commits pending.)

## What to do next

1. Read [[ROADMAP]] for milestone-level priorities.
2. Read [[SESSIONS]] (newest entry) for what just happened (T22 + house-keeping commits).
3. Next natural step: promote the raw-response-saving + tolerant parser into `spike/test_vlm_tagging.py` (no API cost) so Spike 4 inherits the defensiveness. Then proceed to B3 keys or Spike 4 live.
