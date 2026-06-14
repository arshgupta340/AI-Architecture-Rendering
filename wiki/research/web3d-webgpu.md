---
type: research
topic: three.js WebGPU render path (SSGI/GTAO/TRAA + node-safe HDRI IBL + VSM shadows) for the web3d tool
date: 2026-06-14
method: Opus build-agent (Agent A) + EXA research (WebGPU IBL, WebGPU shadows) + in-browser verification on an RTX 4070 / AMD-iGPU
---

# three.js WebGPU realism path — build findings (r0.184)

> Consolidates the work behind the **WebGPU** render mode (`apps/web3d-prototype/src/stages/StageWebGPU.tsx` + `WebGPUPost.tsx` + `WebGPUAreaLights.tsx`, and `SolarSky.WebGPUEnv`). Built by a parallel Opus agent (Agent A) + two follow-up EXA research passes. This is the in-browser **realism ceiling** tier ([[web3d-realism]]).

## Verdict
A three.js **WebGPURenderer + native TSL post-processing node graph (SSGI → GTAO → TRAA → Bloom) + LTC area lights + node-safe HDRI IBL + real VSM cast shadows** renders the shared scene and is a clear step above the WebGL2 N8AO baseline (softer/warmer global illumination, real indirect bounce, better contact darkening). It's the right "quality" tier, $0/client-side, and keeps full interactivity. The migration is **per-stage** (a self-contained `<Canvas>`), so the WebGL2 modes are untouched.

## How the WebGPU stage is built (the working recipe)
- **Renderer:** `import * as THREE from "three/webgpu"`; R3F Canvas async `gl` factory: `new THREE.WebGPURenderer({...props, antialias:false})` → **`await r.init()`** (missing it = silent black) → `r.toneMapping = AgXToneMapping`. `extend(THREE)` (from `three/webgpu`) registers the node classes as R3F JSX — verified safe globally (three/webgpu's core classes are the *same identities* as plain three, so the WebGL stages still work).
- **Tone mapping:** keep the scene pass + all effects in **linear HDR** and let the node `RenderPipeline`'s `outputColorTransform` apply AgX + sRGB ONCE at the end (set `renderer.toneMapping = AgXToneMapping`). This is the WebGPU equivalent of the WebGL2 trailing AgX post pass — NOT a double tone-map. (`NoToneMapping` here blows out the bright sky/windows.)
- **Post graph (native `RenderPipeline`, NOT @react-three/postprocessing — that's WebGL-only):**
  `pass(scene,camera)` with MRT `{output, diffuseColor, normal(packed), velocity}` → `ssgi(beauty,depth,normal,camera)` (GI in `.rgb`, AO in `.a`) → composite `beauty*ao + diffuse*gi` → `bloom` → `traa(composite,depth,velocity)`, driven by `RenderPipeline.render()` in `useFrame(()=>post.render(), 1)` (renderPriority 1 disables R3F auto-render).
- **frameloop="always"** for this stage only — TRAA + SSGI temporal filtering need continuous frames to converge (the WebGL2 stages stay on-demand).
- **Lazy-loaded** in `App.tsx` so `three/webgpu` (~666 kB chunk) + `RectAreaLightTexturesLib` (~247 kB) load ONLY when WebGPU mode is selected.

## Critical r184 gotchas (verified)
1. **`bloom`/`ao`/`ssgi`/`traa` are NOT in `three/tsl`.** They import from `three/addons/tsl/display/{BloomNode,GTAONode,SSGINode,TRAANode}.js`. The TSL *primitives* (`pass`, `mrt`, `output`, `normalView`, `diffuseColor`, `velocity`, `directionToColor`, …) ARE in `three/tsl`.
2. **`PostProcessing` is deprecated since r183** (warns, delegates to `RenderPipeline`) — use `RenderPipeline` directly.
3. **SSGI/GTAO/TRAA/SSR nodes are WebGPU-ONLY** — no `@react-three/postprocessing` / N8AO equivalent (those are WebGL-only).
4. **drei `<Sky>` and `<Environment>` don't compile on WebGPU.** They use GLSL **`ShaderMaterial`s** (Sky's analytic shader; Environment's PMREM equirect→cubeUV passes). The WebGPU node renderer logs `THREE.NodeBuilder: Material "ShaderMaterial" is not compatible` and the sky renders black. **Fix:** see IBL below.
5. **RectAreaLight on WebGPU** needs `RectAreaLightTexturesLib` + `RectAreaLightNode.setLTC(...)`, NOT the WebGL `RectAreaLightUniformsLib`.
6. **SSGI cost** = `sliceCount × stepCount × 2` samples/px. Start low (`sliceCount 1`, `stepCount 12`).

## Node-safe HDRI IBL (the fix for #4)
three added a **WebGPU PMREM path in r163** (PR #27829: `PMREMGenerator.fromEquirectangular` works on WebGPURenderer + a `pmremTexture(tex,uv,roughness)` TSL node). But the **simplest** working pattern (confirmed by a r0.184 forum example) is: **load an equirect HDRI and assign it straight to `scene.environment`** — the WebGPU renderer PMREM-filters it *internally* (node-based), no GLSL ShaderMaterial. drei `<Environment files>` fails only because *it* does its own WebGL ShaderMaterial PMREM.
- Impl (`SolarSky.WebGPUEnv`): `useLoader(HDRLoader, "/hdri/sky.hdr")` → `hdr.mapping = EquirectangularReflectionMapping` → `scene.environment = hdr`. `scene.environmentIntensity` is modulated by daylight (so the static HDRI doesn't keep the scene lit at night). The visible background stays the **dynamic color sky** (so time-of-day still works); the HDRI drives reflections + image-based ambient. Ambient/hemisphere fill lights are dialed to **35%** in WebGPU mode to avoid double-lighting.
- Loader import: `three/addons/loaders/HDRLoader.js` (r183+ name; `RGBELoader.js` still exists as the older name).

## VSM cast shadows on WebGPU (verified real)
The directional **sun casts real shadow maps** computed by the WebGPU renderer from the actual geometry — NOT mimicked from WebGL2 (each renderer does its own shadow pass; the shared `SolarSky` only supplies the *light*, whose position is the real suncalc solar position).
- **VSM is genuinely implemented on WebGPURenderer:** added r169 (PR #29225), optimized r182 (#32209), shadow-acne fixed r183 (#32705 — also: PCF-Soft depth textures need `LinearFilter`). So `shadows="variance"` (VSMShadowMap) on the WebGPU Canvas works in r184.
- **Documented limit:** WebGPU VSM supports a **single shadow-casting light** — which is exactly our case (only the sun casts; ambient/hemi/area lights and the HDRI env don't). Adding a second shadow-caster would silently drop one.
- Verified empirically: cast shadows shift correctly midday (short/even) → golden-hour (long/warm/directional); the roof eaves cast onto the walls.

## Honest realism delta + capture caveat
- WebGPU's win for *exterior* scenes is real but **incremental, not transformational** vs a tuned WebGL2 stack — exteriors are direct-sun + sky-IBL dominated, where SSGI's interior-bounce signature matters less. Both lack offline path-tracing / Lumen. (Full analysis: [[web3d-realism]], [[web3d-ue-browser]].)
- **Capture trap (cost real debugging time):** the Claude-in-Chrome **screenshot can't grab the GPU-composited canvas** (renders black even though the app renders fine) and `canvas.toDataURL` is black without `preserveDrawingBuffer`. The **headless preview has an AMD WebGPU adapter**, so it's the reliable way to screenshot WebGPU. Also: a stale agent-worktree dev server on `:5196` once masqueraded as the integrated build (`:5181`) — always confirm the port + `canvasIsWebGPU` before trusting a WebGPU screenshot.

## Sources (primary)
- WebGPU PMREM: PR #27829 (r163). · WebGPU VSM: PR #29225 (r169), #32209 / #32327 (r182), #32705 (r183). · Dynamic shadowmap type: #32105 (r181). · Scene.environment direct-equirect: forum 0.184.0 example + issue #28827. · WebGPURenderer manual: threejs.org/manual/en/webgpurenderer.html. · SSGI example: `webgpu_postprocessing_ssgi`.

**See also:** [[web3d-realism]] (the in-browser realism ceiling) · [[web3d-ue-browser]] (the honest tiers table) · [[web3d-sky-sun]] (the sky/IBL this swaps for a node-safe HDRI) · [[web3d-engine-choice]] · [[STATE]].
