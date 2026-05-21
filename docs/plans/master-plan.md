# Plan: "Photoshop-for-Architects" AI Rendering Engine

> Migrated from `~/.claude/plans/i-am-thinking-of-jolly-squirrel.md` on 2026-05-19. This is the master plan of record; the original is kept as a personal backup.

## Context

Every AI architecture-rendering tool today (Veras, LookX, ArkoAI, Visoid, PromeAI, Krea, Magnific, and even Photoshop's Generative Fill) ultimately reduces to **"mask a region + type a prompt + re-render."** Even when they wrap Nano Banana 2 (Veras already does), the editing UX is still prose-driven. Architects don't think in prompts — they think *"that wall, in travertine."*

The unfilled niche: a canvas where the AI is invisible plumbing behind **direct-manipulation tools** — click a wall, pick a material from a swatch library, the surface re-renders coherently with correct lighting and perspective. Non-destructive: every change is a re-editable layer, not baked pixels.

**Intended outcome:** ship a web-based MVP that proves the core loop — *upload a 3D-model viewport screenshot from Rhino/SketchUp/Revit (shaded with default cartoon colors and visible edges), render it with Nano Banana Pro preserving geometry, see every element pre-tagged (wall, window, mullion, furniture, tree, person…), click any region, swap its material from a library* — built on a layer-stack foundation so future edits (geometry, lighting) slot in without rewrites. Rhino/SketchUp/Revit plugins follow naturally because every host already exposes a viewport-bitmap API (`RhinoApp.MainWindow.ActiveView.CaptureToBitmap()`, SketchUp `view.write_image()`, Revit `Document.GetView().ExportImage()`).

### Architectural pivots (history of the design)

**Pivot 1 (post-spike-1):** Dropped text-to-image + click-segmentation. That approach is photographer-style, not architect-style: it asks the AI to invent geometry and then asks the AI to identify what it invented — two compounding inference steps. Architects don't start from prompts; they start from models.

**Pivot 2 (current):** Dropped pure line-work input in favor of **shaded model viewport screenshots** as the primary MVP input. Reasons:
- The shaded screenshot carries *both* geometry edges *and* region-boundary cues. Color discontinuities indicate "this is a distinct form or material from its neighbor" — but the *semantic label* (wall, window, mullion) must come from geometric and contextual reasoning, not from a hardcoded color ontology. Different models use different color schemes, and architects often work in custom display modes. The right principle: **a color change is a hint that the regions differ; the VLM uses geometry, position, and context to decide what each one is.**
- Plugin path: every host (Rhino, SketchUp, Revit, Forma) already exposes a one-call viewport-bitmap API. Exporting a hidden-line PDF is an extra manual step; capturing the active viewport is what plugins do natively. Building for screenshots first means the plugin work later is mostly UI wiring, not file-format wrangling.
- Architect workflow: most users work in shaded mode by default. The screenshot is what they're already looking at — no detour through "set display mode to hidden-line → print to PDF".

The pipeline treats the screenshot as ground truth, uses Nano Banana Pro as a controlled image-to-image renderer (photoreal skin over architect's geometry, replacing cartoon shading with real materials while preserving every edge), and uses a VLM (Gemini 3 Pro) to reason about both the screenshot and the render to pre-tag every region semantically. SAM2 becomes a bbox-refiner, not a click-segmenter. Pure line-work input is kept as a deferred v1.1 mode.

## Core concept

**Tagline:** *"Figma + Photoshop + Nano Banana, opinionated for architecture."*

Four primitives the user manipulates directly:
1. **Model screenshot** — the input. PNG viewport capture from Rhino/SketchUp/Revit/Forma in default shaded display mode. Ground truth for all geometry. (Pure line-work PDF input is a v1.1 alternative for users who prefer wireframe exports.)
2. **Tagged regions** — every architectural element, pre-identified by the VLM (wall, floor, ceiling, window, door, mullion, roof, ground, sky, vegetation, furniture, person, vehicle). Click to select. No lasso, no guessing.
3. **Materials** — visual swatches from a library. Applied by drag-drop or click. Never typed.
4. **Layers** — every region→material assignment is a live, re-editable layer. Toggle, reorder, restyle without re-prompting.

The LLM/prompt path stays available as an *escape hatch*, not the default.

## Architecture (MVP, web app)

### Tech stack
- **Frontend:** Next.js + React + TypeScript, canvas via Konva.js or Fabric.js (mature, layer-friendly) — or PixiJS if perf becomes an issue.
- **Backend:** Python FastAPI for the model pipeline; Node/Next API routes for app logic.
- **Storage:** Postgres (project/layer metadata) + S3-compatible object store (images, swatches, masks).
- **Auth:** Clerk or Supabase Auth.
- **Hosting:** Vercel (frontend) + Modal or RunPod (GPU inference) + Supabase (DB + storage).

### Model pipeline (the "AI plumbing")

| # | Stage | Model | Role |
|---|---|---|---|
| 1 | **Ingest screenshot** | (no model) | Accept PNG viewport screenshot from Rhino/SKP/Revit/Forma (default shaded mode: solid color fills + visible edges). Normalize to 1024–1536 px on long side. Cache as `source.png`. Optional: run Canny edge detection to extract a clean line-mask for later overlay/diagnostic use. |
| 2 | **Render** | **Nano Banana Pro** (`nano-banana-pro-preview`, via `generate_content` with image+text input) | Image-to-image: replace cartoon shading with photoreal materials while preserving every edge, opening, and form. Prompt explicitly instructs: "treat color discontinuities in the input as region boundaries (a different color means a different form or material); replace cartoon shading with photoreal materials; do not assume specific colors map to specific architectural elements; preserve geometry exactly." Fallback if fidelity is insufficient: **FLUX.1 + Canny/MLSD ControlNet** seeded from the screenshot's edges. |
| 3 | **Tag regions** | **Gemini 3 Pro** (`gemini-3-pro-preview`) — multimodal VLM | Reason about SCREENSHOT + RENDER together. Return structured JSON: `[{id, label, bbox, confidence, parent_id?}]`. Color discontinuities help locate region *boundaries*; the VLM uses geometry, position, scale, and surrounding context to assign the *semantic label* (wall vs window vs mullion vs door). Hierarchy supported (mullion ⊂ window ⊂ wall). |
| 4 | **Refine masks** | **SAM 2** (Meta, open) | Convert each VLM bbox to a pixel-precise mask. Cached per region. |
| 5 | **Apply material** | **IP-Adapter Plus** + **FLUX.1 Fill** (and/or **Nano Banana edit**) with **depth + MLSD ControlNet** | Inpaint masked region constrained to material swatch. ControlNet ensures lighting/perspective coherence. |
| 6 | **Composite** | (CPU, client-side in prod) | Composite the rendered tile back via the cached mask. Each tile is a layer. |

Depth/normals/segmentation maps are cached once at render time and reused across all edits — this is what makes the layer stack cheap to recompute.

### The layer model (the differentiator vs Photoshop)

A project is a **scene graph**, not a flat pixel stack:

```
Project
 ├─ BaseImage (Nano Banana output + cached depth/normal/segmentation)
 ├─ Layer: "north wall" → Material: Travertine     [visible, opacity 1.0]
 ├─ Layer: "floor"      → Material: Oak herringbone [visible]
 ├─ Layer: "ceiling"    → Material: White plaster  [hidden]
 └─ Layer: "window mullions" → Material: Black steel
```

Each layer stores: `{element_mask_id, material_id, ip_adapter_strength, controlnet_weights, rendered_tile_cache}`. Recomputing a layer is cheap because masks + depth are cached. Reordering or toggling is free (cached tiles composite client-side).

This is the architectural decision that everything else depends on. Get this right and v1 (parametric edits, lighting layers, geometry layers) extends naturally. Get it wrong and you rebuild.

### Material library (three sources, unified interface)

1. **In-house curated** — ~200 PBR swatches at launch, named for architects (*Corten*, *charred cedar*, *board-formed concrete*, *travertine honed*). Source from ambientCG (CC0) + Poliigon free tier; pre-process into 1024×1024 swatch tiles + IP-Adapter embeddings cached.
2. **User upload** — drop any image, auto-crop to square, generate IP-Adapter embedding, save to user's private library.
3. **AI-generated** — text → swatch tile via Nano Banana Pro at swatch resolution; saved as reusable library item.

All three normalize to the same `Material` record: `{id, name, swatch_image, ip_adapter_embedding, pbr_maps?, source: 'curated'|'uploaded'|'generated'}`.

## MVP scope (the killer flow)

**One flow, end-to-end:**
1. User uploads a 3D-model viewport screenshot (PNG) — typically the default shaded display from Rhino/SketchUp/Revit/Forma. (Future plugins capture this directly from the host.)
2. Backend renders it via Nano Banana Pro (image-to-image, geometry-preserving, cartoon-color → photoreal-material). Caches the render alongside the original screenshot.
3. VLM (Gemini 3 Pro) reasons about screenshot + render → returns structured region list (wall, window, mullion, door, floor, ceiling, furniture, person, tree, etc.) with bboxes and parent relationships.
4. SAM2 refines each bbox into a pixel-perfect mask. All masks cached per region.
5. Canvas opens. User sees the render with every region highlighted on hover, tagged by name. User clicks "north wall".
6. Material panel opens. User picks "Travertine" from the curated library (or uploads / generates one).
7. Backend runs IP-Adapter + FLUX Fill + depth-ControlNet on the masked region → Nano Banana edit pass for coherence → returns tile.
8. Tile composites onto canvas as a new **Layer** in the stack. User can toggle, change material, or delete the layer.
9. Project autosaves. User can reopen and continue editing.

**Out of scope for MVP** (explicitly deferred):
- Parametric element edits (resize window, change muntin count) — requires handles + geometry-aware re-render.
- Lighting layers / time-of-day shifts.
- Multi-image scenes, video, exterior↔interior.
- Plugins for Rhino/SketchUp/Revit/Forma (post-validation; will use the same `/render` + `/tag_regions` pipeline as the web app, just sourcing the screenshot from the host's viewport API. In future, the plugin can optionally pass native layer/material data alongside the screenshot to skip the VLM tagging step).
- Pure line-work PDF input (v1.1 mode for architects who export wireframes manually).
- Text-to-image generation (the original concept) — kept as a v1.1 secondary mode.
- Collaboration / multiplayer.

## Build order

1. **Spike 2 — screenshot-to-render fidelity test (DONE)** — single driver in `spike/test_screenshot_fidelity.py`. Tested on a real Revit perspective screenshot (`spike/test_assets/model_views/building.png`). **Outcome:** macro alignment ≥ 90%, but characterized failures: invented windows on right facade, corner windows transformed into wraparounds, slight edge drift in several spots. Gate technically passed (≥80%) but the *critical-severity* failures (changes to core building mass) are architect-blockers. Need a structured comparison to find a renderer that preserves geometry at the critical tier, not just on average.

2. **Spike 2.5 — multi-renderer bake-off + cheap-fix exploration (1 week)** — *added in response to spike 2 failure analysis.* Structured comparison across 7 renderer variants to find the production renderer empirically rather than betting on one. Three phases:

   **B1: Characterize existing failures (30 min, ~$0.12)**
   - Score the existing spike 2 render on the failure rubric (see Verification section). Tag each failure by **type** (invention / omission / displacement / transformation / drift) × **location** (frame edge / distant / repetitive / ambiguous / core mass) × **severity** (critical / high / medium / low).
   - Run Nano Banana Pro 3 more times on the same screenshot at different seeds. Compare failure sets across seeds → identify deterministic vs stochastic failures. Stochastic ones may be fixable with seed control alone.

   **B2: Cheap Nano Banana fixes (1–2 hr, ~$0.50)**
   - Variant a: **Tightened prompt** with explicit constraints ("the right facade has 0 windows; do not add any; corner is recessed not wrapping").
   - Variant b: **Higher input resolution** (try 1920×1280+; current input is 1308×881).
   - Variant c: **Annotated multi-region prompt** describing each facade explicitly.
   - Variant d: **Multi-pass** — first NB render → Gemini 3 Pro tags regions and counts elements → second NB render with explicit constraints based on the count.

   **B3: Multi-renderer bake-off (half day, ~$3–5)**
   - Build `spike/compare_renderers.py` — single driver that fans out the same screenshot to all candidates via their hosted APIs, collects renders, builds the comparison grid + scoring rubric output.
   - **Candidates (7 total):**
     | # | Renderer | Provider | Mode | Why |
     |---|---|---|---|---|
     | 1 | Nano Banana Pro (best variant from B2) | Google AI | Image-to-image (soft) | Current baseline |
     | 2 | FLUX.1 Canny Pro | **BFL** (api.bfl.ml) | Canny ControlNet (hard) | Gold standard for "preserve edges exactly" |
     | 3 | FLUX.1 Kontext Pro | BFL | Image editing (purpose-built) | Trained for restyling-while-preserving |
     | 4 | Magnific Relight / Mystic | Magnific API | Arch-specialized | Built for arch viz restyling, used by pros |
     | 5 | Qwen-Image-Edit | Replicate or fal.ai | Image editing (open) | Strong on detailed/architectural content |
     | 6 | HiDream-E1 | Replicate or fal.ai | Image editing (open) | Claims strong edit fidelity, newer arch |
     | 7 | Recraft V3 | Recraft API or Replicate | Image editing (closed) | Designer-favorite, strong "edit existing" mode |
   - Run all 7 on `building.png`, score with the full rubric, output a single comparison grid PNG + a CSV of scores.
   - **Gate:** pick the winner by lowest critical-failure count, ties broken by photoreal quality and cost. If no candidate has < 1 critical failure, escalate to Tier 3 (SDXL+ControlNet, SD 3.5+Control) or hybrid two-pass pipeline (e.g., FLUX Canny for structure + Nano Banana for material).

3. **Spike 3 — VLM tagging accuracy (1 day)** — send screenshot + winning render to Gemini 3 Pro with a structured prompt asking for region JSON. Manually score: did it identify ≥ 80% of architectural elements correctly? Are bbox positions usable as SAM2 prompts?
4. **Spike 4 — end-to-end edit (1 day)** — wire spike 2.5 winner + spike 3 + the existing Modal SAM2/inpaint pipeline. Click a tagged "wall" → swap to travertine. Confirm latency, cost, and visual quality of the full loop.
4. **Backend pipeline service** — FastAPI on Modal exposing `/render`, `/tag_regions`, `/refine_mask`, `/apply_material` endpoints.
5. **Data model + project persistence** — Postgres schema for Project, LineWork, Render, Region, Layer, Material, User. S3 for assets.
6. **Canvas frontend** — Next.js + Konva. Upload line work → see render with overlaid clickable tagged regions → layer panel → material panel.
7. **Curated material library** — script to ingest ambientCG → swatch tiles + IP-Adapter embeddings → seed DB.
8. **User upload + AI swatch generation** — file upload + Nano Banana swatch generation endpoint.
9. **Polish & private beta** — invite ~10 architects (Arcanum colleagues, Cal Poly faculty) for feedback.

## Critical files (to be created/modified)

- `spike/modal_app.py` — **existing**. Changes required for screenshot-mode MVP:
  - Rename `render_from_linework()` → `render_from_model_view()` (keep `render_from_linework` as a thin alias for back-compat).
  - Update the instruction prompt inside the function. Key principle: do NOT hardcode color-to-element mappings. The prompt should say something like: "This is a 3D-model viewport screenshot. Different colors in the input indicate distinct forms or materials — treat color discontinuities as region boundaries, but do not assume specific colors map to specific architectural elements (different model setups use different color schemes). Replace the cartoon shading with photoreal materials while preserving every edge, opening, and form exactly. Reason from geometry and context, not from color identity."
  - Add `tag_regions()` Modal function (Gemini 3 Pro structured-output call). Same principle: prompt the VLM to use color discontinuities as boundary hints, geometry/context for labels.
  - Repurpose `segment()` to accept a bbox prompt instead of a click point (SAM2 supports both natively; small signature change).
- `spike/test_assets/model_views/` — **new**. User-supplied viewport screenshots for testing. (Old `test_assets/linework/` kept for the deferred v1.1 line-work mode.)
- `spike/test_screenshot_fidelity.py` — **existing spike 2 driver** (replaces deprecated `test_linework_fidelity.py`). Calls `render_from_model_view`. Runs Canny edge detection on the input screenshot, then overlays those edges in red on the render so geometric preservation can be judged visually. Saves `outputs/spike2/render.png`, `edges.png`, `overlay.png`, `sidebyside.png`.
- `spike/compare_renderers.py` — **new spike 2.5 driver**. Single script that:
  - Takes one input screenshot.
  - Fans out to all 7 candidate renderers via their respective hosted APIs (env vars for keys: `GOOGLE_API_KEY`, `BFL_API_KEY`, `REPLICATE_API_TOKEN` or `FAL_KEY`, `MAGNIFIC_API_KEY`, `RECRAFT_API_TOKEN`).
  - Saves each render to `outputs/spike2_5/<renderer>.png`.
  - Builds `outputs/spike2_5/comparison.png` — 4×2 grid of input + all 7 renders.
  - Builds `outputs/spike2_5/overlays.png` — same grid with Canny edges overlaid for fidelity diagnostic.
  - Writes `outputs/spike2_5/scores.csv` — rubric template the architect fills in (or auto-fills the quantitative columns).
- `spike/renderers/` — **new package**, one client per provider:
  - `nano_banana.py` (wraps existing `render_from_model_view`)
  - `flux_bfl.py` (FLUX Canny Pro + FLUX Kontext Pro via api.bfl.ml)
  - `magnific.py` (Magnific Mystic/Relight)
  - `replicate_models.py` (Qwen-Image-Edit, HiDream-E1, optionally Recraft V3)
  - `recraft.py` (Recraft V3 native API as fallback)
- `spike/scoring.py` — **new**. Quantitative metrics: `count_windows(image)` (calls Gemini 3 Pro with structured output), `silhouette_iou(input_img, render_img)`, `edge_density_delta(input_img, render_img, region)`.
- `spike/scoring_rubric.json` — **new**. Template for architect scoring: per-renderer scores on Critical/High/Medium/Low failure counts + Photorealism 1–10 + Material believability 1–10 + Lighting coherence 1–10 + cost + time.
- `spike/test_vlm_tagging.py` — **new spike 3 driver**. Calls `tag_regions`, draws bboxes + labels on render, saves visualization.
- `apps/web/` — Next.js frontend (later)
  - `apps/web/src/canvas/Canvas.tsx` — Konva canvas + layer compositing + tagged region overlay
  - `apps/web/src/panels/LayerPanel.tsx` — layer stack UI
  - `apps/web/src/panels/MaterialPanel.tsx` — swatch picker (3 sources)
  - `apps/web/src/panels/RegionPanel.tsx` — list of all tagged regions, jump-to-region
- `services/inference/` — productionized version of `spike/modal_app.py`
  - `services/inference/pipeline/render.py` — Nano Banana Pro image-to-image (+ FLUX ControlNet fallback)
  - `services/inference/pipeline/tag_regions.py` — Gemini 3 Pro structured tagger
  - `services/inference/pipeline/refine_mask.py` — SAM2 bbox-to-mask
  - `services/inference/pipeline/apply_material.py` — IP-Adapter + FLUX Fill + Nano Banana edit
  - `services/inference/pipeline/cache.py` — depth/normal/region-mask cache
- `services/api/` — Next.js API routes for project/region/layer CRUD
- `db/schema.sql` — Postgres schema (Project, LineWork, Render, Region, Layer, Material, User, Asset)
- `scripts/seed_materials.py` — one-shot ambientCG ingest → DB

## Reusable building blocks (don't reinvent)

- **Nano Banana Pro** (`nano-banana-pro-preview`) via google-genai — image-to-image render. Already wired up in `spike/modal_app.py`.
- **Gemini 3 Pro** (`gemini-3-pro-preview`) — multimodal VLM for region tagging + automated window counting. Same google-genai client, structured-output config.
- **SAM 2** (`facebookresearch/sam2`) — bbox/click → pixel mask. Already wired up in `spike/modal_app.py`.
- **diffusers** (`huggingface/diffusers`) — ControlNet, IP-Adapter, FLUX Fill pipelines. Already in Modal image. (Only used if we end up self-hosting any renderer; spike 2.5 uses hosted APIs.)
- **Konva.js** — mature 2D canvas with layer/transform primitives.
- **ambientCG / Polyhaven** — CC0 PBR materials for the curated library.

### Hosted-API renderer providers (for Spike 2.5 bake-off and likely production)

Self-hosting FLUX on Modal is unnecessary at the volumes we'll hit during validation; hosted APIs win on setup time, cold-start latency, and complexity-per-image until we exceed ~5k images/day. Migration to self-hosted is a one-file swap later if scale economics dictate.

- **Black Forest Labs** (`api.bfl.ml`) — FLUX 1.1 Pro, **FLUX Canny Pro** (Canny ControlNet), **FLUX Depth Pro**, **FLUX Kontext Pro** (purpose-built for image editing). ~$0.04–0.05/image, ~5s. Cleanest, made by FLUX's creators.
- **Replicate** (`replicate.com`) — hosts Qwen-Image-Edit, HiDream-E1, Recraft V3, and many community FLUX variants. Pay-per-second of inference (~$0.02–0.05/image). Easy auth via API token.
- **fal.ai** — alternative for Qwen/HiDream with faster cold start. Use as backup to Replicate if a model is unavailable there.
- **Magnific** — arch-viz-specialized image editing (Relight + Mystic modes). Closed API, ~$0.10/image. Needs subscription/access.
- **Recraft** (`recraft.ai`) — native API for Recraft V3 image editing. Replicate hosts it too; either works.

## Open questions / risks (ranked by impact)

1. **Renderer geometry fidelity (HIGHEST RISK — partly resolved).** Spike 2 confirmed Nano Banana Pro achieves macro alignment (~90%) but produces *critical-severity* failures (invented windows, corner wraparounds) that an architect would reject. Spike 2.5 (multi-renderer bake-off) is the structured response: empirically compare 7 candidates (Nano Banana variants, FLUX Canny Pro, FLUX Kontext, Magnific, Qwen-Image-Edit, HiDream-E1, Recraft V3) and pick the production renderer by lowest critical-failure count, tiebreak by photoreal quality and cost. If no single renderer wins outright, hybrid two-pass (e.g., FLUX Canny for structural pass + Nano Banana for material pass) is the likely answer.
2. **VLM region tagging accuracy.** Can Gemini 3 Pro reliably distinguish "mullion" from "frame" from "window pane"? Color discontinuities in the screenshot help locate region boundaries, but labels must come from geometric/contextual reasoning (the VLM cannot assume cyan ≡ mullion across different model setups). Tunable via prompt engineering + structured-output schema. Test in spike 3 across multiple screenshots with different color conventions.
3. **Plugin parity.** Each host (Rhino/SKP/Revit/Forma) exposes a viewport-bitmap API but with different default display modes and color conventions. Need to validate that our render prompt generalizes across all four. Test once the web app is live by manually grabbing screenshots from each.
4. **Cost per render-edit cycle.** Nano Banana Pro render ≈ $0.04, Gemini 3 Pro VLM call ≈ $0.01, FLUX Fill on Modal A10G ≈ $0.02. Roughly $0.05–0.10 per session-start, $0.02 per material swap. Sustainable for a paid tier.
5. **Inference cost at scale.** If Nano Banana Pro edit pass is expensive per swap, IP-Adapter + FLUX Fill alone may be good enough for most layers, with Nano Banana only on final export.
6. **Desktop wrapper (Tauri)** for offline / local-GPU power users — later.
7. **Pricing model** — likely credit-based with a free tier (~10 edits/mo), pro at $20–30/mo.

## Verification

### Failure taxonomy & scoring rubric (used in spikes 2.5 and 3)

Every render gets scored on three axes:

| Axis | Categories |
|---|---|
| **Type** | Invention · Omission · Displacement · Transformation · Style drift |
| **Location** | Frame edges · Distant/small · Repetitive patterns · Ambiguous regions · Core building mass |
| **Severity** | **Critical** (changes building footprint, story count, window grid — architect rejects) · **High** (proportions/mullion patterns deviated) · **Medium** (material/glass tint — meant to change) · **Low** (shadows, sky, foreground) |

Quantitative metrics (auto-computed by `spike/scoring.py`):
- **Window count delta** per facade (via Gemini 3 Pro structured-output call)
- **Building silhouette IoU** (extract outline from input + render via Canny + flood-fill, compute Intersection-over-Union)
- **Edge density preservation** (Canny pixel count in input region vs corresponding render region)

Subjective scores (architect fills in): Photorealism 1–10, Material believability 1–10, Lighting coherence 1–10.

### End-to-end success criteria for MVP

1. **Spike 2 gate (DONE):** Real model viewport screenshot → Nano Banana Pro render preserves ≥ 80% of geometry visually (passed at ~90%, but critical-failure count motivated spike 2.5).
2. **Spike 2.5 gate:** At least one renderer (or hybrid two-pass) produces **zero critical-severity failures** on `building.png`, with ≥ 7/10 photorealism. Winner is locked in as the production renderer.
3. **Spike 3 gate:** Gemini 3 Pro correctly tags ≥ 80% of major architectural regions (walls, windows, mullions, floors, ceilings, doors) on 5 diverse test screenshots.
3. **Spike 4 gate:** Click a tagged "wall" → travertine applied with correct perspective + lighting in < 15s.
4. Switch material on the same region → old layer replaced, not stacked.
5. Toggle layer off → wall reverts to original render. Toggle on → restored from cache (< 1s).
6. Close browser, reopen project → line work, render, tagged regions, layer stack all intact.
7. Upload a photo of a custom material → appears in library, applies to a clicked region.
8. Manual QA on 10 diverse model screenshots (modern interior, traditional exterior, mixed materials, complex window patterns, urban context with people/cars/trees, etc.) — material swaps look coherent in ≥ 7/10.

If spikes 2–4 pass their gates and criteria 4–8 hold, MVP is ready for private beta.
