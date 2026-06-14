---
type: log
updated: 2026-05-19
---

# Decision Log

Append-only. **Newest at top.** One entry per non-obvious or non-reversible choice — what we picked, what we considered, why.

Each entry follows the same shape so it can be scanned in 15 seconds:

```
## YYYY-MM-DD — <decision title>           {anchor: kebab-case-title}
**Decision:** the choice, in one sentence.
**Context:** what prompted it.
**Alternatives considered:** 1–3 bullets, briefly.
**Reasoning:** why this over the alternatives.
**Revisit if:** what would invalidate this.
```

---

## 2026-06-14 — Client-ready render = the WebGPU realtime Stage made presentable + captured high-res; T3/T4 deferred {#web3d-clientready-composition}

**Decision:** After the research sweep ([[research/web3d-clientready]]), the client-ready image is **NOT a new render route** — it is the **existing WebGPU realtime Stage made presentable then captured at high-res**: expanded KTX2/jpg materials → real CC0 entourage → golden-hour HDRI + atmosphere → a subtle TSL/post grade → Presentation mode + high-res Export. This whole path is **$0, deterministic, interactive, and was built this session**. The Gaussian-splat environment (T3) and depth+canny FLUX diffusion hero (T4) are **explicitly deferred to scaffold-only** — they are paid and/or renderer-forking finishing layers, documented (not built).

**Context:** Refines [[#client-ready-render]] (the planning-phase "compose all four routes" decision) with what the deep research actually found about cost, renderer compatibility, and effort. The build phase delivered the $0 tracks (T1/T2/T5/T6) and verified them; T3/T4 got a research bible instead of code.

**Alternatives considered:** (a) Build the splat-context now — rejected: no three.js WebGPU splat renderer exists in 2026 (Spark/mkkellogg/drei are all WebGLRenderer-only), so splats can't appear in the WebGPU quality tier; a *good* generated environment costs ~$20/mo (World Labs Marble) or a capture rig; baked-lighting-vs-our-sun mismatch is unsolved at $0. (b) Wire the FLUX diffusion hero now — rejected: FLUX.2 has NO hosted depth/canny ControlNet (only a local 80GB-VRAM checkpoint), the geometry lock stays FLUX.1-dev Union, and the call is paid (~$0.04–0.13/img) needing a FAL_KEY backend shim (app is backendless) — gate behind explicit auth + the $0.05 cap. (c) Lightmap bake — deferred: the model's `uv1` is a box-projection not a real unwrap; runtime N8AO/SSGI already covers exterior GI.

**Reasoning:** The $0 realtime tracks deliver ~90% of the "toy→real" jump (entourage + materials + grounding + grade + atmosphere) with full live editing and zero vendor/cost risk; the export + presentation mode turn that into an actually-sendable file. T3/T4 are higher cost/risk for the last 10% and fork either the renderer or the budget — best as opt-in finishing layers once the realtime base is rich, exactly the order shipped.

**Revisit if:** a production three.js WebGPU/TSL Gaussian-splat renderer ships (unforks T3), or BFL/fal host a FLUX.2 depth+canny ControlNet (upgrades T4), or a client demands the literal Lumen/Nanite look while navigating (→ pixel-streamed UE).

**Orchestration note (reusable):** Same-tree parallel build agents on **strictly disjoint files** merge with zero conflicts IF the one universally-shared file (`store.ts`) is **pre-edited by the orchestrator with every slice up front** so agents only *read* it, and all cross-cutting wiring (shared `App`/`NavBar`/stages) is reserved for the orchestrator. De-risk every asset-download URL before fan-out. This beat worktree isolation (no node_modules-per-worktree, no merge step) for a 3-agent web build.

---

## 2026-06-14 — Path to a client-ready render: compose WebGPU-realtime + consistency-locked diffusion + splat context; WebGPU is the live quality tier {#client-ready-render}

**Decision:** The route to an architect-sendable, "decked-out" render is a **composition**, not one technique: (1) push the **WebGPU real-time** tier (SSGI/GTAO/TRAA + HDRI IBL + VSM shadows — now built) with a much bigger material library, real entourage, lightmaps + atmosphere; (2) an optional **diffusion hero** still on top, with the **hallucination/consistency problem solved by conditioning on the render's own depth + canny edges** (the depth+canny multi-ControlNet we already proved, [[#render-mask-registration]]) and single-still scope; (3) a **Gaussian-splat environment** for photoreal surroundings around the editable polygon building; (4) **Twinmotion / UE Lumen** as the absolute ceiling (runbook ready). WebGPU is the live quality tier; splat-bake-of-the-whole-scene and pixel-streamed UE stay **terminal "publish" exports** (they bake away live editing).

**Context:** The 3 render modes ([[#web3d-realism-tiers]]) are a strong base but minimal — sparse materials, placeholder entourage, bare environment. User wants a client-ready render and named the two hard problems himself: diffusion hallucination/inconsistency, and generating rich environments. Next chat is ultracode multi-agent ([[../docs/HANDOFF-web3d.md]] §NEXT-STEPS).

**Alternatives considered:** (a) Diffusion-only hero as the *core* — rejected: naive diffusion hallucinates geometry + breaks cross-view consistency (the old 2D spike's whole pain); only safe when conditioned on the render's depth+edges and scoped to one still. (b) Splat-bake the whole scene (D5-Render approach) as the *editor* — rejected: it bakes materials, killing the live per-element-swap moat; keep it a publish export. (c) Pixel-streamed UE — the true Lumen look but per-viewer GPU cost + abandons $0/client-side; reserve for explicit client demand.

**Reasoning:** Each route fixes a different gap (materials/entourage/atmosphere → WebGPU realtime; photoreal polish → diffusion-locked; surroundings → splat; ceiling → Lumen). Composing them — with diffusion constrained by our own ControlNet work so it can't drift — keeps geometry truth + live interactivity while reaching send-quality.

**Revisit if:** depth+canny-locked diffusion still hallucinates unacceptably on real renders; or a text-to-3D-splat environment proves too low-fidelity / too heavy for the web; or the WebGPU-realtime tier alone (+ lightmaps + atmosphere) already clears the client bar.

---

## 2026-06-13 — Realism path: bank WebGL2 wins now; client-side UE5 is a parallel spike, not a pivot {#web3d-realism-tiers}

**Decision:** Pursue front-end photorealism in tiers. **Now:** upgrade the live WebGL2 R3F stack (post-processing AO/bloom/AgX, real transmission glass, VSM soft shadows, richer IBL) — $0, fully interactive, no dependency. **Parallel spike (low commitment):** a "Cinematic (UE5)" toggle via **Wonder Interactive / SimplyStream** (client-side UE5 over WebGPU+WASM) for a baked-archviz hero — to be *evaluated*, not bet on. **Later:** a staged **WebGPU three.js** migration (SSGI/GTAO/TRAA) for the ceiling. Do NOT adopt Unreal as the core.

**Context:** User wants Enscape/Lumion/Twinmotion quality on the web and surfaced SimplyStream ("the death of pixel streaming"). EXA deep-research ([[research/web3d-ue-browser]]) established: SimplyStream is real (Epic MegaGrant, live `garage.cjponyparts.com` configurator, self-serve upload-a-build, local/hybrid/remote smart-render) BUT (1) **no Nanite/Lumen in-browser** → it's baked archviz, *not* the live-Lumen arcway look (that's cloud pixel-streaming); (2) you **upload a packaged UE build** authored at build time — our live Rhino→glTF edits can't stream into it (glTFRuntime-in-WASM is unverified); (3) **5% UE royalty above $1M revenue**; (4) vendor = 2-person seed-stage startup. A tuned WebGPU three.js reaches comparable realism (both lack Lumen) with full interactivity, $0, and no royalties.

**Alternatives considered:** (a) Pivot to client-side UE5 now — rejected: heavy per-model UE pipeline, sacrifices our live-edit moat *in that view*, vendor/royalty risk, and it isn't even the true Lumen look. (b) Cloud pixel-streamed UE5 (the real arcway look) — rejected for now: per-viewer GPU cost, the exact thing we set out to avoid; revisit only if a client demands pixel-perfect Lumen while freely navigating. (c) Stay WebGL2 forever — rejected: WebGPU is the realism ceiling worth a later spike.

**Reasoning:** The cheap WebGL2 wins are immediate, interactive and $0; the UE toggle is worth a proof-of-concept but its honest ceiling (baked, no Lumen) doesn't justify adopting the whole Unreal toolchain as the core; WebGPU three.js is the better long-term bet because it keeps interactivity + $0.

**Revisit if:** a SimplyStream POC looks dramatically better on our model than the WebGPU three.js path AND the per-model UE build cost is acceptable; or a client needs literal arcway/Lumion fidelity (→ pixel-streaming); or glTFRuntime-in-WASM matures enough to stream our live scene into UE.

---

## 2026-06-13 — Geo-context: bring the city to the model (tiles→local feet), not the model to the globe {#web3d-geo-context}

**Decision:** Real-world site context loads **Google Photorealistic 3D Tiles** via `3d-tiles-renderer`'s **`ReorientationPlugin`**, which re-centres the tileset so the site lat/lon sits at the **local world origin (Y-up)**. An outer group then **scales metres→feet (×3.2808)**, offsets to the building's ground-centre (`siteAnchor`), and rotates for north (`heading`). The model and every existing feet-based system (shadows, entourage heights, box-projected UVs, saved views) stay **untouched**. Site lat/lng is the **same** state the sun uses (`sky.lat/lng`). `geo.enabled` is **never persisted** (tiles bill per session, so loading must be an explicit click). Google tiles are decoded with a **`DRACOLoader` via `GLTFExtensionsPlugin`** (geometry is Draco; textures are JPEG — no KTX2). Key handling: an in-app field (persisted to localStorage) **or** `.env.local` `VITE_GOOGLE_MAPS_API_KEY`; never committed.

**Context:** Roadmap pillar #3 ([[research/web3d-geo-context]]). Two ways to fuse a local Rhino model (feet, near-origin) with Google's planet-wide ECEF tiles (metres, ~6.4e6 m coords). The model is the precious, precise thing; the existing app is entirely feet-based.

**Alternatives considered:** (1) **Model→globe** (place the model in ECEF via `EastNorthUpFrame`, use `GlobeControls`) — rejected: ~6.4e6 m float32 jitter on a small building, and it would force re-basing shadows/entourage/UVs/controls into metres. (2) **Scale the model down to metres** to match tiles — rejected: same invasive rewrite of every feet-based system. (3) **Cesium/threebox/three-geo** — rejected per [[research/web3d-geo-context]] (wrong architecture / abandoned). (4) Persist `enabled` for convenience — rejected: auto-loads (bills) on every reload.

**Reasoning:** Reorienting the *tileset* to a local Y-up origin keeps the building at small, precise coordinates and leaves the whole existing engine intact — the only new transform is one outer group (scale + offset + heading). Sharing one lat/lng for sun + context means "the site" is a single concept. Decoders had to be wired by hand because `GoogleCloudAuthPlugin.useRecommendedSettings` only sets `errorTarget=20` (verified in the 0.4.28 source), not loaders.

**Revisit if:** terrain auto-snap (raycast the tiles to seat the building) replaces the manual Seat slider; Rhino true-north is exported so `heading` is automatic; the in-browser tile realism warrants `EnvironmentControls`/`GlobeControls` for a true globe mode; or Google changes the P3DT compression (KTX2) so a `KTX2Loader` is also needed.

---

## 2026-06-13 — Engine-first web 3D rendering tool; 2D diffusion becomes a future add-in {#web3d-pivot}
**Decision:** Build the product as a **web-native 3D configurator** — export real geometry + semantic IDs from Rhino to glTF, render live in three.js/R3F, configure materials / sun / entourage in 3D. Demote the 2D diffusion pipeline (FLUX.2 + semantic masking, `apps/canvas-prototype`) to a future "diffusion hero" **add-in** on a 3D viewport grab.
**Context:** Teardown of competitor [[research/arcway-teardown|arcway.ai]] showed photoreal web configurators run on a real renderer (Unreal, pixel-streamed) — multi-view consistency + instant swaps are *free* with real geometry, the exact thing the diffusion spike bled on (the multiview-lock saga, [[#multiview-honest-metric]]). We already extract clean geometry + semantic IDs from Rhino — which Arcway's "Bridge AI" exists only to reverse-engineer from flat PDFs.
**Alternatives considered:** (1) keep refining the 2D diffusion canvas — rejected: consistency/geometry fidelity is a permanent uphill fight there. (2) Unreal + pixel streaming like Arcway — rejected for now: heavy infra + per-viewer GPU cost (QOOP sunset theirs on cost); revisit if the web-PBR realism ceiling blocks sales. (3) Babylon/PlayCanvas — rejected per [[research/web3d-engine-choice]].
**Reasoning:** With Rhino geometry + semantics in hand, engine-first gives exact geometry, free multi-view consistency, instant swaps, $0/client-side, and a clean path to sun studies / entourage / geo-context. Diffusion becomes a last-10% hero/styling pass — its hardest problem (consistency) disappears.
**Revisit if:** the in-browser PBR realism ceiling ([[research/web3d-realism]]) proves unsellable (add pixel-streamed UE for hero scenes), or a diffusion model gains reliable multi-view + exact-geometry control (the 2D path could lead again).

---

## 2026-06-13 — Cross-view consistency is measured illuminant-invariantly; the textured lock (A2) already beats naive {#multiview-honest-metric}

**Decision:** The honest measure of "same material across views" is **illumination-invariant chroma**: de-light each view's wall by its own white-trim illuminant (a von-Kries divide — the trim is painted white, so its rendered colour *is* that view's sun), then compare `(a*, b*)`. This — not v2's lit-chroma `dE_ab` — is the bar for the multi-view lock. Under it the **A2 neutral-reference lock BEATS swatch-only naive for textured red_brick (honest dE_ab 1.59 vs 4.41, −64%)**, so no new technique is adopted (the candidate A4 was built and rejected). `spike/run_multiview_lock_v3.py:_delit_wall_lab/honest_de_ab` is the reference implementation.

**Context:** v2 ([[#multiview-material-class]]) concluded A2 "stops brick hurting but doesn't beat naive" (lit dE_ab 9.55 vs 8.09) and flagged the residual as "correct re-lighting." v3 confirmed that literally: v2's metric compares each view's *lit* wall to the golden-hour anchor's *lit* wall, so it penalises a view for being correctly cooler. De-lighting both views first shows A2's intrinsic brick chroma (12.4, 21.5) sits on the anchor's realised brick (13.9, 20.9), while naive drifts redder (a*=18.2) by re-interpreting the raw swatch per view. $0 — the win came from re-scoring cached composites, not new renders.

**Alternatives considered:** A4 (flatten the directional shadow + recolour the reference's mean to the swatch) — rejected on offline evidence: the A4 reference is redder (a*=23.2) than the anchor's realised brick, so it would pull view-2 toward naive's error. Per-view sun-direction prompt — unnecessary once the metric factors lighting out. Keep v2's lit metric — rejected; it rewards copying the anchor's light, the exact v1 failure mode.

**Reasoning:** The product claim is "change a material once, it stays consistent across views" — that is material *identity*, i.e. chroma after the per-view sun is removed, not lit appearance. The missing piece was the metric, not the technique; A2 was already correct.

**Revisit if:** a relight-aware material model makes lit-appearance matching safe; or the canvas needs to *display* a consistency number to users (then this metric is what it should report).

**Reopens [[#multiview-material-class]] for SMOOTH materials.** Under the honest metric, the raw-anchor (v1) lock that decision routes travertine/stucco through is the *lit* winner but the honest *worst* (travertine v1 honest dE_ab 12.86 — it injects the anchor's light), while naive ≈ A2 at honest parity. Smooth materials show no directional-shadow artifact, so this was invisible to the lit metric. **Open product call:** route smooth → A2 neutral too (one strategy, never injects light) vs keep raw-anchor for maximal perceptual lit-sameness in the demo. Recommend the former; not yet changed in code.

---

## 2026-06-13 — Multi-view material lock: branch the strategy by material class {#multiview-material-class}

**Decision:** "One swatch → all views" uses an anchor-reference lock (edit the anchor view, feed its edited result as a 3rd FLUX.2 Edit reference for the other views), but the reference differs by material class: **smooth/colour-dominated materials (e.g. travertine) → raw anchor edit** as reference; **textured/shadow-interacting materials (e.g. brick) → a lighting-neutralized anchor crop** ("A2": divide out the golden-hour illuminant estimated from white trim, then luminance-flatten the wall region). Cross-view consistency is measured by **chroma-only ΔE (dE_ab)**, not full-Lab ΔE.

**Context:** v1 anchor-reference won on travertine (ΔE 7.43→4.14) but **backfired on brick** (8.25→21.62, blotchy wash, texture-energy error 25.9). Root cause: the anchor render is golden-hour with strong directional shadows and the camera-relative sun direction differs between views, so "match this exact appearance" injects the anchor's baked lighting into a differently-lit view. L* legitimately differs across views (different sun), so full-Lab ΔE penalizes correct re-lighting — chroma is the honest identity measure.

**Alternatives considered:** prompt-softened lock ("same material type/tone, this view's lighting") — helped but weaker than A2 on brick; one global strategy for all materials — fails one class or the other.

**Reasoning:** A2 fixes the brick failure (texture-energy 25.9→9.5, chroma 20.7→9.6) so the lock at least stops hurting; smooth materials are lighting-insensitive so the raw anchor is the better, simpler reference for them. Engine: `spike/multiview_apply.py`. (A2 doesn't yet *beat* swatch-only naive on a hue the swatch already nails; residual is correct re-lighting.)

**Revisit if:** a lighting-aware material model (per-view sun direction, or a relight pass) lets one strategy serve all classes; or a future model transfers material identity without baked light.

---

## 2026-06-13 — Rhino capture is the (size, displayMode) overload — reverses an E1 note {#capture-overload}

**Decision:** The white/ID reference passes in `rhino_capture.py` MUST use `view.CaptureToBitmap(size, displayModeDescription)`. The bare `CaptureToBitmap(size)` is forbidden for these passes. A white-pass brightness health gate (`MIN_LIGHT_PASS_MEDIAN=180`) raises rather than returning silently-undecodable masks.

**Context:** Capture was reliable only on the *first* call per doc-open; the 2nd+ collapsed to ~0.3% decode. Root-caused (not guessed): the bare overload returns a **stale, default-lit frame** in a headless/MCP-driven viewport (proved: byte-identical output across Wireframe/Shaded/Rendered; foreground median 157 == background). The mode-arg overload forces a real render of E1_IDMask → median 191, ~97% decode. This **reverses** the E1-era note (now corrected in `host_probe_rhino.py` finding #5) that claimed the mode-arg overload "ignores attributes."

**Alternatives considered:** doc reopen between captures (works but heavy, breaks multi-view-from-one-session); forcing flat-unlit shading / deleting+recreating the display mode (no effect — not the cause).

**Reasoning:** `capture()` is now idempotent in-session — independently re-validated 90.5% & 92.9% on two captures, one session, no reopen — which unblocks reliable multi-view capture and the Grasshopper button.

**Revisit if:** a future Rhino/RhinoCommon version changes CaptureToBitmap semantics, or a true off-screen GL path becomes available.

---

## 2026-06-12 — Material application: hosted FLUX.2 Edit + mask composite; MatSwap deferred {#material-apply-hosted}

**Decision:** The production apply-material step is `composite.paste_tile(base, host_mask, FLUX.2-Edit(base, swatch))` — FLUX.2 [pro] Edit (fal `flux-2-pro/edit`) with the render + swatch as references, then composite ONLY masked pixels back over the base. ~$0.06/swap. The self-hosted MatSwap-on-Modal contingency from the master plan is **not built for v1**.

**Context:** E3 shootout: text-only FLUX Fill barely acts on the surface; XLabs IP-Adapter gives muddy style-mush; FLUX Kontext reframes the camera (breaks mask registration); FLUX.2 Edit produced travertine that reads as travertine and held the camera. The mask composite makes the whole-image editor's out-of-region drift irrelevant.

**Alternatives considered:** MatSwap / Refaçade self-hosted (best measured fidelity, takes true normals — but GPU setup + Modal spend, and FLUX.2 cleared the "reads as the material" gate); IP-Adapter; Kontext.

**Reasoning:** Hosted single-call path clears the v1 quality bar at trivial cost and no GPU ops; reserve MatSwap for if/when swatch-exact fidelity (tile scale, veining) becomes the bottleneck.

**Revisit if:** users need exact-swatch tile scale/pattern fidelity that FLUX.2's cross-attention can't deliver; or a FLUX-backbone material-transfer model (HiFi-Inpaint-class) ships hosted.

---

## 2026-06-12 — Render = depth+canny multi-ControlNet; "geometry preservation = mask registration" {#render-mask-registration}

**Decision:** The production renderer is fal `flux-general` with a **ControlNetUnion of canny + depth** (FLUX.1-dev-ControlNet-Union-Pro-2.0), rendered at the capture's native pixel size. The canny control is a **ground-truth line drawing** = `Canny(beauty) ∪ instance-boundaries`. The success criterion for "geometry preservation" is reframed as **mask registration**: the host's ground-truth masks must land on the rendered pixels.

**Context:** E2 picked depth-only as the best of the bake-off, but the canvas masking was visibly wrong (brick over windows, smudged pillars). Diagnosed: depth ControlNet pins massing but **cannot pin coplanar features** (a window flush in a wall ≈ same depth), so FLUX re-placed openings 5–25px off the ground-truth masks. Edge alignment: depth-only 51.7% of GT edges within 2px → depth+canny **98.5%**. Also: BFL deprecated its standalone Canny/Depth Pro endpoints (Oct 2025) and fal's `flux-pro/v1/canny` queue is dead, so the union lives on `flux-general` (the FLUX-dev model). Warmth is a prompt matter, not a model limit (recovered with no re-drift).

**Alternatives considered:** depth-only (drifts coplanar features); screenshot i2i / Nano Banana / FLUX.2 Edit i2i (reframe 20–40px+, break mask registration); FLUX-pro depth (no multi-control on fal).

**Reasoning:** Only the plugin tier can supply a true z-buffer AND exact GT edges; the union locks both massing and openings so masks register — the third stage where host data beats inference.

**Revisit if:** a hosted seg-map→photoreal model (e.g. Seg2Any) or a FLUX.2-grade multi-ControlNet appears that registers as tightly with better photorealism.

---

## 2026-06-12 — Plugin-first pivot: extract ground truth from the host, delete the tag+segment AI stages {#plugin-first-pivot}

**Decision:** The primary input path is a host plugin (Rhino → Revit → SketchUp) exporting `{beauty.png, id_mask.png (per-object flat color), depth.png (true z-buffer where available), objects.json (id → category/layer/material)}`. On this tier the VLM-tagging and SAM2-segmentation stages are **deleted** — host data is ground truth. The screenshot pipeline is retained as a fallback tier (web demo, Forma, no-plugin users) with its tagging stack upgraded (Florence-2 → SAM 3). AI is reserved for the two things only it can do: photoreal synthesis and material application.

**Context:** User-requested foundational pressure test (2026-06-11/12). Measured evidence: Gemini tagging ≈0.4 mAP, 0 mullions on a mullion-grid facade (T21), 0 windows on raw screenshots; SAM 2 documented to lose thin structures. Four Sonnet research agents confirmed: Rhino exposes a true z-buffer + per-object draw control; Revit has native categories including `OST_CurtainWallMullions` — the exact label the VLM kept missing; G-buffer-conditioned diffusion is research-validated and unshipped from any BIM host; Veras (closest competitor) is screenshot-level only.

**Alternatives considered:**
- Stay screenshot-first and upgrade models (better VLM, SAM 3) — keeps paying an accuracy tax on data the host has for free; mullion-level precision likely never reaches ground truth.
- Hybrid with screenshot primary, plugin "premium" — splits engineering effort while leaving the flagship experience on the weaker data.
- Wait for Vision Banana public API — timeline unknown; Veras has partner access we don't.

**Reasoning:** Cheapest-information-first still holds: the keystone experiment (E1, Rhino MCP extraction probe) costs $0 and a few hours. The pivot deletes the two weakest stages instead of improving them, upgrades render conditioning from screenshot-i2i to true depth+edges, and gives MatSwap true normal maps if material fidelity needs it. Competitive window: nobody ships host-extracted G-buffer conditioning; Veras est. 6–12 months from closing the swatch+layers gap. User confirmed full pivot appetite, all three hosts relevant, $50 experiment budget.

**Revisit if:** E1 fails (ID masks not pixel-accurate on thin members, depth unusable); or plugin install friction kills adoption in beta; or a public Vision-Banana-class API makes screenshot-tier tagging good enough that plugin extraction stops being a differentiator.

---

## 2026-05-20 — Defend against Gemini malformed bbox JSON; never lose paid data to schema validation {#gemini-bbox-malformed-json}

**Decision:** Wherever we call `tag_regions` (or any Gemini structured-output call), the caller must persist the raw response *before* attempting pydantic validation, and must use a tolerant JSON parser that handles known model output bugs (currently: duplicate `y` keys in bboxes). Schema validation is best-effort; data loss on schema failure is not acceptable.

**Context:** T22 ran `tag_regions` on 4 new (screenshot, photoreal_render) pairs. 3 of 4 returned clean schema. On urban_exterior, every bbox came back as `{"x": 499, "y": 361, "w": 25, "y": 425}` — duplicate `y` key, no `h`. JSON parsers silently drop the first key on duplicates, so pydantic saw `{x, y, w}` and threw 37 validation errors. Reproducible on a $0.01 retry (same screenshot, same render, same prompt → same malformation). 47 regions worth of paid data would have been lost if the raw response hadn't been saved. The `spike/salvage_urban_tags.py` script recovered 44 of 47 via `json.loads(..., object_pairs_hook=...)` that promotes the second `y` to `h`.

**Alternatives considered:**
- Trust schema validation and re-call on failure — rejected; the malformation is reproducible, so retries waste money without recovering data.
- Rewrite the `tag_regions` prompt to avoid the bug — uncertain whether it would help (we don't know what's triggering it on this specific image), and risks regressing the cases that already work.
- Accept the loss as a one-off — rejected; with $0.01 per Gemini call, every paid response is data that future eval and prompt iteration depends on. Schema failures will recur as the model evolves.

**Reasoning:** Save raw, then attempt validation, then attempt tolerant repair, then surface. Cost: a few lines of code and a small disk overhead per call. Benefit: never throw away paid data because of a schema mismatch.

**Revisit if:** Gemini stops producing the duplicate-key malformation entirely (in which case we still want the safety net); or we discover the malformation has a meaning other than "duplicate key" (e.g., maybe the second `y` is actually `y2` not `h`, in which case the salvage hook's interpretation needs revision).

---

## 2026-05-20 — tag_regions requires the photoreal render, not a raw screenshot {#tag-regions-needs-photoreal}

**Decision:** `tag_regions` is only invoked on `(screenshot, photoreal_render)` pairs in production. Calling it on a raw 3D-model screenshot alone (e.g., for a pre-render preview) is not supported by Gemini 3 Pro at the quality level the Spike 4 pipeline needs.

**Context:** T21 ran the revised `tag_regions` prompt on 5 images: pair 1 was the existing T17 (screenshot, render) pair; pairs 2–5 were 4 new screenshots passed as both screenshot and render (budget would not stretch to ~$0.20 of Nano Banana renders for the 4 new shots). Pair 1 cleanly cleared the Spike 3 gate with 94 tight regions including 77 per-window bboxes. Pair 4 (urban exterior screenshot) returned 25 regions and **zero windows** despite the screenshot showing many visible bright-blue window blocks. Pair 5 (complex-windows screenshot) returned 97 regions but zero mullions despite the entire facade being a mullion grid.

**Alternatives considered:**
- Make `tag_regions` accept a single-image mode (cheaper for previews) — rejected because it underperforms badly on raw screenshots; supporting a degraded mode invites users into a UX they will then judge the product on.
- Accept the screenshot-only quality and design the UI to mask it — rejected; the whole point of the Photoshop-for-Architects UX is clean per-element masks for material swap, and "missed every window" is a categorical failure for that UX.

**Reasoning:** The photoreal render gives Gemini the visual context it needs to distinguish glazing (translucent, reflective) from solid wall, mullion (thin frame) from wall strip, and door (passage) from balcony glazing. Without that context the model treats the screenshot's color blocks too literally and produces categorical misses. Spike 4's pipeline already runs render before tagging, so this decision matches what the production flow does anyway — it makes the constraint explicit.

**Revisit if:** Gemini 4 / next-gen VLM lifts performance on raw screenshots; or we add a single-image preview mode and find a prompt variant that doesn't degrade. T22 will provide a real production-shape benchmark on the 4 new screenshots.

---

## 2026-05-19 — Knowledge wiki as single source of truth {#wiki-ssot}

**Decision:** Stand up `wiki/` at repo root as the project's SSOT. Plain markdown, Obsidian-friendly. Existing docs (`docs/plans/`, `spike/TASKS.md`, `spike/REPORTS/`, `spike/PROVIDERS.md`) stay where they are and the wiki links to them. Every chat appends to [[SESSIONS]] at session end; non-obvious choices also append here.

**Context:** Project knowledge was scattered. New agents re-derived "what is B1?", "Photoshop or VLM?", "what's blocked?" every session. No decision log existed.

**Alternatives considered:**
- Consolidate everything under `docs/wiki/` — breaks existing links and rewrites history references.
- Full Obsidian vault with `.obsidian/` committed — clutters git, only helps Obsidian users.
- Skip wiki, just improve `CLAUDE.md` — doesn't solve the "where do decisions live" gap.

**Reasoning:** Lowest churn (nothing existing breaks) + Obsidian-friendly without forcing Obsidian on anyone + cross-linking avoids duplication that would go stale.

**Revisit if:** wiki turns into another stale corner. The session-log protocol in `CLAUDE.md` is what keeps it alive — if it stops being followed, the wiki will rot.

---

## 2026-05-19 — Coordinate-space rescaling is owned by the *consumer*, not the model {#coord-space-consumer}

**Decision:** Treat Gemini 3 Pro's normalized 0–1000 bbox output as the source of truth. Local code (`test_vlm_tagging.py:_draw_regions`, `end_to_end_edit.py` before SAM2) rescales to pixel space.

**Context:** T17 smoke test revealed Gemini returns bboxes in 0–1000 normalized space regardless of input image dimensions. Drawing code was treating them as pixel coords; every bbox was drawn at ~79% width / ~118% height.

**Alternatives considered:**
- Instruct Gemini to return pixel coords directly. VLMs often ignore this instruction.
- Override the schema to enforce pixel ranges. Same problem — the model normalizes anyway.

**Reasoning:** Trust the model's documented behavior (0–1000 is the standard VLM spatial output). Rescaling on the client side is deterministic and testable; relying on prompt compliance is not.

**Revisit if:** Gemini changes its default spatial output convention, or we switch tagger to a model that emits pixel coords natively.

See [[references/coordinate-systems]] and the T17 report.

---

## 2026-05-17 — Overnight scaffolding via constrained subagent {#overnight-scaffolding}

**Decision:** Build Spike 2.5/3/4 scaffolding overnight via the `spike-builder` subagent. Agent allowed to edit only `spike/**`, allowed git status/diff/add/commit (no push/reset/rebase/merge), zero network calls except a single T17 Gemini smoke test (~$0.01). Hard $0.05 cap.

**Context:** 20 tasks of scaffolding (renderer clients, scoring, drivers, tests) would have taken multiple manual sessions. Subagent with tight boundaries can ship it in one night.

**Alternatives considered:**
- Manual session-by-session implementation. Slower, but more oversight per step.
- Less-constrained agent. Higher risk of unwanted edits outside `spike/` or premature live API calls.

**Reasoning:** Tight boundaries (edit scope, git ops, network) plus per-task report contract keeps blast radius small. Bills only $0.01 for the entire run.

**Revisit if:** subagent produces poor-quality scaffolding (it didn't — T01–T20 all passed), or if we ever need to repeat this for another spike phase.

See `docs/plans/overnight-spike-builder.md`.

---

## 2026-05-15 — Branch model: overnight → renderer-bakeoff → main {#branch-model}

**Decision:** Overnight work goes on `overnight/spike-builder-2026-05-17`. Merges into `renderer-bakeoff` only after user review. `main` is sacred — never direct-commit, never force-push, never `--no-verify`, never `--amend` on shared history.

**Context:** Multi-day scaffolding work with an autonomous agent. Need a quarantine branch.

**Alternatives considered:**
- Direct to `renderer-bakeoff`. Less isolation if the agent makes a mistake.
- PR-based workflow. Adds friction for a solo developer.

**Reasoning:** Branch-of-a-branch gives a review checkpoint without the GitHub PR overhead.

**Revisit if:** team grows beyond solo dev (need real PR workflow), or scaffolding phase ends.

---

## 2026-05-10 — B1 → B2 → B3 cascade before any GPU spend {#b-cascade}

**Decision:** Order Spike 2.5 work by cost. B1 (characterize Nano Banana failures, ~$0.12) → B2 (try cheap prompt fixes, ~$0.50) → B3 (multi-renderer bake-off, ~$3–5). Each phase has a clear gate; only escalate if the prior phase doesn't resolve the issue.

**Context:** Spike 2 showed Nano Banana has critical failures. We could (a) jump straight to a multi-renderer bake-off and burn $3–5 on the first try, or (b) characterize the failure mode and try cheap fixes first.

**Alternatives considered:**
- Jump to B3 immediately. Faster but expensive if a B2-style fix would have sufficed.
- Skip B1, go to B2. Lose the deterministic-vs-stochastic question.

**Reasoning:** Cheapest information first. B1 tells us if the failure is even fixable in-renderer; B2 tries the cheapest fix; B3 is the expensive escape hatch.

**Revisit if:** B1/B2 are taking longer than expected (sunk-cost trap — be willing to skip ahead).

---

## 2026-04 — Empirical multi-renderer bake-off, not a single renderer bet {#empirical-bake-off}

**Decision:** Spike 2.5 B3 evaluates 8 renderer candidates (Nano Banana Pro, FLUX Canny Pro, FLUX Kontext Pro, Magnific Mystic, Qwen-Image-Edit, HiDream-E1, Recraft V3 native, Recraft V3 via Replicate) on the same input and picks by score, rather than committing to one based on first impressions.

**Context:** Spike 2 showed Nano Banana Pro at ~90% macro alignment but with critical-severity failures (invented windows, corner wraparounds altering building mass). Picking the next renderer without comparison would just repeat the gamble.

**Alternatives considered:**
- Bet on FLUX Canny Pro because of its explicit edge-conditioning. Single point of failure if it doesn't generalize.
- Bet on Magnific because of its arch-viz reputation. Highest per-call cost, hard to justify without comparison.
- Bet on whichever model "looked best" on a casual test. Confirmation bias.

**Reasoning:** Empirical comparison on the same input with the same rubric is the only honest way to choose. The cost ($3–5 for one round) is much smaller than committing to the wrong renderer for months.

**Revisit if:** B3 finishes and one renderer is a clear winner (then this decision retires). Or if a new renderer arrives that we'd want to add to the field.

---

## 2026-04 — VLM (Gemini 3 Pro) for region tagging, not color-coded mask passes {#vlm-tagging}

**Decision:** Use a Vision-Language Model on the *render* to identify regions (wall / window / mullion / door / floor / ceiling / etc.). Do not bake material IDs or color codes into the 3D model.

**Context:** Need to know which region the user clicked. Two options: (a) tag the render with a VLM, (b) ask the host application (Rhino / SketchUp / Revit) to render a per-material-ID color pass alongside the shaded screenshot.

**Alternatives considered:**
- **Color-coded mask passes.** Requires plugin work per host, and the encoding (one color per region) bakes geometry assumptions into the input. Doesn't generalize across renderers either — different renderers can blur or fail to preserve color discontinuities.
- **Manual mask drawing.** Defeats the "click a wall" UX hypothesis.

**Reasoning:** VLM reads pixels, so it generalizes across hosts and renderers. The architect already gives us a screenshot — no extra rendering step required from their tool. Cost is ~$0.01/tag, acceptable.

**Revisit if:** VLM tagging quality remains poor after T21 prompt revision + 5-screenshot eval. See [[STRATEGY#Q2]] for fallback options.

---

## 2026-03 — Shaded model viewport screenshot as primary input (not line drawings) {#shaded-screenshot-input}

**Decision:** Input to the pipeline is a *shaded* viewport screenshot from the architect's 3D modeling tool — not a line drawing, axonometric, or pure wireframe.

**Context:** Multiple input formats are possible from 3D modelers. Need to pick one.

**Alternatives considered:**
- **Pure line drawings (axon / hidden-line).** Gives geometry but no surface or material cues.
- **Materials-only render (matte shaded).** Loses lighting cues.
- **Photorealistic render from the host.** Defeats the purpose — we're trying to *produce* photorealism downstream.

**Reasoning:** Shaded screenshots carry both geometry edges *and* color discontinuities. The renderer gets geometry to preserve; the VLM gets region boundary hints. One input, two downstream uses.

**Revisit if:** real-world architect workflows produce a different default input that we want to support natively.

---

## 2026-02 — Dropped text-to-image + click-segmentation (Spike 1 pivot) {#dropped-text-to-image}

**Decision:** Killed the original architecture: user prompts a text-to-image model to generate a building, then clicks elements in the resulting image to identify them. Replaced with: user provides a 3D-model viewport screenshot, we re-render it preserving geometry, then a VLM tags regions.

**Context:** Spike 1 tried the text-to-image + click-segmentation flow. Two compounding generative steps kept failing — the model invented geometry that was then hard for downstream segmentation to identify.

**Alternatives considered:**
- Keep text-to-image but with better prompts. The compounding-error problem is structural; prompt tuning doesn't fix it.
- Text-to-image with a separate "redraw to fix" pass. More compounding.

**Reasoning:** Architects don't think in prompts — they already have geometry from their 3D model. Anchoring the input to that geometry eliminates one whole class of compounding failures. The renderer's job becomes "preserve this geometry, just change the surface treatment" — a much more constrained problem.

**Revisit if:** text-to-image models reach a quality where they preserve a sketched layout precisely (we'd still probably prefer the model-anchored flow, but it stops being categorically required).

---
