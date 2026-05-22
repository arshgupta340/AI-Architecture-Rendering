---
type: state
updated: 2026-05-22
---

# Current State

> Overwrite this file at session end if the state has changed. Don't append — it's a snapshot, not a log. The log is [[SESSIONS]].

## Phase

**Spike 4 pipeline + FLUX Fill inpainter landed (T24 + T25 done).** Spike 4 driver now supports two inpainters via `--inpainter` flag; FLUX Fill (Replicate) is 8× cheaper than SD Inpaint and produces native-resolution output. Material conditioning gap (text-only, no IP-Adapter) is the last remaining v1 inpainter bottleneck.

## Branch

`overnight/spike-builder-2026-05-17`. Targets `renderer-bakeoff` after review; never direct to `main`.

## Spike status

| Spike | Status | Next |
|-------|--------|------|
| [[spikes/spike-1]] | rejected (historical) | — |
| [[spikes/spike-2]] | done (incumbent baseline) | replaced by Spike 2.5 |
| [[spikes/spike-2.5]] | B1: rubric written, manual scoring pending. B2: tightened sweep run committed. B3: renderer clients rewritten (commit `885ef67`), Nano Banana panel saved, other clients awaiting keys. | Acquire BFL / Magnific / Replicate / Recraft keys → run B3 |
| [[spikes/spike-3]] | T22 + T23 done. Production-shape gate PASSES on 4/5 pairs; production paths defended against Gemini's duplicate-`y` bbox bug. 50/50 tests green. | Optional mullion-on-grid prompt iteration (~$0.01); otherwise no work needed |
| [[spikes/spike-4]] | T24 + T25 done. Two inpainter backends wired (`--inpainter`); FLUX Fill (Replicate) preferred at $0.05/call native-res vs SD at $0.40/call 512×512. 52/52 tests green. | IP-Adapter on FLUX (the remaining v1 piece) — either via Replicate (preferred) or Modal-hosted FLUX.1-Fill-dev + IP-Adapter weights |

## Cost ledger

**Running total: $0.89.** Breakdown:
- $0.01 T17 smoke test
- $0.05 T21 (5 Gemini tag calls)
- $0.04 B3-PREP (unintended Nano Banana from compare_renderers.py)
- $0.21 T22 (4 Nano Banana renders + 4 Gemini tags + 1 retry)
- $0.45 T24 (SAM2 segment + SD Inpaint apply_material; render + tag stages cached)
- $0.08 B3-RUN-1 (2 successful renderers, 7 failed-no-bill)
- $0.05 T25 (FLUX Fill Pro on Replicate; render + tag + mask cached from T24)

T21, T22, T22-retry, T24, B3-RUN-1, and T25 spend was user-authorized. B3-PREP was unintended. See [cost_ledger.md](../spike/REPORTS/cost_ledger.md).

## Blocked / awaiting

- **B3 live run** — requires user to provide `BFL_API_KEY`, `MAGNIFIC_API_KEY`, `REPLICATE_API_TOKEN`, `RECRAFT_API_TOKEN` (see [PROVIDERS.md](../spike/PROVIDERS.md)).
- **v1 material conditioning swap** — replace SD Inpaint 1.5 with FLUX Fill + IP-Adapter so the swatch image actually conditions the result. Largest single quality win still on the table.

## Known issues

- **Material conditioning weak.** SD Inpaint 1.5 doesn't use the swatch image; only the material name string. Output applies *a* texture but doesn't read as the specific material requested. Resolution: v1 swap to FLUX Fill + IP-Adapter, per the master plan.
- **Resolution ceiling at 512×512.** apply_material downsamples; upscaled tile is composited back at full render resolution. Fine for the spike, needs native-resolution inpainting or tiling for v1.
- **Wall_1 bbox spans sky on spike2 photoreal.** Tag bbox starts at y=0 in normalized space. SAM2 correctly excluded sky from the mask, but tighter bboxes would help downstream. Low-cost prompt iteration on `tag_regions`.
- **Gemini bbox malformation** (T22 finding): on certain images Gemini returns `{x, y, w, y}` with duplicate `y` keys. Production paths now defended via [[DECISIONS#gemini-bbox-malformed-json]].
- **Mullion detection inconsistent.** Hit on traditional/interior; missed on complex_windows tower. Not photoreal-vs-screenshot dependent — prompt iteration needed.
- **Confidence field still flat-ish.** 0.85–0.99 range; not usable as filter.
- **`modern interior.jpg` / `traditional exterior.jpg` filenames swapped** — interior is exterior, exterior is interior. Rename when convenient.

## Recent commits

`1cd10a1` [T24] mark complete · `f92bfff` [T24] first live Spike 4 run · `a010834` [T23] mark complete · `2aaa1bf` [T23] defensive tag_regions · `885ef67` spike2.5/B3 renderer clients · `49c51d8` spike2.5/B3 .env. (T25 commits pending.)

## What to do next

1. Read [[ROADMAP]] for milestone-level priorities.
2. Read [[SESSIONS]] (newest entry) for what just happened (T25 — FLUX Fill backend).
3. Natural next steps in priority order: (a) IP-Adapter on FLUX (the remaining v1 inpainter piece — material conditioning via swatch image), (b) more cheap FLUX (region, material) comparisons (~$0.05 each on warm cache), (c) finish B3 once funded providers can be re-attempted.
