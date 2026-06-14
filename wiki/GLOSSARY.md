---
type: glossary
updated: 2026-06-14
---

# Glossary

> ⚠️ **Two pivots happened after most of this page was written (2026-05).** The project went **2D diffusion pipeline → plugin-first host ground-truth → engine-first web3d**. The current direction + vocabulary live in [[STATE]]; the **Spikes / B1–B3 / Renderers / Modal** sections below are the **historical 2D-pipeline arc** — still valid as history, and the basis for the future "diffusion hero" add-in, but not the live build. For today's terms jump to **[[GLOSSARY#web3d-terms-current|web3d terms (current)]]** at the bottom. Pivots: [[DECISIONS#web3d-pivot]] · [[DECISIONS#plugin-first-pivot]].

## Spikes

**Spike 1 — rejected.** Text-to-image + click-segmentation. Architect prompts the model, then clicks elements to identify them. Killed because two compounding generative steps fail too often, and architects start from 3D models, not prompts. See [[spikes/spike-1]].

**Spike 2 — done.** Baseline screenshot-to-render fidelity. Nano Banana Pro on a single shaded viewport screenshot. Achieves ~90% macro alignment but produces critical-severity failures (invented windows, corner wraparounds that alter building mass). See [[spikes/spike-2]].

**Spike 2.5 — in progress.** Multi-renderer bake-off to replace or validate the Spike 2 incumbent. Three phases B1 / B2 / B3 (see below). Cap budget across phases. See [[spikes/spike-2.5]].

**Spike 3 — in progress.** VLM region tagging via Gemini 3 Pro structured output → `Region[]`. T17 smoke test passed; gate failed on quality. See [[spikes/spike-3]].

**Spike 4 — scaffolded.** End-to-end edit pipeline: render → tag → segment → apply material → composite. Mock tests green; awaiting live renderer + tagger. See [[spikes/spike-4]].

## B1 / B2 / B3 (phases inside Spike 2.5)

**B1 — Baseline Characterization.** Run Nano Banana Pro on the same screenshot 4× at different seeds (42, 100, 200, 300). Score per-render on silhouette IoU, edge density, manual rubric. Answers: "is the failure deterministic or stochastic?" Budget: $0.12. Code: `spike/run_b1_baseline.py`.

**B2 — Cheap Interventions.** Improve Nano Banana *without changing renderer*. Four variants: (1) `tightened_prompt` — inject geometry-pinning constraints, (2) `higher_res` — resize input to 1920px long edge, (3) `multi_region_annotated` — per-facade region callouts, (4) `multi_pass` — first NB render, Gemini-tag elements, second NB render with derived constraints. Default dry-run. Budget: $0.50. Code: `spike/run_b2_variants.py`.

**B3 — Multi-Renderer Bake-Off.** Compare all eight candidates on one screenshot: Nano Banana Pro (best B2 variant), FLUX Canny Pro, FLUX Kontext Pro, Magnific Mystic, Qwen-Image-Edit, HiDream-E1, Recraft V3 native, Recraft V3 via Replicate. Gate: zero critical failures + ≥7/10 manual photorealism score. Budget: $3–5. Code: `spike/compare_renderers.py`.

**Cascade.** B1 characterizes the problem → B2 tries cheap fixes on incumbent → B3 compares incumbent against challengers → winner used in Spike 4.

## Failure taxonomy

- **Critical** — building mass changed (invented windows, corner wraparound, geometry warp). Disqualifying for production.
- **High** — wrong material on a major surface, lighting impossible for the scene.
- **Medium** — element count off by 1–2, mullion spacing inconsistent.
- **Low** — cosmetic (slight reflection artifact, minor color drift).

## Routes

**Photoshop route** — the *product*. Direct-manipulation canvas: click a region, pick a material, see the re-render. Layer stack, swatch library, undo/redo, non-destructive.

**VLM route** — the *plumbing*. Use a Vision-Language Model (Gemini 3 Pro) to automatically tag every region in the render with semantic labels (wall / window / mullion / door / floor / etc.) so click-to-select can resolve to a real region. Alternative would be color-coded mask passes from the 3D model — rejected because it doesn't generalize across renderers and bakes geometry into the input.

Routes are **sequential**, not competing — see [[STRATEGY]].

## Coordinate spaces

**Input pixel space.** The screenshot's native dimensions, e.g. 1259×848. This is what UI clicks and SAM2 use natively.

**Gemini normalized 0–1000.** Gemini 3 Pro returns bboxes in this space regardless of the input image's resolution. Must be rescaled before drawing or feeding into SAM2. Discovered in T17. See [[references/coordinate-systems]].

**SAM2 prompt space.** Pixel coordinates of the image being segmented. Accepts both point `(x, y)` and bbox `(x, y, w, h)` prompts.

## Renderers

| Class | API / Model | Env | $/call | Notes |
|-------|-------------|-----|--------|-------|
| `NanoBananaProRenderer` | Gemini 2.5 Flash Image via Modal | `GOOGLE_API_KEY` | $0.039 | Spike 2 incumbent. |
| `FluxCannyProRenderer` | BFL FLUX Pro 1.1 Canny | `BFL_API_KEY` | $0.05 | Server-side Canny conditioning — geometry-preserving. |
| `FluxKontextProRenderer` | BFL FLUX Kontext | `BFL_API_KEY` | $0.05 | Instruction-edit variant. |
| `MagnificMysticRenderer` | Magnific Mystic / Relight | `MAGNIFIC_API_KEY` | $0.10 | Highest cost; strong arch-viz prior. |
| `RecraftV3Renderer` | Recraft V3 native | `RECRAFT_API_TOKEN` | $0.04 | — |
| `RecraftV3ReplicateRenderer` | Recraft V3 via Replicate | `REPLICATE_API_TOKEN` | $0.04 | — |
| `QwenImageEditRenderer` | Qwen-Image-Edit (Replicate) | `REPLICATE_API_TOKEN` | $0.03 | Strong layout preservation. |
| `HiDreamE1Renderer` | HiDream-E1 (Replicate) | `REPLICATE_API_TOKEN` | $0.04 | Geometry-friendly. |

Full provider docs: [PROVIDERS.md](../spike/PROVIDERS.md).

## Modal functions

Defined in `spike/modal_app.py`:

- `render_from_model_view()` — Gemini 2.0/2.5 Flash Image render of the screenshot.
- `tag_regions(screenshot_bytes, render_bytes)` — Gemini 3 Pro region tagging, returns raw JSON (validated by `spike/schemas.py:TagRegionsResponse` locally).
- `segment(image_bytes, prompt)` — SAM2; `prompt` is either `{"type":"point","x":..,"y":..}` or `{"type":"bbox","x":..,"y":..,"w":..,"h":..}`.
- `apply_material(base_bytes, mask_bytes, swatch_bytes)` — SD Inpainting v1.5 with material conditioning.

## Cost rules

**$0.05/session cap.** Read `spike/REPORTS/cost_ledger.md` before any live call. If the call would push over $0.05, stop and ask.

**Dry-run defaults.** Every driver script (`compare_renderers.py`, `run_b2_variants.py`, `test_vlm_tagging.py`, `end_to_end_edit.py`) is dry-run by default. `--live` is opt-in. Env-gated keys raise clean `RuntimeError` when missing — that's intended behavior, not a bug.

---

## web3d terms (current)       {#web3d-terms-current}

The vocabulary of the live engine-first build (`apps/web3d-prototype/`). Snapshot: [[STATE]].

**web3d-prototype / engine-first.** The current app: export real geometry + semantic IDs from Rhino → glTF, render live in three.js / R3F at $0/client-side. "Engine-first" = real 3D (geometry fidelity + multi-view consistency are *exact*), as opposed to the 2D diffusion pipeline above. Spark: [[research/arcway-teardown]]; rationale: [[DECISIONS#web3d-pivot]].

**renderMode + the three tiers.** A store toggle that mounts one of three self-contained **Stage** components, each owning its own `<Canvas>` + renderer + post, all rendering the shared `<Scene>`:
- **WebGL2** — N8AO + AgX + glass + VSM shadows (the baseline).
- **WebGL2 + GI** — adds RectAreaLight (LTC) area lights + `MeshReflectorMaterial` reflective ground + stronger AO.
- **WebGPU** — three.js `WebGPURenderer` + TSL **SSGI/GTAO/TRAA/Bloom** + node-safe HDRI IBL + real VSM cast shadows (the in-browser ceiling). [[research/web3d-webgpu]] · tiers rationale [[DECISIONS#web3d-realism-tiers]].

**Semantic element IDs.** Per-mesh `node.extras = {semantic, guid, layer}` (12 classes: wall/window/roof/door/…) injected into the glTF host-side, so "click an element → swap its material" resolves to a real class. Pipeline: [[research/web3d-rhino-gltf]].

**Box-projected world-space (feet) UVs.** Texture coords projected in real-world feet so material scale is metric-consistent on any surface (no per-mesh UV unwrap). Underpins the NEXT "scale-aware material library" track.

**Render-tech glossary.** **N8AO** = screen-space ambient occlusion (WebGL2). **AgX** = tone-mapping operator (handles window blowout better than ACES). **SSGI/GTAO/TRAA** = screen-space global illumination / ground-truth AO / temporal AA (WebGPU-only TSL nodes). **VSM** = variance shadow maps (the soft sun shadows; replaced the r184-broken drei `<SoftShadows>`). **IBL / HDRI / PMREM** = image-based lighting from an equirect HDRI, pre-filtered for roughness. **LTC RectAreaLight** = analytic area lights (sky-fill, window emitters). **Transmission glass** = one shared `MeshPhysicalMaterial`. Ceiling analysis: [[research/web3d-realism]].

**suncalc sun.** Real solar position from lat/long/date/time drives both the directional light and the sky → real shadow studies. [[research/web3d-sky-sun]].

**Entourage.** Placed trees/bushes/people (currently procedural placeholders; NEXT track = real CC0 assets + impostors + cutout people). [[research/web3d-entourage]].

**Geo-context.** Google Photorealistic 3D Tiles (P3DT) georeferenced around the model via `3d-tiles-renderer`. [[research/web3d-geo-context]] · [[DECISIONS#web3d-geo-context]].

**Diffusion hero.** The demoted 2D pipeline's future role: a last-10% photoreal/atmosphere pass on a viewport grab — with the hallucination/consistency fix = condition on the render's own **depth + canny** edges ([[DECISIONS#render-mask-registration]]) + single-still scope. [[DECISIONS#client-ready-render]].

**Gaussian splatting.** Candidate for generating a photoreal *environment* around the editable polygon building (a NEXT open question; bakes materials, so a "publish" export not the editor).

**Lumen reference / Cinematic (UE5).** The realism ceiling: **Twinmotion** (real Lumen, runbook-driven on the RTX) + an in-app **Cinematic** toggle that embeds a SimplyStream client-side-UE5 build. Why these are terminal, not the editor: [[research/web3d-ue-browser]].

**KTX2 / Basis.** GPU-compressed textures (NEXT material-library track — VRAM + grazing-angle sharpness).
