---
type: research
updated: 2026-07-13
---

# Full-360 multi-view-consistent hero: options anchored to a known mesh

> Seeds the next attended session on the open [[STATE]] "Multi-view hero" follow-up. Anchor decision: [[DECISIONS#web3d-reproject-consistency]]. Current engine: `apps/web3d-prototype/src/lib/reproject.ts` (projective-texture reproject) + a self-hosted FLUX.1-dev + ControlNet-Union (depth ∪ canny ∪ id-edge) hero backend on Modal A100 (`spike/modal_flux.py`).

## 1. Problem statement

We can already make ONE geometry-locked photoreal still (FLUX hero) and reproject its pixels onto the real mesh to synthesize **nearby** angles with perfect material/lighting consistency (verified). The open failure is a **full 360° turntable**: our current method chains forward around the circle — each new view reprojects its already-rendered neighbours and inpaints the disoccluded gaps with `/region_edit`. Chained gap-fill inpainting cannot *reconstruct* sides the hero never saw (the back of the building dissolves into the ground), appearance **drifts** as errors compound view-to-view, and there is **no loop closure** (view N-1 and view 0 disagree where the circle meets). The root cause is that appearance lives in **2D image space and propagates sequentially**. Every credible fix below moves appearance into a **global representation anchored to the mesh we already own** (exact geometry + depth + normals + semantic IDs + UVs for every view — the rare luxury here), so that "unseen" and "loop closure" stop being special cases.

## 2. Three candidate approaches

### Candidate A — Texture-space synchronized multi-view diffusion (bake appearance INTO the mesh's UV texture)

**How it works.** Instead of generating images and trying to keep them consistent, generate a single **global UV texture** for the mesh. Methods in the SyncMVD / TexFusion / MVPaint lineage render the mesh from N cameras, run a diffusion denoise step on all N views, then **project every view's latent/pixel back into the shared UV atlas and blend** before the next denoise step. Consistency is enforced in UV space every step, so all views literally read from one texture. Depth-ControlNet locks each view to the true geometry. Once the texture is baked, the full 360 renders in three.js **for free and exactly consistent** — loop closure and back views are structurally impossible to get wrong because there is only one texture covering the whole surface.

**Evidence (code exists unless noted).**
- SyncMVD — "Text-Guided Texturing by Synchronized Multi-View Diffusion," SIGGRAPH Asia 2024 (arXiv [2311.12891](https://arxiv.org/abs/2311.12891)). Official PyTorch+Diffusers repo: [github.com/LIU-Yuxin/SyncMVD](https://github.com/LIU-Yuxin/SyncMVD). Uses a **depth-conditioned ControlNet v1-1 on SD1.5**, PyTorch3D for render/back-project, latent UV size 1536 / view res 768; needs clean non-overlapping UVs or falls back to xatlas auto-unwrap.
- MVPaint — "Synchronized Multi-View Diffusion for Painting Anything 3D," arXiv [2411.02336](https://arxiv.org/html/2411.02336v1) (Nov 2024), project page [mvpaint.github.io](https://mvpaint.github.io/).
- TexFusion — NVIDIA, arXiv [2310.13772](https://arxiv.org/html/2310.13772) ([project](https://research.nvidia.com/labs/toronto-ai/texfusion/)); FlashTex (relightable, arXiv [2402.13251](https://arxiv.org/pdf/2402.13251)).
- 2025 successors: RomanTex (arXiv [2503.19011](https://arxiv.org/html/2503.19011v1), Mar 2025, 3D-aware attention); Im2SurfTex (arXiv [2502.14006](https://arxiv.org/pdf/2502.14006), Feb 2025, neural back-projection); LumiTex (arXiv [2511.19437](https://arxiv.org/pdf/2511.19437), Nov 2025, PBR + illumination) — *code availability unconfirmed for the 2025 three*. Survey: "Advances in Neural 3D Mesh Texturing" (arXiv 2606.00137).

**Fit to our stack.** Excellent. We already own the mesh, per-view depth/normal buffers, and the three.js render loop — SyncMVD's render/back-project step is essentially what `reproject.ts` already does, in reverse. **Hybrid worth prototyping:** seed the UV atlas by reprojecting our existing **FLUX hero** pixels into UV (reuse `reproject.ts` machinery), then run synchronized diffusion ONLY to fill/harmonize the unseen UV regions — this preserves the shipped FLUX hero look where the hero saw it and only *invents* the unseen sides. Per-region material edits map cleanly onto UV regions keyed by our **semantic IDs** (edit the texture per-island, non-destructive).

**Experiment plan.** Build: a Modal A100 job wrapping SyncMVD on our `house_pt.glb` (dequantized) with xatlas UVs; feed our depth ControlNet; optionally the hero-seeded-UV hybrid. Measure: (a) 360 turntable rendered in-app — visual back-view integrity (does the building survive?), (b) loop-closure error (pixel/LPIPS diff between view 0 and the wrapped-around last view — should be ~0 by construction), (c) edge-alignment vs geometry using our existing canny∪id metric, (d) whether hero-seeded regions stay byte-stable. Expected cost: **~$0.15–0.40/full-texture** on A100 (many denoise steps × N views; more than one hero but amortized across ALL 360 frames). Engineering lift: **medium-high** (PyTorch3D + xatlas + diffusers pin on Modal; UV cleanup on our mesh is the main unknown).

**Risks.** (1) Base model is **SD1.5/SDXL depth ControlNet, not FLUX** → lower fidelity than our shipped hero, and the look changes (baked albedo-ish texture re-lit by three.js loses FLUX's baked photoreal lighting) — the hero-seeded hybrid mitigates this. (2) Our UVs are box-projected world-feet (good for tiling swatches, not a clean atlas) → likely need xatlas re-unwrap, which changes the material-edit UV keys. (3) SyncMVD tuned for objects, not whole buildings with interiors/thin trim; seams on large flat facades possible.

### Candidate B — Simultaneous multi-view generation with cross-view attention + our ControlNet locks

**How it works.** Generate all N turntable frames **in one joint denoising pass** where the U-Net's self-attention is extended to attend **across views** (every frame sees every other frame each step). Consistency — including loop closure — is "by construction" because there is no sequential chain; view 0 and view N-1 are denoised together and see each other. Camera pose + geometry (our depth/normals) enter through a unified condition encoder, so each frame stays geometry-locked. This is the "batched generation with cross-view attention + depth ControlNet" family.

**Evidence (code exists).**
- MV-Adapter — "Multi-view Consistent Image Generation Made Easy," ICCV 2025, arXiv [2412.03632](https://arxiv.org/abs/2412.03632), repo [github.com/huanngzh/MV-Adapter](https://github.com/huanngzh/MV-Adapter). A **plug-and-play adapter** (duplicated self-attention + parallel attention + unified condition encoder for **camera params AND geometry**) on **SDXL at 768**, trained without touching the base weights → supports text+geometry and image+geometry conditioned multi-view + texturing. *Base is SDXL; no confirmed FLUX port.*
- MeSS — "City Mesh-Guided Outdoor Scene Generation with Cross-View Consistent Diffusion," arXiv [2508.15169](https://arxiv.org/abs/2508.15169) (Aug 2025, TU Munich/ETH/Wuhan/Huawei). **Almost exactly our setup**: textureless **building meshes** → ControlNet generates key views in reverse order transferring info backward, projects all pixels onto the mesh as 2D Gaussian surfels, fills intermediate views with Appearance-Guided Inpainting, and a **Global Consistency Alignment simultaneously denoises multi-view renderings**. Strong prior art that this family handles architecture at 360. *Code availability unconfirmed (listed in Awesome-3D-Scene-Generation).*
- Supporting: MvDeDiffusion (cross-view deformable attention, 2025); "Multi-View Depth Consistent Image Generation" (CAADRIA 2025, [caadria2025_567](https://papers.cumincad.org/data/works/att/caadria2025_567.pdf)) — architecture-specific, ControlNet backbone tuned to multi-view building models.

**Fit to our stack.** Good. Consumes exactly the conditioning we already generate (depth + canny + id-edges + camera pose). Output stays a set of per-frame **images** closer to the hero's look than a baked texture. But it's a **new model to self-host** (SDXL + adapter on Modal), not an add-on to the deployed FLUX backend, and joint attention means **memory scales with N** → caps how dense a single-pass 360 can be (likely tile into overlapping windows, reintroducing a mild seam-management problem).

**Experiment plan.** Build: Modal A100/H200 job running MV-Adapter (image+geometry mode) seeded with our FLUX hero as the image condition + our depth for all N poses; if N doesn't fit, sliding overlapping windows with shared anchor frames. Measure: back-view integrity, view-0↔view-N loop diff, per-frame edge-alignment (canny∪id), max N views per pass on 80GB, whether the hero identity survives as the image condition. Expected cost: **~$0.10–0.30/turntable** (one big batched inference). Lift: **medium** (repo is turnkey inference; integration = pose export + condition plumbing we mostly have).

**Risks.** (1) **SDXL not FLUX** → fidelity/style gap vs the shipped hero; the hero becomes a soft image-prompt, not the literal output. (2) N-view memory ceiling → windowing → partial return of the seam/loop problem. (3) Adapter trained on Objaverse-style objects; whole-building generalization is the open question MeSS suggests is solvable but with more machinery.

### Candidate C — Video-diffusion camera-orbit with 3D camera control (fast baseline / smoothness upper bound)

**How it works.** Treat the turntable as a **camera-controlled video**: give a diffusion NVS model our hero as the input view + an explicit orbit trajectory, and it renders temporally smooth novel views around the building. Temporal attention gives frame-to-frame coherence "for free"; some models accept multiple input views (front + back hero anchors) to constrain the far side.

**Evidence (code + weights exist).**
- Stable Virtual Camera — Stability AI, arXiv [2503.14489](https://arxiv.org/abs/2503.14489) (Mar 2025; v1.1 Jun 2025). 1.3B generalist NVS diffusion, **arbitrary target camera trajectory**, any number of input views, reports beating CAT3D and ViewCrafter. Repo [github.com/Stability-AI/stable-virtual-camera](https://github.com/Stability-ai/stable-virtual-camera) + [HF checkpoint](https://huggingface.co/stabilityai/stable-virtual-camera) (non-commercial license — check before productizing).
- Lineage/alternatives: CAT3D (Google, 2024, no public weights); SV3D (Stability, orbit video, 2024); Cavia (view-integrated attention, arXiv 2410.10774); PostCam (arXiv 2511.17185, Nov 2025, camera-controllable NVS video).

**Fit to our stack.** Lowest lift to *try* — released weights, image-conditioned on our hero, arbitrary orbit. **But** it does NOT natively consume our depth/semantic locks (camera pose only), so our exact geometry and per-region material edits are **not guaranteed** — and our own grand-idea red team already found **AI video warps building geometry across camera motion** (see [[SESSIONS]] 2026-07-03; all hosted video models). Best used as a **fast baseline** and an upper bound on temporal smoothness, and as a **prior** whose frames are then snapped back onto the true mesh via `reproject.ts` (video → reproject → keep only geometry-valid pixels).

**Experiment plan.** Build: run Stable Virtual Camera on Modal with the hero (+ optional back-anchor hero) and a 360 orbit; then pass its frames through our existing reproject to measure how much survives the geometry snap. Measure: geometry warp (edge-alignment drift vs our depth), loop closure, material-edit survival, subjective smoothness. Expected cost: **~$0.05–0.15/orbit** on A100 (single video pass). Lift: **low** to try, **high** to make production-safe (fighting geometry warp).

**Risks.** Geometry warp (documented, load-bearing), no semantic/material lock, non-commercial license, object-centric training (buildings + ground plane may confuse it).

## 3. Recommendation

**Try Candidate A (texture-space synchronized diffusion, SyncMVD/MVPaint lineage), in the FLUX-hero-seeded-UV hybrid form, first.** It is the only option where loop closure and back-view reconstruction are *structurally impossible to fail* (one global UV texture covering the whole mesh, rendered 360 for free in the three.js pipeline we already own), it maximally exploits our rare luxury (exact mesh + depth + semantic IDs + reprojection code we can reuse for the UV back-projection), and per-region material edits map to UV islands keyed by semantic ID. Run **Candidate B (MV-Adapter)** in parallel as the fidelity fallback if the SD-based texture look can't match the shipped FLUX hero, and use **Candidate C** only as a one-day baseline to bound achievable smoothness — do not build production on it given the documented geometry-warp risk.

## See also
[[STATE]] · [[DECISIONS#web3d-reproject-consistency]] · [[SESSIONS]] (2026-06-15 multi-view A/B/C; 2026-07-03 video-warp red-team) · [[research/web3d-clientready]] · `apps/web3d-prototype/src/lib/reproject.ts` · `spike/modal_flux.py`
