---
type: research
updated: 2026-07-18
---

# Full-360 multi-view-consistent hero: options anchored to a known mesh

> Seeds the next attended session on the open [[STATE]] "Multi-view hero" follow-up (NEXT #2c). Anchor decision: [[DECISIONS#web3d-reproject-consistency]]. Current engine: `apps/web3d-prototype/src/lib/reproject.ts` (projective-texture reproject) + self-hosted FLUX.1-dev + ControlNet-Union (depth ∪ canny ∪ id-edge) hero backend on Modal A100 (`spike/modal_flux.py`). Refreshed 2026-07-18 (prior draft 2026-07-13) — headline changes: **Hunyuan3D-2.1-Paint** (permissive-commercial, PBR, mesh-conditioned) supersedes SD1.5 SyncMVD as the texture-bake tool of choice; the **IP-Adapter block is lifted** in current diffusers, which unblocks the cheapest engineering fix. **2026-07-23: an independent overnight re-survey ([research/full360-options.md](../../research/full360-options.md), link-verified) CONFIRMS the recommendation** — multi-hero anchoring first — and adds: FlashTex (relightable bake, code released), a concrete MeSS-style GCAlign exposure-harmonisation step for the anchor plan, MV-Adapter-as-anchor-generator as the escalation if bracketing anchors still lose the back, and SEVA's **576p output cap** (a second product disqualifier beside its license).

## 1. Problem statement

We can make ONE geometry-locked photoreal still (FLUX hero) and reproject its pixels onto the real mesh to synthesize **nearby** angles with perfect material/lighting consistency (verified). The open failure is the **full 360° turntable**: the current method chains forward around the circle — each new view reprojects its already-rendered neighbours and inpaints disoccluded gaps with `/region_edit`. Chained gap-fill cannot *reconstruct* sides the hero never saw (the back of the building dissolves), appearance **drifts** as errors compound view-to-view, and there is **no loop closure** (view N-1 and view 0 disagree where the circle meets). Root cause: appearance lives in **2D image space and propagates sequentially**. Every fix below moves appearance into a **global representation anchored to the mesh we already own** (exact geometry + depth + normals + semantic IDs + UVs for every view — the rare luxury; most published multi-view work has none of this), so "unseen" and "loop closure" stop being special cases.

## 2. Three candidate approaches

### Candidate A — Bake appearance INTO the mesh's UV texture (texture-space, structurally consistent)

**How it works.** Stop generating images and keep them consistent; instead generate ONE **global texture** for the mesh. The SyncMVD / MVPaint lineage renders the mesh from N cameras, runs a diffusion denoise step across all N views, then **back-projects every view into a shared UV atlas and blends** before the next step — consistency is enforced in UV space every step, so all views read one texture. Depth-ControlNet locks each view to the true geometry. Once baked, the full 360 renders in three.js **for free and exactly consistent**; loop closure and back views are *structurally impossible to get wrong* (one texture covers the whole surface). **2025 productized this idea**: mesh-conditioned multi-view paint models now emit **PBR** (albedo/roughness/metallic), which is a far better fit for our engine than a baked-lighting albedo — three.js re-lights it with the same sun/HDRI/material system we already ship.

**Evidence (code + weights unless noted).**
- **Hunyuan3D-2.1 / Hunyuan3D-Paint** — Tencent, arXiv [2506.15442](https://arxiv.org/html/2506.15442v1), repo [github.com/Tencent-Hunyuan/Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) (released **13 Jun 2025**). A **mesh-conditioned multi-view diffusion model that outputs view-consistent PBR** (albedo+roughness+metallic), up to 6 reference photos fused. **Fully open weights + training code; permissive license that explicitly allows commercial asset distribution** (attribution line required) — the standout for productization.
- **SeqTex** — VAST-AI, SIGGRAPH Asia 2025, arXiv [2507.04285](https://arxiv.org/html/2507.04285v1), repo [github.com/VAST-AI-Research/SeqTex](https://github.com/VAST-AI-Research/SeqTex). Single-stage feed-forward net: untextured mesh **+ one reference image (→ our FLUX hero)** → UV texture in one pass, via a **video-diffusion prior** with geometry-informed cross-domain attention. Directly consumes a hero as the reference; no chaining.
- SyncMVD — SIGGRAPH Asia 2024, arXiv [2311.12891](https://arxiv.org/abs/2311.12891), repo [github.com/LIU-Yuxin/SyncMVD](https://github.com/LIU-Yuxin/SyncMVD) (depth-ControlNet on **SD1.5**, PyTorch3D render/back-project, xatlas fallback). The clearest reference implementation of the loop, but SD1.5 fidelity.
- Others: MVPaint ([mvpaint.github.io](https://mvpaint.github.io/), arXiv 2411.02336), TEXGen (feed-forward, SIGGRAPH 2024), MD-ProjTex (arXiv [2504.02762](https://arxiv.org/pdf/2504.02762)), RomanTex (arXiv 2503.19011), MV-Painter ([amap-cvlab.github.io/MV-Painter](https://amap-cvlab.github.io/MV-Painter/)). Survey: arXiv 2606.00137.

**Fit to our assets.** Excellent. We own the mesh, per-view depth/normals, and a three.js render loop — `reproject.ts` already does the render/back-project SyncMVD needs (in reverse). **PBR output is the killer fit**: it slots into our existing swatch/material/sun/HDRI relight path, and per-region material edits map to UV islands keyed by our **semantic IDs** (non-destructive per-island edit). **Hero-seeded hybrid:** seed the UV atlas by reprojecting the shipped FLUX hero (reuse `reproject.ts`), then run the paint model only to fill/harmonize *unseen* UV regions — preserves the hero look where it exists, invents only the back.

**Hardware + cost.** Fits A100-80GB. Hunyuan3D-Paint inference ≈ tens of seconds–few min/mesh; **~$0.10–0.40 per full texture** amortized across ALL 360 frames (cheaper per-frame than one hero). H200 not required.

**Risks.** (1) Tuned for **objects**, not whole buildings with interiors + thin trim → possible seams on large flat facades, weak interiors. (2) Our UVs are box-projected world-feet (good for tiling swatches, not a clean atlas) → likely need xatlas re-unwrap, which changes material-edit UV keys. (3) Hunyuan3D-Paint's reference conditioning may not ingest our exact per-view depth/pose out of the box — integration work to force our geometry lock.

**Experiment plan (attended).**
1. Modal A100 job: Hunyuan3D-Paint on `house_pt.glb` (dequantized) with xatlas UVs, our FLUX hero as the reference image. **Kill if** the repo won't run our non-watertight arch mesh after ~½ day of loader wrangling → fall back to SeqTex, then SyncMVD.
2. Render the baked PBR 360 in-app; check **back-view integrity** (does the building survive?) and **loop-closure error** (view0 vs wrapped last view — ~0 by construction). **Kill if** facades seam badly or interiors are mush.
3. Hero-seeded-UV hybrid; measure whether hero regions stay byte-stable and edge-alignment vs our canny∪id metric. **Kill if** the seam between hero-seeded and model-filled UV is visible after harmonization.

### Candidate B — Multi-hero anchoring + loop closure (engineering fix on the SHIPPED pipeline)

**How it works.** Keep the deployed FLUX + reproject pipeline; fix the two failures directly. (1) **Anchors instead of a chain:** render K full heroes (e.g. 4–6) at spread azimuths (0/60/120/…°) that *together* see every side, all sharing seed + a common **reference-image conditioning** so they agree on materials/lighting. (2) **Reproject each anchor onto the mesh** (`reproject.ts`), giving every 360 frame real hero pixels from its nearest anchor(s). (3) **Blend overlaps and inpaint only true gaps** (surfaces no anchor saw) with `/region_edit`. Because frames derive from a fixed set of mesh-anchored heroes — not a chain — errors don't compound and **loop closure is automatic** (frame 359 blends anchors 300° and 0° symmetrically). The missing ingredient in the shipped stack was cross-hero appearance agreement; that is exactly what an image-prompt adapter provides.

**Evidence / what unblocks it.**
- **IP-Adapter is no longer blocked.** The 2026-06 finding ("`FluxControlNetPipeline` has no `load_ip_adapter` on diffusers 0.32.2", `spike/REPORTS/modal_flux.md`) is stale: current **`FluxControlNetPipeline` inherits `FluxIPAdapterMixin`** ([diffusers ControlNet-Flux docs](https://huggingface.co/docs/diffusers/en/api/pipelines/controlnet_flux); [pipeline_flux_controlnet.py](https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/flux/pipeline_flux_controlnet.py)). So **bumping diffusers unblocks image-prompt + ControlNet together** — re-verify the 0.32.2 `FluxMultiControlNetModel` batching workaround still holds after the bump.
- **Reference conditioning options, best-first:** **FLUX.1 Redux** (official BFL image-prompt adapter, [redux guide](https://stable-diffusion-art.com/flux-redux/)); **InstantX FLUX.1-dev IP-Adapter** ([release](https://comfyui-wiki.com/en/news/2024-11-22-instantx-flux-ipadapter-release)); or training-free **reference/shared-attention** (style-aligned generation) if the adapter route drifts.
- Prior art that anchored-generation + mesh-projection + gap-inpaint works at building scale: **MeSS** (arXiv [2508.15169](https://arxiv.org/abs/2508.15169), Aug 2025) — building meshes → key views generated in reverse order, projected to the mesh as surfels, intermediate views filled by Appearance-Guided Inpainting, plus a Global Consistency Alignment. Same shape as this plan; validates feasibility.

**Fit to our assets.** Best. Reuses `reproject.ts` + the live FLUX backend + our depth/canny/id locks; **no new base model to host**, output keeps the exact shipped FLUX look. K is small and bounded (heroes are independent → cheap, parallelizable), so no N-view memory ceiling.

**Hardware + cost.** A100-80GB, unchanged. **~K × single-hero cost ≈ $0.05–0.12 per turntable** (4–6 heroes @ ~$0.01–0.02 warm) + cheap gap inpaints. No H200.

**Risks.** (1) Adapter-driven agreement is *soft* — heroes may still disagree at grazing angles → residual seams where two anchors meet (blend weighting + `/region_edit` harmonize, but this is the real work). (2) True gaps (deep re-entrant geometry no anchor saw) still need honest inpainting — smaller than the whole back, but nonzero. (3) A diffusers bump is a stack change to re-verify (multi-controlnet batching, negative-prompt/true-cfg paths).

**Experiment plan (attended).**
1. Bump diffusers on a branch of `modal_flux.py`; smoke-test that the shipped single-hero base still matches (canny∪id edge-align ≥ prior). **Kill/park if** multi-controlnet regresses and can't be re-fixed in ~½ day.
2. Add a `ref_image` path (Redux first) and render 4 heroes at 0/90/180/270° sharing seed+ref; eyeball material/lighting agreement. **Kill if** anchors visibly disagree on material even with a shared ref → the appearance-lock is too weak, pivot to A.
3. Reproject all 4, blend by nearest-anchor confidence, `/region_edit` the residual gaps; render the 360 and measure loop-closure + back-view integrity. **Kill if** seams survive blending and inpaint.

### Candidate C — Multi-view / video diffusion with camera + geometry conditioning (the "new model" fallback)

**How it works.** Generate all N frames jointly. Two sub-flavors: **(C1) cross-view attention** — one denoising pass where the U-Net attends across all views (loop closure by construction), camera + our depth/normals enter via a condition encoder; **(C2) camera-controlled video** — feed a hero + an explicit 360 orbit to an NVS video model; temporal attention gives smoothness, extra input views (front+back hero) constrain the far side.

**Evidence (code + weights).**
- **MV-Adapter** — ICCV 2025, arXiv [2412.03632](https://arxiv.org/abs/2412.03632), repo [github.com/huanngzh/MV-Adapter](https://github.com/huanngzh/MV-Adapter) (+ [ComfyUI nodes](https://github.com/huanngzh/ComfyUI-MVAdapter)). Plug-and-play adapter (duplicated + parallel self-attention, unified encoder for **camera AND geometry**) on **SD2.1 (512) / SDXL (768)**, base weights frozen; supports image+geometry conditioned multi-view + texturing. **No confirmed FLUX port** → fidelity/style gap vs our hero.
- **Stable Virtual Camera (SEVA)** — Stability, arXiv [2503.14489](https://arxiv.org/abs/2503.14489), repo [github.com/Stability-AI/stable-virtual-camera](https://github.com/Stability-AI/stable-virtual-camera), [HF ckpt](https://huggingface.co/stabilityai/stable-virtual-camera) (v1.1 Jun 2025). 1.3B generalist NVS, arbitrary orbit, beats CAT3D/ViewCrafter. **⚠ Non-commercial license on BOTH weights and OUTPUT** — a hard productization blocker; research baseline only.
- MeSS (above) is the geometry-conditioned building-scale exemplar; CAADRIA 2025 [caadria2025_567](https://papers.cumincad.org/data/works/att/caadria2025_567.pdf) tunes a multi-view depth-consistent ControlNet to building models.

**Fit to our assets.** Moderate. C1 consumes exactly our conditioning (depth+canny+id+pose) but is a **new SDXL-class model to self-host** (not an add-on to the live FLUX backend), joint attention makes **memory scale with N** (→ windowing → mild seam return), and SDXL≠FLUX so the hero becomes a soft prompt, not the literal output. C2 does **not** natively consume our depth/semantic locks (pose only), and our own red team documented **AI video warps building geometry across camera motion** ([[SESSIONS]] 2026-07-03) — usable only as a *prior* whose frames get snapped back through `reproject.ts`, keeping only geometry-valid pixels.

**Hardware + cost.** C1: A100/H200, **~$0.10–0.30/turntable** (one batched pass); H200 if N-per-pass is tight. C2: A100, **~$0.05–0.15/orbit**, but non-commercial license + geometry-warp make it a throwaway baseline.

**Risks.** SDXL fidelity gap (C1); geometry warp + non-commercial output (C2); both object-centric training → whole-building generalization unproven; new backend to host and maintain.

**Experiment plan (attended).** Run MV-Adapter (image+geometry mode) seeded with the FLUX hero + our depth for all poses; if N doesn't fit 80GB, sliding overlapping windows with shared anchor frames. Measure back-view integrity, view0↔viewN loop diff, per-frame edge-align, max-N per pass, hero-identity survival. **Kill if** the SDXL look can't be graded to match the shipped hero, or windowing reintroduces the seam problem it was meant to remove. (Run SEVA one afternoon purely to bound achievable smoothness; do not build on it.)

## 3. Recommendation

**Try Candidate B (multi-hero anchoring + loop closure) FIRST**, because it is the lowest-risk, lowest-lift path that reuses everything already shipped (`reproject.ts` + the live FLUX A100 backend + our depth/canny/id locks), keeps the exact hero look, and its one blocker — cross-hero appearance agreement via IP-Adapter/Redux — **is now unblocked** in current diffusers. A 4–6-hero anchored reproject with gap-only inpaint could close the 360 in one attended session at ~$0.10/turntable, and MeSS is published proof the shape works at building scale. **If B's anchors won't agree on materials even with a shared reference (its live kill criterion), fall to Candidate A (Hunyuan3D-2.1-Paint, hero-seeded UV)** — the only option where loop closure and back views are *structurally impossible to fail*, now with **PBR output that re-lights natively in our engine** and a **commercial-friendly license**. Treat **Candidate C** as research only (SEVA's non-commercial output + documented geometry-warp rule it out for production). **Downstream, either B or A yields a set of truly 3D-consistent views → feed the existing `spike/modal_splat.py` bake to distill a 3DGS for a free, consistent walkthrough** — the splat distillation the repo is already wired for becomes a consumer of consistency, not a separate research bet.

## 4. Watch list (could change the answer)

1. **A FLUX-native mesh-paint or FLUX ControlNet-inpaint texturing model** (or a FLUX port of MV-Adapter / a FLUX.2-Fun texturing head). Any of these erases Candidate A's "SDXL/SD1.5 fidelity gap" and would likely make A the outright first choice over B.
2. **Hunyuan3D-Paint (or SeqTex) proving it ingests our exact per-view depth + poses**, not just a reference image. If our geometry lock plugs straight in, A's integration risk collapses and it leapfrogs B.
3. **A commercially-licensed, geometry-conditioned NVS video model** (SEVA-class quality without the non-commercial output clause, or a licensed CAT3D successor) — would revive Candidate C as a real production path for smooth fly-throughs, not just turntables.

## See also
[[STATE]] (NEXT #2c) · [[DECISIONS#web3d-reproject-consistency]] · [[SESSIONS]] (2026-06-15 multi-view A/B/C; 2026-07-03 video-warp red-team) · [[research/web3d-clientready]] · `apps/web3d-prototype/src/lib/reproject.ts` · `spike/modal_flux.py` · `spike/REPORTS/modal_flux.md`
