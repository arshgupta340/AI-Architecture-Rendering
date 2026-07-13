---
type: state
updated: 2026-07-03
---

# Current State

> Snapshot, not a log. Overwrite at session end. Log is [[SESSIONS]]; rationale is [[DECISIONS]].

## Direction

**Web-native 3D-consistent rendering tool** (engine-first). Export real geometry + semantic element IDs from Rhino → glTF, render live in **three.js / React-Three-Fiber**, configure materials / sun / entourage / render-quality / atmosphere directly in 3D, then **export a client-ready still**. Geometry fidelity + multi-view consistency are *exact and free* (it's real 3D) — exactly what the old 2D diffusion path bled on. Spark: [[research/arcway-teardown]]; rationale: [[DECISIONS#web3d-pivot]]. The **diffusion "hero render"** (depth+canny-locked FLUX, self-hosted on Modal) + a **Gaussian-splat environment** are now BUILT in-app ([[DECISIONS#web3d-hero-splat]]) — the geometry-truthful last-10% photoreal layer on top of the real-time engine.

## The web3d app — `apps/web3d-prototype/`  (Vite + React + R3F + three **r0.184**, $0 / client-side)

Run: `npm install --prefix apps/web3d-prototype` then `npm --prefix apps/web3d-prototype run dev` → http://localhost:5181 (launch.json `web3d`, port 5181). App README: `apps/web3d-prototype/README.md`.

### Working & verified
- **Model:** meshopt-compressed semantic `house.glb` (6.5 MB), 12 element classes, auto-framed.
- **Material library at scale (NEW):** **29 CC0 ambientCG PBR materials** (`lib/swatches.ts`, fetched by `scripts/fetch_materials.py`) across brick/stone/concrete/plaster/wood/travertine·marble/paving/metal/roofing/ground, each with `category` + `tags` + correct real-world metric `tileFeet`. **Searchable swatch grid** UI (search box + category pills + albedo thumbnails) in `ui/Sidebar.tsx`. Box-projected world-feet UVs → metric texture scale + live per-material scale slider; non-destructive layer stack; localStorage-persisted. (KTX2: `scripts/encode_ktx2.mjs` + `public/basis/` transcoder ready; jpg ships until a `ktx` binary is available.)
- **Real entourage (NEW):** **12 CC0 Quaternius GLBs** (8 trees, 4 bushes) in `public/entourage/`, instanced per-species (one InstancedMesh per sub-mesh, hash-distributed across species) behind the **unchanged** click-to-place / scatter-paint UX (`Entourage.tsx` + `lib/entourageAssets.ts`). People = improved procedural (licensing-safe; real CC0 PNGs a follow-up). Real-ft height sliders.
- **Real glass:** windows use ONE shared `MeshPhysicalMaterial` (transmission/ior 1.5).
- **Sky & Sun + Atmosphere:** real `suncalc` solar position + mood/time/date/intensity/cloud presets; **4 golden-hour CC0 HDRI presets** (`SolarSky` `HDRI_PRESETS`, drives WebGPU IBL + WebGL2 reflections + the PT hero); **sun-path arc** overlay (day arc + analemma, node-safe `<line>`/`<points>`); **drei clouds** plate (WebGL2 modes).
- **Output / client-ready (NEW):** **high-res Export still** (`lib/exportImage.ts` — 2× supersample via dpr + aspect crop 16:9/3:2/4:3/1:1/free + JPG/PNG; `preserveDrawingBuffer` on WebGL2; verified 2620×1474 non-black); **Presentation mode** (hides all panels for a clean client frame); **Cinematic grade** (WebGL2 contrast/sat/vignette/film-grain in `Effects`/`EffectsGI`; WebGPU vignette in `WebGPUPost`); **ContactShadows** grounding (`stages/ContactGround.tsx`, WebGL2 stages only). Export/grade/presentation controls live in `ui/NavBar.tsx` (moved off the Sky panel).
- **Geo-context:** Google Photorealistic 3D Tiles via `3d-tiles-renderer` (`GeoTiles.tsx`), georeferenced. Needs the user's Google Maps key to validate live.
- **Nav:** Orbit + Walk; saved views.
- **THREE RENDER MODES** behind a `renderMode` toggle (NavBar) — each a self-contained Stage owning its own `<Canvas>` + renderer + post, all rendering the shared `<Scene>`:
  - **WebGL2** (`stages/StageWebGL2`): N8AO + tamed Bloom + AgX + SMAA + grade (`Effects.tsx`), VSM soft shadows, 256px sky-baked IBL, ContactShadows.
  - **WebGL2 + GI** (`stages/StageWebGL2GI`): RectAreaLight (LTC) + `MeshReflectorMaterial` reflective plaza + stronger N8AO + grade (`EffectsGI`), ContactShadows.
  - **WebGPU** (`stages/StageWebGPU` + `WebGPUPost` + `WebGPUAreaLights`): `WebGPURenderer` + TSL **SSGI**/GTAO/TRAA/Bloom + **vignette grade** + LTC area lights + **node-safe HDRI IBL** + **real VSM cast shadows**. The realism ceiling.
- **Path tracer — FIXED (NEW):** `PathTracer.tsx` now traces an **isolated `ptScene`** (dequantized `house_pt.glb` + mirrored live-swatch materials + physical glass + HDRI `scene.environment` + a `.color` guard) instead of the live scene — kills the old `MaterialsTexture.updateFrom` `.color.r` crash. Verified rendering the building with the architect's chosen materials + HDRI GI at 46 spp (WebGL2 / + GI modes).
- **Cinematic (UE5) toggle** (`Cinematic.tsx`): embeds a SimplyStream UE5 WebGPU build (user supplies the build). **Lumen reference:** Twinmotion 2025.1 (RTX 4070) — `UE_LUMEN_RUNBOOK.md`.
- **Hero render — diffusion, geometry-locked (NEW, built + QA'd + LIVE):** NavBar **✦ Hero render** (WebGL2/+GI) captures the viewport's beauty + a LINEAR near=white depth + a per-semantic byte-exact id buffer (`lib/heroCapture.ts`) and opens a full Photoshop modal (`HeroRender.tsx`) — base geometry-locked layer + independent re-rollable region layers (masked, byte-stable elsewhere), prompt/seed/scale controls. Backend = **self-hosted FLUX.1-dev + ControlNet-Union (canny∪id-edges + depth) on Modal A100-80GB** (`spike/modal_flux.py`, one `@modal.asgi_app()` FastAPI app, `/hero_render` + `/region_edit` routes). **DEPLOYED + LIVE-VERIFIED through the real app UI** (`…--arch-rendering-flux-heroflux-web.modal.run`): base render 14.9 s warm → photoreal house with every window/porch/stair/roof-gable/trim geometry-locked; `/region_edit` 21 s warm → masked roof layer composited byte-stable over the base; both returned 200. Idle = $0 (scale-to-zero). Also verified vs a GPU-free mock (`spike/mock_hero_server.py`). **UX polish (NEW, live-verified):** a cheap `/warm` route + a header **🔥 Keep warm** toggle (pings every 240 s → no cold start mid-session; settled to "Warm" in ~18 s live), a **⚡ last-render timing badge**, a warm/cold-aware busy overlay, a **backend-model badge** (from `/warm`), and a **FLUX.1↔FLUX.2 preset switch** in the Backend card. Runbook + the 7 live-debug gotchas: `spike/REPORTS/modal_flux.md`. [[DECISIONS#web3d-hero-splat]]
- **Hero render — FLUX.2 experimental backend (NEW, built + deploy-gated):** `spike/modal_flux2.py` — **FLUX.2-dev + alibaba-pai Fun-Controlnet-Union on H200 via VideoX-Fun**, same CORS `/hero_render`+`/region_edit`+`/warm` contract as FLUX.1, canny∪id-edge lock, **native inpaint** region edits. FLUX.1 stays the live default (FLUX.2 = 32B + Mistral-24B → BF16 needs H200, and its ControlNet is VideoX-Fun-only). Switchable by URL preset in the app. Feasibility + deploy gate: `spike/REPORTS/flux2_feasibility.md`. [[DECISIONS#web3d-flux2-experimental]]
- **Gaussian-splat environment (NEW, built):** `SplatContext.tsx` (`@sparkjsdev/spark`, lazy/code-split, WebGL2-only) composites a splat backdrop around the building + a shadow-catcher; `SplatPanel.tsx` (source toggle + alignment sliders). Fed by a drop-in Marble/CC0 `.spz`/`.ply` (verified rendering a real `.spz` with the building) OR a **Modal scene-bake** (`lib/splatBake.ts` + `spike/modal_splat.py` — render-to-3DGS via splatfacto, deploy-gated).

### Known-broken / deferred
- **WebGPU console noise:** 6 benign `THREE.NodeBuilder: ShaderMaterial not compatible` warnings = the 6-face equirect→cube **PMREM of the HDRI `scene.environment`** (three internals). Render is correct; pre-existing, not a regression.
- **drei `<SoftShadows>` (PCSS) broke on three r184** → use VSM (`shadows="variance"`). ContactShadows/AccumulativeShadows ARE safe on WebGL2 (used), but break on WebGPU (MeshDepthMaterial node-incompat) → WebGL2-only.
- **Diffusion hero (T4) + Splat env (T3) = scaffold/deferred** ([[DECISIONS#web3d-clientready-composition]]). Recipes in [[research/web3d-clientready]]: T4 = depth+canny-locked FLUX.1-dev Union (paid, backend shim); T3 = Spark `@sparkjsdev/spark` splat-context (WebGL2-only, ~$20/mo Marble to generate).

### The three realism tiers (all verified rendering)
| Mode | Tech | Look |
|---|---|---|
| **WebGL2** | N8AO + AgX + glass + VSM + grade + contact | the baseline |
| **WebGL2 + GI** | + area lights + reflective ground + contact | richer; payoff strongest at ground level |
| **WebGPU** | SSGI + GTAO + TRAA + HDRI IBL + VSM + vignette | softest/warmest GI — the in-browser ceiling |
Lumen reference = **Twinmotion** (runbook). Ceiling analysis: [[research/web3d-realism]] · [[research/web3d-ue-browser]] · [[research/web3d-clientready]].

## PRD (NEW, 2026-07-03) — the productization plan

**[PRD v1 "mesh-first"](../docs/plans/PRD-v1-mesh-first.md)** — written from a 17-agent research fleet (7 research dimensions, each adversarially stress-tested, + 2 red teams + synthesis; evidence in `docs/plans/research/grand-idea-2026-07/`). Verdict: **the mesh is the product** — V1 = model-locked non-destructive re-rendering as a Food4Rhino plugin ($29–39/mo). Phase 0 = global **command/undo bus** (the load-bearing unbuilt piece) + Rhino capture plugin + auth/cost-gated hero. Phase 1 = still turntable + labeled static splat backdrop + light-coherent entourage + read-only copilot. Video fly-through, editable-splat authoring, mutating copilot, generative entourage = deferred behind evidence gates (PRD §6). Rationale: [[DECISIONS#mesh-first-prd]]. Key external facts: Veras is free-bundled in every Chaos tier; AI video warps building geometry (all hosted models); Chaos shipped splat relighting Jun 2026; Nuit = nearest thesis rival (watch: model binding).

## NEXT — remaining client-ready polish (follow-ups)

The $0 realtime path + the **hero render** are **built + QA'd + LIVE** (the hero backend is deployed and verified through the UI). Remaining (mostly deploy-gated / polish):
1. ~~**DEPLOY the hero backend**~~ — **DONE + live-verified** (2026-06-15). Live on `arch-flux` secret (HF_TOKEN + HERO_SHARED_SECRET); both `/hero_render` + `/region_edit` return 200 through the app. ⚠️ **Rotate the HF token** (pasted in plaintext during setup). FLUX.2-dev-Fun ControlNet as a switchable "experimental" model is an open follow-up.
2. **DEPLOY the splat-bake** — `modal deploy spike/modal_splat.py` (verify the gsplat CUDA build on first deploy) → paste the URL into the Splat panel. Generate a real Marble env `.spz` to replace the butterfly test asset (the live hero invents its own context; the splat env is what seats the building on a chosen site).
2b. **(optional) DEPLOY FLUX.2** — `modal run spike/modal_flux2.py::warm_weights` (~70 GB) + `modal deploy spike/modal_flux2.py` (H200; validate the VideoX-Fun loader block on first deploy) → select the FLUX.2 preset in the Backend card. Opt-in, ~2–4× FLUX.1 cost. `spike/REPORTS/flux2_feasibility.md`.
2c. **Multi-view hero** (NEW): the **per-view turntable is BUILT + live-verified** (`heroCaptureViewsFn` → N same-seed base renders → gallery + Export all + `bakeFromHeroViews` bridge), but per-view FLUX is NOT 3D-consistent (geometry/lighting/material drift). True consistency = **reproject-from-3D** ([[DECISIONS#web3d-reproject-consistency]], `lib/reproject.ts`): hero pixels → real mesh → other angles, gaps inpainted. **Reproject CORE verified** (perfect consistency for nearby angles); A/B/C findings: tighten-lock fixes geometry only (74.5→93.1% edge-align), IP-Adapter blocked on diffusers 0.32.2. **OPEN follow-up:** the full-360 CHAINED turntable loses the building in back views (chained gap-fill doesn't reconstruct unseen sides) — needs multi-hero anchors + loop closure + UI. Evidence + run scripts logged in [[SESSIONS]]. **region_edit v2 true inpaint** still scoped/deferred.
3. **Hero v2** — true `FluxControlNetInpaintPipeline` for `region_edit` (vs the full-pass+composite); WebGPU hero capture (async readback); multi-view-consistent hero → feed the scene-bake for a photoreal walkthrough.
4. **KTX2 encode** — run `scripts/encode_ktx2.mjs` on a machine with the KhronosGroup `ktx` CLI (+ `npm i -D sharp`), then enable the KTX2 load path behind `setKTX2Renderer`.
5. **Real cutout people** — source genuinely-CC0 PNGs; **entourage scale check** (trees read slightly small).
6. **Atmosphere ceiling** — optional takram physically-based sky/clouds; WebGPU clouds.

## Pipeline (Rhino → web), all `$0`
```
Rhino 8 (live MCP) → spike/rhino_export_gltf.py → spike/gltf_postprocess.py (node.extras semantics) → gltf-transform meshopt → public/model/house.glb
PBR swatches: apps/web3d-prototype/scripts/fetch_materials.py (ambientCG CC0 ×29) ;  HDRI: spike/ingest_hdri.py + 4 golden-hour presets (Poly Haven → public/hdri/*.hdr) ;  Entourage: scripts/fetch_entourage.py (Quaternius CC0 via poly.pizza → public/entourage/)
```

## Research (this arc)
[[research/arcway-teardown]] · [[research/web3d-engine-choice]] · [[research/web3d-rhino-gltf]] · [[research/web3d-realism]] · [[research/web3d-clientready]] · [[research/web3d-entourage]] · [[research/web3d-sky-sun]] · [[research/web3d-geo-context]] · [[research/web3d-ue-browser]] · [[research/web3d-webgpu]]

## Cost ledger
The **real-time engine stays $0** (local geometry + client render; CC0 assets). The **hero render + splat bake are opt-in paid** (user-authorized; user raised the Modal limit): self-hosted Modal FLUX ≈ **$0.01–0.02/render active** on A100-80GB (idle = $0, scale-to-zero; a cold start adds ~40–60 s of boot, and the 300 s scaledown window is billed after the last call). **This session: live deploy + verification + UX-polish redeploy** — 2 base renders (14.9 s warm + 58.3 s cold) + 1 region edit (21 s warm) + a `/warm` cold-boot verify (~18 s) + container boot/idle ≈ **~$0.35–0.55** of Modal GPU time (user-authorized; redeploys/builds are free). FLUX.2 not deployed ($0). Splat bake (untested) ≈ **$0.30–0.50/scene**; optional World Labs Marble **$20/mo**. Geo-context bills the user's own Google PAYG. Prior diffusion spend ≈ $2.22.

## Handoff
Fresh-chat continuation prompt + the next-step plan: [[../docs/HANDOFF-web3d.md]]. Build bible: [[research/web3d-clientready]].
