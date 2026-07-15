# PRD — Reve Canvas: architecture-native layer editing on Reve's layout API (Track 2, "2D fast-to-market")

**Status:** Draft for founder review · **Date:** 2026-07-14
**Inputs:** deep research pass on Reve 2.x + layouts API (api.reve.com docs, blog.reve.com "The Layout Bet", pricing/license pages, official SDK) + repo synthesis (mesh-first PRD, web3d layer models, spike conventions).
**Relationship to the mesh-first track:** sibling product, shared Photoshop-for-Architects brand and taxonomy. Supersedes nothing — [PRD-v1-mesh-first.md](PRD-v1-mesh-first.md) remains the 3D track. This is the ship-while-the-3D-work-is-in-the-pipeline track.

---

## 0. Executive summary

Reve (reve.com — ex-Adobe Research / ex-Stability leadership; #2 on the Artificial Analysis image arena) made a bet no other frontier image lab made: their model's internal scene representation — a hierarchical JSON **layout** of labeled, bounded regions — is exposed **read/write via API**. You can extract a layout from any image, edit one region ("sofa" → "low cream boucle sofa"; move the lamp; swap the wall material), and re-render with everything else held stable. Their own docs demo interior-design edits as the canonical use case. Their consumer UI, however, is a generic creative canvas: no persistent layer system, no domain taxonomy, no versioning, no CAD awareness.

> **The layout JSON is an editable scene graph over pixels. Nobody has wrapped it in an architecture-native layer system. We can ship in weeks what the mesh-first track ships in quarters — and the layer taxonomy we build here is the same taxonomy the 3D product will speak.**

**V1 is a web app**: an architect uploads a viewport screenshot, draft render, or site photo → gets a **layer panel** of every architectural element (walls, glazing, roof, vegetation, sky…) → swaps materials from a curated swatch library, adds/removes objects, changes lighting — per layer, non-destructively, with full version history and variant branching → re-renders in ~a minute at up to 4K. Plus one thin **Rhino bridge** (push-viewport command). Credits SaaS on the founder's Reve API key, $19–29/mo, solo/small-firm architects.

Honest admissions up front:

- **This track has platform risk the mesh track doesn't.** The entire product sits on one vendor's endpoints, and the layout endpoints are marked *experimental*. Mitigations in §9; the risk is accepted because the build is weeks, not quarters, and the taxonomy/layer IP transfers to the 3D track even if Reve changes underneath us.
- **"Fine-tuned for architecture" means workflow, not weights.** Reve offers no fine-tuning (closed weights, no LoRA path). Our tuning = domain region taxonomy, material prompt scaffolds, saved project references, architect-native defaults. That is also exactly the layer where a moat can exist — Reve owns the model; nobody owns the architect's workflow on top of it.
- **Layers are not pixel layers.** Reve returns one flat image + the layout that describes it; regions are bounding boxes, not masks. Our "layers" are named, typed, persistent handles onto layout regions, carrying edit stacks whose results are immutable snapshots in a version DAG. Photoshop mental model on the surface; git underneath. The UI never claims masks it doesn't have.
- **A ≤$5 validation spike gates all build spend** (§5 Phase 0). If Reve bleeds edits outside the target region on architectural imagery, the product dies for $5.

---

## 1. Product definition

**One-liner:** *Upload your viewport screenshot or draft render, get a layer panel of every architectural element, swap materials and objects per-layer, re-render in a minute — with full version history.*

**Job-to-be-done:** "I have a SketchUp export / Rhino screenshot / phone photo and a client meeting Thursday. I need it to look designed, and I need to try five material options on that facade without redoing anything or learning a rendering suite."

**Target user (beachhead):** solo and small-firm architects (74% of US firms are sole-proprietor or <3 architectural staff — same beachhead as the mesh track), but a **wider funnel**: no Rhino requirement, no plugin install, any image works. Also captures students, interior designers, and the SD/DD-phase "make it presentable" moment that precedes any real rendering pipeline.

**Positioning:** NOT another prompt-to-render button (commoditized; Veras is free-bundled; a dozen "AI archviz" tools exist). We are **the layered one**: the only tool where every element of the image is a named, re-editable, versioned layer — because we're the only ones building on the only model that exposes its scene representation. Competitors:

- **Reve's own app** — the model, none of the workflow: no persistent projects/layers/history, no domain taxonomy, no CAD bridge. Our upstream and our benchmark; if they ship an architecture vertical, see risk §9.5.
- **Veras / D5 / Gendo / prompt-to-render tools** — regenerate whole images; edits drift; no per-element handles. Their users' #1 complaint (48%, Chaos survey: "unreliable results") is precisely what layout-anchored edits address.
- **Photoshop generative fill** — real layers, real masks, but no scene understanding, no re-render coherence, manual masking labor per edit.
- **Nuit** — nearest thesis rival on the versioning/branching axis; text/image-first, no layout-level region handles, no architecture taxonomy.

**Anti-goals (project doctrine, adapted):**
- No prompting as the primary UX. Layers, swatches, and presets are the UX; prompts are plumbing (an "advanced" escape hatch per layer, not the front door).
- No user-visible multi-model choice — Reve's API license prohibits aggregator UX; any provider hedging stays internal (§9.1).
- No fake masks. Region bounds render as honest rectangles/outlines; marketing says "element-aware editing," never "pixel-perfect masking" (until gate G1 ships SAM refinement).
- Nothing dimensioned read off generated content — "illustrative, not survey" stays a hard rule on this track too.
- No unlimited-render tier, ever. Every render is metered ledger spend.

---

## 2. The architecture invariant

**Primary DAG (the whole product):**

```
Source image (upload | Rhino push)
   → extract_layout (Reve)                        → root Snapshot (image + layout, verbatim)
   → auto-layerize (taxonomy match, RegionKeys)   → CanvasLayers (OUR model)
   → staged per-layer edits → explicit Render     → render_layout → child Snapshot
   → variants (DAG branches) · diff overlay · drift score · history replay
```

Invariants:

1. **Every Reve response is stored verbatim** (raw JSON + image bytes) before any parsing or normalization — paid data is never lost to a validation bug, and stored layouts remain re-processable if our model or Reve's schema evolves. (The `save_raw_response` lesson from the spike phase, promoted to product law.)
2. **Snapshots are immutable and append-only.** A "layer edit" never mutates pixels; it produces a new (image, layout) snapshot whose parent pointer records lineage. Undo/redo/variants/history are all reads over the DAG.
3. **The Reve key exists server-side only** (worker function secrets). Every credit-spending call passes through the metered job pipeline: auth → ledger balance check → debit reservation → job → worker → settle. No path from browser to Reve.
4. **Exactly one stochastic engine.** Reve is the only generative stage; no chained generative pipelines (no gen-image → gen-video, no multi-model relay). Same law as the mesh track, same reason: errors compound.
5. **The taxonomy is shared IP.** `packages/arch-taxonomy` is the single vocabulary for semantic classes and material scaffolds, consumed by this app now and by `apps/web3d-prototype` at the convergence milestone (§5).

---

## 3. V1 scope — features and requirements

### F1 — Snapshot/edit-graph engine ⭐ *the core IP*
- **R1.1** `Snapshot { id, imagePath, layout (verbatim jsonb), parentId, producedByEditId, driftScore }` — immutable DAG rooted at the upload.
- **R1.2** `CanvasLayer { name, type ∈ base|material|object|lighting|sky|entourage|text, semantic (taxonomy), regionKeys[], prompt, materialId?, visible, locked, variants[], activeVariantId, sortOrder }` — a persistent handle onto a set of layout regions, deliberately shape-compatible with the web3d `HeroLayer` (same semantic strings; `regionKeys` ↔ `regionIds`; same base/region split). Convergence contract: *a layer is (semantic class, region set, prompt, variant stack); the region-set representation is backend-specific* (Reve labels here, GL id-buffer ints there, mesh GUIDs later).
- **R1.3** `RegionKey` = stable identity encoded into the Reve region label (`${semantic}.${slug}#${suffix}` — labels are free-form ≤255 chars and unique, so they can carry our IDs through round-trips). Spike criterion C6 verifies verbatim round-trip; IoU re-matching is the designed fallback.
- **R1.4** `Edit { layerId, kind ∈ material_swap|object_add|object_remove|object_move|lighting|sky|global_style|text, baseSnapshotId, resultSnapshotId, regionPromptPatches, layoutCommands?, status, creditsCost }`.
- **Acceptance:** 10 mixed edits across 3 layers → history shows 10 edits/N snapshots → step back to any snapshot → branch a variant → reload the project → graph intact.

### F2 — Upload → extract → layer panel
- **R2.1** Drag-drop upload (JPEG/PNG/WebP, ≤20MB) → storage → `extract_layout` job → root snapshot.
- **R2.2** **Auto-layerize:** group returned regions by taxonomy class (fuzzy `ALIASES` matcher over Reve's free-form labels), rewrite labels to RegionKeys, one `CanvasLayer` per group; unmatched regions land in an "Unsorted" layer for one-click manual triage. Region `parent` hierarchy → layer nesting hints (mullions under glazing).
- **R2.3** Canvas region overlay: hover a layer → its bboxes highlight on the image; click a region → select its layer. Honest rectangles.
- **Acceptance (ties to spike C1):** on a typical exterior render, ≥70% of major elements land in correctly-named layers with no manual work.

### F3 — Per-layer edit loop
- **R3.1** Edit surfaces per layer type: **material** → swatch grid (the 29-scaffold library + search/category pills, ported from the web3d Sidebar pattern); **lighting/sky** → preset chips (golden hour, overcast, dusk…, mirroring web3d `MOODS`); **object** → add/remove/move via layout `commands`; every surface has an advanced free-prompt escape hatch.
- **R3.2** Edits **stage** on layers (dirty markers); an explicit **Render button** builds one target layout from the active snapshot + all dirty visible layers and makes **one** `render_layout` call (compound ref: current image + target layout). Batching is the cost-control UX: one ~$0.11 call carries N layer changes. Projected credit cost shows on the button before commit.
- **R3.3** Async job pattern for 40–80s renders: queued → running → done with progress states in a render queue panel; failure refunds the ledger reservation.
- **R3.4** Layer visibility is a render-input flag, and the UI says so: hiding a baked-in layer marks the graph dirty and offers **Rebuild** ("replays N edits ≈ $X — confirm"), replaying remaining visible edits from the nearest clean ancestor. Honest non-destructive: replayable history, not free compositing.
- **Acceptance:** upload exterior render → swap wall to travertine → re-render → geometry outside the wall region visually stable at presentation size → undo to previous version — under 3 minutes, ~$0.22 COGS.

### F4 — Version history, variants, and trust
- **R4.1** Version tree UI = the snapshot DAG; click any node to view; any node can be the base for new edits (branching).
- **R4.2** Variants: re-rolling a layer edit creates sibling snapshots collected on the layer (`variants[]`, `activeVariantId`); side-by-side compare of up to 4 variants.
- **R4.3** **Diff overlay + drift score** on every render completion (client-side canvas diff, zero API cost): heatmap toggle, edited-region outlines, and a badge showing % of pixels changed *outside* the edited regions — the "did it bleed?" trust number, tracked per edit as a product KPI (same metric as spike C2).
- **Acceptance:** render 3 wall variants → compare side-by-side → pick one → history shows the branch; drift badge visible on each.

### F5 — Credits, metering, accounts
- **R5.1** Supabase magic-link auth; per-user append-only `credit_ledger` (delta, reason, job_id, balance_after; insert via RPC only).
- **R5.2** Every job debits before dispatch and settles/refunds on completion; balance and per-action projected cost always visible (CreditMeter).
- **R5.3** V1 billing = **manual credit grants** (admin path). Stripe is gate G2. Tiers designed now, charged later: $19/mo = 100 edit-renders + 20 uploads; $29/mo = 200 + 40; top-ups $5/40 renders.
- **R5.4** Server-side queue smooths the founder-key rate limits (10/min, 200/hr, 2,000/day); per-user daily caps enforced at job creation.

### F6 — Rhino bridge (thin, V1.x)
- **R6.1** `push_to_canvas` script/command: RhinoCommon `CaptureToBitmap` of the active viewport (proven pattern in `spike/rhino_capture.py`) → POST to `/api/ingest` with a hashed device token → browser opens the new project with the extract already queued.
- **R6.2** Device tokens minted in account settings; revocable; no Rhino-side credentials beyond the token.
- **Acceptance:** Rhino model → pushed → layered → wall swapped → rendered, in under 5 minutes, verified live via the repo's Rhino MCP.

### F7 — Export
- **R7.1** Full-resolution download of any snapshot (PNG/JPEG/WebP).
- **R7.2** 2–4× upscale as a metered postprocess action (Reve upscale, ~$0.002/MP) for print/board output.

### Out of scope for V1 (explicit)
Stripe (G2) · SAM/mask refinement (G1 — but `regionKeys` indirection keeps the design mask-ready) · any user-visible multi-model · Photoshop plugin · create-from-prompt as a primary mode (G3) · team/multi-seat (G4) · mobile · video · the cheap v1 endpoints (`/v1 create/edit/remix` — evaluate post-V1 as a "quick edit" cost tier only if economics demand).

---

## 4. Pricing & unit economics

**COGS (Reve credits ≈ $0.00133 ea):** extract_layout ≈ $0.11 · render_layout ≈ $0.11 · v2 create ≈ $0.20 · upscale ≈ $0.002/MP. Typical flows: first upload ≈ $0.11; edit round ≈ $0.11 (batched N edits per render); extract+render ≈ $0.22.

| Tier | Price | Allowance | Full-utilization COGS | Worst-case margin | Expected margin (~50% util) |
|---|---|---|---|---|---|
| Starter | $19/mo | 100 edit-renders + 20 uploads | ≈ $13.30 | ≈ 30% | ≈ 65% |
| Studio | $29/mo | 200 edit-renders + 40 uploads | ≈ $26.60 | ≈ 8% → cap via rollover rules | ≈ 55–65% |
| Top-up | $5 | 40 renders | ≈ $4.40 | — | ~12% floor, priced to protect subscriptions |

- **COGS discipline (inherited from mesh PRD):** model everything as *unit cost × attempts-to-acceptance* — the spike's S7 reroll measurement feeds the real multiplier. If acceptance needs 2 attempts, allowances halve before launch.
- **No flat-unlimited tier.** Allowances + metered top-ups only.
- **Hard ceiling named honestly:** one founder key at 2,000 renders/day caps the whole userbase at roughly ~100 active users × 20 renders/day. Fine through beta; a Reve partnership/quota conversation (sales@reve.com) is a **pre-scale milestone**, not an afterthought.
- Watch item: layout endpoints are experimental — pricing could change under us; ledger architecture makes repricing a config change, not a migration.

---

## 5. Phased roadmap

### Phase 0 — now: the $5 validation spike (go/kill gate)
*Build:* `spike/reve/run_reve_spike.py` (dry-run default, `--live` opt-in, raw responses saved, cost ledger updated). Fixtures: photoreal render (`spike/outputs/e2_house/renders/flux_depth.png`), raw shaded viewport (`spike/outputs/e2_house/beauty.png`), one founder-supplied interior photo.
*Criteria:* **C1** extraction sanity (≥70% of major elements sensibly tagged; taxonomy matcher maps ≥80% of labels) · **C2 (kill gate)** geometry preservation (<5% mean pixel change outside edited region; no warping of windows/rooflines at 100% zoom) · **C3** client-deck quality (founder judgment at full res) · **C4** iterative stability over 5 sequential edits · **C5** shaded-viewport photorealization (gates how hard V1.x sells the Rhino bridge; C5 failure does not kill the web product) · **C6** RegionKey label round-trip.
*Exit:* C1 ∧ C2 pass → Phase 1. C2 fails → kill decision written to DECISIONS.md; sunk cost ≤$5.

### Phase 1 — weeks: V1 web app
*Build order:* skeleton (Supabase schema, auth, job pipeline, upload→extract→overlay vertical slice) → layer engine (taxonomy package, auto-layerize, layer panel, edit loop, render batching) → history/trust (version tree, variants, diff+drift, export/upscale) → beta hardening (manual grants, queue smoothing, deploy Vercel+Supabase).
*Exit:* a stranger uploads an image and reaches a re-rendered material swap in <5 minutes; 10 beta architects with manual grants.
*Wow demo:* screenshot → layer panel appears by itself → "that wall, in travertine" → three variants side-by-side → full history scrub. The demo IS the layer panel doing the work Reve's own UI can't.

### Phase 2 — V1.x
Rhino bridge (F6) → upscale export polish → onboarding templates (exterior/interior/aerial presets).
*Convergence milestone:* `packages/arch-taxonomy` adopted by `apps/web3d-prototype` (its `Layer.semantic`/`HeroLayer.semantic` strings become taxonomy-typed; material ids unify). From then on, a material picked in Reve Canvas is replayable as a PBR assignment in the 3D app.

### Phase 3 — gated (see §6)
SAM-refined masks (G1) · Stripe self-serve (G2) · create-from-prompt as a first-class mode (G3) · team features (G4) · Reve quota partnership (pre-scale).

---

## 6. Evidence gates for deferred features

| Gate | Feature | Ships only when… |
|---|---|---|
| **G1** | SAM-refined region masks (client-side compositing of edited region onto parent snapshot) | bbox bleed is a top-3 beta complaint AND a SAM-HQ spike composites cleanly on ≥3 real projects — until then, honest rectangles |
| **G2** | Stripe self-serve billing | >10 active manual-grant users AND week-2 retention ≥20% |
| **G3** | Create-from-prompt as a primary entry ("start from a brief") | upload-first activation is strong (don't dilute the wedge before it's proven) |
| **G4** | Team/multi-seat | never before 100 paying seats |

---

## 7. Distribution & GTM

1. **Founder-led to first 25 users:** the demo clip is "screenshot → layered by itself → three material options in 5 minutes" posted to Rhino Discourse, r/architecture, architecture Twitter/X, small-firm Discords, studio crit groups.
2. **The Rhino bridge is the hook back into the mesh-track audience** — same forums, same users, and it pre-sells the deeper 3D product under the same brand.
3. **Manual-grant beta** keeps burn bounded (ledger caps) while measuring the two numbers that matter: drift complaints (G1 signal) and week-2 return rate (kill/G2 signal).
4. Do not market as "AI rendering" (commodity shelf); market as **layers for AI images** — the Photoshop noun architects already trust.

## 8. Success metrics

- **Activation:** stranger upload → first re-render < 5 min; ≥60% of signups reach first render.
- **Core value:** ≥50% of week-1 users render ≥2 variants of one layer (the variant loop is the retention event).
- **Trust KPI:** median drift score per edit <5%; drift complaints outside top-3 in beta feedback (else G1 triggers).
- **Business:** 25 manual-grant beta users → ≥20% week-2 return; then G2 → 100 paying seats within 2 quarters.
- **Kill signals respected:** spike C2 fail = never build; <20% week-2 return after 25 users = stop and reassess against the mesh track before further spend.

## 9. Top risks (ranked, with mitigations)

1. **Platform risk on an experimental API** (extract/create/render_layout are flagged experimental; only available direct from Reve; whole product = one vendor). → Spike before build; raw layouts stored verbatim (re-processable); internal `LayoutProvider` interface so the layout source is swappable in principle; revisit-triggers named in DECISIONS. Accepted because build cost is weeks and the layer/taxonomy IP transfers to the 3D track regardless.
2. **bbox-only regions bleed edits into neighbors.** → C2 is the kill gate; per-edit drift badge makes bleed visible instead of hidden; tight child bboxes via region hierarchy; SAM refinement pre-designed behind G1 (regionKeys indirection means masks slot in without a data-model change).
3. **Arch-viz quality unproven** (a published review found melting building windows at zoom). → C3 zoom checks at full res; upscale in the export path; market as *design iteration*, not final-render replacement, until beta evidence says otherwise.
4. **Rate-limit ceiling / key economics.** → Server-side queue smooths 10/min; ledger-enforced per-user caps; top-ups priced to protect margin; Reve partnership conversation before scale.
5. **Reve ships this UI themselves** (they own the model and the layout concept; interior demos are already in their docs). → Speed-to-niche, same posture as the mesh PRD: our moat is arch taxonomy + material scaffolds + versioned project workflow + CAD bridge — none of which a general creative tool prioritizes. If this track dies, the layer IP feeds the 3D product; the brand keeps the audience.
6. **Label round-trip instability** (RegionKeys mangled by render_layout). → C6 tests it for $0.53; IoU re-matching fallback designed in.

## 10. Open questions

- **User-facing brand name** ("Reve Canvas" is internal; shipping under a name containing "Reve" invites trademark trouble — decide before public beta).
- Interior vs exterior as the wedge demo (spike S2/S3 quality difference decides).
- Whether `render_layout` preserves our labels verbatim (C6) or we ship IoU re-matching from day one.
- Supabase region + storage cost posture at 4K image scale (renders are ~5–15MB each; lifecycle policy for orphaned snapshots).
- Whether the cheap v1 endpoints ($0.024–0.04) can serve a "quick tweak" tier without breaking the one-engine invariant (post-V1).

---

*Reve API facts referenced throughout (verified 2026-07-14): layout schema (regions: label ≤255 unique, prompt, bbox normalized 0–1 rectangles, parent, region_type ∈ coarse/medium/fine_detail|text|hand|face; layout width/height multiples of 32, area 3072×2560–4096×4096) · endpoints /v2/image/create ($0.20), extract_layout / create_layout / render_layout ($0.11 ea, experimental), commands add/place/shift/remove/keep/change · ≤8 refs/call · renders 40–80s · rate limits 10/min, 200/hr, 2000/day · license: embedding permitted, aggregator UX prohibited · no fine-tuning offering · official Python SDK github.com/reve-ai/reve-sdk.*
