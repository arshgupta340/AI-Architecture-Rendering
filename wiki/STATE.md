---
type: state
updated: 2026-06-13
---

# Current State

> Snapshot, not a log. Overwrite at session end. Log is [[SESSIONS]]; rationale is [[DECISIONS]].

## Direction (NEW, 2026-06-13)

**Web-native 3D-consistent rendering tool.** Pivoted from the 2D diffusion canvas to an **engine-first** approach: export real geometry + semantic IDs from Rhino → glTF, render it live in **three.js / React-Three-Fiber**, and configure materials / sun / entourage directly in 3D. Geometry fidelity and multi-view consistency are *exact and free* (it's real 3D), which is precisely what the diffusion path struggled with. Spark + rationale: [[research/arcway-teardown]] (Arcway = Unreal pixel-streamed; our edge is we already have Rhino geometry + semantics) and [[DECISIONS#web3d-pivot]].

**The 2D pipeline (FLUX.2 + semantic masking, `apps/canvas-prototype/`) is reframed as a future ADD-IN** — a "diffusion hero" pass on a 3D viewport grab (sky/entourage/mood/photoreal), not the core. Its reports/ladder (E1–E6, multiview) remain valid and are the basis for that add-in.

## The web3d app — `apps/web3d-prototype/` (Vite + React + R3F, $0/client-side)

Run: `npm install --prefix apps/web3d-prototype` then `npm --prefix apps/web3d-prototype run dev` → http://localhost:5181 (launch.json name `web3d`; port 5181).

**Working & verified (preview):**
- Loads the meshopt-compressed semantic `house.glb` (6.5 MB), 12 element classes, auto-framed.
- Click element → swap **real PBR material** (ambientCG CC0); brick lands on walls only.
- **Box-projected world-space UVs (feet)** → metric-consistent texture scale + **live per-material "Texture scale" slider** (persisted).
- Non-destructive **layer stack** (toggle / remove / replace-not-stack) + localStorage persistence.
- **Walk + Orbit** modes; **saved views** (Overview, Rhino view, user "+ Save").
- **Sky & Sun left panel** (`SkyPanel`/`SolarSky`): real solar position via `suncalc` from lat/long + date/time; mood presets (sunny/overcast/golden/dusk/night), time-of-day slider, equinox/solstice date presets, sun intensity, cloud cover.
- **Entourage**: Tree/Bush/Person, click-to-place, `InstancedMesh` + billboard, **real-ft height sliders** (tree 3–30, bush 0.5–5, person 5–6), persisted.
- **Geo-context (NEW, 2026-06-13)**: `SkyPanel` "Real-world context" → paste a Google Maps key (or `.env.local` `VITE_GOOGLE_MAPS_API_KEY`) → **Google Photorealistic 3D Tiles** load around the model (`src/GeoTiles.tsx`, `3d-tiles-renderer` + `ReorientationPlugin` + Draco). Tiles recenter to the site lat/lng (shared with the sun) at the local origin, scaled m→ft, seated under the building; **elevation / Seat / North-heading / hide-Rhino-site** controls. `$0` until a key is entered; `enabled` not persisted (won't auto-bill on reload). **UI + mount path verified in preview without a key (auth request fires, bad key degrades gracefully); actual tile imagery + georeference fidelity pending the user's valid key.** [[research/web3d-geo-context]] · [[DECISIONS#web3d-geo-context]]

- **Realism pass (NEW, 2026-06-13)**: post-processing stack (`src/Effects.tsx` — **N8AO** ambient occlusion + tamed **Bloom** + **AgX ToneMapping** + grade/vignette/SMAA; renderer is `NoToneMapping`, the AgX *effect* owns tone mapping), **real transmission glass** on windows (one shared `MeshPhysicalMaterial`), **VSM soft shadows** (`shadows="variance"`), **256px IBL** that re-bakes with time-of-day, texture anisotropy 16. All verified in preview. This is the **tier-1 WebGL2** realism floor; the photoreal hero is the WebGPU / UE tiers. [[research/web3d-realism]] · [[DECISIONS#web3d-realism-tiers]]
- **Cinematic (UE5) toggle (NEW, 2026-06-13)**: `src/Cinematic.tsx` + a NavBar button + store `cinematic`/`cinematicUrl`. Toggles a full-screen overlay that **embeds a SimplyStream-hosted UE5 WebGPU build** of the model in an `<iframe>`, deep-linked with the current materials + sun; setup card (with runbook) when no URL, + Open-in-tab / Change-build / Exit. **Verified embedding works** (SimplyStream allows framing; `garage.cjponyparts.com` streamed to 100% in-app). Needs the **user's own UE build** (Unreal + SimplyStream account) to show the house; UE render needs a real WebGPU GPU. [[research/web3d-ue-browser]] · [[DECISIONS#web3d-realism-tiers]]

**Known-broken / deferred:**
- **drei `<SoftShadows>` (PCSS) is incompatible with three r0.184** — it emits `unpackRGBAToDepth`, removed in r184 → shader won't compile → every MeshStandardMaterial fails → washout. Soft shadows now use **VSM** (`shadows="variance"`). Don't re-add `<SoftShadows>` (or untested `<ContactShadows>`/`<AccumulativeShadows>`) without checking r184 shader compat.
- **Path-trace hero render** runs (builds building-only BVH ~1.2 s, accumulates) but shows only sky — `three-gpu-pathtracer` is incompatible with our **meshopt/KHR_mesh_quantization** geometry (BVH builds, ray intersection misses). Fix = path-trace an *uncompressed* model copy, OR switch the hero to the **diffusion** pass / UE-toggle. See [[research/web3d-realism]].
- Harmless pre-existing console noise: 3d-tiles `'content'` + "Invalid hook call" (geo r3f), stale SoftShadows shader errors, PointerLock-in-iframe — non-fatal; the *render* is the reliable signal (the preview CDP buffer doesn't flush on `console.clear()`).

## Pipeline (Rhino → web), all `$0`

```
Rhino 8 (live MCP)
  → spike/rhino_export_gltf.py     name objects {semantic}__i (non-destructive) → FileGltf.Write → house_raw.glb + semantics.json + camera.json
  → spike/gltf_postprocess.py      pure-python GLB rewrite: node.extras semantics (581/581 tagged)
  → gltf-transform meshopt          14.5 MB → 6.5 MB, semantics preserved
  → apps/web3d-prototype/public/model/house.glb
PBR swatches:  spike/ingest_pbr_swatches.py  (ambientCG CC0 → public/materials/)
HDRI:          spike/ingest_hdri.py           (Poly Haven → public/hdri/, now superseded by procedural Sky)
```

## Roadmap (the "real arch-viz tool" pillars)
1. **Entourage** ✅ built (procedural placeholders; real Quaternius/Kenney glTF + MrCutout people = drop-in). [[research/web3d-entourage]]
2. **Sky/sun/time-of-day** ✅ built. Next: PMREM env-from-sky, sun-path arc, real volumetric clouds. [[research/web3d-sky-sun]]
3. **Geo-context from coordinates** ✅ built (`src/GeoTiles.tsx`): Google Photorealistic 3D Tiles via `3d-tiles-renderer` + `ReorientationPlugin`, georeferenced (tiles→local feet) around the model. **Needs the user's Google Maps key to validate live**; then auto-snap to terrain + auto true-north are the polish. [[research/web3d-geo-context]] · [[DECISIONS#web3d-geo-context]]
4. **Diffusion hero add-in** — wire FLUX.2 (from `apps/canvas-prototype`) onto a viewport grab. Not built; recommended over the path tracer.
5. **Realism** — ✅ tier-1 WebGL2 pass done (post-processing AO/bloom/AgX, real glass, VSM soft shadows, 256 IBL, anisotropy). Next: ground/reflective-floor + detail-map anti-tiling + real PBR library; then the two ceilings — **(a)** WebGPU three.js staged spike (SSGI/GTAO/TRAA), **(b)** a "Cinematic (UE5)" toggle via SimplyStream (client-side UE5 — *evaluate*, not bet). [[research/web3d-realism]] · [[research/web3d-ue-browser]] · [[DECISIONS#web3d-realism-tiers]]

## Research (this arc)
[[research/arcway-teardown]] · [[research/web3d-engine-choice]] · [[research/web3d-rhino-gltf]] · [[research/web3d-realism]] · [[research/web3d-entourage]] · [[research/web3d-sky-sun]] · [[research/web3d-geo-context]] · [[research/web3d-ue-browser]]

## Cost ledger
web3d arc = **$0 API** (local geometry + client render). ambientCG/PolyHaven/Quaternius = CC0. Prior diffusion spend ≈ $2.22 of $50 (unchanged). pip unblocked (removed the `pip install` deny in `.claude/settings.local.json`). **Geo-context is $0 to build/run until a key is entered; once keyed, Google Photorealistic 3D Tiles bill on the *user's* Google PAYG (~$6/1k sessions + $0.20/1k tile requests), not the Anthropic budget.**

## Handoff
A fresh-chat continuation prompt + detailed breakdown is in [[../docs/HANDOFF-web3d.md]].
