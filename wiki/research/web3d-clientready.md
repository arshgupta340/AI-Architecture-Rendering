---
type: research
topic: client-ready render push — materials at scale, real entourage, splat env, diffusion hero, atmosphere, high-res export
date: 2026-06-14
method: ultracode Workflow — 6 parallel EXA research agents (deep_researcher for splat + diffusion) + 1 synthesis agent (~1M tokens)
---

# Client-ready render — research synthesis + build plan

> The phase-1 research behind the "decked-out, client-ready render" push. Consolidates 6 track agents (materials/entourage/splat/diffusion/atmosphere/compositing) + a synthesis. This is the **build bible** for the parallel build phase. Tiers + WebGPU recipe: [[web3d-realism]] · [[web3d-webgpu]]. Entourage basics: [[web3d-entourage]].

## The reframe (the one big finding)

**The client-ready image is NOT a new render route.** It's the **existing WebGPU realtime Stage made presentable, then captured at high-res.** Composition stack (in the order the `WebGPUPost` graph already runs — pass→ssgi→bloom→traa):

1. **Base** — editable polygon building + expanded **KTX2 PBR material library** (T1), metric box-projected UVs already in `Scene.tsx`.
2. **Ground/context** — **real CC0 entourage** (T2): instanced Quaternius GLB trees/bushes + CC0 cutout people on the existing drei `<Billboard>`. The #1 "toy" tell studios cite (people-for-scale + landscaping).
3. **Atmosphere** — golden-hour CC0 HDRI on `scene.environment` driven by the existing suncalc sun + a cheap cloud plate for the hero.
4. **Grade** — a subtle TSL grade in `WebGPUPost` (DoF before bloom, film grain after traa, gentle LUT/contrast), AgX stays the single final tone-map.
5. **Export** — **Presentation mode** (hide DOM UI) + async high-res capture → JPG.

**This whole path is $0, deterministic, interactive, buildable now.** Gaussian-splat env (T3) and depth+canny FLUX diffusion hero (T4) are **explicitly NOT** the default path — they are paid/renderer-forking opt-in finishing layers (scaffold only this session). The **WebGL2 export path always works as a guaranteed fallback** if WebGPU async readback is flaky.

## Prioritized build plan

| Track | Pri | Scope this session | Key files |
|---|---|---|---|
| **T2 Real entourage** | P0 | FULL $0 build | `Entourage.tsx`, `lib/entourageAssets.ts`(new), `public/entourage/*` |
| **T6 High-res export + Presentation** | P0 | FULL $0 build (WebGPU readback = only risk → WebGL2 fallback) | `lib/exportImage.ts`(new), `App.tsx`, `ui/NavBar.tsx`, all 3 stages, `store.ts` |
| **T5 Path-tracer fix + grounding/atmosphere** | P0 | FULL $0 (takram atmosphere deferred → cheap clouds) | `PathTracer.tsx`, `SunPath.tsx`(new), WebGL2 stages, `SkyPanel.tsx`, `public/hdri/*` |
| **T1 KTX2 materials at scale** | P1 | Build-time fetch+encode scripts + loader + UI ($0, CC0 downloads) | `scripts/*.mjs`(new), `lib/swatches.ts`, `ui/Sidebar.tsx`, `public/materials`, `public/basis` |
| **T6/T1 Cinematic grade** | P1 | FULL $0 build | `WebGPUPost.tsx`, `Effects.tsx` |
| **T4 Diffusion hero** | P2 | SCAFFOLD only — $0 depth+canny capture buildable; paid FLUX gated | `lib/captureHero.ts`(new); server shim deferred |
| **T3 Splat environment** | P2 | SCAFFOLD only — renderer fork + ~$20/mo | `SplatContext.tsx`(new, webgl2gi-only) |

## Verified $0 asset pipeline (tested this session)

- **Materials (ambientCG, CC0):** direct zip `https://ambientcg.com/get?file={AssetId}_2K-JPG.zip` (tested Bricks097 → 15.9 MB zip, HTTP 200). Map suffixes → slots: `_Color`→albedo, `_NormalGL`→normal (NOT `_NormalDX`), `_Roughness`→roughness, `_AmbientOcclusion`→ao, `_Displacement`→height. Strong arch ids: Bricks*, PavingStones*, Concrete*, Travertine*, Marble*, WoodSiding*, Planks*, Plaster*, Metal*, CorrugatedSteel*, Rock*, Ground*, Grass*, RoofingTiles*, Terracotta*.
- **HDRIs (Poly Haven, CC0):** `https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/{slug}_2k.hdr` (tested spruit_sunrise → 5.9 MB, HTTP 200). Golden-hour: spruit_sunrise, qwantani_sunrise, citrus_orchard_road_puresky, golden_gate_hills.
- **Entourage GLBs (poly.pizza, CC0 Quaternius/Kenney):** two-step — GET `https://poly.pizza/m/{slug}` page → regex `https://static.poly.pizza/{uuid}.glb` → download (tested → 2.5 MB, valid `glTF` magic). The bare `static.poly.pizza/{slug}.glb` guess **403s**; you must scrape the UUID from the page. Khronos `raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/...` is a reliable backup host.

## Per-track key facts

### T1 — Materials at scale (P1, $0)
- **KTX2Loader works on BOTH WebGL2 and WebGPU in r184** (r180 fix #31721). **GOTCHA: on WebGPU you MUST `await renderer.init()` before `ktx2Loader.detectSupport(renderer)`** — StageWebGPU already awaits init in its glFactory; the shared loader must defer `detectSupport` until each Stage hands over its initialized renderer.
- Transcoder `basis_transcoder.{js,wasm}` is already vendored at `node_modules/three/examples/jsm/libs/basis/` → copy to `public/basis/` (Vite serves `public/` statically, no config change needed).
- **Encode** loose maps with KhronosGroup `ktx create` (needs PNG input — convert jpg→png with sharp first). Albedo = ETC1S (sRGB), data maps (normal/roughness/ao/height) = **UASTC** (`--encode uastc --zstd 18`; ETC1S on normals = artifacts). `--generate-mipmap` always.
- **Keep a jpg fallback** so nothing breaks if a `.ktx2` is missing (loader tries ktx2, falls back to jpg).
- **Anti-tiling: `three-hex-tiling` is WebGL2-only** (patches GLSL via onBeforeCompile, breaks the WebGPU node renderer like Sky/SoftShadows). WebGPU-safe path = TSL detail-map multiply / `triplanarTexture()` from `three/tsl`. **Highest-impact/lowest-risk first:** correct `tileFeet` + 2K maps + anisotropy 16 + mipmaps.
- **Verified tileFeet by category:** brick ~2.5–3, stone veneer ~2–4, wood plank ~3–4, travertine/marble ~2–4, stucco ~5–8, concrete panel ~6–10, paving ~1.5–3, grass ~3–6, metal seam ~1.5–2.5, roofing/terracotta ~1–2. (Current `materials.json` repeat:14 for brick is too dense.) Poly Haven metadata carries real-world dims → auto `tileFeet` (m×3.281).
- **Searchable swatch UI** = in-memory `.filter()` over `category`+`tags` + category chips + a thumbnail grid. No new dep (fuse.js ~5KB only if fuzzy ranking wanted).

### T2 — Real entourage (P0, $0) — highest payoff-per-effort
- **Primary source:** Quaternius **Stylized Nature MegaKit** (CC0, 40 trees + bushes/grass) via poly.pizza; **Ultimate Stylized Nature Pack** (CC0, normal-mapped, reads better under N8AO/SSGI). Kenney Nature Kit CC0 fallback.
- **`Entourage.tsx` is already the drop-in target:** `writeMatrices()`/`EntItem`/`addEnt`/`entHeight` + InstancedMesh + drei Billboard are reusable verbatim — only `trunkGeo/foliageGeo/bushGeo` and `personTexture()` change. Load species GLB once via `useGLTF`, instance its geometry+material per species filtered from `store.entourage`.
- **People:** alpha-cutout PNG billboards (keep the existing `<Billboard lockX lockZ>` + `alphaTest:0.5` + `toneMapped:false`). **Licensing minefield** — strictly-CC0 only for the redistributable bundle: **OpenGameArt CC0** (safe to commit) or **tonytextures Architecture People** (commercial-OK). **AVOID Skalgubbar** (arch-viz-only) and **MrCutout** (no-resale) in `public/`. Add `ATTRIBUTIONS.md`.
- Foliage cards: `alphaTest` (NOT `transparent`) → renders in the opaque pass, correct depth-sort + free shadows. `side:DoubleSide` for two-sided leaves.
- **Do NOT add octahedral impostors** (`@three.ez/octahedron-imposter`) — WebGL2-only (GLSL3 ShaderMaterial + WebGLRenderer atlas baker, breaks WebGPU node renderer), WIP/no docs, and 20–100 trees don't need them. Poly Haven photoscan trees are 5–8M tris → impostor-source only, never instance raw.

### T3 — Gaussian-splat environment (P2, SCAFFOLD only)
- **Renderer fork:** Spark (`@sparkjsdev/spark`, by World Labs, MIT, peer three>=0.180), mkkellogg, drei `<Splat>` are **ALL WebGLRenderer-only.** No three.js WebGPU/TSL splat renderer exists in 2026. So splats compose with `StageWebGL2GI`, **not** the WebGPU ceiling tier — a product contradiction (most photoreal context ≠ most photoreal renderer).
- **Not $0 to GENERATE:** World Labs **Marble** (~$20/mo Standard unlocks .spz/.ply export; native .spz loads in Spark, same company; API gives `metric_scale_factor`/`ground_plane_offset`; OpenCV→three flip Y,Z). Open-source (HunyuanWorld 2.0, Brush in-browser WebGPU training) needs real GPU. $0 holds only for RENDERING a pre-made splat.
- **Splats write NO depth** → break N8AO/SSGI/DoF over the splat region; composite as a non-depth backdrop layer. Baked-lighting-vs-our-sun mismatch is unsolved at $0 (V-Ray U3 just shipped relighting commercially). **Hybrid pattern:** splat "context bowl" + building in a footprint hole (pruned offline via SuperSplat) + transparent shadow-catcher plane for our sun. Reuse `GeoTiles.tsx` coord strategy (siteAnchor + m→ft + heading). **Defer to a v2 "Context backdrop" gated to webgl2gi.**

### T4 — Diffusion hero (P2, SCAFFOLD only) — prior art already proven
- **We already proved it:** `spike/run_e2b_registration.py:render_locked()` runs `fal-ai/flux-general` + `Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0` at **canny@0.8/depth@0.5** (32 steps, guidance 3.5, native size) → **98.5% edge alignment** on our house (51.7%→98.5% after seeding canny from ground-truth instance-id boundaries). REUSE verbatim; don't re-research. See [[DECISIONS#render-mask-registration]].
- **KEY 2026 fact: FLUX.2 has NO hosted depth/canny ControlNet** (only a local-only 8GB / ~80GB-VRAM `alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`). The geometry lock **stays on FLUX.1-dev Union**; FLUX.2 [pro] Edit ($0.045/MP) is for the per-region material pass, not the structural lock.
- **$0 part buildable now:** capture **TRUE depth + id-boundary canny** from our own three.js render (`MeshDepthMaterial`→`WebGLRenderTarget`→`readRenderTargetPixels`; `MeshNormalMaterial`+Sobel; id-buffer from the 12 semantic classes). Strictly better than MiDaS (eliminates the ~30% archviz depth error ArchiGen flags). web3d has **zero** depth/canny plumbing today (grep confirmed).
- **Scoped passes in risk order:** full-frame lock → sky-only Fill → entourage-only Fill → material-only (highest risk, last). Never one prompt for everything (ArchiGen's #1 failure mode). **The FLUX call is PAID** (~$0.04–0.13/img) + needs a backend shim to hold FAL_KEY (app is backendless) — **gate behind explicit authorization + the $0.05 cap.**

### T5 — Atmosphere + path-tracer fix (P0, $0)
- **Path-tracer crash root cause (verified):** `MaterialsTexture.updateFrom` reads `m.color.r` with no guard; `PathTracer.tsx` calls `pt.setScene(liveScene)` which includes the drei `<Sky>` **ShaderMaterial** (no `.color`) in webgl2 modes / NodeMaterials in webgpu mode → crash. **FIX:** build a dedicated `const ptScene = new THREE.Scene()`, add ONLY the dequantized building clone, assign the HDRI to `ptScene.environment`, `pt.setScene(ptScene, camera)`. Add a defensive `.color` guard. **AND mirror the user's live swatch layer assignments onto the traced copy** or the hero shows default materials (silently wrong). three-gpu-pathtracer DOES support transmission glass via MeshPhysicalMaterial (give windows a defined `.color`).
- **ContactShadows / AccumulativeShadows are SAFE on r184 WebGL2 stages** (they use MeshDepthMaterial+blur FBO, NOT the broken `<SoftShadows>` PCSS `unpackRGBAToDepth` chunk). But **`MeshDepthMaterial` is node-incompatible on WebGPU** (R3F #3458, black square) → ContactShadows **WebGL2 stages only**; keep VSM+SSGI on WebGPU.
- **Atmosphere:** `@takram/three-atmosphere` (+`/webgpu` TSL build, three>=0.182) is the only physically-based sky that runs on BOTH our stages (drei `<Sky>` breaks on WebGPU) — BUT it's **ECEF/globe-scale**, needs `worldToECEFMatrix` rebasing into our feet/near-origin scene = real integration work → **scaffold/defer.** Low-risk hero alternative now: **drei `<Cloud>`/`<Clouds>`** billboard puffs (host cloud.png locally), works on all stages.
- **Sun-path arc:** sample `SunCalc.getPosition` across the day (+ analemma = 21st of each month) at site lat/lng, map each via SolarSky's exact `setFromSphericalCoords(r, PI/2−altitude, azimuth)`, render as a drei `<Line>`. Safe on all stages.
- **Lightmap bake:** the current `uv1` is a box-projection, NOT a valid lightmap unwrap → would need a real 2nd UV (Blender Smart UV Project / xatlas). Low priority for an exterior (runtime N8AO/SSGI already covers GI) → hero-export only.

### T6 — Client-ready compositing & export (P0, $0)
- **High-res export:** WebGL2 path is canonical/low-risk — `gl={{preserveDrawingBuffer:true}}` then save size/pixelRatio → `setPixelRatio(scale)`+`setSize(W,H,false)` → `gl.render` → `domElement.toBlob('image/jpeg', 0.92)` → restore in a `finally`. **WebGPU has NO preserveDrawingBuffer** → must render the pipeline into a sized RenderTarget and `await renderer.readRenderTargetPixelsAsync` (un-premultiply), with the WebGL2 path as guaranteed fallback. GPU canvas reads **black** if captured deferred — render-then-grab in the same tick.
- **Presentation mode:** one `store.presentation` boolean + NavBar toggle + conditional panel render in `App.tsx` → clean client view, guarantees preview==export. Aspect/res/format picker (16:9, 3:2, 4:3, 1:1 × 1x/2x/4x × PNG/JPG), default 4K 16:9 JPG q0.92.
- **Tasteful grade** (arch-viz, not Instagram): DoF off-by-default or large focus (building stays sharp), film grain <0.08, vignette ~0.3, near-zero chromatic aberration, one subtle LUT. AgX stays LAST. WebGL2 = `@react-three/postprocessing` (DoF/Noise/Vignette/LUT); WebGPU = TSL `DepthOfFieldNode`/`FilmNode`/`Lut3DNode` slotted into the existing `WebGPUPost` graph (parallel impls, kept visually matched).

## Cross-cutting contradictions / gotchas (honor during build)
1. **Renderer fork:** splats (T3) WebGL2-only; WebGPU is the hero. → splats = webgl2gi-only "Context backdrop", deferred.
2. **"$0 client-side" breaks for T3/T4** (paid: ~$20/mo Marble; ~$0.04–0.13/img FLUX + backend shim). Holds for T1/T2/T5/T6 + the depth+canny *capture*.
3. **Anti-tiling forks by renderer** (three-hex-tiling WebGL2 / TSL detail-map WebGPU) — keep behind one `swatchMaterial()` API.
4. **Path-tracer fix must mirror live swatch edits** or the hero shows default materials (spans T5+T1).
5. **WebGPU readback risk spans T6 + T4** → shared WebGL2-capture fallback.
6. **ContactShadows/clouds/DoF not uniform across stages** → parallel WebGL2 (EffectComposer) + WebGPU (TSL) grades, visually matched.

## Open questions deferred to build/verify
- WebGPU `readRenderTargetPixelsAsync` non-black at 4x on the real target browser (#31658 closed r180; verify) — else always export via a WebGL2 pass.
- Can one `MeshStandardNodeMaterial` serve all 3 stages (for TSL anti-tiling) or must `swatchMaterial()` branch by renderMode.
- TRAA/SSGI convergence frames before a clean 4x WebGPU capture (maybe bump SSGI samples for the still only).
- CC0 people licensing call for what ships in `public/entourage/people/`.
- fal.ai commercial-output terms for FLUX.1-dev Union-Pro-2.0 weights before wiring a paid "Make Hero".

## Sources
Full source lists per track in the workflow result. Primary: ambientCG/PolyHaven APIs, threejs.org KTX2Loader + PR #31721, three/tsl triplanar, Quaternius/Kenney CC0, `@sparkjsdev/spark` + World Labs Marble docs, BFL FLUX.2 overview + Shakker-Labs Union-Pro-2.0, three-gpu-pathtracer MaterialsTexture, `@takram/three-atmosphere`+`three-clouds`, drei ContactShadows.
