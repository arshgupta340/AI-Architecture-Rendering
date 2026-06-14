# web3d-prototype — engine-first architectural rendering tool

A **$0, fully client-side** web app where you load a real Rhino-exported building (geometry + semantic element IDs), click an element, swap a PBR material, set the real sun, place entourage, and render it live in the browser at three quality tiers. This is the engine-first core of "Photoshop-for-Architects" — geometry fidelity and multi-view consistency are exact because it's real 3D, not diffusion.

Project SSOT is the wiki: **`../../wiki/STATE.md`** (current state) and **`../../docs/HANDOFF-web3d.md`** (handoff + next steps).

## Run

```bash
npm install          # from this dir, or:  npm install --prefix apps/web3d-prototype
npm run dev          # → http://localhost:5181   (launch.json name: "web3d")
npm run build        # production build (Vite + rolldown)
npx tsc --noEmit     # typecheck
```

Stack: Vite 8 + React 19 + React-Three-Fiber 9 + drei 10 + **three.js r0.184**. No backend, no API calls (geo-context optionally bills the user's own Google Maps key).

## What it does (all verified)

- **Load** the meshopt-compressed semantic `public/model/house.glb` (12 element classes), auto-framed.
- **Material swap** — click an element → search/filter a **29-material CC0 PBR library** (ambientCG; brick/stone/concrete/plaster/wood/travertine/paving/metal/roofing/ground) in a thumbnail grid. UVs are **box-projected world-space in feet**, so texture scale is metric-consistent; each material carries a real-world `tileFeet`; live per-material scale slider. Non-destructive **layer stack**, localStorage-persisted.
- **Real glass** — windows share one `MeshPhysicalMaterial` (transmission).
- **Sky & Sun + atmosphere** — real `suncalc` solar position + mood/time/cloud presets, **golden-hour HDRI presets**, a **sun-path arc** overlay (day arc + analemma), and a cloud plate (WebGL2).
- **Real entourage** — place Tree/Bush/Person; trees/bushes are **real CC0 Quaternius GLBs** (instanced per-species, hash-varied), real-ft height sliders.
- **Output / client-ready** — **high-res Export still** (supersample + aspect crop, JPG/PNG), **Presentation mode** (hides all panels), **Cinematic grade**, **ContactShadows** grounding.
- **Geo-context** — Google Photorealistic 3D Tiles around the model (needs your Google Maps key).
- **Three render modes** (see below) + a **Cinematic (UE5)** toggle that embeds a SimplyStream UE WebGPU build.

## Architecture — the `renderMode` switch

`App.tsx` reads `store.renderMode` and mounts one of three **Stage** components, each owning its own `<Canvas>` + renderer + post, all rendering the shared `Scene.tsx`. Stages are **lazy-loaded** so `three/webgpu` (~900 kB) only downloads in WebGPU mode.

| Mode | Stage file | Renderer + post |
|---|---|---|
| `webgl2` | `stages/StageWebGL2.tsx` | WebGL2 + `Effects.tsx` (N8AO, Bloom, AgX, SMAA), VSM shadows, 256px sky-baked IBL |
| `webgl2gi` | `stages/StageWebGL2GI.tsx` (+`AreaLights`,`ReflectiveGround`,`EffectsGI`) | + RectAreaLight (LTC) area lights, `MeshReflectorMaterial` ground, stronger N8AO |
| `webgpu` | `stages/StageWebGPU.tsx` (+`WebGPUPost`,`WebGPUAreaLights`) | three.js `WebGPURenderer` + TSL **SSGI**/GTAO/TRAA/Bloom + node-safe HDRI IBL + VSM cast shadows |

**Shared:** `Scene.tsx` (model load, semantic resolve, box-UVs, material/highlight sync, glass, picking), `SolarSky.tsx` (suncalc sun + lights + sky/IBL — render-mode-aware: drei `<Sky>`/`<Environment>` on WebGL2, node-safe HDRI `WebGPUEnv` on WebGPU), `state/store.ts` (Zustand, single source of truth, persisted), `Effects.tsx`, `lib/swatches.ts`.

## Key gotchas (don't re-learn these the hard way)

- **Vite + R3F:** `resolve.dedupe` must include `react`, `react-dom`, `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`, `three` — else "Invalid hook call".
- **drei `<SoftShadows>` (PCSS) is broken on three r184** (emits removed `unpackRGBAToDepth` → washout). Use **VSM** (`shadows="variance"`). Vet `<ContactShadows>`/`<AccumulativeShadows>` before adding.
- **WebGPU:** drei `<Sky>`/`<Environment>` GLSL ShaderMaterials don't compile on the WebGPU node renderer → use the node-safe HDRI env (`SolarSky.WebGPUEnv`, equirect on `scene.environment`). VSM supports a single shadow-casting light (our sun). `RenderPipeline` not deprecated `PostProcessing`; `ssgi/ao/bloom/traa` from `three/addons/tsl/display/*`.
- **Verifying WebGPU:** the Claude-in-Chrome screenshot can't capture the GPU canvas (shows black). The **headless preview has an AMD WebGPU adapter** — screenshot WebGPU there. Confirm port `:5181` + `canvas.getContext('webgpu')` first.
- **Bloom veils the frame white** if too strong (the bright procedural sky in the HDR buffer) — keep it ≤0.15 / threshold ~1.1.

## Known issues / deferred
- **Path tracer — FIXED.** `PathTracer.tsx` now traces an isolated `ptScene` (dequantized `house_pt.glb` + mirrored live swatches + physical glass + HDRI `scene.environment` + a `.color` guard) instead of the live scene, killing the old `.color.r` crash. Runs in WebGL2 / + GI modes.
- **WebGPU console noise:** 6 benign `NodeBuilder: ShaderMaterial not compatible` warnings = the 6-face equirect→cube PMREM of the HDRI `scene.environment` (three internals); render is correct.
- **KTX2 deferred:** `scripts/encode_ktx2.mjs` + `public/basis/` are ready; jpg ships until a KhronosGroup `ktx` binary (+ `sharp`) is available to encode. Materials are large as jpg (KTX2 cuts ~4–8×).
- **Scaffold-only:** the Gaussian-splat environment (T3) + depth+canny FLUX diffusion hero (T4) are documented but not built — see `../../wiki/research/web3d-clientready.md` + `../../wiki/DECISIONS.md#web3d-clientready-composition`.

## How `house.glb` is made
`Rhino 8 → spike/rhino_export_gltf.py → spike/gltf_postprocess.py (node.extras semantics) → gltf-transform meshopt`. PBR swatches via `spike/ingest_pbr_swatches.py` (ambientCG CC0); HDRI via `spike/ingest_hdri.py` (Poly Haven → `public/hdri/sky.hdr`, used for WebGPU IBL).
