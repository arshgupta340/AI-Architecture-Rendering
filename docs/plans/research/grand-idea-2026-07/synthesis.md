# Synthesis architect — decision-ready verdict

**Headline:** Ship the one defensible primitive — model-locked non-destructive re-rendering — as a Rhino plugin; defer video, editable-splats, entourage-gen, and the copilot as garnish that fails the revision test.

## Verdict on the grand idea

The signal is the unanimity: seven dimensions, seven "viable-with-changes," two red teams converging on one conclusion. Translation: every pillar is a real tech demo and a losing product bet standalone. The grand idea is a capabilities tour, not a wedge.

**(a) Ship-now — the mesh-anchored core.** Rhino→glTF semantic IDs → engine buffers (depth/canny/ID) → FLUX+ControlNet-Union hero → masked `region_edit`. ~90% built and verified at $0.01–0.02/render. This is the *only* stage that is deterministic-plus-one-stochastic-hop and survives "move the window 2 ft" (the mesh re-propagates; the hero re-rolls one view, byte-stable elsewhere). It's also the only thing incumbents structurally can't clone fast: geometry-truth from the *actual model*, not VLM-inferred masks on a flat screenshot.

**(b) Ship-with-changes — static splat backdrop + still turntable.** Keep Spark compositing a *non-editable* splat backdrop around the always-mesh building, hard-labeled "illustrative context, not survey." Replace "continuous video fly-through" with a **still turntable**: 6–12 pre-rendered hero angles the user clicks between — captures ~80% of the fly-through wow, stays per-view maskable, sidesteps the frame-1-vs-frame-240 consistency wall entirely.

**(c) Defer/research — video fly-through, full-360 hero, reproject-from-3D.** Geometry-true video is research-grade: every hosted model (Seedance 2.0, Kling 3.0, Veo 3.1, Ray3.2) warps building geometry across camera motion; Ray3.2's "Modify Video" knobs *loosen* geometry, they don't lock it. The only real fix (GEN3C-style depth/point-cloud V2V) has open weights but zero hosted API — a multi-month self-host build. Keep reproject-from-3D as R&D toward full-360 turntable, but do not over-invest: Nano Banana Pro reference-conditioning is closing the easy-angle cases for free, inside Veras.

**(d) Kill (as pillars) — editable-splat authoring, generative entourage as moat, mutating copilot v1.** Editable/relightable splats are research-stage AND partly obsoleted (Chaos shipped GS relighting + clip-trim in V-Ray 7 U3 / Vantage 3.3.0). Splats fail on glass/thin members (most of architecture), freeze lighting, and carry dimensional-liability exposure. Generative entourage is a thin feature Gendo already ships. A mutating copilot has no undo bus to join and is wrong 1-in-4 (Figma's own 42–74% data) — a time-sink under deadline.

## Recommended product architecture

**Primary DAG (single recommendation):**

`Rhino model (source of truth) → capture button → engine buffers [depth/canny/semantic-ID] → FLUX+ControlNet hero (Modal, scale-to-zero) → masked region_edit layer stack → [optional] Spark static splat backdrop → still turntable (N discrete hero angles)`

- **Client-side (browser, $0):** the R3F/three scene, direct-manipulation region selection, material/entourage/sun/camera edits, turntable navigation, project-file persistence of region→material assignments as re-editable layers.
- **Modal (GPU, scale-to-zero):** FLUX+ControlNet hero + masked re-rolls only. Cost-gate every hero-triggering action in the request path against the session budget. No always-on warm pool (avoids the unverified non-preemptible multiplier).
- **Third-party API:** none on the critical path. Marble/World Labs only as an opt-in backdrop generator, gated behind explicit budget + a client-IP/confidentiality warning (their ToS licenses free-tier content). Prefer self-hosted HY-World 2.0 for confidential/enterprise work — reframe it from "cost lever" to "the only legally viable path for NDA'd geometry."

**How non-destructive editing survives each stage:** the mesh is the *single source of truth for geometry at all times*. Splat and turntable are downstream *renders* of the mesh, never the editable substrate. Region→material assignments persist as layers keyed to semantic element IDs, not baked pixels — so a geometry change re-derives them deterministically. **The one unbuilt foundational piece:** a global transactional command/undo bus. The R3F app currently has only per-feature localStorage stacks. "Every AI edit is a re-editable non-destructive layer / Ctrl+Z works" is a claim without a mechanism until every direct-manipulation UI action routes through one transactional bus. **Build the bus before any copilot** — it is the single most valuable unbuilt piece in the whole vision, worth more than any generative stage, because it is what makes "non-destructive" actually true.

**Fallback (only if Rhino-plugin distribution stalls):** ship the same core as a standalone web app targeting the un-penetrated ~54% of solo/small firms *not* on a Chaos seat — but this loses the model-native advantage and competes in the commoditized $20–40/mo cluster, so it's strictly second choice.

## Phased roadmap

**Phase 0 — this month. "The core, productized."**
- *Entry:* hero + region_edit verified (done).
- *Build:* auth, Rhino-side capture button, project file persisting region→material layers, Modal cost-gating in request path, **the transactional command/undo bus** (route existing UI actions through it).
- *Exit:* an architect opens their own Rhino model, gets a geometry-locked photoreal render, swaps one wall's material, and Ctrl+Z / re-edits it — all persisted, all re-derivable after a geometry change.
- *Wow-demo:* "That wall, in travertine" → coherent re-render in the same file, then "move the window" → everything re-propagates. This is the one demo incumbents can't casually match.

**Phase 1 — this quarter. "Multi-angle without the drift."**
- *Entry:* Phase 0 shipped, first paying users onboarded via Food4Rhino.
- *Build:* still turntable (6–12 discrete hero angles, per-view maskable); reproject-from-3D pushed toward full-360 for the turntable set; static Spark splat backdrop with the hard "illustrative, not survey" label; read-only scene-critique copilot (zero mutation, cheapest UX to validate, hard-capped vision iterations/resolution).
- *Exit:* a client-showable turntable that doesn't drift across the discrete angles; backdrop compositing that survives a sun-time change on the mesh layer (backdrop stays fixed, labeled).
- *Wow-demo:* click-through turntable of a geometry-locked photoreal building with real site context behind it — the "video feeling" without the video failure mode.

**Phase 2 — two quarters. "Prove the premium, or don't."**
- *Entry:* validated retention on core + turntable; explicit budget authorization for live video/splat COGS experiments.
- *Build:* narrowly-scoped live tests of (i) GEN3C-style depth-conditioned V2V self-host on Modal for *concept-only* clips, (ii) SAM-HQ + Gaussian-Grouping "remove that one tree from the backdrop" as the single splat-edit primitive worth shipping, (iii) compound-macro copilot actions gated behind mandatory diff-preview + explicit-apply (never auto-commit).
- *Exit:* live reroll-economics data proving (or killing) a video/splat premium tier before pricing it.
- *Wow-demo:* an art-directable concept clip generated from the model — shipped only if reroll COGS clears margin.

## Integrate-vs-compete

**Compete on the narrow wedge; distribute via the incumbent's *shelf*, not their *pipeline*.** Do not build against the Enscape SDK — it embeds *their* renderer in *your* app; it is not an injection point into their material/mask layer (export-only via NVIDIA MDL). The realistic channel is **Food4Rhino** (10M+ downloads, zero listing fees, Rhino is already the primary host, install base = concept-phase architects who live in the model). Accept the hard truth: you're a *paid* plugin next to *free-bundled* Veras (Nano Banana Pro, in 85/100 top firms). You win only by being decisively better at *one* job for Rhino-native architects — model-locked non-destructive re-rendering with deterministic re-propagation — for the solo/small-firm segment (74% of US firms, only 46% AI-adopting, #1 barrier "unreliable results" not cost) that Chaos's enterprise pricing underserves. **Partner conversation to seed, not depend on:** Twinmotion (visible AI lag, most receptive host) and McNeel/Food4Rhino editorial placement. Do *not* pursue Enscape/V-Ray integration — they don't need you and won't open the layer you'd need.

## Top 8 risks, ranked

1. **Founder builds the exciting 80% Chaos gives away free, instead of the boring defensible 20%.** *Mitigation:* Phase 0 is render-core + command bus only; video/splat/copilot are explicitly deferred behind user-demand gates. This is the single highest risk.
2. **No model-layer moat — Veras runs the same Nano Banana Pro your hero depends on, bundled free.** *Mitigation:* moat is workflow-fit + true 3D-model-native geometry lock (semantic IDs from the mesh), not model capability. Ship speed to a loyal Rhino niche before Chaos prioritizes model-native editing.
3. **Compounding stochastic error (11% end-to-end first-pass yield across the full chain).** *Mitigation:* the minimal DAG has exactly one stochastic hop (masked hero). Never chain generative stages in series; every generative output is a re-derivable render of the deterministic mesh.
4. **Non-destructiveness is a claim without the command/undo bus.** *Mitigation:* build the transactional bus in Phase 0, before any copilot; route all existing UI actions through it so agent-undo and manual-undo don't diverge.
5. **Reroll economics silently break margin (COGS = unit × attempts-to-acceptance; video 3–5×).** *Mitigation:* defer all video/splat COGS out of Phase 0–1; price the render-only tier where serving is $0.01–0.02; validate reroll rates live before pricing any premium.
6. **Dimensional/photometric liability — generated backdrops hallucinate streetscape; 3DGS ~8cm±11cm off LiDAR.** *Mitigation:* hard product rule — all generated/backdrop context labeled "illustrative, not survey"; ground real sites to Genie 3 Street View / Photorealistic 3D Tiles; keep all dimensioned geometry in the mesh.
7. **Nuit beats you if you abandon the 3D-native lock.** Nuit is live, content-marketing the non-destructive-branching thesis; its only gap is being text/image-first, not model-bound. *Mitigation:* never ship a screenshot-only path; the model binding is the entire seam.
8. **Client-IP/confidentiality blocks the hosted splat/world path at firms.** *Mitigation:* self-host HY-World 2.0 for confidential work; make third-party API use opt-in with an explicit data-retention warning; keep the default path fully self-hosted on Modal.

**Bottom line:** the mesh is the product. Everything generative is a downstream, re-derivable render of it. Ship the one real, defensible thing — model-native geometry-locked non-destructive re-rendering — as a Rhino plugin, and let the first 100 users tell you which garnish they'd pay extra for.