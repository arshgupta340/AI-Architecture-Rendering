# Host Integration — Native Data Extraction Research

> Research date: 2026-06-11 (Sonnet agent, web research). Feeds the plugin-first pivot ([master plan v2](../master-plan.md)). Question answered: *what can a plugin extract from each 3D host, and does it make the screenshot pipeline obsolete?*

## Bottom line

| Host | Verdict |
|---|---|
| **Revit** | Screenshots largely obsolete. Native BIM categories (incl. `OST_CurtainWallMullions`), clean per-element ID masks. No depth API. |
| **Rhino** | Screenshots largely obsolete with ~2 weeks of plugin work. True depth + ID masks + full material R/W. Semantics depend on layer discipline. |
| **SketchUp** | Partial. Pixel-perfect ID masks feasible (~2–3 days, material-swap trick); **no depth buffer exists at all**. |
| **Forma** | Screenshot tier only. No viewport capture API, coarse semantics. |
| **Web / no-plugin users** | Screenshot tier remains necessary — it is the universal entry path and demo surface. |

The plugin export bundle (target contract for tier 1):

```
beauty.png    — shaded viewport capture
id_mask.png   — per-object flat color, AA off, transparency forced to 0
depth.png     — true z-buffer where available (Rhino), 16-bit grayscale
objects.json  — { id → layer/category, material, name, color }
camera.json   — eye/target/up, FOV/frustum (for reprojection & multi-view)
```

## Capability matrix

| Capability | Rhino | SketchUp | Revit | Forma |
|---|---|---|---|---|
| Object-ID pixel mask | Yes — DisplayConduit workaround | Yes — material-swap, slow, mutates state | Yes — SetElementOverrides + ExportImage, clean | No |
| Depth buffer | **Yes — `ZBufferCapture`** (non-linear, viewport-res-capped) | No (hard blocker) | No | No |
| Normal buffer | No (synthesizable from meshes) | No | No | No |
| Semantic labels | Layer names (convention-dependent) | Tags/components (convention-dependent) | **Native BIM categories** (no discipline needed) | building/terrain/road/vegetation only |
| Material read | Full (`GetRenderMaterial`, PBR) | `face.material` (+ texture path) | `GetMaterialIds`, face-level | Vertex colors only |
| Material write | Full (`ModifyRenderMaterial`) | `face.material=` | `doc.Paint(element, face, material)` | Vertex colors |
| Camera intrinsics+extrinsics | Full (`RhinoViewport`, `GetFrustum`) | Full (`camera.eye/target/up/fov`) | Partial (orientation yes; FOV derived from CropBox) | No |
| Off-screen capture | Yes (`CaptureToBitmap` custom size) | No (model must be open/foreground) | Yes (`ExportImage`, headless-capable) | N/A |

## Per-host implementation notes

### Rhino (RhinoCommon, C#/Python — FIRST TARGET)

- **ID masks:** no direct C# per-object color override; the documented workaround is a `DisplayConduit` that suppresses default drawing (hook `ObjectCulling`), then redraws each object with `DrawBrepShaded`/`DrawMeshShaded` using a unique flat `DisplayMaterial` (set diffuse+specular+ambient+emission to the same RGB). Alternative: generate a custom display-mode INI at runtime, import, capture, clean up ("dumb but works" — McNeel forum). Never use `CommitChanges()`-based attribute edits for capture (permanently mutates the doc).
- **Depth:** `Rhino.Display.ZBufferCapture` — `ZValueAt`, `WorldPointAt`, `GrayscaleDib()`. Values are perspective-divided and scaled to the visible range per capture → linearize via near/far + camera matrix before use as ControlNet conditioning; two captures from different cameras are not directly comparable. Resolution capped at viewport size (temporarily resize `view.Size` for higher res; causes flicker).
- **Known risk:** Rhino 8 regressions in `DrawMeshShaded` inside conduits (McNeel discourse #168931).
- **Effort:** ~2 weeks for a full .rhp plugin (capture pipeline 1 wk; HTTP POST + robustness + installer 1 wk). **Grasshopper component fast path: 3–5 days.** The connected Rhino MCP (`run_python`/`run_csharp`) allows a zero-install probe first (experiment E1).

### Revit (C#/.NET add-in — SECOND TARGET)

- **ID masks:** per element, in a transaction: `view.SetElementOverrides(id, ogs)` with solid surface fill pattern + unique RGB + transparency 0, then `doc.ExportImage(...)` (overrides are honored), then roll back. Per-category coloring gives a semantic map; per-instance coloring gives instance masks.
- **Semantics:** the prize. `BuiltInCategory`: `OST_Walls`, `OST_Windows`, `OST_CurtainWallMullions`, `OST_Doors`, `OST_Floors`, `OST_Ceilings`, `OST_Planting`, `OST_Entourage` — ground truth for exactly the labels our VLM pipeline kept getting wrong.
- **Depth:** not accessible (DirectContext3D shares but doesn't expose the buffer). Options: monocular estimation from the beauty pass, or raytrace from exported geometry.
- **Gotchas:** override behavior differs between Revit 2023/2024 — test per version; color overrides only affect edges unless a solid fill pattern is set; AA can't be disabled (use high `ImageResolution`); linked models need separate override calls.

### SketchUp (Ruby — THIRD TARGET)

- **ID masks:** `DisplayColorByLayer` rendering option is unreliable at runtime; the working approach is save → assign unique `Sketchup::Color` per face → `view.write_image(file, w, h, false)` (AA off, up to 16k px) → restore. Wrap in an operation for undo-safety. Handle nested-component material inheritance.
- **Depth:** none. No GL/framebuffer access in Ruby or C SDK. Fallbacks: monocular depth estimation, or export glTF and render depth offline.

### Forma

- Embedded View SDK gives geometry-by-category (triangles) for analysis but no viewport capture, no depth, no per-element masks. **Screenshot tier only** — consistent with how Veras handles Forma.

## Cross-host gotchas

1. **Anti-aliasing destroys thin structures** (mullions are 2–5 px at 1024). Disable AA wherever possible; in Revit compensate with resolution.
2. **Transparent glazing** shows what's behind it in ID masks — force transparency to 0 during capture, restore after.
3. **Entourage**: Revit RPC objects are billboards; SketchUp Warehouse components carry no semantic type; Rhino blocks have none either. Entourage labeling may still need a (cheap) VLM pass on the object *list*, not the pixels.
4. **Nested blocks/components** require recursive traversal in Rhino and SketchUp.

## Prior art

- **Veras (Chaos/EvolveLAB):** screenshot-level only — captures the viewport and sends to cloud diffusion. The "geometry override" slider is a ControlNet weight, not geometry extraction. Supports 7 hosts. → Our plugin-extraction approach is differentiated, not catch-up.
- **D5 Render:** closest prior art — LiveSync sends real geometry+materials to its engine, which exports Z-depth/Material-ID/sky-mask passes. But Material ID is per-*material* (not per-element), and it requires D5 as an intermediary renderer.
- **Research validation:** FrameDiffuser (arXiv 2512.16670), G-buffer diffusion (2503.15147), DiffusionRenderer (2501.18590) — G-buffer-conditioned diffusion is established. **No shipped arch-viz product does it from a BIM host as of June 2026.**

## Sources

Key references (full list in research transcript): McNeel discourse #163495 (semantic segmentation capture in .NET), #71380 (ZBufferCapture usage), #168931 (Rhino 8 conduit regression); developer.rhino3d.com RhinoCommon API (ZBufferCapture, RhinoViewport, DisplayConduit); ruby.sketchup.com (View#write_image, Face, Camera); learnrevitapi.com (override graphics); Autodesk forums (override behavior 2023→2024, focal-length derivation); aps.autodesk.com Forma SDK; d5render.com + forum (render passes); arXiv 2512.16670, 2503.15147, 2501.18590.
