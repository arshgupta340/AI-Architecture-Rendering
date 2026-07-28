---
type: research
topic: full-360 multi-view-consistent hero rendering with a ground-truth mesh anchor
created: 2026-07-23
status: memo (no code changes)
---

# Full-360 options — multi-view-consistent diffusion when a real mesh anchor exists

> **Relation to the canonical memo:** an earlier survey lives at
> [wiki/research/full360-options.md](../wiki/research/full360-options.md) (refreshed 2026-07-18).
> This 2026-07-23 sweep was run independently and **converges on the same first choice**
> (multi-anchor + loop closure on the shipped FLUX stack, MeSS as precedent). New here:
> FlashTex (relightable texture bake), the GCAlign-style exposure-harmonisation step,
> MV-Adapter-as-anchor-generator as the escalation path, and SEVA's 576p output cap.
> Known there but not here: **Hunyuan3D-2.1-Paint** (permissive-commercial, PBR,
> mesh-conditioned) as the strongest texture-bake candidate. Read both before the next
> attended session; the wiki memo remains canonical.

## 1. Problem statement

The web3d app already ships a live-verified per-view turntable: N same-seed FLUX.1-dev
+ ControlNet-Union base renders from the real three.js mesh, plus `lib/reproject.ts`, which
projective-texture-maps hero pixels onto the real mesh (semantic IDs, depth + canny∪id-edge
conditioning) and carries them to nearby cameras, inpainting disocclusion gaps via `/region_edit`.
That reproject **core is verified for nearby angles** — materials and lighting are consistent *by
construction* because they ride the real geometry. The failure is the **full-360 CHAINED**
turntable: propagating appearance forward around the circle, the building **dissolves in the back
views** because a pure forward chain never has a source that saw the back — chained gap-fill cannot
*reconstruct* unseen sides, and grazing smear compounds. The team's standing hypothesis (from
`SESSIONS.md`, 2026-06-15) is that this needs **multiple hero anchors at spaced azimuths + loop
closure**, not a forward chain. This memo surveys 2025-26 approaches that exploit the one asset most
methods lack — the ground-truth mesh with semantic IDs — and recommends what to try first.

## 2. Three candidate approaches

### Approach A — Multi-anchor + loop-closure inpainting on the existing FLUX pipeline (team hypothesis)

**What it is.** Instead of a forward chain from a single hero, render **K full FLUX hero anchors at
spaced azimuths** (e.g. 4-6 poses: front, back, both sides ± obliques), each independently locked to
the same mesh via ControlNet-Union (depth + canny∪id-edge) and the same seed/prompt. Then, for every
in-between camera, reproject from **the two nearest anchors on each side** (the existing
`reproject.ts` machinery already does quality-weighted multi-source blend), so every surface has a
near-square source from *some* anchor — no region stays unseen. A final **loop-closure /
global-consistency pass** harmonises exposure and seam colour across the ring, and `/region_edit`
inpaints only the residual grazing gaps.

**Prior art validating the pattern (all real, dated):**
- **Instruct-NeRF2NeRF** (ICCV 2023, still the canonical reference) — its *Iterative Dataset Update*
  shows that per-frame 2D diffusion edits become globally 3D-consistent only when repeatedly
  consolidated against a shared 3D representation; a naive independent-per-view pass drifts. Our mesh
  is that shared representation. https://instruct-nerf2nerf.github.io/ · https://arxiv.org/abs/2303.12789
- **MeSS: City Mesh-Guided Outdoor Scene Generation with Cross-View Consistent Diffusion**
  (arXiv 2508.15169, submitted 2025-08-21, rev 2026-01-04) — *the closest published analogue to our
  exact problem*: untextured **city mesh** → photoreal multi-view via **image-diffusion + ControlNet**
  (explicitly chosen over video diffusion "to better maintain geometry-aligned results"). Its
  three-stage recipe is almost exactly this approach: **(1) Cascaded Outpainting ControlNets** =
  sparse anchor views, **(2) AGInpaint** = dense in-between propagation, **(3) GCAlign** = global
  consistency / exposure harmonisation. Validates cascaded anchors + inpaint-propagate + global-align
  on a ControlNet stack like ours. https://arxiv.org/abs/2508.15169
- **SIn-NeRF2NeRF** (arXiv 2408.13285, 2024) — segmentation + inpainting for disocclusion during
  scene edits; a reference for the gap-fill mask design. https://arxiv.org/abs/2408.13285

**Why it fits our stack.** Zero new models. Reuses `modal_flux.py`, ControlNet-Union, `reproject.ts`,
and `/region_edit`. The mesh gives free, exact anchor poses and per-pixel occlusion. It directly tests
the team's own hypothesis and is the lowest-lift path from today's verified nearby-angle core.

**Experiment plan (Modal A100-80GB, ~$2-4/hr → ~$0.01-0.02 per warm FLUX pass):**
1. Add a `heroAnchorsFn` that renders K=4 (then 6) same-seed anchors at even azimuths; keep depth+id
   buffers per anchor. (~4-6 × 15 s warm ≈ $0.02-0.03.)
2. Change the turntable from forward-chain to **nearest-two-anchor reproject** per target view
   (reproject.ts already supports multi-source; feed it the two bracketing anchors, not the previous
   frame).
3. Add a **GCAlign-style** pass: per-view low-freq exposure/white-balance normalisation to the anchor
   ring mean (cheap, CPU/GPU; reuse the honest-illuminant de-light trick from the 2026-06-14 session).
4. Inpaint only residual grazing gaps via `/region_edit`.
5. **Success =** a 12-view turntable where the building is present and identity-stable in ALL views
   (no back-view dissolve), inter-view material ΔE_ab within the ~1-2 band already achieved for nearby
   angles, and seams invisible after GCAlign. Full sweep est. **$0.10-0.20** of GPU.

**Risks.** Independent anchors can still disagree where their coverage overlaps (seed helps but does
not guarantee cross-anchor material identity) → seam blends may need feathering + GCAlign to hide.
Grazing bands between anchors may still smear if K is too small. Loop closure is an exposure/colour
fix, not a geometry fix — but geometry is already carried by the mesh, so this is the right division
of labour.

### Approach B — Synthesize a consistent TEXTURE on the mesh once, then render classically

**What it is.** Stop chaining screen-space renders entirely. Use a mesh-texturing diffusion method to
bake **one view-consistent texture (ideally PBR/albedo) into the mesh's UV space**, then render all
360 views with the ordinary three.js/path-tracer already in the app. Consistency becomes *definitional*
— it is one texture rendered from many cameras.

**Evidence / lineage (real, dated):**
- **SyncMVD / "Text-Guided Texturing by Synchronized Multi-View Diffusion"** (arXiv 2311.12891) —
  synchronises multi-view denoising in UV latent space; the seam-consistency workhorse. MVPaint
  (CVPR 2025) code carries the lineage: https://github.com/3DTopia/MVPaint · https://arxiv.org/abs/2311.12891
- **FlashTex: Fast Relightable Mesh Texturing with LightControlNet** (ECCV 2024, Roblox) — *disentangles
  lighting from material* so the texture is **relightable** (critical for architecture: the same
  building re-lit for different times of day). Code released.
  https://flashtex.github.io/ · https://github.com/Roblox/FlashTex
- **TEXGen: a Generative Diffusion Model for Mesh Textures** (arXiv 2411.14740, NeurIPS 2024) — a
  *feed-forward* diffusion directly on the UV/point-cloud domain, not per-view optimisation →
  scalable. https://arxiv.org/abs/2411.14740
- **SeqTex: Generate Mesh Textures in Video Sequence** (arXiv 2507.04285, 2025-07-06, newest) —
  reframes texturing as sequence generation on a **video foundation model**, image- or text-conditioned,
  with geometry-informed cross-domain attention; generates the **full UV map directly** rather than
  post-processing multi-view images. https://arxiv.org/abs/2507.04285

**Why it fits (and strains).** Fits: our mesh + semantic IDs + box-projected world-feet UVs are exactly
these methods' inputs, and per-facet material edits map naturally to per-semantic-region texturing.
FlashTex's relightable output composes with the app's existing sun/HDRI lighting. Strains: (1) these
methods target *object* texturing; a whole building + entourage + ground is larger scope; (2) they
produce a **material/albedo texture**, not FLUX's photoreal "hero look" with baked ambient occlusion,
soft shadows, and atmosphere — so the wow-factor last-10% would come back from the app's PT/WebGPU
renderer, not from FLUX; (3) most (except FlashTex/MVPaint) have **no released weights** we can drop into
Modal.

**Experiment plan (Modal A100/H200):**
1. Start with **FlashTex** (code + relightable output) on a single semantic region (e.g. roof or wall)
   of `house_pt.glb`; bake an albedo/PBR texture into that region's UV island.
2. Render the region across 360° in the app's path tracer; compare material consistency + relight
   behaviour vs the FLUX turntable.
3. If promising, extend to all facets; evaluate SeqTex/TEXGen only if their weights are released.
4. **Success =** a single baked texture that renders 360° with zero cross-view drift and correct
   re-lighting, at a look the architect accepts as a base layer. Est. FlashTex SDS-optimisation run
   **$0.30-0.80** per building (SDS is minutes on A100).

**Risks.** Look gap vs FLUX photoreal is real — this trades "photoreal-in-one-shot" for
"consistent-and-relightable, renderer-dependent polish." UV seams on complex architectural geometry.
Biggest scope change to the pipeline of the three options.

### Approach C — Geometry-conditioned multi-view diffusion model (MV-Adapter; SEVA noted)

**What it is.** Replace per-view FLUX with a model that generates all views *jointly*, conditioned on
the mesh geometry, so cross-view consistency is learned in the network rather than reconstructed
afterward.

**Primary candidate — MV-Adapter** (ICCV 2025; arXiv 2412.03632; geometry-conditioned adapters
released 2025-06, <10 GB VRAM). A plug-and-play adapter that gives an existing T2I base **multi-view
attention** + a **geometry condition guider** fed exactly the signals we can render for free from the
mesh: **position maps + normal maps** (per-pixel 3D correspondence across views). Supports
**image-conditioning** (lock to our hero) and is **ControlNet-compatible**.
https://github.com/huanngzh/MV-Adapter · https://huanngzh.github.io/MV-Adapter-Page/ · https://arxiv.org/abs/2412.03632
· ComfyUI nodes: https://github.com/huanngzh/ComfyUI-MVAdapter

**Secondary — Stable Virtual Camera / SEVA** (Stability AI, arXiv 2503.14489, v1.1 2025-06). Generalist
"M-in N-out" NVS diffusion with 3D camera-trajectory control; SOTA vs CAT3D/ViewCrafter.
https://stable-virtual-camera.github.io/ · https://github.com/Stability-AI/stable-virtual-camera —
**but two hard strikes for a commercial product: (1) non-commercial license, (2) max output 576p**,
far below hero-render resolution. Useful as a research yardstick, not a shippable backbone.

**Why it fits (and strains).** Fits: MV-Adapter's geometry conditioning is a native consumer of our
mesh; joint multi-view attention is the principled cure for chained drift; image-conditioning could
also be the **IP-Adapter replacement** that experiment B in the 2026-06-15 session was blocked on
(diffusers 0.32.2 had no FLUX `load_ip_adapter` — note: the 2026-07-18 wiki survey verified this
block is **lifted** in current diffusers, `FluxControlNetPipeline` now inherits `FluxIPAdapterMixin`,
so a diffusers bump also unblocks Redux/IP-Adapter directly on FLUX). Strains: MV-Adapter's released backbones are **SDXL /
SD2.1, not FLUX** — adopting it means running a *second, non-FLUX* renderer (or fine-tuning), and its
768px multiview tiles are lower-res than the FLUX hero, so it may serve better as a **consistency
prior / anchor generator** than as the final-resolution renderer.

**Experiment plan (Modal A100-80GB):**
1. Stand up MV-Adapter SDXL image-to-multiview + geometry (position/normal maps from the mesh) on Modal;
   feed the FLUX hero as the image condition. (~1 GPU-hr setup; inference cheap, <10 GB.)
2. Generate 6-8 consistent multiview tiles; use them as the **K anchors** for Approach A's reproject
   (best-of-both: MV-Adapter guarantees anchor agreement, FLUX/reproject supplies resolution + polish).
3. **Success =** MV-Adapter anchors are mutually consistent (no back-view loss) AND, once reprojected,
   the turntable matches the app's hero look. Est. **$0.10-0.30** per building incl. setup amortised.

**Risks.** Two-backbone complexity; SDXL look ≠ FLUX look (style seam where MV-Adapter regions meet FLUX
hero pixels — mitigated by using it only for anchor *placement*, not final pixels). SEVA is out on
license + resolution.

## 3. Recommendation — try Approach A first

Try **Approach A (multi-anchor + loop-closure on the existing FLUX pipeline) in the next attended
session.** It is the lowest-lift, highest-confidence path: it adds no new model, reuses the already-
verified `reproject.ts` multi-source core and `/region_edit`, and directly tests the team's own
hypothesis — the only missing pieces are (a) render K spaced full anchors instead of one, (b) reproject
each target from its two bracketing anchors instead of the previous frame, and (c) a cheap GCAlign-style
exposure/white-balance harmonisation, all backed by the **MeSS** (Aug 2025) three-stage precedent that
solves this exact mesh-guided, ControlNet-based, cross-view problem for city meshes. Estimated GPU cost
is **~$0.10-0.20** for a full 12-view sweep — within a normal attended session. If back-view dissolve
persists even with bracketing anchors, escalate to **Approach C's MV-Adapter as an anchor generator**
(consistency guaranteed in-network, then reprojected at FLUX resolution). Hold **Approach B
(texture-on-mesh)** as the strategic bet if the product ever needs true 360° free-orbit rather than a
finite turntable — it is definitionally consistent but the largest pipeline change and trades FLUX's
one-shot photoreal look for renderer-dependent polish.

## 2026-07-28 delta survey

DELTA sweep for developments since ~2026-07-20. **Recommendation UNCHANGED** (Approach A / multi-hero
anchoring + loop closure first). Two findings worth recording, both *corroborating* not *redirecting*:

1. **WorldMesh — a code-released, architecture-scale instantiation of the recommended approach.**
   *Navigable Multi-Room 3D Scenes via Mesh-Conditioned Image Diffusion*, arXiv 2603.22972v3
   (v3 submitted 2026-07-05; code + data at https://mschneider456.github.io/world-mesh/). Not in either
   prior memo. It builds an explicit mesh scaffold, conditions image diffusion on **mesh-rendered depth
   + color**, keeps cross-view style coherent via **greedy nearest-neighbour camera selection**, then
   **projects synthesized images back onto mesh surfaces to accumulate consistent textures
   progressively**, with **edge-recall validation** against mesh depth. This is almost exactly Approach
   A's shape (mesh-anchored ControlNet-style diffusion → back-project → progressive accumulate →
   structural-fidelity check), now the strongest *building-scale* published analogue beside MeSS — and
   unlike MeSS it ships code. **What changes:** nothing in the ranking; it adds a second published
   validation of Approach A and a concrete reference implementation to mine for the back-projection /
   camera-ordering / edge-recall details. https://arxiv.org/abs/2603.22972

2. **diffusers IP-Adapter unblock is confirmed merged (not just `main`).** The exact block the memos
   cite — issue #10689, "Support IPAdapter for all Flux pipelines, not only txt2img" — is now
   **Closed / Done**, i.e. `FluxControlNetPipeline` officially inherits `FluxIPAdapterMixin` in a tagged
   line (per HF docs + closed issue). I could not pin the precise version tag from public release notes
   (fetch was unreliable), so the Approach-A experiment plan should still smoke-test the multi-controlnet
   batching path after the bump, as the memo already says. https://github.com/huggingface/diffusers/issues/10689
   · https://huggingface.co/docs/diffusers/en/api/pipelines/controlnet_flux

**Not material (checked, no change):**
- **Hunyuan3D-2.5** — tech report predates the window (2025-06-23); PBR multi-view paint is the same
  lineage as the already-covered Hunyuan3D-2.1-Paint fallback; no new open-weights *Paint* drop or
  license change found post-2026-07-20. Fallback stands as written. https://arxiv.org/abs/2506.16504
- **Object-scale texture-bake churn** (VCD-Texture, RomanTex, AssetGen, MD-ProjTex) — same
  SyncMVD/Hunyuan lineage the memos already survey under Approach B; nothing that closes B's
  building-scale / FLUX-look gap.
- **Watch-list add:** **FLUX.2** ControlNet support is landing in diffusers (e.g. "Flux.2 Dev Fun
  ControlNet", issue #13351). No FLUX.2 mesh-paint or multi-view head yet — but a FLUX-native texturing
  backbone remains the one development that would promote the texture-bake route over anchoring; keep
  watching. https://github.com/huggingface/diffusers/issues/13351
