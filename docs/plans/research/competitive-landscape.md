# Competitive Landscape — AI Arch-Viz, mid-2026

> Research date: 2026-06-11 (Sonnet agent, web research). Feeds positioning in [master plan v2](../master-plan.md).

## Verdict on our gap

**The complete workflow — click a pre-tagged region → pick a material from a swatch library → coherent local re-render → non-destructive layer — is unshipped in any product as of June 2026.** Each component exists somewhere; the intersection exists nowhere:

- **Region selection:** Veras 4.5 "Smart Selection" (May 2026) — 1-click AI selection by object/material/category. Closest shipped feature; what happens *after* the click is still a text prompt.
- **Swatch-driven material:** only consumer-grade approximations (Spacely "upload texture + select area", MyArchitectAI swatch upload). No curated professional library anywhere.
- **Non-destructive layers:** only Photoshop (mask+prompt, not swatch, not architectural). No arch-viz AI tool has a layer model.

## Market structure

Bifurcated: (a) real-time renderers with AI sprinkled on (D5, Enscape, V-Ray, Lumion, Twinmotion) — materials handled traditionally in 3D; (b) diffusion re-renderers from screenshots (Veras, PromeAI, LookX, Visoid, mnml.ai, SketchUp Diffusion, Krea). Our product lives in (b) but with (a)'s ground-truth data via plugins — a lane nobody occupies.

Key business event: **Chaos acquired EvolveLAB/Veras (Feb 2025)** — Veras now bundled with Enscape, 7 host integrations, ships every 4–6 weeks.

## Veras deep-dive (closest competitor)

| Version | Date | Feature |
|---|---|---|
| v2.4 | Aug 2025 | Enscape selection by material/object |
| v4.0 | Feb 2026 | Nano Banana Pro engine; image reference input |
| v4.1 | Feb 2026 | "Material" reference type (match a reference photo) |
| v4.4 | May 2026 | Modify mode (materials in selection) + Replace mode |
| v4.5 | May 2026 | **Smart Selection** — runs on **Vision Banana** (confirmed, EvolveLAB forum; non-public Google partner access). Cached/persisted selection maps. |

Missing from Veras: browsable swatch library, non-destructive layers, applying a *specific* material without typing a prompt. Their own value framing is "you just change the prompt" — the exact failure mode our product removes. **Important:** Veras is screenshot-level; it does not extract depth/ID-masks/semantics from hosts. Estimated 6–12 months for them to close the swatch+layers gap if they choose to.

## Threat ranking

1. **Veras/Chaos** — right architecture to add a swatch picker (Enscape material IDs + Cosmos PBR library + distribution). Fastest mover.
2. **Spacely AI** ($1M seed) — converging on the same UX from consumer interiors (Point & Edit, Material Visualizer, SketchUp extension). Missing pro library, BIM, layers, exteriors.
3. **Adobe** — owns every piece (Generative Fill layers + Substance materials + Firefly); announced architecture-aware AI in beta for early 2026. A product decision away from our whole product, with 35M-subscriber distribution.

## Demand evidence (architect pain points)

- Architects reject ~80% of first-pass AI output (gloss, wrong materials, floating furniture).
- Top complaints: "modify specific elements without regenerating everything"; "changing curtain wall bronze→silver requires full regeneration with unpredictable results"; prompt fatigue ("6 hours getting prompts right").
- **Multi-view consistency is the unmet enterprise need**: developers need 8–12 coordinated angles with identical materials; no tool solves it (Veras same-seed is partial; arXiv 2503.03068 is research).
- Adoption gap: 44% of architects use AI for concepts, only 11% have it in formal viz workflows (Chaos State of ArchViz 2025) — a large uncaptured middle that needs *control*, not more generation.

## Positioning implications

1. **The prompt is the failure mode, not the feature.** Every competitor doubles down on better prompting; we remove it.
2. **Geometry preservation is becoming table stakes; the moat is the material system**: curated architect-grade swatch library (manufacturer SKUs), non-destructive layers, multi-view material lock.
3. **Scheme comparison via layers** (Scheme A travertine / B corten / C fiber-cement, toggled live in a client meeting) is a workflow-adoption reason no competitor offers.
4. **Plugin-extracted ground truth** (our pivot) is structurally ahead of Veras's screenshot pipeline and defensible for as long as they stay image-level.

Pricing norms: AI-only tools $20–79/mo; BIM-integrated $29–199/mo. Funding: Visoid €700K, Spacely $1M; no notable shutdowns — additive market, pre-shakeout.

## Source index

Chaos/Veras: chaos.com/veras, blog.chaos.com (4.0, what's-new, AI tools, State of ArchViz 2025), design8.com changelogs, forum.evolvelab.io (4.5 thread — Vision Banana confirmation). Acquisition: chaos.com/press, aecmag.com. Pain points: ravelin3d.com reality-check, forums.cgarchitect.com, transparenthouse.com, archrender.ai. Adjacent: spacely.ai, reimaginehome, collov, homedesigns.ai, cylindo, threekit, Adobe Substance/Firefly announcements. Multi-view: arXiv 2503.03068.
