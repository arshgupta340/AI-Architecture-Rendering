# Master Plan v2: "Photoshop-for-Architects" AI Rendering Engine

> **v2, 2026-06-12** — plugin-first pivot after the foundational pressure test (four research tracks; see [research/](research/) and [wiki/DECISIONS](../../wiki/DECISIONS.md)). v1 (screenshot-first) is preserved in git history of this file. Sub-documents: [host-integration](research/host-integration.md) · [generative-stack](research/generative-stack.md) · [competitive-landscape](research/competitive-landscape.md) · [experiments](experiments.md).

## Context

Every AI architecture-rendering tool in mid-2026 still reduces to **"select/mask a region + type a prompt + re-render."** Veras 4.5 made the *selection* one click (Smart Selection, powered by DeepMind's non-public Vision Banana), but what follows the click is still prose. Architects don't think in prompts — they think *"that wall, in travertine."*

The unfilled niche (verified open as of June 2026 — see [competitive-landscape](research/competitive-landscape.md)): a canvas where AI is invisible plumbing behind **direct-manipulation tools** — click a wall, pick a material from a swatch library, the surface re-renders coherently. Non-destructive: every region→material assignment is a re-editable layer. Multi-view: materials lock across all camera angles of the project.

**Intended outcome:** ship a product that proves the core loop — *capture a view of the architect's 3D model, render it photorealistically preserving geometry, every element pre-tagged, click any region, swap its material from a library, compare schemes via layers* — with **host plugins as the primary input path** and screenshot upload as the universal fallback.

### The v1→v2 pivot (why)

v1 used a viewport **screenshot as the only input** and reconstructed everything by inference: VLM tagging (Gemini) + bbox→mask segmentation (SAM2). Measured results killed that architecture's weakest stages:

- Gemini tagging ≈ 0.4 mAP; found **0 mullions on a facade that is a mullion grid** (T21); returns 0 windows on raw screenshots; flat confidence; occasional malformed JSON.
- SAM 2 documented to lose thin structures (mullions, frames) in its low-res mask head.
- Meanwhile the hosts **natively know** the answer: Revit has a built-in `OST_CurtainWallMullions` category; Rhino exposes a true z-buffer (`ZBufferCapture`) and per-object draw control; every host can render a per-object flat-color ID pass.

**The principle: stop using AI to re-derive ground truth the host already has. Reserve AI for the two things only it can do — photoreal synthesis and material application.**

Competitive timing: Veras (Chaos) operates screenshot-level only; G-buffer-conditioned diffusion is validated in research but unshipped from any BIM host. The extraction lane is open.

## Core concept

**Tagline:** *"Figma + Photoshop + Nano Banana, opinionated for architecture."*

Four primitives the user manipulates directly:
1. **Model capture** — from a host plugin (beauty + ID-mask + depth + object table) or, in fallback, a plain screenshot.
2. **Tagged regions** — pre-identified, click to select. Ground truth on the plugin tier; AI-detected on the fallback tier.
3. **Materials** — visual swatches from a curated library (+ user upload + AI-generated). Never typed.
4. **Layers** — every region→material assignment is a live, re-editable layer; the scene graph also carries the **multi-view material lock** (change a material once, it propagates to all views of the project).

The LLM/prompt path stays available as an escape hatch, not the default.

## Architecture — two tiers, one product

```
TIER 1 — PLUGIN (primary, ground truth)        TIER 2 — SCREENSHOT (fallback, universal)
─────────────────────────────────────          ─────────────────────────────────────
Rhino / Revit / SketchUp plugin exports:       browser upload of any viewport screenshot
  beauty.png   (shaded viewport)                (also: Forma, no-plugin users, demos)
  id_mask.png  (per-object flat color)
  depth.png    (true z-buffer; Rhino only —    render: FLUX.2 [pro] Edit i2i
               Revit/SKP use estimated depth)          (Nano Banana Pro as alternate)
  objects.json (id → category/layer/material)  tag+segment: Florence-2 → SAM 3
  camera.json  (eye/target/FOV)                        (watch: Vision Banana public API)

render: FLUX depth+canny ControlNet
        (true z-buffer conditioning)
tag/segment: NONE — ground truth

           └──────────────── SHARED BACKEND ────────────────┘
           apply material: swatch-conditioned regional re-render
             (FLUX.2 Edit multi-ref hosted; MatSwap self-hosted
              if fidelity gate fails — takes true normals from tier 1)
           layer model · composite · multi-view material lock
           canvas frontend (Next.js + Konva)
```

Per-host reality (full matrix in [host-integration](research/host-integration.md)): **Rhino** = depth + ID masks + material R/W, ~2wk plugin, first target. **Revit** = best semantics (native BIM categories), clean ID masks, no depth — second. **SketchUp** = ID masks only — third. **Forma** = tier 2 only.

### Model pipeline

| # | Stage | Tier 1 (plugin) | Tier 2 (screenshot) |
|---|---|---|---|
| 1 | Ingest | plugin POST: beauty/id_mask/depth/objects/camera | PNG upload, normalize 1024–1536px |
| 2 | Render | FLUX.1-dev ControlNet depth+canny (fal `flux-general`) — true z-buffer conditioning | FLUX.2 [pro] Edit i2i (NB Pro alternate) |
| 3 | Tag | **none** — objects.json is ground truth (cheap VLM pass only for unnamed entourage, labeling the object *list*, not pixels) | Florence-2 open-vocab detection (+ YOLOE pass for repeated thin elements) |
| 4 | Segment | **none** — id_mask.png is exact | SAM 3 bbox→mask refinement |
| 5 | Apply material | swatch-conditioned: FLUX.2 Edit multi-ref → (if fidelity gate fails) MatSwap w/ true normals | same, minus true normals |
| 6 | Composite | CPU alpha composite per cached mask; each tile a layer | same |

Depth/masks/object table cached once per capture and reused across all edits — this is what keeps the layer stack cheap to recompute.

### The layer model (the differentiator)

A project is a **scene graph**, not a flat pixel stack:

```
Project
 ├─ View[] (camera.json each; multi-view material lock spans views)
 │   └─ BaseImage (render + cached depth/id_mask/objects)
 ├─ Layer: "north wall" → Material: Travertine   [visible, opacity 1.0]
 ├─ Layer: "floor"      → Material: Oak          [visible]
 └─ Layer: "mullions"   → Material: Black steel  [hidden]
```

Each layer stores `{region_ids, material_id, conditioning_params, rendered_tile_cache (per view)}`. Changing a material re-renders the affected tiles in every view (anchor-reference technique keeps them consistent). Toggling/reordering is free (cached tiles composite client-side). **This is the make-or-break design decision — prototype it on E1's real ground-truth data before building the full app.**

### Material library (three sources, unified)

1. **Curated** — ~200 PBR swatches named for architects (Corten, charred cedar, board-formed concrete, travertine honed). ambientCG (CC0) + Poliigon; 1024² tiles + conditioning embeddings cached. *Long-term moat: manufacturer-SKU partnerships.*
2. **User upload** — any image → auto-crop → embedding → private library.
3. **AI-generated** — text → swatch tile, saved as a reusable item.

## MVP scope (the killer flow)

1. Architect clicks "Capture" in the Rhino plugin (or uploads a screenshot).
2. Backend renders photorealistically; regions arrive pre-tagged (ground truth or detected).
3. Canvas opens; hover highlights regions by name; click "north wall."
4. Material panel: pick "Travertine honed."
5. Backend re-renders the region, conditioned on the swatch; returns a tile.
6. Tile lands as a Layer. Toggle/restyle/delete; Scheme A/B/C comparison live.
7. Switch to another saved view — the travertine is already there (material lock).
8. Project autosaves; reopen with everything intact.

**Deferred:** parametric edits, lighting layers, video, collaboration, line-work input, text-to-image mode, desktop wrapper, writing materials *back* to the host model (possible — `ModifyRenderMaterial` / `doc.Paint` — and a natural v2 feature).

## Build order

1. **Phase 0–1 (done 2026-06-12):** pressure test, research docs, this plan.
2. **Phase 2 — experiment ladder** ([experiments.md](experiments.md)): E1 Rhino extraction probe ($0, keystone) → E2 render shootout → E3 swatch shootout → E4 Vision-Banana probe → E5 fallback tagging → E6 ID-mask end-to-end. ~$10–15 of a $50 authorized budget.
3. **Phase 3 — build:** Rhino capture plugin (Grasshopper fast path 3–5 days, full .rhp ~2wk) → layer-model + canvas prototype on real ground-truth data → backend service (FastAPI on Modal: `/ingest`, `/render`, `/apply_material`) → material library seeding → Revit add-in → SketchUp → private beta (~10 architects).

## Open questions / risks (ranked)

1. **Swatch fidelity** — hosted models give "travertine-like," not "this travertine" (CLIP-I ceiling ~82.5%). E3 gates this; MatSwap contingency exists but is SD1.5-based. A FLUX-backbone material-transfer model (HiFi-Inpaint-style) would be the unlock; none hosted yet.
2. **Veras velocity** — they ship every 4–6 weeks with Chaos distribution and privileged Vision Banana access. Our moat must be the material system + layers + multi-view lock, not selection.
3. **Layer-name discipline (Rhino/SketchUp)** — semantics depend on user conventions; mitigation: VLM labeling of the object list + UI for quick relabeling. Revit needs no discipline.
4. **Depth gaps** — Revit/SketchUp have no z-buffer; monocular estimation from the beauty pass is the fallback (still better than nothing; Rhino proves the ceiling).
5. **ID-mask edge quality** — AA/transparency gotchas on thin members; E1 validates.
6. **Cost per edit** — ~$0.03–0.08 per material swap hosted; sustainable for credit-based pricing ($20–30/mo pro tier per market norms).

## Verification

- Experiment gates as defined in [experiments.md](experiments.md) (E1 mask accuracy at 1:1, E2 zero-critical-failure render, E3 blind material naming, E4/E5 IoU vs ground truth, E6 stage-deletion parity).
- End-to-end MVP criteria (carried from v1): swap < 15s; re-swap replaces not stacks; layer toggle restores from cache < 1s; project reopen intact; custom material upload works; 7/10 coherent swaps on 10 diverse models.
- Test suite stays green throughout: `spike\.venv\Scripts\python.exe -m pytest spike/tests/ -v`.
