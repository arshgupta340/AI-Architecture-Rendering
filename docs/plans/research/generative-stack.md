# Generative Stack — Per-Stage Model Choices (mid-2026)

> Research date: 2026-06-11/12 (two Sonnet agents, web research). Feeds [master plan v2](../master-plan.md) and the [experiment ladder](../experiments.md). Prices as of June 2026; re-verify before committing spend.

## Headline shifts since the v1 plan

1. **BFL deprecated FLUX.1 Canny/Depth Pro API endpoints (Oct 31, 2025).** The B3 bake-off design predated this. Canonical hosting for FLUX ControlNets is now **fal.ai `flux-general`** ($0.075/MP, supports depth+canny+IP-Adapter together) and Replicate community variants.
2. **FLUX.2 [pro] Edit** (fal.ai, $0.03/MP) supersedes FLUX.1 Kontext for hosted editing: up to 9 reference images, 4MP output, addressable refs ("make the wall match @image2").
3. **SAM 3** (Meta, Nov 2025; 3.1 Mar 2026): +22% LVIS zero-shot mask AP over SAM 2 (47.0 vs 38.5); "presence head" addresses under-detection of repeated elements (our mullion failure). Self-host via Ultralytics; not first-class on Replicate yet.
4. **Vision Banana** (DeepMind, Apr 2026): see [§ Vision Banana](#vision-banana) — relevant, not yet usable.

## Stage 1 — Render (geometry-preserving photoreal)

| Rank | With host data (tier 1) | Notes |
|---|---|---|
| 1 | (watch) **Seg2Any** — perfect semantic map + per-region captions → photoreal, FLUX backbone | Research only (arXiv 2506.00596); no hosted API. Cleanest fit for our perfect-input path; monitor. |
| 2 | **FLUX.1-dev ControlNet depth+canny via fal `flux-general`** ($0.075/MP) | Feed TRUE z-buffer (normalized 0–255, slight gaussian blur to match the monocular-trained distribution; conditioning scale 0.5–0.8) + Canny from beauty pass. |
| 3 | **FLUX.2 [pro] Edit** i2i with depth map as extra reference ($0.03/MP) | Simpler; weaker structural lock. |

| Rank | Without host data (tier 2) | Notes |
|---|---|---|
| 1 | **FLUX.2 [pro] Edit** ($0.03/MP, fal) | Best hosted i2i; multi-ref. |
| 2 | FLUX.1-dev ControlNet Union Pro 2.0 (depth+canny, no seg mode) | More control, lower ceiling than single-purpose ControlNets. |
| 3 | **Nano Banana Pro** (current baseline) | Geometry-faithful mode but documented invent/crop/noise failures; keep as control. |

Architecture guidance from practitioners: Canny strength ~0.7 alone, or Canny 0.4 + Depth 0.5 combined.

## Stage 2+3 — Tag + Segment

**Tier 1 (plugin): stages deleted.** Host ID masks are ground truth; semantics from Revit categories / Rhino layers / SketchUp tags. Cheap VLM pass only to label objects with garbage layer names (labeling a *list* of cropped objects is far easier than detecting regions in pixels).

**Tier 2 (screenshot) recommended stack:**

```
1. Florence-2 (open-vocab detection; HF, ~free)        — prompts: wall, window, door, floor,
2. YOLOE parallel pass for repeated thin elements        ceiling, curtain wall, glazing mullion…
3. SAM 3 mask refinement (Ultralytics, self-host)
4. Mask validation: dilate mullion-class masks <4px before inpainting
```

Evidence: Gemini 3 Pro bbox ≈ 0.407 mAP (2020-era YOLO); T21 measured 0 mullions on a mullion-grid facade; SAM 2's low-res mask head documented to lose thin structures. DINO-X is the precision alternative to Florence-2 (enterprise API).

## Stage 4 — Apply material (the critical gap)

Measured problem (T24/T25): text-only conditioning → "a beige wall," not "this travertine."

| Rank | Hosted | Notes |
|---|---|---|
| 1 | **FLUX.2 [pro] Edit + swatch as reference** ($0.03/MP) | Best hosted; "travertine-like," not exact-swatch. CLIP-I ceiling ~82.5%. |
| 2 | fal `flux-general` inpainting + IP-Adapter ($0.075/MP) | True IP-Adapter conditioning + ControlNet in one call. |
| 3 | FLUX Fill [pro] + Redux ($0.05 + $0.04) | Upgrade of current baseline; global-style only. |
| 4 | FLUX.1 Kontext [pro] + swatch ($0.04) | Simple; style-level. |

| Rank | Self-hosted (fidelity ceiling) | Notes |
|---|---|---|
| 1 | **MatSwap** (`ilopes/matswap`, CGF 2025) | Light-aware material transfer: target + mask + swatch → 78% user preference over FLUX Fill/ZeST; PSNR +1.5dB. SD1.5 backbone (photorealism ceiling). **Accepts true normal maps — direct synergy with the host plugin.** Modal deploy. |
| 2 | **Refaçade** (arXiv 2512.04534) | Purpose-built facade retexturing (texture remover + jigsaw permutation). Evaluate. |
| 3 | ZeST (ECCV 2024) | Training-free, lower quality (PSNR 19.1). |

Watch: **HiFi-Inpaint** (CVPR 2026, FLUX-based, CLIP-I 95%) — human-product domain today; a retrain on PBR materials would be the dream stack. **Pinco** (ICCV 2025) — foreground-conditioned inpainting adapter for FLUX.

Decision (user-confirmed): hosted shootout first (experiment E3); MatSwap on Modal only if hosted fails the "blind viewer names the material" gate.

## Stage 5 — Multi-view material consistency

1. Same swatch refs via FLUX.2 multi-reference across all N views (+ fixed seed).
2. The proven in-house **anchor-reference technique**: render the aerial/establishing view first, feed it as a reference into every other view.
3. With host data: deterministic — same swatch + per-view masks/normals through MatSwap per view.
4. Research: MVPaint (CVPR 2025, mesh-level texturing), 3D-Adapter (ICLR 2025).

## Vision Banana

**What:** DeepMind instruction-tuned **Nano Banana Pro** into a generalist vision model ("Image Generators are Generalist Vision Learners", arXiv 2604.20329, Apr 2026; Kaiming He / Saining Xie sponsorship). Segmentation as image generation: prompt a class→color mapping, model paints a color-coded image, you decode masks. Also depth + normals + referring/reasoning segmentation.

**Benchmarks:** beats SAM 3 on zero-shot *semantic* seg (Cityscapes 0.699 vs 0.652 mIoU) and referring/reasoning seg; **loses on instance seg** (SA-Co pmF1 0.540 vs 0.661). No LVIS/ADE20K numbers; no architectural evaluation; thin-structure performance unknown (generative painting of 2px lines is unproven).

**Availability:** research artifact only — no public API, no weights (June 2026). **Veras v4.5 Smart Selection confirmed to use it** (EvolveLAB forum) → they have Google partner access; we cannot get the tuned model.

**Our play:**
- E4 probe: prompt the *public* base model (`gemini-3-pro-image-preview`, ~$0.13–0.24/image) with Vision-Banana-style color-coding instructions; decode; score IoU vs E1 ground truth. Cheap read on what Veras ships and whether prompting alone gets usable masks.
- Watch the [Gemini API changelog](https://ai.google.dev/gemini-api/docs/changelog) for a productized endpoint; if it ships, it could collapse tier-2 tag+segment into one call (referring-expression selection maps directly onto our click UX).
- It does NOT change tier 1: host ID masks are exact and free.

## Pricing quick reference (June 2026)

| Use | Model | Cost |
|---|---|---|
| Render | FLUX.2 [pro] Edit (fal) | $0.03/MP |
| Render w/ ControlNets+IP-Adapter | fal flux-general | $0.075/MP |
| Inpaint | FLUX Fill [pro] | $0.05/MP |
| Edit | FLUX Kontext [pro] | $0.04/img |
| Tag (VLM) | Gemini 3.x Flash | ~$0.0014/call |
| Segment | SAM 2 (Replicate) | $0.013/run |
| Segment | SAM 3 (Ultralytics) | self-host GPU only |
| Seg probe | Nano Banana Pro (color-coded) | ~$0.13–0.24/img |
| Material (self-host) | MatSwap on GPU | ~$0.01–0.05/img + setup |
