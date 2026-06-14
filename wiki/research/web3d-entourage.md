---
type: research
topic: entourage / asset placement for the web3d tool
agent: "Sonnet research agent (V3 phase, 2026-06-13)"
---

# Entourage for three.js / R3F arch-viz

> Sonnet web-research agent. Question: how to add trees / people / cars / props to the web3d configurator. Verbatim-faithful synthesis of the agent's findings.

## Asset sources (CC0 unless noted)
- **Trees / vegetation:** Quaternius **Stylized Nature MegaKit** & **Ultimate Nature Pack** (CC0, glTF, via [poly.pizza](https://poly.pizza)); Poly Haven models (CC0, photoreal, fewer trees); Kenney Nature/City kits (CC0, low-poly streetscape props).
- **People:** **2D alpha billboard cutouts are the arch-viz standard** — [MrCutout.com](https://www.mrcutout.com/people-cutouts) (free personal+commercial, diverse, professionally lit PNG-with-alpha), TonyTextures. 3D figures (Quaternius Background Posed Humans) only if you need them rigged.
- **Cars:** Quaternius Cars Pack / Downtown City MegaKit (300+ urban pieces incl. vehicles); Kenney Car Kit.
- **Props:** Kenney City Kit (benches, lamps, signs); ToxSam/Polygonal-Mind ~991 CC0 GLBs.
- **Skip:** Khronos glTF-Sample-Assets (demo helmets, not entourage). Sketchfab CC0 is inconsistently tagged. Commercial photoreal: Maxtree/Laubwerk ($100–400/pack, FBX→Blender conversion needed).

## Rendering approach
- **Trees:** two-tier. Tier 1 (<50 m): full 3D via **`InstancedMesh`** (1 draw call for 1000 trees). Tier 2 (distance): **octahedral impostors** ([three.ez InstancedMesh2](https://github.com/agargaro/instanced-mesh) renders 200k trees @60fps). For an arch context scene (20–100 trees) Tier 1 alone is fine. Do NOT use drei `<Instances>` for >1k items (React-reconciler overhead).
- **People:** drei `<Billboard lockX lockZ>` + plane + `MeshBasicMaterial({map, transparent, alphaTest:0.1})`. For walkthroughs, an 8-angle spritesheet gives pseudo-3D.
- **Cars/props:** `InstancedMesh` per variant; `BatchedMesh` (three r156+) for varied geometry sharing one atlas material.

## Placement UX
Ghost-preview + **click-to-place** (raycast ground, commit instance, command-stack undo) + **scatter-paint** (brush mode: on mousemove-held, raycast + min-spacing check + add). Validity feedback (green/red ghost). Store entourage as a flat `{type,pos,rot,scale}[]` in state; diff → `setMatrixAt`.

## Performance
~15–20 draw calls for a full streetscape. `InstancedMesh` per species, `BatchedMesh` for props, atlas all people into one 4096² texture, octahedral impostors for distant fill, `frustumCulled` via InstancedMesh2 BVH. `meshoptimizer` for LOD simplification.

## What we built (MVP)
Procedural low-poly **Tree / Bush / Person** (`src/Entourage.tsx`): instanced trunk+foliage & bush, canvas-silhouette billboard person; click-to-place; **real-ft height sliders** (tree 3–30, bush 0.5–5, person 5–6) via `entHeight` in the store + `BASE_HEIGHT`. Real Quaternius/Kenney GLBs + MrCutout PNGs are a drop-in behind the same instanced renderer.

## Key libs (June 2026)
`three` r176+, `@react-three/fiber` v9, `@react-three/drei` (Billboard), `@three.ez/instanced-mesh` (InstancedMesh2 + BVH culling + LOD), `three-mesh-bvh` v0.9+, `meshoptimizer` v0.23.

**See also:** [[STATE]] (the NEXT-step "real entourage" track — replace the procedural placeholders with these assets) · [[web3d-realism]] · [[../docs/HANDOFF-web3d.md]] §Next-steps.
