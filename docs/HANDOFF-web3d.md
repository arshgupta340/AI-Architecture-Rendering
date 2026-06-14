# Handoff — web3d 3D-consistent rendering tool (updated 2026-06-14)

This doc lets a fresh session continue with zero re-derivation. **Read `wiki/STATE.md` first, then this, then `apps/web3d-prototype/README.md`.**

---

## ⭐ NEXT-STEPS — paste this prompt into the next chat (turn on **ultracode** for multi-agent orchestration)

> Continue the **web3d engine-first architectural rendering tool** (`apps/web3d-prototype/`, Vite + React + R3F + three r0.184, $0/client-side, `npm --prefix apps/web3d-prototype run dev` → http://localhost:5181, launch.json `web3d`). **First read `wiki/STATE.md`, `apps/web3d-prototype/README.md`, `docs/HANDOFF-web3d.md`, and the research docs `wiki/research/web3d-realism.md`, `web3d-webgpu.md`, `web3d-entourage.md`, `web3d-ue-browser.md`.** Keep the wiki current per `CLAUDE.md` § Session-log protocol.
>
> **Where we are:** three working render modes behind a `renderMode` toggle — **WebGL2** (N8AO/AgX/glass/VSM), **WebGL2+GI** (RectAreaLight LTC area lights + `MeshReflectorMaterial` reflective ground + stronger N8AO), and **WebGPU** (three.js `WebGPURenderer` + TSL SSGI/GTAO/TRAA/Bloom + node-safe HDRI IBL + real VSM cast shadows). Plus a Cinematic (UE5/SimplyStream) embed toggle, a Twinmotion 2025.1 Lumen runbook (installed on the RTX 4070), suncalc sun, geo-context (Google 3D Tiles), and metric material swaps. It's a strong base but **minimal** — sparse material library, placeholder entourage, bare environment.
>
> **The goal:** go from this minimal base to a **fully art-directed, high-res, client-ready render** an architect / construction builder can send to clients — correct lighting, rich materials, real entourage, real environment/context, atmosphere. Use **ultracode multi-agent orchestration**: research first (prefer the **EXA** MCP tools — `mcp__exa__*` — per the standing preference; deep-researcher for the big open questions), then build in parallel. $0/client-side where possible; WebGPU is the quality tier.
>
> **Tracks (research, then build in parallel where independent):**
>
> 1. **Material library at scale, auto-scaled to input.** Expand far past the current 5 swatches: many CC0 PBR sets (ambientCG, PolyHaven). **KTX2/Basis-compress** them (`@gltf-transform` + `KTX2Loader`) for VRAM + grazing-angle sharpness. Make tiling **scale-aware** — each material carries a real-world tile size (feet) so it auto-scales on any surface (the app already box-projects world UVs in feet — extend `lib/swatches.ts` + a materials manifest). Add detail/triplanar mapping to kill tiling on big walls. A searchable swatch-library UI.
>
> 2. **Real entourage — trees, bushes, people that look REAL, not gimmicky.** Replace the procedural Tree/Bush/Person placeholders with real-looking CC0 assets at **Twinmotion / good-low-poly** quality. Sources: Quaternius/Kenney/KhronosGroup CC0 nature, Poly Haven 3D models, alpha-tested foliage cards, **octahedral impostors** for distant trees (perf), **MrCutout-style cutout people** (alpha billboards facing the camera). Drop them in behind the existing `Entourage` `InstancedMesh` placement so the scatter-paint UX is unchanged. Study how Twinmotion/Lumion entourage actually works (real meshes + impostors + cutouts). Meshes or impostors — whatever performs on the web.
>
> 3. **Gaussian splatting for environment generation (RESEARCH this — the big open question).** What we have is good but the *surroundings* are bare. Can we **generate a photoreal splat environment** around the (editable polygon) building and render it in-browser? Two angles: **(a) hybrid** — keep the building as editable polygon, surround it with a Gaussian-splat *context* (real-site photogrammetry splat, or an AI/text-to-3D-generated splat environment) composited in the same three.js scene (`@sparkjsdev/spark` / a gsplat loader); **(b) publish-export** — bake a high-quality offline render of the whole scene to a splat for a photoreal walkthrough (the D5-Render approach — but it BAKES materials, killing live editing, so keep it a terminal "publish" export only). Find the cleanest "minimal → decked-out environment" path.
>
> 4. **Diffusion hero (last-10% photoreal) WITHOUT the hallucination/inconsistency problem.** We can screenshot a render and run a diffusion model (FLUX.2, from `apps/canvas-prototype`) for photoreal/atmosphere — but naive diffusion hallucinates geometry and isn't consistent across views. **The fix is the project's own prior art:** condition the diffusion *tightly on the render's own depth + canny edges* (the **depth+canny multi-ControlNet** — `wiki/DECISIONS.md#render-mask-registration` proved "geometry preservation = mask registration", 98.5% edge alignment), so the output can't drift from the geometry; and scope it to a **single hero still** (cross-view consistency isn't needed for one frame). Also consider diffusion for *parts only* (sky, entourage, material detail) rather than the whole frame. The multiview-lock work (`#multiview-honest-metric`) is the basis if cross-view consistency is ever required.
>
> 5. **Lighting + atmosphere polish** — lightmap bake (needs a UV2 rebuild of the model; Blender Cycles → `lightMap` on uv1), volumetric clouds (`@takram/three-clouds`, hero-only), aerial-perspective sky (`@takram/three-atmosphere`), ground/contact shadows, sun-path arc; and **fix the deferred in-app path tracer** (crashes in `three-gpu-pathtracer` `MaterialsTexture.updateFrom` reading `.r` of a material with no color — geometry is already dequantized in `public/model/house_pt.glb`; give every traced mesh, esp. the glass, a path-trace-safe color).
>
> **How to think about "client-ready":** the routes compose — (a) push the **WebGPU real-time** path (more materials + real entourage + lightmaps + atmosphere + the built geo-context), (b) a **diffusion hero** still on top (consistency-locked via depth+canny), (c) a **Gaussian-splat environment** for photoreal surroundings, (d) the **Twinmotion/UE Lumen** path for the absolute ceiling. Figure out which combination produces a sendable image, and whether depth+canny conditioning actually solves the diffusion-hallucination problem for us.
>
> **Constraints / gotchas:** three r0.184 — drei `<SoftShadows>` and `<Sky>`/`<Environment>` break on WebGPU (use VSM + the node-safe HDRI env); WebGPU VSM = single shadow-casting light; **verify WebGPU via the headless preview's AMD adapter** (Claude-in-Chrome screenshots the GPU canvas black — confirm port `:5181` + `canvas.getContext('webgpu')`); keep the `renderMode` Stage architecture (each mode self-contained, lazy-loaded).

---

## 0. Latest update — 2026-06-14 (3-way render build + WebGPU IBL/shadows + bundle split)

Built **three render modes** behind a `renderMode` toggle (NavBar), via **3 parallel Opus agents** in isolated git worktrees, then integrated + verified. Full detail: `wiki/SESSIONS.md` (2026-06-14) + `wiki/research/web3d-webgpu.md`.
- **`StageWebGL2`** baseline (`Effects.tsx`) · **`StageWebGL2GI`** RectAreaLight LTC area lights + `MeshReflectorMaterial` reflective ground + stronger N8AO · **`StageWebGPU`** `WebGPURenderer` + TSL SSGI/GTAO/TRAA/Bloom + **node-safe HDRI IBL** (`SolarSky.WebGPUEnv` — equirect HDRI on `scene.environment`, PMREM'd internally) + **real VSM cast shadows** from the suncalc sun. All three verified rendering (WebGPU on the integrated build, real WebGPU context).
- `App` **lazy-loads** the stages → `three/webgpu` (~900 kB) only loads in WebGPU mode (main chunk 306 kB gzip). Path-trace button guarded out of WebGPU mode.
- **Machine scout:** Twinmotion 2025.1 + Lumion 2024 Student installed, RTX 4070 → `apps/web3d-prototype/UE_LUMEN_RUNBOOK.md` (the real Lumen reference, user-driven).
- **Deferred:** in-app path tracer crashes on a material color (geometry dequantized = fixed; task chip spawned). WebGPU verified shadows are REAL VSM (not mimicked from WebGL2).
- Commits `d99d8ae`→`4a3cbc2` on `overnight/spike-builder-2026-05-17`.

---

## 0-prev. Earlier update — 2026-06-13 (realism pass + UE-in-browser research)

Full log: [[wiki/SESSIONS.md]]; rationale: [[wiki/DECISIONS.md#web3d-realism-tiers]]. Two things happened:

**(A) Tier-1 WebGL2 realism pass — DONE & verified in preview.** The live app is markedly more realistic (AO depth, real glass, soft sun shadows, AgX grade):
- `src/Effects.tsx` (NEW) — `<EffectComposer>`: **N8AO** (ambient occlusion, the big win) + tamed **Bloom** (`intensity 0.12 / luminanceThreshold 1.1` — higher veils the whole frame white) + BrightnessContrast + HueSaturation + Vignette + SMAA + **AgX `ToneMapping`** (LAST). Mounted in `App.tsx`, gated on `!rendering`.
- `App.tsx` — renderer `gl.toneMapping = NoToneMapping` + `antialias:false` (the AgX *effect* owns tone mapping; leaving the renderer's AgX on double-maps → washout). `shadows="variance"` (VSM).
- `Scene.tsx` — `window` meshes use ONE shared **`GLASS` `MeshPhysicalMaterial`** (transmission 1, ior 1.5, roughness 0.07), `castShadow=false`.
- `SolarSky.tsx` — IBL env 128→**256** + a re-bake `key` so reflections track time-of-day; directional light `shadow-radius`/`shadow-blurSamples` for VSM softness.
- `lib/swatches.ts` — texture anisotropy 8→16. `vite.config.ts` — `@react-three/postprocessing`+drei added to `dedupe`/`optimizeDeps` (Invalid-hook-call fix).
- **GOTCHA:** drei `<SoftShadows>` (PCSS) is **broken on three r0.184** (`unpackRGBAToDepth` removed → shader fails → washout). Use **VSM** (`shadows="variance"`). Vet `<ContactShadows>`/`<AccumulativeShadows>` before adding.

**(B) Client-side UE5-in-browser — researched, decision made.** User surfaced Wonder Interactive / **SimplyStream** (UE5 over WebGPU+WASM, "death of pixel streaming"). EXA deep-research → [[wiki/research/web3d-ue-browser.md]]. Verdict: real & impressive, but **no Lumen/Nanite in-browser** (baked archviz, *not* the live-Lumen arcway look) and you **upload a per-model UE build** (can't stream our live scene in). Decision: **bank WebGL2 now (done), spike the UE toggle in parallel (not a product bet), WebGPU three.js later** ([[wiki/DECISIONS.md#web3d-realism-tiers]]).

### UE5 "Cinematic" toggle — app-side BUILT + verified; you supply the UE build
**The in-app toggle is built** (`src/Cinematic.tsx` + a "Cinematic (UE5)" NavBar button + store `cinematic`/`cinematicUrl`). Verified in-preview: button → setup card (this runbook) → paste a build URL → it embeds a SimplyStream build in an `<iframe>` deep-linked with the current materials + sun, with Open-in-new-tab / Change-build / Exit controls. **Key validated finding: SimplyStream builds DO allow iframe embedding** — tested `garage.cjponyparts.com`, which streamed to 100% inside the app (the UE 3D render itself needs a real WebGPU GPU, absent in the headless preview but present in a normal browser). What's left is **producing YOUR build** (needs Unreal + a SimplyStream account):
1. **Sign up** at `app.simplystream.com` (join their Discord for access if needed).
2. **Get the model into Unreal**: import `apps/web3d-prototype/public/model/house.glb` (or the uncompressed `house_raw.glb`) via **Datasmith glTF**. Assign PBR materials (reuse the ambientCG maps in `public/materials/`).
3. **Bake** Lightmass GI (no Lumen in-browser) for a fixed (or few-preset) sun. Build a **material-variant configurator** (Variant Manager / Blueprint) keyed to our semantic element IDs (wall/roof/window/…) so swaps map across.
4. **Package + Upload** to SimplyStream → get a shareable WebGPU URL.
5. **Paste it** into the Cinematic overlay's setup card → it embeds instantly. Materials + sun are already deep-linked as query params (`?materials=wall:red_brick,…&lat=…&time=…`); the UE build parses them. **Camera sync is the one TODO** (needs the live R3F camera pose threaded into the store).
6. Compare quality/perf on our model vs the WebGPU three.js path before committing to either as the hero.

---

## 1. The direction (the "why")

We pivoted from the 2D diffusion canvas to a **web-native 3D rendering tool**. The spark was a teardown of competitor **arcway.ai** ([[wiki/research/arcway-teardown.md]]): photoreal web home-configurators run on a *real renderer* (Unreal, pixel-streamed) — with real geometry, **multi-view consistency and instant material swaps are free**, which is exactly what our diffusion spike fought for months ([[wiki/DECISIONS.md#multiview-honest-metric]]). And we already extract clean **geometry + semantic element IDs** from Rhino — the very thing Arcway's "Bridge AI" exists to reverse-engineer from flat PDFs. So: **engine-first.** The 2D FLUX.2 + semantic-masking pipeline (`apps/canvas-prototype/`) is demoted to a future **"diffusion hero" add-in** (a photoreal/entourage pass on a 3D viewport grab). Full rationale: [[wiki/DECISIONS.md#web3d-pivot]].

## 2. Run it

```
npm install --prefix apps/web3d-prototype        # if node_modules missing
npm --prefix apps/web3d-prototype run dev        # → http://localhost:5181
```
Preview-tool launch config: `.claude/launch.json` name **`web3d`**, port **5181**. Vite + React + TS + R3F. **$0 / fully client-side** — no API calls in any feature.

## 3. What's built (file map)

**Web app — `apps/web3d-prototype/src/`:**
- `App.tsx` — Canvas (WebGL2, AgX tonemap, frameloop demand/always), mounts `SkyPanel` (left), `Sidebar` (right, materials/layers), `NavBar` (bottom-left, nav/entourage/render).
- `Scene.tsx` — loads `house.glb`, `semOf()` (resolve element class up the node tree), `boxProjectUVs()` (world-space ft UVs), building-bbox framing, material+highlight sync, save/goto views, click-to-place + click-to-select pick. Renders `<SolarSky>`, `<Entourage>`, conditional `<PathTracer>`, controls.
- `SolarSky.tsx` — drei `<Sky>` + sun/hemisphere/ambient from `suncalc` (lat/long+date/time) + sky-baked env map.
- `Entourage.tsx` — procedural Tree/Bush/Person; `InstancedMesh` + billboard; `BASE_HEIGHT` + `ENT_RANGE` for real-ft scaling.
- `PathTracer.tsx` — three-gpu-pathtracer hero (see "broken" below).
- `Walk.tsx` — PointerLock + WASD.
- `GeoTiles.tsx` — **(NEW)** Google Photorealistic 3D Tiles via `3d-tiles-renderer` (GoogleCloudAuth + GLTFExtensions/Draco + Reorientation + Compression + Fade + AttributionOverlay), wrapped in an outer group that puts the geolocated origin under the building (`siteAnchor`), scales m→ft, and applies `groundOffset`/`heading`. See [[wiki/DECISIONS.md#web3d-geo-context]].
- `vite-env.d.ts` — **(NEW)** `vite/client` types + `VITE_GOOGLE_MAPS_API_KEY` typing (the app had no env types before).
- `lib/swatches.ts` — ambientCG PBR material factory; `tileFeet` + live per-swatch scale (`setSwatchScale`).
- `lib/cameraFromRhino.ts` — camera.json → three.js camera (frustum→FOV, Z-up→Y-up).
- `state/store.ts` — Zustand (persisted: layers, views, swatchScale, entourage, entHeight, sky). **Single source of truth.**
- `ui/Sidebar.tsx`, `ui/NavBar.tsx`, `ui/SkyPanel.tsx`.
- `public/model/house.glb` (6.5 MB meshopt), `public/materials/<swatch>/`, `public/hdri/sky.hdr`.

**Rhino→web pipeline — `spike/`:** `rhino_export_gltf.py` (Rhino-side via MCP), `gltf_postprocess.py` (pure-python GLB extras rewrite), `ingest_pbr_swatches.py` (ambientCG), `ingest_hdri.py` (Poly Haven). Reuses `rhino_capture.py` semantic rules.

## 4. Working (verified in preview) vs broken

**Working:** model load + 12 semantic classes; click→PBR material swap (only that class); metric-consistent textures + live scale slider; non-destructive layers + persistence; orbit/walk; saved views (Overview/Rhino/user); **Sky & Sun** (real sun, mood/time/date/intensity/cloud presets); **entourage** (place trees/bushes/people, real-ft height sliders, persisted); **geo-context** (Google Photorealistic 3D Tiles, key-gated, georeferenced tiles→local feet around the model — UI + mount path verified in preview; tile imagery + georeference fidelity pending the user's real key).

**Broken / deferred:**
- **Path tracer** builds a building-only BVH (~1.2 s) and accumulates, but renders **only sky** — `three-gpu-pathtracer` is incompatible with our **meshopt / KHR_mesh_quantization** geometry (BVH builds, ray intersection misses the quantized meshes; tried: async-worker, reduced scene, frozen controls, render-target reset, low-res off, single shared material). **Fixes:** (a) path-trace an *uncompressed* `house.glb` copy, or (b) **switch the hero to the diffusion pass** (recommended — fast, adds entourage/sky/mood, reuses `apps/canvas-prototype` FLUX.2).
- Stale preview console errors (PointerLock in iframe; an old HMR pathtracer module) — harmless.

## 5. The Rhino→glTF pipeline (reproducible)
1. Open the model in Rhino 8 (sample: kCs_SampleHouseProject, CSI layers). Live MCP slot.
2. `run_python` exec `spike/rhino_export_gltf.py` → `export(out_dir)`: renames objects `{semantic}__i` (restored in `finally`), `FileGltf.Write(MapZToY, ExportLayers, ExportOpenMeshes, CullBackfaces=False, ExportMaterials=False)`, writes `house_raw.glb` + `semantics.json` + `camera.json`.
3. `spike\.venv\Scripts\python.exe spike/gltf_postprocess.py` → injects `node.extras` semantics (NODE not mesh — three.js #15728); windows recovered via the `08 - OPENINGS` layer node.
4. `npx @gltf-transform/cli meshopt <in> apps/web3d-prototype/public/model/house.glb` (meshopt-only preserves extras).
Details + gotchas: [[wiki/research/web3d-rhino-gltf.md]].

## 6. Agent research (each a wiki doc under `wiki/research/`)
- **arcway-teardown** — competitor = Unreal pixel-streamed; our edge = native Rhino geometry+semantics. (The pivot's basis.)
- **web3d-engine-choice** — three.js + R3F + drei (vs Babylon/PlayCanvas). WebGL2 for now.
- **web3d-rhino-gltf** — the export pipeline + the meshopt/quantization + #15728 gotchas.
- **web3d-realism** — HDRI/PBR/AgX/lightmaps/GTAO/SSGI ceiling; path-tracer vs diffusion hero; WebGPU.
- **web3d-entourage** — Quaternius/Kenney CC0 + MrCutout people; InstancedMesh + billboards; scatter-paint.
- **web3d-sky-sun** — drei Sky + suncalc; PMREM-from-sky IBL; shadow studies; mood/clouds.
- **web3d-geo-context** — Google Photorealistic 3D Tiles via `3d-tiles-renderer`; georeference; cost/licensing; MapLibre fallback.

## 7. Roadmap / recommended next
1. **Geo-context** ✅ **built** (`GeoTiles.tsx`) — enter coords → Google 3D Tiles georeferenced around the model. **To validate:** paste a Google Maps key (Map Tiles API enabled) into SkyPanel → "Real-world context" → Load; set **Site elevation** ≈ the site's metres-above-sea-level, then nudge **Seat building** (ft) + **North heading** until the model sits/aligns on the real terrain. Polish left: raycast auto-snap to terrain (replace the Seat slider), auto true-north from Rhino, a `load-error` toast for bad keys. [[wiki/research/web3d-geo-context.md]] · [[wiki/DECISIONS.md#web3d-geo-context]]
2. **Diffusion hero add-in** — wire FLUX.2 onto a viewport grab (replaces the broken path tracer; the project's core strength).
3. **Real entourage assets** — swap procedural Tree/Bush/Person for Quaternius/Kenney GLBs + MrCutout cutouts (drop-in behind the instanced renderer).
4. **Sky polish** — PMREM env-from-sky (reflections track time-of-day), sun-path arc, real volumetric clouds.
5. **Realism** — lightmap bake, KTX2 textures, WebGPU/SSGI.

## 8. Hard-won gotchas
- Vite + R3F → **`resolve.dedupe: ['react','react-dom','@react-three/fiber','three']`** or "Invalid hook call".
- Heavy scene → **`frameloop="demand"`** (continuous render saturates GPU; screenshots time out).
- GLTFLoader puts extras on a **Group** for multi-primitive nodes → resolve semantic up ancestors.
- meshopt-quantized geometry breaks `three-gpu-pathtracer`.
- **`3d-tiles-renderer` (geo-context):** Google P3DT tiles are **Draco** glTF (JPEG textures, no KTX2) → MUST register `GLTFExtensionsPlugin({ dracoLoader })`; `GoogleCloudAuthPlugin.useRecommendedSettings` only sets `errorTarget=20`, it does **not** wire decoders. R3F `<TilesPlugin args>` is typed `any[]` → pass the single options object **wrapped in an array** `args={[{…}]}` (runtime does `new plugin(...args)`). `ReorientationPlugin` lat/lon are **radians**, and it handles the Z-up→Y-up flip itself (don't also rotate the group). Tiles stream only while frames render → geo on ⇒ `frameloop="always"`. A bad/expired key → non-fatal `reading 'content'` lib log (no crash).
- pip was deny-blocked; **removed `Bash(pip install *)` from `.claude/settings.local.json` deny** this session.
- `.claude/plans/` is permission-blocked for Write.

## 9. Continuation prompt (paste verbatim into the new chat)

> See the prompt block in the chat message that delivered this handoff, or copy from here:
>
> ---
> Continue the **web3d 3D-consistent rendering tool**. First read `wiki/STATE.md`, `docs/HANDOFF-web3d.md`, and `wiki/DECISIONS.md#web3d-pivot`. The app is `apps/web3d-prototype/` (Vite+React+R3F, run `npm --prefix apps/web3d-prototype run dev` → localhost:5181, launch.json name `web3d`); it's $0/client-side. Working: Rhino→semantic-glTF pipeline, click-to-swap PBR materials with metric UVs + scale slider, non-destructive layers, orbit/walk, saved views, a left **Sky & Sun** panel (suncalc real sun + mood/time/date presets), **entourage** (place trees/bushes/people with real-ft height sliders), and **geo-context** (`GeoTiles.tsx` — Google Photorealistic 3D Tiles georeferenced around the model; key-gated, UI/mount verified, see `wiki/DECISIONS.md#web3d-geo-context`). The **path tracer is broken** (three-gpu-pathtracer can't intersect our meshopt/KHR_mesh_quantization geometry) — replace the hero with a **diffusion pass** (FLUX.2 from `apps/canvas-prototype`) OR path-trace an uncompressed model. **Open geo follow-ups:** validate live with a real Google Maps key, raycast auto-snap to terrain, auto true-north from Rhino, bad-key `load-error` toast. **Other pillars:** diffusion-hero add-in, real entourage assets (Quaternius/Kenney), PMREM env-from-sky + sun-path arc. Verify every change in the browser preview (the `preview_*` tools, server name `web3d`). Keep the wiki current per `CLAUDE.md` § Session-log protocol.
> ---
