---
type: research
topic: Rhino → glTF export preserving semantics
agent: "Sonnet research agent (planning phase, 2026-06-13)"
---

# Rhino → semantic glTF pipeline

> Sonnet web-research agent. This is the pipeline we built (`spike/rhino_export_gltf.py` + `spike/gltf_postprocess.py`).

## The pipeline
1. **Name objects in Rhino** `"{semanticClass}__{i}"` — object **Name → glTF node.name** is the only identity channel Rhino's native exporter reliably preserves (no UserStrings/GUID export). Do it non-destructively (save/restore Names in a `finally`).
2. **Mesh + export** via Rhino 8 `Rhino.FileIO.FileGltf.Write(path, doc, FileGltfWriteOptions)`. Key options: `MapZToY=True` (Rhino Z-up → glTF Y-up, −90° about X), `ExportLayers=True` (layer hierarchy as parent nodes — our **window-block fallback** rides on this), `ExportOpenMeshes=True`, `CullBackfaces=False`, `ExportVertexNormals=True`, `ExportMaterials=False` (we assign our own PBR; dodges non-PBR crash RH-81003). The generator **skips invisible meshes** (`if(c.visible)`).
3. **Inject semantics host-side** — pure-Python GLB rewrite (no pygltflib needed) sets `node.extras = {semantic, guid, layer}` on every mesh node. **Put extras on the NODE, never `mesh.extras`** (three.js GLTFLoader bug #15728 overwrites mesh extras). Resolve unnamed block-flattened nodes (windows) via their ancestor layer node + the CSI ruleset.
4. **Optimize** with `gltf-transform meshopt` (or `gltfpack -cc -ke -kn`) — `-ke`/`-kn` non-negotiable (keep extras + node names). meshopt-only avoids mesh merging that would drop extras.

## Pitfalls
- Units: Rhino feet/mm → glTF "meters". We kept feet throughout (IBL has no distance falloff) — note this for geo-referencing later.
- **Block instances flatten** (no native EXT_mesh_gpu_instancing) → file bloat + they lose their object Name (recovered via layer fallback).
- GLTFLoader puts node.extras on a **Group** when a node has >1 primitive (multi-face Breps like walls) → the leaf Mesh lacks it; resolve semantic by walking up ancestors (`semOf`).
- **KHR_mesh_quantization (from meshopt) breaks `three-gpu-pathtracer`** — BVH builds but ray intersection misses quantized meshes. Path-trace from an uncompressed copy if needed.

## Result
326 objects → `house.glb`, **581/581 mesh nodes tagged**, all 12 semantic classes, 14.5 MB → 6.5 MB meshopt (semantics preserved). Brep→render-mesh via `Mesh.CreateFromBrep` + `MeshingParameters` (we relied on FileGltf's internal meshing).

Sources: [FileGltfWriteOptions API](https://developer.rhino3d.com/api/rhinocommon/rhino.fileio.filegltfwriteoptions) · [GLTFLoader extras bug #15728](https://github.com/mrdoob/three.js/issues/15728) · [gltfpack](https://meshoptimizer.org/gltf/) · [gltf-transform](https://gltf-transform.dev/).
