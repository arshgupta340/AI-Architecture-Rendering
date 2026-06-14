---
type: state
updated: 2026-06-14
---

# Current State

> Snapshot, not a log. Overwrite at session end. Log is [[SESSIONS]]; rationale is [[DECISIONS]].

## Direction

**Web-native 3D-consistent rendering tool** (engine-first). Export real geometry + semantic element IDs from Rhino → glTF, render live in **three.js / React-Three-Fiber**, configure materials / sun / entourage / render-quality / atmosphere directly in 3D, then **export a client-ready still**. Geometry fidelity + multi-view consistency are *exact and free* (it's real 3D) — exactly what the old 2D diffusion path bled on. Spark: [[research/arcway-teardown]]; rationale: [[DECISIONS#web3d-pivot]]. The 2D FLUX.2 + semantic-masking pipeline (`apps/canvas-prototype/`) is the future **"diffusion hero"** add-in (scaffold-only — [[DECISIONS#web3d-clientready-composition]]).

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

## NEXT — remaining client-ready polish (follow-ups)

The $0 realtime client-ready path is **built + verified**. Remaining (lower priority):
1. **KTX2 encode** — run `scripts/encode_ktx2.mjs` on a machine with the KhronosGroup `ktx` CLI (+ `npm i -D sharp`), then enable the KTX2 load path behind `setKTX2Renderer` + call it from each stage.
2. **Real cutout people** — source genuinely-CC0 PNGs (OpenGameArt CC0 / tonytextures), commit to `public/entourage/people/`, extend `entourageAssets.ts` (a license call).
3. **Entourage scale check** — trees read slightly small; verify the `baseHeightFt`/`glbHeightUnits` normalization.
4. **T4 diffusion hero** — build the $0 depth+canny+id-edge capture (`lib/captureHero.ts`), gate the paid FLUX call behind auth + a backend shim (reuse `apps/canvas-prototype` + `spike/run_e2b_registration.py`).
5. **T3 splat context** — `SplatContext.tsx` via Spark in the webgl2gi stage (needs a generated/captured splat).
6. **Atmosphere ceiling** — optional takram physically-based sky/clouds (ECEF rebasing into feet); WebGPU clouds.

## Pipeline (Rhino → web), all `$0`
```
Rhino 8 (live MCP) → spike/rhino_export_gltf.py → spike/gltf_postprocess.py (node.extras semantics) → gltf-transform meshopt → public/model/house.glb
PBR swatches: apps/web3d-prototype/scripts/fetch_materials.py (ambientCG CC0 ×29) ;  HDRI: spike/ingest_hdri.py + 4 golden-hour presets (Poly Haven → public/hdri/*.hdr) ;  Entourage: scripts/fetch_entourage.py (Quaternius CC0 via poly.pizza → public/entourage/)
```

## Research (this arc)
[[research/arcway-teardown]] · [[research/web3d-engine-choice]] · [[research/web3d-rhino-gltf]] · [[research/web3d-realism]] · [[research/web3d-clientready]] · [[research/web3d-entourage]] · [[research/web3d-sky-sun]] · [[research/web3d-geo-context]] · [[research/web3d-ue-browser]] · [[research/web3d-webgpu]]

## Cost ledger
web3d arc = **$0 API** (local geometry + client render; CC0 assets from ambientCG / Poly Haven / Quaternius). Geo-context bills the user's own Google PAYG once keyed. Prior diffusion spend ≈ $2.22 / $50 (unchanged). This session: **$0** (research via EXA on the user's quota; all build assets CC0).

## Handoff
Fresh-chat continuation prompt + the next-step plan: [[../docs/HANDOFF-web3d.md]]. Build bible: [[research/web3d-clientready]].
