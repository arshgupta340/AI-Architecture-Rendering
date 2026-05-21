---
type: index
updated: 2026-05-19
---

# Project Wiki — Photoshop-for-Architects

This is the **single source of truth** for the project. New session? Read this, then [[STATE]]. Need a term defined? [[GLOSSARY]]. Wondering why we chose X? [[DECISIONS]]. Want history? [[SESSIONS]].

Existing docs (`docs/plans/master-plan.md`, `spike/TASKS.md`, `spike/REPORTS/`, `spike/PROVIDERS.md`) are still authoritative for what they cover — this wiki links to them rather than duplicating.

## 60-second orientation

**Product.** A canvas where architects click a wall, pick a swatch (travertine, brick, stucco), and the surface re-renders coherently. AI is invisible plumbing; the UX is direct manipulation, non-destructive layers. Input is a 3D-model viewport screenshot (Rhino / SketchUp / Revit / Forma) — not a prompt.

**Pipeline.**

```
screenshot ── render ── tag ── segment ── apply material ── composite
              (Nano       (Gemini  (SAM2)   (FLUX Fill +     (PIL alpha)
               Banana      3 Pro)            IP-Adapter)
               Pro?*)

* Spike 2.5 is choosing the production renderer.
```

**Phase.** Spikes 2.5 / 3 / 4 — all scaffolded ([[spikes/spike-2.5]], [[spikes/spike-3]], [[spikes/spike-4]]). Live gate evaluation pending API-key + budget authorization.

**Routes.** Two strategic routes — Photoshop UX (the product) and VLM region tagging (the plumbing) — are sequential, not competing. See [[STRATEGY]].

## Wiki map

| Page | What's there |
|------|--------------|
| [[STATE]] | Current state. What's done / blocked / next. Updated every session. |
| [[GLOSSARY]] | B1/B2/B3, spike definitions, coordinate spaces, key terms. |
| [[STRATEGY]] | Photoshop route vs VLM route, current decision, open questions. |
| [[ROADMAP]] | Next 2–3 milestones with entry/exit criteria. |
| [[DECISIONS]] | Append-only decision log. Why we did X, what we considered. |
| [[SESSIONS]] | Append-only conversation log. One entry per chat. |
| [[spikes/spike-1]] | Rejected: text-to-image + click-segmentation. |
| [[spikes/spike-2]] | Screenshot-to-render fidelity baseline (Nano Banana Pro). |
| [[spikes/spike-2.5]] | Multi-renderer bake-off (B1 / B2 / B3). |
| [[spikes/spike-3]] | VLM region tagging (Gemini 3 Pro). |
| [[spikes/spike-4]] | End-to-end edit pipeline. |
| [[references/coordinate-systems]] | Pixel vs normalized 0–1000 vs SAM2. The T17 finding. |

## External (not duplicated here)

- [Master plan](../docs/plans/master-plan.md) — design rationale, full pipeline spec, pivotal decisions.
- [Overnight scaffolding plan](../docs/plans/overnight-spike-builder.md) — the T01–T20 execution plan.
- [Live task board](../spike/TASKS.md) — T-status with commit SHAs.
- [Per-task reports](../spike/REPORTS/) — what was tried, what worked, surprises.
- [Cost ledger](../spike/REPORTS/cost_ledger.md) — running paid-API spend (cap: $0.05/session).
- [Providers](../spike/PROVIDERS.md) — signup URLs, pricing, env vars per renderer.

## Update protocol (for agents)

At session end, append to [[SESSIONS]]. If a non-obvious choice was made, also append to [[DECISIONS]]. If repo state changed (task done / blocked / new), overwrite [[STATE]]. Full protocol in `CLAUDE.md` § Session-log protocol.
