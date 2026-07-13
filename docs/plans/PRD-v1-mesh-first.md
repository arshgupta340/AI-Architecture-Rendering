# PRD — Model-Locked Rendering for Rhino (v1, "mesh-first")

**Status:** Draft for founder review · **Date:** 2026-07-03
**Inputs:** 17-agent research fleet (7 Sonnet 5 researchers + 7 Opus 4.8 stress-testers + 2 cross-cutting red teams + 1 synthesis architect), run `wf_f03d1538-42b`. Full evidence: [docs/plans/research/grand-idea-2026-07/](research/grand-idea-2026-07/README.md).
**Supersedes nothing** — this is the productization plan on top of the engine-first web3d direction ([wiki/STATE.md](../../wiki/STATE.md), `DECISIONS#web3d-pivot`).

---

## 0. Executive summary

The grand idea (entourage-gen → video fly-through → editable splat world → embedded copilot, plus incumbent integration) was researched and adversarially stress-tested across 7 dimensions. The unanimous finding:

> **Every pillar is a real tech demo; only one is a defensible product.** The mesh is the product. Everything generative must be a downstream, re-derivable render of the mesh — never the editable substrate.

The one defensible primitive — already ~90% built and verified in this repo — is **model-locked, non-destructive re-rendering**: real semantic element IDs + depth/canny buffers from the *actual Rhino model* drive a geometry-locked photoreal render (FLUX+ControlNet on Modal, $0.01–0.02/render) with per-region, byte-stable re-edits. It is the only stage in the whole vision that survives the industry's #1 pain: **"move the window 2 ft" arriving after renders are done** — the mesh re-propagates deterministically; incumbents' AI (Veras = VLM-inferred masks on a flat screenshot) structurally cannot.

**V1 ships that primitive as a Rhino plugin distributed on Food4Rhino**, wrapped in the one unbuilt foundational piece: a **global transactional command/undo bus** that makes "non-destructive" true rather than claimed. The fly-through wow is delivered as a **still turntable** (6–12 discrete geometry-locked hero angles), not AI video. Splats ship as a **static, hard-labeled backdrop**. The copilot ships **read-only first**. Video generation, editable-splat authoring, and mutating copilot actions are explicitly deferred behind evidence gates defined in §6.

Why this shape (full argument in §2 and the research appendix):
- **Veras is free.** Chaos bundles Veras (running Nano Banana Pro — the same class of model our hero uses) into every Enscape/V-Ray/Corona tier; Enscape sits in 85 of the top 100 firms. There is zero model-layer moat. The only durable seam is **true 3D-model-native geometry lock** — semantic IDs from the mesh, not VLM tags on pixels.
- **AI video warps buildings.** Every hosted model (Seedance 2.0, Kling 3.0, Veo 3.1, Ray3.2) hallucinates/warps geometry across camera motion; practitioners: *"useless at anything where the building has to look the same in frame 1 and frame 240."* The keyframe-interpolation workaround is already a shipped commodity (Carve, Vibe3D). Geometry-true V2V (GEN3C/DepthDirector pattern) has open weights but zero hosted APIs — research track, not MVP.
- **Editable splats don't exist at product quality.** Splat editing/relighting/insertion is research-stage; splats bake lighting, fail on glass/thin members (i.e., most of architecture), and carry dimensional liability (~8 cm ± 11 cm vs LiDAR). Chaos already shipped splat relighting + clip-trim (V-Ray 7 U3, Vantage 3.3.0) — that half of the "whitespace" closed while we watched.
- **Mutating copilots are wrong ~1-in-4** (Figma's own 42–74% success data) and there is currently no global undo bus for agent actions to join. Read-only critique first; mutation only after the command bus, always diff-preview-then-apply.

---

## 1. Product definition

**One-liner:** *Turn your actual Rhino model into a client-ready photoreal image — change one material or one region and re-render without the building drifting — and when the design changes, everything re-propagates.*

**Job-to-be-done (the invoice-justifying sentence):** "I live in Rhino. I need photoreal stills for clients this week, the design will change after I render, and I refuse to re-do the work every revision round."

**Target user (beachhead):** Rhino-native architects in solo/small firms.
- 74% of US firms are sole proprietors or <3 architectural staff (AIA, Feb 2026); only 46% of small firms use AI vs 78% of 50+ firms.
- Their #1 adoption barrier is **"unreliable results" (48%), not cost** (Chaos/Architizer 2026 survey). Reliability *is* the product.
- They are underserved by Chaos's enterprise-priced suites and are exactly Food4Rhino's install base (10M+ downloads, zero listing fees).

**Positioning:** NOT "a cheaper/better AI render button" (that tier is commoditized at $20–40/mo and Veras is free-bundled). We are **the model-locked one**: the only tool where the AI edit is anchored to real per-element geometry and survives design revisions. Competitors:
- **Veras (Chaos)** — free, distribution king, but VLM-on-a-screenshot; concept-grade; documented failures on entourage fidelity and cross-view consistency.
- **Nuit** — the nearest thesis rival (branching, non-destructive project tree); its structural gap is that it is text/image-first, **not bound to a real 3D model**. If Nuit ships Rhino/Revit binding, our seam narrows — primary watch item.
- **D5 Render 3.0** — 15+ AI features, scene-native, $30–38/mo; geometry drift up to 0.5 m on AI generations per independent review.
- **Gendo** — already ships 2D entourage cutouts + in-canvas populate + copilot; treat as the competitor to beat on entourage, not the validator.

**Anti-goals (unchanged from project doctrine, sharpened by research):**
- No prompting as the primary UX. Direct manipulation; AI is invisible plumbing.
- No screenshot-only path. The model binding is the entire moat (kill it and Nuit beats us).
- No generative stage may ever become the source of truth for geometry.
- Nothing dimensioned may ever be read off generated content ("illustrative, not survey" is a hard rule, not a caption).

---

## 2. The architecture invariant

**Primary DAG (the whole product):**

```
Rhino model (single source of truth, always)
   → capture (plugin button)
   → engine buffers [beauty / linear depth / canny∪ID-edges / per-element semantic ID]
   → FLUX+ControlNet hero render (Modal, scale-to-zero, $0.01–0.02)
   → region_edit layer stack (masked, byte-stable elsewhere, keyed to semantic IDs)
   → [optional] static Spark splat backdrop (labeled illustrative)
   → still turntable (N discrete hero angles)
```

- **Exactly one stochastic hop** (the hero). Never chain generative stages in series — the red team modeled end-to-end first-pass yield of the full grand-idea chain at ~11% (0.8 entourage × 0.7 hero × 0.4 video × 0.5 splat). Errors compound geometrically *and* photometrically (mismatched light-transport signatures stack; viewers register it pre-consciously).
- **Client-side ($0):** R3F scene, region selection, material/entourage/sun/camera edits, turntable navigation, project persistence.
- **Modal (GPU, scale-to-zero):** hero + masked re-rolls only. Cost-gate every GPU-triggering action in the request path. No always-on warm pool.
- **Third-party APIs on the critical path: none.** Marble/World Labs = opt-in backdrop generator behind an explicit budget + client-IP warning (their ToS licenses free-tier content; NDA'd geometry cannot go there). Self-hosted HY-World 2.0 on Modal is the confidentiality-compliant backdrop path for firm work — a legal requirement for the segment, not a cost lever.
- **The revision test is the design constraint:** every feature must answer "what happens when the window moves 2 ft after renders are done?" Mesh edits re-propagate; the hero re-rolls per view (masked); layers re-derive from semantic IDs. Anything that must be regenerated from scratch on a geometry change is disqualified from the interactive scene.

---

## 3. V1 scope — features and requirements

### F1 — Transactional command/undo bus ⭐ *the foundational unbuilt piece*
The single most valuable unbuilt piece in the whole vision. Today the app has per-feature localStorage stacks; "non-destructive" is a claim without a mechanism.
- **R1.1** One global transactional bus; *every* mutation (material assign, entourage place/remove, sun/sky change, camera save, layer toggle, future agent action) is a command object with do/undo, grouped into labeled transactions.
- **R1.2** Ctrl+Z / Ctrl+Shift+Z across all features, in one linear history (branching history is a fast-follow, not V1).
- **R1.3** Project file = serialized command history + current state snapshot; layers keyed to semantic element IDs so a geometry re-capture re-derives assignments deterministically.
- **R1.4** All existing direct-manipulation UI actions route through the bus (or agent-undo and manual-undo diverge — disqualifying for the later copilot).
- **Acceptance:** perform 10 mixed edits across 4 features, undo all 10, redo all 10, reload the project, history intact.

### F2 — Rhino capture plugin (Food4Rhino distributable)
- **R2.1** One-button capture from Rhino 8: viewport beauty + linear depth + per-element semantic ID buffer + camera, pushed to the web canvas (existing `rhino_export_gltf.py` / capture path, productized as a proper plugin package — Grasshopper component acceptable for beta, .rhp for launch).
- **R2.2** Re-capture of a changed model preserves semantic ID stability for unchanged elements (IDs are the layer keys — this is load-bearing).
- **R2.3** Installable by a stranger: signed package, no venv/CLI steps, Food4Rhino listing with screenshots.
- **Acceptance:** a non-founder Rhino user goes from download → captured model → hero render in <15 minutes without support.

### F3 — Geometry-locked hero render (productize what's live)
- **R3.1** Existing FLUX.1+ControlNet-Union Modal backend (live, verified) behind auth; per-user API keys retired in favor of app auth; **rotate the exposed HF token** (open item from 2026-06-15).
- **R3.2** Cost gating in the request path: per-session budget meter visible in UI; hero-triggering actions show projected cost; hard stop at user-set cap.
- **R3.3** Region re-roll (`region_edit`) exposed as layers in the bus (F1) — every AI edit is an undoable, re-editable layer.
- **R3.4** Warm-keeper stays opt-in (existing 🔥 toggle); no always-on GPU.
- **Acceptance:** the Phase-0 wow demo (§5) runs end-to-end on a stranger's model.

### F4 — Still turntable (the fly-through answer without the failure mode)
- **R4.1** 6–12 saved views → batched same-seed hero renders (existing `heroCaptureViewsFn` path) presented as a click-through/scrub turntable; per-view region re-rolls allowed.
- **R4.2** Reproject-from-3D (existing verified core) applied across the turntable set to pin materials/lighting for adjacent views; full-360 remains R&D (do not block V1 on back-view reconstruction).
- **R4.3** Export: image set + an auto-assembled MP4 slideshow with crossfades (a *presentation* of stills — not generative video; no geometry risk).
- **Acceptance:** a client-showable 8-view turntable with no material/geometry drift visible at presentation size across adjacent views.

### F5 — Splat context backdrop (static, honest)
- **R5.1** Existing Spark compositing path, productized: drop-in `.spz/.ply`, alignment controls, shadow-catcher.
- **R5.2** Hard-labeled **"Illustrative context — not survey"** watermark/badge whenever a generated backdrop is present; measurement tools disabled on backdrop content.
- **R5.3** Time-of-day is pre-baked states on the backdrop (dawn/noon/dusk swap), never a live slider promise — splat lighting is frozen at generation; mesh HDRI is matched per state.
- **R5.4** Backdrop sources: (a) user-supplied capture, (b) Marble API (opt-in, budget-gated, client-IP warning), (c) self-hosted HY-World 2.0 on Modal (deploy-gated; the NDA-safe path).
- **Acceptance:** building mesh + backdrop composite survives a sun-state swap without a visible seam at presentation size.

### F6 — Entourage: curate first, light-coherent always
Entourage is table stakes, not a moat (Gendo ships the generative thesis today). Our edge is that we own the true buffers and the real sun.
- **R6.1** Curated library remains primary (existing 29 PBR materials + 12 CC0 species; expand tree/people/vehicle sets from CC0/licensed sources; fix the known tree-scale issue).
- **R6.2** **Light-coherent insertion:** entourage placed in 3D is re-rendered *through the same hero pass* as the building — one light transport, attacking the unanimous "weightless, sourceless, plastic" AI-entourage failure mode. This is the one entourage feature Gendo structurally cannot do.
- **R6.3** Entourage assignments are bus commands keyed to scene anchors; they survive geometry edits.
- **R6.4** Generative 2D cutouts (chromakey pipeline) = Phase-2 nice-to-have; generated 3D meshes for named foreground objects = out (uncanny next to precise geometry); splat entourage (TripoSplat) = fenced R&D only, fixed-lighting hero stills only.

### F7 — Read-only copilot (validate before any mutation)
- **R7.1** Docked chat + action-log panel over the *typed scene graph* (semantic elements, layers, entourage, sun, camera): scene critique, composition feedback, grounded material recommendations from the real swatch library.
- **R7.2** Zero mutation in V1. No tool that writes.
- **R7.3** Vision loops hard-capped (iteration count + screenshot resolution) with a live $-spent meter; prompt caching on from day one (agent loops cost ~O(n²) in naive form).
- **R7.4** Mutation graduates only per §6 gate G3: bus exists (F1) + every action diff-preview-then-apply + never auto-commit.

### Out of scope for V1 (explicit)
AI video generation of any kind (incl. keyframe interpolation — commodity, see §6 G1) · editable-splat authoring (research) · splat insertion/relighting · mutating copilot · generative 3D entourage · Revit/SketchUp hosts (post-V1) · team/multi-seat features · standalone-web GTM (fallback only, per synthesis).

---

## 4. Pricing & unit economics

- **V1 tier: $29–39/mo** ("Rhino-native model-locked rendering"), anchored against Veras paid ($29–59) and D5 Pro ($38) — *not* framed as cheaper-than-Enscape (you cannot undercut free-bundled).
- Serving cost at V1 scope is deterministic + one cheap stochastic hop: ~$0.01–0.02/hero render on Modal A100 scale-to-zero. At 50–150 renders/user/month, COGS ≈ $0.50–3.00 → **>90% gross margin** without video/splat COGS.
- **COGS discipline:** model all future generative COGS as *unit cost × attempts-to-acceptance* (video rerolls run 3–5×). No flat-rate bundling of video/splat ever — metered credits only, and only after gate G1/G2 evidence.
- The bimodal-usage trap (heavy shops vs one-pitch-a-quarter users): V1 flat tier is safe *because* serving is near-free; revisit only when expensive stages ship.
- Watch item: verify Modal's non-preemptible/region multipliers before any warm-pool decision (unverified claim; only bites if we break the no-always-on rule — so don't).

---

## 5. Phased roadmap

### Phase 0 — this month: "The core, productized"
*Entry:* hero + region_edit live-verified (done 2026-06-15).
*Build:* F1 command bus → F2 capture plugin → F3 auth/cost-gating/HF-token rotation → project persistence.
*Exit:* a stranger's Rhino model → geometry-locked photoreal render → one wall re-materialed → Ctrl+Z works → geometry change re-propagates. All persisted.
*Wow demo:* **"That wall, in travertine" → coherent re-render → "move the window 2 ft" → everything re-propagates.** The one demo Veras/D5 structurally cannot match.

### Phase 1 — this quarter: "Multi-angle without the drift"
*Entry:* Phase 0 shipped; Food4Rhino listing live; first paying users.
*Build:* F4 turntable + reproject hardening → F5 labeled splat backdrop (incl. HY-World 2.0 self-host deploy) → F6 light-coherent entourage → F7 read-only copilot.
*Exit:* client-showable turntable, no drift across adjacent angles; backdrop survives sun-state swap; ≥1 architect uses the copilot critique weekly by choice.
*Wow demo:* click-through turntable of a geometry-locked photoreal building seated in real site context — the video *feeling* without the video failure mode.

### Phase 2 — two quarters out: "Prove the premium, or don't" (all gated, §6)
- G1-gated: depth/G-buffer-conditioned V2V (self-hosted Wan2.2-Fun-Control-Camera / GEN3C-pattern on Modal) for *concept-clip* video — our differentiation is the geometry-locked control signal from our own engine, never the video model.
- G2-gated: the ONE splat edit primitive near product quality — "remove that object from the backdrop" (SAM-HQ + Gaussian-Grouping masking + inpaint). Removal only; insertion/relighting stays research.
- G3-gated: compound copilot macros (diff-preview-then-apply, never auto-commit).
- Revit or SketchUp as host #2 (Revit has native BIM semantics; prior research in `docs/plans/research/host-integration.md`).
*Exit:* live reroll-economics data that prices (or kills) a metered premium tier.

---

## 6. Evidence gates for deferred pillars

| Gate | Pillar | Ships only when… |
|---|---|---|
| **G1** | Video fly-through | (a) ≥20% of active users export turntables monthly AND ask for motion; (b) a self-hosted depth-conditioned V2V run on Modal produces 1 client-showable 5 s clip of a *specific* building in ≤3 attempts; (c) per-clip COGS × measured attempts clears margin at metered pricing; (d) licensing resolved (Runway/US or self-hosted Wan for deliverables; Kling/Seedance/Veo confined to internal concept use — Veo is Pre-GA commercial-prohibited; Kling/Seedance carry China-jurisdiction licensing). |
| **G2** | Splat object-removal | The narrow spike (capture → segment → remove → inpaint → re-render, one real scene) hits presentation quality; feature stays removal-only. |
| **G3** | Mutating copilot | F1 bus routed under 100% of UI actions; every agent action diff-preview + explicit-apply; measured action-acceptance ≥80% in dogfood before default-on. |
| **G4** | Generative entourage | User demand signal from V1 cohort; chromakey 2D pipeline only; licensing standardized (self-hosted or Meshy-paid/Rodin-class terms); never splat entourage in the interactive scene. |

---

## 7. Distribution & GTM

1. **Food4Rhino** is the channel (10M+ downloads, $0 listing, exactly our user). Accept the hard truth: we are a *paid* plugin next to *free* Veras — we win only by being decisively better at the one job.
2. **Founder-led acquisition to 100 users:** Rhino forums/Discourse, architecture-school studios, small-firm Discords, direct outreach with the Phase-0 wow demo (the revision demo, not a beauty reel).
3. **McNeel editorial** placement push once the listing has reviews; **Twinmotion** partner conversation seeded (most AI-lagging incumbent, most receptive) — seed, don't depend.
4. **Do not** build against the Enscape SDK (it embeds *their* renderer in *your* app; no material/mask-layer access exists — export-only via NVIDIA MDL). Do not pursue Chaos partnership; they bundle for free what partners would sell.
5. **Competitor watch cadence:** hands-on Nuit teardown in week 1 (if Nuit ships real 3D-model binding, our seam narrows — the single biggest strategic watch item); quarterly re-check of Veras video features, D5 AI drift-fidelity, Chaos splat tooling. Assume Chaos closes any feature we ship within 12–18 months — this is a **speed-to-niche bet, not a castle bet**.

## 8. Success metrics

- **Activation:** stranger install → first hero render <15 min; ≥60% of installs reach first render.
- **Core value:** ≥50% of week-1 users perform a region re-roll; ≥30% return after a geometry re-capture (the revision loop is the retention event).
- **Quality (the 48% "unreliable results" barrier):** hero geometry-lock edge-alignment ≥93% (current tightened-lock benchmark); zero critical geometry failures in the demo path.
- **Business:** 100 paying seats within 2 quarters of Food4Rhino listing; churn <5%/mo; COGS <10% of revenue at V1 scope.
- **Kill signal respected:** if the Phase-0 wow demo doesn't convert Rhino-forum architects at meaningful rates, the problem is positioning or the seam is smaller than research says — stop and reassess before Phase 1 spend.

## 9. Top risks (ranked, with mitigations)

1. **Founder builds the exciting 80% Chaos gives away free instead of the boring defensible 20%.** → Phase 0 is render-core + command bus *only*; everything shiny sits behind §6 gates. (Highest risk; this PRD is itself the mitigation.)
2. **No model-layer moat (Veras runs the same class of model, free).** → Moat = workflow-fit + true model-native lock; ship speed to a loyal Rhino niche.
3. **Compounding stochastic error.** → One stochastic hop, ever. Generative outputs are re-derivable renders of the mesh.
4. **"Non-destructive" stays a claim.** → F1 bus is Phase 0, before any copilot.
5. **Reroll economics silently break margin.** → No video/splat COGS in V1; metered credits + measured attempts-to-acceptance before any premium tier.
6. **Dimensional/photometric liability.** → "Illustrative, not survey" hard rule; measurement disabled on generated content; dimensioned geometry lives only in the mesh.
7. **Nuit closes the seam.** → Week-1 teardown; never ship a screenshot-only path; accelerate host binding depth (re-capture stability R2.2).
8. **Client-IP blocks hosted world/splat APIs at firms.** → Self-hosted HY-World 2.0 path; third-party APIs opt-in with explicit retention warnings; default fully self-hosted on Modal.

## 10. Open questions

- Grasshopper-component beta vs .rhp for launch packaging (speed vs polish) — decide at Phase-0 start.
- Auth/billing stack for the web canvas (needs selection; nothing in repo yet).
- Semantic-ID stability contract across Rhino edits (R2.2) — needs a spike defining ID persistence rules for split/joined/copied geometry.
- Whether Phase-1 turntable uses same-seed batching alone or same-seed + reproject pinning by default (quality/cost tradeoff to measure).
- Marble vs HY-World 2.0 backdrop quality gap on architectural streetscapes (needs one budgeted live comparison).

---

*Research appendix (per-dimension reports + adversarial stress-tests + red teams + synthesis): [docs/plans/research/grand-idea-2026-07/](research/grand-idea-2026-07/README.md)*
