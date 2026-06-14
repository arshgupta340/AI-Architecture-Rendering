---
type: state
updated: 2026-06-14
---

# Current State

> Snapshot, not a log. Overwrite at session end. Log is [[SESSIONS]]; rationale is [[DECISIONS]].

## Direction

**Web-native 3D-consistent rendering tool** (engine-first). Export real geometry + semantic element IDs from Rhino → glTF, render live in **three.js / React-Three-Fiber**, configure materials / sun / entourage / render-quality directly in 3D. Geometry fidelity + multi-view consistency are *exact and free* (it's real 3D) — exactly what the old 2D diffusion path bled on. Spark: [[research/arcway-teardown]]; rationale: [[DECISIONS#web3d-pivot]]. The 2D FLUX.2 + semantic-masking pipeline (`apps/canvas-prototype/`) is demoted to a future **"diffusion hero"** add-in.

## The web3d app — `apps/web3d-prototype/`  (Vite + React + R3F + three **r0.184**, $0 / client-side)

Run: `npm install --prefix apps/web3d-prototype` then `npm --prefix apps/web3d-prototype run dev` → http://localhost:5181 (launch.json `web3d`, port 5181). App README: `apps/web3d-prototype/README.md`.

### Working & verified
- **Model:** meshopt-compressed semantic `house.glb` (6.5 MB), 12 element classes, auto-framed.
- **Material swap:** click element → swap CC0 PBR material (ambientCG); **box-projected world-space (feet) UVs** → metric texture scale + live per-material scale slider; non-destructive layer stack; localStorage-persisted.
- **Real glass:** windows use ONE shared `MeshPhysicalMaterial` (transmission/ior 1.5).
- **Sky & Sun:** real `suncalc` solar position (lat/long/date/time) + mood/time/date/intensity/cloud presets (`SolarSky`/`SkyPanel`).
- **Entourage:** Tree/Bush/Person, click-to-place, InstancedMesh + billboard, real-ft height sliders. *(procedural placeholders — a NEXT-step track is real assets.)*
- **Geo-context:** Google Photorealistic 3D Tiles via `3d-tiles-renderer` (`GeoTiles.tsx`), georeferenced (tiles→local feet). Needs the user's Google Maps key to validate live.
- **Nav:** Orbit + Walk; saved views.
- **THREE RENDER MODES** behind a `renderMode` toggle (NavBar) — each a self-contained Stage owning its own `<Canvas>` + renderer + post, all rendering the shared `<Scene>`:
  - **WebGL2** (`stages/StageWebGL2`): baseline — N8AO + tamed Bloom + AgX + SMAA (`Effects.tsx`), VSM soft shadows, 256px sky-baked IBL.
  - **WebGL2 + GI** (`stages/StageWebGL2GI`): RectAreaLight (LTC) sky-fill + per-window emitters (`AreaLights`), `MeshReflectorMaterial` reflective plaza (`ReflectiveGround`), stronger N8AO (`EffectsGI`).
  - **WebGPU** (`stages/StageWebGPU` + `WebGPUPost` + `WebGPUAreaLights`): three.js `WebGPURenderer` + native TSL post graph (**SSGI** + GTAO + TRAA + Bloom) + LTC area lights + **node-safe HDRI IBL** (`SolarSky.WebGPUEnv` — equirect HDRI on `scene.environment`, PMREM-filtered internally) + **real VSM cast shadows** from the suncalc sun. The realism ceiling. `App` lazy-loads the stages so `three/webgpu` (~900 kB) only loads in WebGPU mode.
- **Cinematic (UE5) toggle** (`Cinematic.tsx`): full-screen overlay that embeds a SimplyStream-hosted UE5 WebGPU build of the model (deep-linked materials+sun). Embedding verified; needs the user's own UE build.
- **Lumen reference:** Twinmotion 2025.1 installed (RTX 4070) — `apps/web3d-prototype/UE_LUMEN_RUNBOOK.md` renders the house in real Lumen.

### Known-broken / deferred
- **In-app path tracer crashes at runtime** (`three-gpu-pathtracer` `MaterialsTexture.updateFrom` reads `.r` of an undefined material color) — geometry fixed (dequantized `public/model/house_pt.glb`, BVH builds), but a material (likely the transmission glass) needs a path-trace-safe color. Task chip spawned.
- **drei `<SoftShadows>` (PCSS) broke on three r184** (`unpackRGBAToDepth` removed → washout) → use VSM (`shadows="variance"`). Vet `<ContactShadows>`/`<AccumulativeShadows>` before adding.
- **WebGPU gotchas** ([[research/web3d-webgpu]]): drei `<Sky>`/`<Environment>` GLSL ShaderMaterials don't compile on the WebGPU node renderer (→ node-safe HDRI env on `scene.environment` instead); VSM supports a single shadow-casting light (our sun = fine); the Claude-in-Chrome screenshot can't capture the GPU canvas (shows black) — use the **headless preview** (it has an AMD WebGPU adapter) to screenshot WebGPU.

### The three realism tiers (all verified rendering)
| Mode | Tech | Look |
|---|---|---|
| **WebGL2** | N8AO + AgX + glass + VSM shadows | the baseline |
| **WebGL2 + GI** | + RectAreaLight area lights + reflective ground | richer; payoff strongest at ground level |
| **WebGPU** | SSGI + GTAO + TRAA + HDRI IBL + VSM | softest/warmest GI — the in-browser ceiling |
Lumen reference = **Twinmotion** (runbook, user-driven). Honest ceiling analysis: [[research/web3d-realism]] · [[research/web3d-ue-browser]].

## NEXT — the "decked-out, client-ready render" push (for ultracode multi-agent orchestration)

The 3 modes are a strong base but **minimal**. Goal: a fully art-directed, high-res render an architect / construction builder can send to clients. The detailed plan + the paste-in continuation prompt are in [[../docs/HANDOFF-web3d.md]] §Next-steps. Tracks:
1. **Material library at scale** — many CC0 PBR sets (ambientCG/PolyHaven), **KTX2-compressed**, **scale-aware tiling** (real-world tile-feet per material so input auto-scales), detail/triplanar anti-tiling on big surfaces, a searchable swatch UI. [[research/web3d-realism]]
2. **Real entourage** — replace the procedural Tree/Bush/Person with **real-looking** CC0 trees/bushes/people (Quaternius/Kenney/KhronosGroup/Poly-Haven meshes, alpha-tested foliage, octahedral impostors for distance, MrCutout-style cutout people). Twinmotion/low-poly quality, **not** gimmicky. [[research/web3d-entourage]]
3. **Gaussian splatting for environment** — explore generating photoreal splat *environments* around the (editable polygon) building; hybrid polygon-building + splat-context. *(Needs a fresh research pass — see prompt.)*
4. **Diffusion hero (consistency-safe)** — FLUX.2 on a viewport grab for the last-10% photoreal/atmosphere, with the **hallucination/consistency fix = condition tightly on the render's depth + canny edges** (the project's depth+canny multi-ControlNet, [[DECISIONS#render-mask-registration]]) + single-still scope. [[research/web3d-realism]]
5. **Lighting/atmosphere polish** — lightmap bake (needs a UV2 rebuild), volumetric clouds, ground/contact, aerial-perspective sky, sun-path arc.

## Pipeline (Rhino → web), all `$0`
```
Rhino 8 (live MCP) → spike/rhino_export_gltf.py → spike/gltf_postprocess.py (node.extras semantics) → gltf-transform meshopt → public/model/house.glb
PBR swatches: spike/ingest_pbr_swatches.py (ambientCG CC0) ;  HDRI: spike/ingest_hdri.py (Poly Haven → public/hdri/sky.hdr — now used for WebGPU IBL)
```

## Research (this arc)
[[research/arcway-teardown]] · [[research/web3d-engine-choice]] · [[research/web3d-rhino-gltf]] · [[research/web3d-realism]] · [[research/web3d-entourage]] · [[research/web3d-sky-sun]] · [[research/web3d-geo-context]] · [[research/web3d-ue-browser]] · [[research/web3d-webgpu]]

## Cost ledger
web3d arc = **$0 API** (local geometry + client render; CC0 assets). Geo-context bills the user's own Google PAYG once keyed (~$6/1k sessions). Prior diffusion spend ≈ $2.22 / $50 (unchanged). This session: **$0** (research via EXA on the user's quota).

## Handoff
Fresh-chat continuation prompt + the next-step (ultracode) plan: [[../docs/HANDOFF-web3d.md]].
