---
type: research
topic: web 3D engine choice (three.js vs Babylon vs PlayCanvas)
agent: "Sonnet research agent (planning phase, 2026-06-13)"
---

# Engine choice for the web3d configurator

> Sonnet web-research agent. Decision: **three.js + React Three Fiber (R3F) + drei**.

## Why three.js / R3F
- Non-destructive region→material **layers map cleanly to React/Zustand state** (a `Map<semantic,swatchId>`); idiomatic in R3F, awkward in imperative engines.
- glTF + KHR extension coverage is near-complete built-in (r170+): Draco, meshopt, KHR_materials_* (clearcoat/transmission/volume/iridescence/anisotropy/ior/specular), KTX2/basisu, mesh quantization, EXT_mesh_gpu_instancing. Gaps (`sheen`, `materials_variants`) covered by `three-gltf-extensions`.
- **WebGPU is baseline (2026)** and zero-config in three r171+ (`three/webgpu`, auto WebGL2 fallback). Orbit + walk = drei `<OrbitControls>` / `<PointerLockControls>`. Huge ecosystem (drei, @react-three/postprocessing, leva, r3f-perf).

## When to pick the others
- **Babylon.js 9** — if you need `KHR_materials_variants`/`sheen` natively, Babylon 9 IBLShadows, Node Material Editor, mature WebXR, or your team is Unity/Unreal-native (not React).
- **PlayCanvas** — best mobile frame-rate + visual cloud editor + strongest *product* configurator portfolio (Polaris/Airstream), but weakest code-first/React story. Not for an archviz, version-controlled, React app.

## MVP stack we adopted
`three` 0.184, `@react-three/fiber` 9, `@react-three/drei` 10, `@react-three/postprocessing`, `three-mesh-bvh`, `zustand`, Vite. **WebGL2 target** for now (three-gpu-pathtracer is WebGL2-only; WebGPU postproc bridge still rough mid-2026). Gotchas: dedupe react in Vite (`resolve.dedupe`) or R3F throws "Invalid hook call"; IBL not optional; serve Draco/KTX2/meshopt WASM as static.

Sources: [three.js vs Babylon vs PlayCanvas 2026 (Utsubo)](https://www.utsubo.com/blog/threejs-vs-babylonjs-vs-playcanvas-comparison) · [WebGPU baseline 2026](https://vr.org/articles/webgpu-baseline-2026-three-js-webxr-default) · [Babylon 9.0](https://blogs.windows.com/windowsdeveloper/2026/03/26/announcing-babylon-js-9-0/).

> **Since-built (2026-06-14):** the WebGPU path this doc deferred ("postproc bridge still rough, target WebGL2 for now") is now a working render mode (SSGI/GTAO/TRAA + node-safe HDRI IBL + VSM) — see [[web3d-webgpu]] and [[STATE]]. The MVP stack ([[STATE]]) settled on `three` 0.184.

**See also:** [[web3d-rhino-gltf]] · [[web3d-realism]] · [[web3d-webgpu]] · [[STATE]].
