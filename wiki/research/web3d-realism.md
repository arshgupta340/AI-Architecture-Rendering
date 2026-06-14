---
type: research
topic: in-browser PBR realism + hero render + WebGPU
agent: "Sonnet research agent (planning phase, 2026-06-13)"
---

# In-browser realism ceiling vs Enscape/D5/Lumion

> Sonnet web-research agent.

## Bang-for-buck stack (ranked)
1. **HDRI + PMREM** image-based lighting (highest impact, ~free).
2. **PBR** `MeshPhysicalMaterial` (albedo/normal/roughness/metalness/AO/transmission/clearcoat) + KTX2/Basis + anisotropy.
3. **AgX tone mapping** (`THREE.AgXToneMapping`) — handles window blowout far better than ACES.
4. **Baked lightmaps** (Blender Cycles GI → UV2 lightMap) — best GI you'll get on web, zero runtime cost, but static.
5. **GTAO** (`GTAONode`, WebGPU) over old SSAO.
6. **SSGI** (`SSGINode`, three r171+, WebGPU, ~30–40% frame budget) for runtime indirect bounce.
7. **CSM + PCSS** soft sun shadows; **RectAreaLight (LTC)** for windows; **TAA + bloom + DoF**; **SSR** for floors; **transmission+IOR** glass.

## Honest ceiling
Will look worse than Enscape/D5: multi-bounce diffuse GI, sharp off-screen reflections, caustics, denoised path-traced softness. Mitigate with baked lightmaps + SSGI-fills-the-delta + cubemap probes. Ceiling ≈ Enscape **real-time** (non-path-traced) mode for exteriors.

## Hero still
- **`three-gpu-pathtracer`** (WebGL2-only): same scene/materials, progressive GGX path trace; 256 SPP ≈ Cycles on simple scenes, 30–90 s on mid dGPU. Limits: no InstancedMesh, **KHR_mesh_quantization incompatible** (our compressed GLB), emissive skips MIS.
- **Diffusion hero** (FLUX.2 Edit on a viewport grab): ~5 s, "imagined" materials/lighting, can add entourage/sky/mood. **Recommended hero for this tool** (geometry-accurate path-trace as the $0 fallback on an uncompressed model).

## WebGPU vs WebGL2 (2026)
WebGPU is "baseline" (~95% coverage, auto WebGL2 fallback via `three/webgpu`). Unlocks SSGINode/GTAONode/TRAA/compute + 10× lower draw-call overhead. **But** target **WebGL2** for the MVP: three-gpu-pathtracer is WebGL2-only and the @react-three/postprocessing WebGPU bridge is still rough.

Sources: [SSGINode docs](https://threejs.org/docs/pages/SSGINode.html) · [three-gpu-pathtracer](https://github.com/gkjohnson/three-gpu-pathtracer) · [Deferred Path Tracing by Enscape (AMD)](https://gpuopen.com/learn/deferred-path-tracing-enscape/) · [lightmap baking in Blender](https://www.pixel-capture.com/tutorials/lightmap-baking-in-blender).

> **Since-built (2026-06-14):** the WebGPU path this doc called "still rough, target WebGL2 for the MVP" is now a working render mode (SSGI/GTAO/TRAA + node-safe HDRI IBL + VSM cast shadows) — [[web3d-webgpu]], [[STATE]]. The `three-gpu-pathtracer` hero is still deferred (the KHR_mesh_quantization incompatibility above + a material-color crash, [[web3d-rhino-gltf]]); the **diffusion hero** is the recommended route, with the hallucination/consistency fix = condition on the render's own depth + canny edges ([[DECISIONS#render-mask-registration]]).

**See also:** [[web3d-webgpu]] · [[web3d-ue-browser]] · [[web3d-rhino-gltf]] · [[web3d-entourage]] · [[STATE]].
