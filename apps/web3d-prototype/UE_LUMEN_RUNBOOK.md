# Lumen-class render runbook — `house.glb` on the RTX

**Goal:** a real, photoreal, Lumen-class (UE5-quality) still of the exact same model the
web configurator renders, so you can compare it side-by-side against the three web paths
(WebGPU, WebGL2+GI) and the in-app offline-GI path tracer.

This is the part an autonomous agent **cannot** do for you: these are GUI apps with no
headless still-render CLI for an arbitrary glb. The steps below are the fastest hands-on
path, branched by what's actually installed on this machine.

---

## What this machine has (scouted 2026-06-13, read-only)

| Tool | Status | Path | Verdict for a glb Lumen still |
| --- | --- | --- | --- |
| **Twinmotion 2025.1** (`RELEASE_WINDOWS_2025.1.40019550`) | ✅ installed | `C:\Program Files\Epic Games\Twinmotion2025.1` | **USE THIS.** Native `.glb` import, UE5 Lumen real-time GI + a true Path Tracer, one-click image export. |
| **Lumion 2024 Student** | ✅ installed (standalone `Lumion.exe`) | `C:\Program Files\Lumion 2024 Student\Lumion.exe` | Good fallback. Imports glb/Collada, ray-traced stills — **but the Student edition stamps a watermark** on exports. |
| **Enscape 4.7.0** | ⚠️ plugin-only | `C:\Program Files\Enscape\` (Revit / Rhino / SketchUp host plugins; **no standalone**) | Only usable if you open the model inside Revit/Rhino/SketchUp first. Not ideal for a raw glb. |
| Unreal Engine (standalone) | ❌ not found | — | Would need a full UE5 + Datasmith install (~30+ GB). Skip unless you want it. |
| Blender | ❌ not found | — | Not installed. Cycles fallback unavailable without an install. |
| D5 Render | ❌ not found | — | Not installed. |

**GPU:** NVIDIA GeForce RTX 4070 Laptop GPU (driver 32.0.15.9608) + an AMD Radeon 610M
iGPU. The RTX 4070 supports DXR / Lumen hardware ray tracing and Twinmotion's Path Tracer.

> ⚠️ **Two gotchas before you start the Path Tracer:**
> 1. **VRAM:** Twinmotion's *Path Tracer* requires **≥ 8 GB dedicated VRAM** (any NVIDIA RTX).
>    The scout reported 4 GB for the 4070 Laptop, but that is almost certainly the classic
>    32-bit WMI `AdapterRAM` under-report — check the real figure in **Task Manager →
>    Performance → GPU** or **`dxdiag`**. If it's a true 8 GB 4070 Laptop, the Path Tracer
>    qualifies. **Lumen real-time GI has no 8 GB requirement** and will work either way.
> 2. **dGPU, not iGPU:** make sure Twinmotion/Lumion run on the RTX 4070, not the Radeon
>    610M. Windows → *Settings → System → Display → Graphics* → add the app → set **High
>    performance**, or use the NVIDIA Control Panel. (Lumen/Path Tracer will silently fall
>    back to DX11 / refuse to enable on the iGPU.)

---

## PATH A — Twinmotion 2025.1 (recommended, fastest, no watermark)

Twinmotion *is* Unreal Engine 5 under the hood — its Lumen and Path Tracer are the same
tech as a hand-built UE5 scene, with none of the project setup. Two quality tiers:

- **Lumen (real-time GI)** — interactive, exports in seconds. The honest "UE5/Lumen
  quality" comparison target for the web paths.
- **Path Tracer** — offline, physically-correct GI/reflections. The gold-standard
  reference (takes longer; needs the 8 GB VRAM above).

Render **both** if you can — Lumen is the apples-to-apples "live Lumen" the user asked
about; the Path Tracer is the ground-truth ceiling.

### A1. Launch & import
1. Open Twinmotion (Epic Games Launcher → Library → Twinmotion 2025.1, or run
   `C:\Program Files\Epic Games\Twinmotion2025.1\...\Twinmotion-Win64-Shipping.exe`).
2. **File → Import** (or the **Import** button in the bottom dock) → **Geometry**.
3. Select `apps\web3d-prototype\public\model\house.glb` (the original compressed glb is
   fine — Twinmotion imports glb/meshopt/quantization natively; you do **not** need
   `house_pt.glb`, that copy is only for the web path tracer).
4. In the Import dialog:
   - **Collapse mode → Keep hierarchy.** (Epic explicitly recommends this for Lumen — it
     maximizes surface-cache / mesh-card coverage so GI isn't dark/noisy.)
   - **Unit conversion:** the model is authored in **feet**. If the building comes in at
     the wrong scale, re-import with *Unit conversion* unchecked and a value of `100`, then
     select the container in the Scene graph and scale it to `1%` in the XYZ panel
     (Epic's documented large-scene workflow).
   - Click **Import**. (glb caveat: frosted-glass / sheen shaders convert to a generic
     Twinmotion material — expect to reassign the window glass by hand if it matters.)

### A2. Match the web camera (so the comparison is fair)
The web app's "Rhino view" preset comes from `public/model/camera.json`. To line the
Twinmotion camera up with it, eyeball the web app's **Overview** or **Rhino view** and
orbit Twinmotion to match, or just pick a clean 3/4 exterior. (There's no glb camera
import in Twinmotion; matching is manual.) Save the view: **Media → Create Image** (adds a
camera you can return to).

### A3a. Lumen real-time GI render
1. **Edit → Preferences → Settings tab:** under *Graphic hardware support*, confirm
   **DirectX 12** is selected (required for Lumen). Close Preferences.
2. **Preferences → Quality tab:** set **High** or **Ultra**.
3. Open the **Properties / Ambience** panel → **Render** tab → click **Real time**.
4. Under **Global illumination**, click **Lumen**. The viewport now shows Lumen GI.
5. Tune sun/sky in the Ambience/Lighting dock to match the web app's time-of-day if you
   want parity with a specific SolarSky setting (default app sun is ~13:00, sunny).
6. **Export:** bottom dock **Export → Image** (or the **Image** tab) → pick a **format /
   size** (4000 or 8000 px is fine for Lumen — it's quick) → **Start export** → choose a
   folder. *Save the project first* (export is RAM/GPU heavy).
   Exports are always rendered at **Ultra** regardless of the viewport Quality setting.

### A3b. Path Tracer reference render (the gold standard)
1. Confirm the 8 GB VRAM + DX12 prerequisites above.
2. **Ambience → Render** tab → click **Path tracer** (instead of Real time). The viewport
   begins progressively accumulating samples — let it converge (noise clears over
   seconds-to-minutes depending on the view).
3. *(Optional)* **Preferences → Settings → Path tracer:** set samples-per-pixel / bounces
   for the **High** preset; enable **Multi-GPU** only if you have a second NVIDIA card
   (you don't — single 4070, leave it off). The new **Fireflies** slider (logarithmic in
   2025.1) tames bright speckles.
4. **Export → Image** → choose size (drop to ~2000–4000 px for the Path Tracer; it's much
   slower than Lumen) → **Start export**. The exported still is the physically-correct,
   apples-to-apples reference for the same `house.glb`.

---

## PATH B — Lumion 2024 Student (fallback if Twinmotion won't cooperate)

Standalone, no host app needed. **Caveat: Student edition watermarks every export** — fine
for an internal quality comparison, not for client-facing output.

1. Launch `C:\Program Files\Lumion 2024 Student\Lumion.exe` (force it onto the RTX 4070 —
   see the dGPU gotcha above; Lumion is very GPU-hungry).
2. Start a new scene (e.g. a simple/flat environment so the building reads cleanly).
3. **Import:** Objects mode → **Import** (the folder/“+” import button) → select
   `apps\web3d-prototype\public\model\house.glb` (Lumion imports `.glb`/`.dae`/`.fbx`/`.skp`).
   Place it at the origin; fix scale if needed (model is in **feet**).
4. Set sun/weather to match the web app's lighting (Lumion's sun + sky controls).
5. **Ray tracing:** enable Lumion's **Ray Tracing** effect for accurate GI/reflections
   (Photo mode → Effects → add **Ray Tracing**), or use the high-quality preset.
6. **Render still:** **Photo** mode → compose the shot → **Render Photo** → choose
   resolution (e.g. 1920×1080 or higher) → render to a PNG. Expect the watermark.

---

## PATH C — Enscape 4.7.0 (only via a host CAD app)

Enscape on this machine is **plugin-only** (Revit / Rhino / SketchUp). There is no
standalone Enscape that opens a glb directly. Use this **only** if you already have the
model open in one of those hosts:

1. The project's source is a **Rhino** model (the web glb was exported from Rhino, and the
   repo has Rhino tooling). If you have the original `.3dm`, open it in Rhino, then click
   **Enscape → Start Enscape** (the Enscape Rhino plugin toolbar).
2. Enscape gives real-time GI + ray-traced reflections in its own window.
3. **Export still:** Enscape toolbar → **Screenshot** (or **Export → Image**) → set
   resolution → save.
4. If you only have the `house.glb` (no `.3dm`), Enscape is not the right tool — prefer
   Path A or B. (Importing a glb into Rhino just to host Enscape is possible but slower
   than Twinmotion.)

---

## PATH D — UE5 / Datasmith or Blender Cycles (not installed; do only if you want them)

Neither standalone Unreal Engine nor Blender is installed, so these require a download
first. Listed for completeness:

- **UE5 + Datasmith glTF + Lumen:** install UE5 via the Epic Launcher → enable the
  **Datasmith glTF Importer** plugin → **File → Import** `house.glb` → drop it in a level
  with a Sky/Directional light → in **Project Settings** enable **Lumen** for *Global
  Illumination* and *Reflections* → for the gold-standard still switch the viewport to
  **Path Tracing** (`Show → Path Tracing`, requires DXR) → render with **Movie Render
  Queue** (or High Resolution Screenshot). This is what Twinmotion automates — use raw UE5
  only if you need fine control.
- **Blender Cycles (offline-GI ground truth, renderer-agnostic):** install Blender →
  **File → Import → glTF 2.0** `house.glb` → set the render engine to **Cycles** with GPU
  (OptiX on the RTX 4070) → add a Sun + world HDRI → **F12** to render → **Image → Save
  As**. Cycles is a true unbiased path tracer; a good cross-check against Twinmotion's.

---

## How this ties back to the web app (the comparison you're actually running)

You're comparing four renders of **one** model:

1. **Web — three.js WebGPU** (`renderMode: "webgpu"`, `StageWebGPU`)
2. **Web — WebGL2 + GI** (`renderMode: "webgl2gi"`, `StageWebGL2GI`)
3. **Web — in-app offline-GI path tracer** (the "Path-trace render" button → `rendering=true`
   → `src/PathTracer.tsx`). **This now renders real geometry** — it path-traces a
   dequantized copy of the model (`public/model/house_pt.glb`) instead of only the sky.
   *(Background: the compressed `house.glb` is meshopt + KHR_mesh_quantization; the path
   tracer reads raw CPU vertex data to build its BVH and was intersecting the
   un-dequantized integer positions, so the building vanished and only the IBL/sky
   rendered. `house_pt.glb` is a float32, extension-free copy of the same 581 meshes /
   6543 primitives, produced offline with `gltf-transform dequantize`.)*
4. **Lumen-class reference** — the Twinmotion (or Lumion) still from this runbook.

The web in-app path tracer (#3) is the closest *in-browser* offline-GI reference; the
Twinmotion Path Tracer (#4) is the true ceiling. Render the same camera/lighting across
all four and compare.

### Driving the in-app path tracer (#3) on the RTX — for the main agent
The full visual path-trace needs a real GPU, so run it on the RTX 4070, not in CI:

```bash
cd apps/web3d-prototype
npm install          # if node_modules isn't present
npm run dev          # serves at http://127.0.0.1:5181 (strict port)
```

Then in the browser at `http://127.0.0.1:5181`:
1. Let the model load (orbit to the **Rhino view** or **Overview** preset for parity).
2. Click the **Path-trace render** button (HUD/NavBar) — this flips `rendering=true`,
   mounts `<PathTracer/>`, loads `house_pt.glb`, builds a small BVH over the
   building + paving (~1–2 s), and starts accumulating samples. The sample counter
   (`ptSamples`) ticks up in the HUD.
3. Let it accumulate to a clean image, then screenshot the canvas.

If it ever renders only sky again, re-check that `public/model/house_pt.glb` exists and is
still extension-free (`npx @gltf-transform/cli inspect public/model/house_pt.glb` →
`extensionsRequired: none`). To regenerate it from the source:

```bash
cd apps/web3d-prototype
npx @gltf-transform/cli dequantize public/model/house.glb public/model/house_pt.glb
```
