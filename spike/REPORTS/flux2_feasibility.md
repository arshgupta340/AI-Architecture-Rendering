# FLUX.2 hero backend — feasibility & deploy decision

**TL;DR.** FLUX.2-dev geometry-locked rendering is **feasible but heavyweight**: it needs an
**H200** (or A100-80GB with float8 quantization) and runs through the **VideoX-Fun**
framework (not diffusers), because FLUX.2's only canny/depth ControlNet is
`alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`. The backend is **written and deploy-gated**
(`spike/modal_flux2.py`); FLUX.1-dev + ControlNet-Union (`spike/modal_flux.py`) stays the
**live, verified default**. Switch by pointing the app's Hero Backend panel at the FLUX.2 URL.

## Why FLUX.1 is the default (and what FLUX.2 buys)

| | FLUX.1-dev + ControlNet-Union (LIVE) | FLUX.2-dev + Fun-Controlnet-Union (experimental) |
|---|---|---|
| Params | 12B DiT + T5/CLIP | **32B DiT + Mistral-Small-3.2-24B** text encoder |
| BF16 VRAM | fits A100-80GB | **~64–110 GB → "requires an H200"** (A100-80GB only w/ float8) |
| ControlNet | diffusers `FluxControlNetPipeline` (proven) | **VideoX-Fun** framework (`Flux2ControlPipeline`) |
| Geometry lock | **dual**: canny ∪ id-edges **+** depth (2 controls) | **single** structural control (we feed canny ∪ id-edges) |
| region_edit | full pass + server composite | **native inpaint** (mask + base image) ✅ upgrade |
| Cost / render | ~$0.01–0.02 (A100, ~15s warm) | ~2–4× (bigger model, H200 ~$4–6/hr, slower steps) |
| Status | **deployed + live-verified** | code written, **deploy-gated** |

**FLUX.2 upside:** newer model (stronger prompt-adherence / detail per BFL), a unified
ControlNet covering canny/depth/pose/HED/MLSD/scribble/gray, and **true inpainting** for
region edits (seam-consistent lighting vs FLUX.1's composite). **Downside:** larger/slower/
pricier, single-control geometry lock (we drop the depth massing channel — canny ∪ id-edges
already gives ~98.5% edge alignment, so this is an acceptable but real reduction), and the
VideoX-Fun stack is less battle-tested than diffusers.

## Hard facts (sources: HF model cards, willitrunai, VideoX-Fun repo, the ComfyUI port)

- **FLUX.2-dev** = 32B rectified-flow transformer + Mistral-24B text encoder. Naive
  diffusers load OOMs at ~178 GB (double-load bug); ~110 GB after the fix; **BF16 needs an
  H200/B200**. Quantized: Q8 ~35 GB, Q4/float8 ~17–20 GB DiT (+ control +3.6 GB).
- **The only FLUX.2 depth/canny ControlNet** is `alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`
  (~8.3 GB). It is **NOT** a diffusers `FluxControlNetModel`; it loads into the transformer
  via VideoX-Fun and runs through `Flux2ControlPipeline`. "FLUX.1 ControlNets are largely
  compatible with FLUX.2" (some catalogs) is misleading — the architectures differ.
- **Inference shape** (from `examples/flux2_fun/predict_t2i_control.py` + its z_image analog):
  `pipe(prompt, negative_prompt, height, width, generator, guidance_scale, image=inpaint,
  mask_image=mask, control_image=control, num_inference_steps, control_context_scale)`.
  Single `control_image`; **native inpaint** via `image`+`mask_image`. 260-ch control context
  = 128 control + 4 mask + 128 inpaint. ControlNet injected at 4 double-stream blocks.
  Recommended `control_context_scale` 0.65–0.80; detailed prompts strongly advised.
- **Memory modes** (VideoX-Fun): `""` (none, H200/B200), `model_cpu_offload`,
  `model_cpu_offload_and_qfloat8` (float8 DiT → fits **A100-80GB**), `sequential_cpu_offload`.

## What's built (`spike/modal_flux2.py`, deploy-gated)

- Separate Modal app `arch-rendering-flux2` (never rebuilds the live FLUX.1 app), shared
  `arch-rendering-weights` Volume + `arch-flux` secret.
- `GPU = "H200"` (one-line const) + `GPU_MEMORY_MODE` const (set to
  `"model_cpu_offload_and_qfloat8"` to run on A100-80GB instead).
- Image clones VideoX-Fun + installs its requirements; `warm_weights()` prefetches FLUX.2 +
  the Fun ControlNet to the Volume.
- **Same browser contract** as FLUX.1: CORS ASGI app with `/hero_render` + `/region_edit` +
  `/warm`, shared-secret in the body. Same `prep_canny` (canny ∪ id-edges) geometry lock.
  `region_edit` uses the **native inpaint** path.

### The one thing to validate on first deploy
The VideoX-Fun loader block in `HeroFlux2.load()` (the `videox_fun.*` import paths +
`Flux2ControlPipeline` construction) is written against the repo examples; class/module
names can drift between revisions. Confirm against the cloned repo at `/root/VideoX-Fun` on
the first deploy and adjust **only that block** — the Modal scaffolding, contract, CORS,
conditioning, and auth around it are final. (Same posture as the gsplat-build note in
`spike/modal_splat.py`.)

## To bring it up (one-time, user-authorized GPU spend)
```
# 1. Accept the FLUX.2-dev license at https://huggingface.co/black-forest-labs/FLUX.2-dev
#    (HF_TOKEN on the arch-flux secret already has access if it's the same account).
modal run    spike/modal_flux2.py::warm_weights   # ~70 GB download into the Volume (slow, one-time)
modal deploy spike/modal_flux2.py                 # publish; validate the loader block in load()
# 2. In the app: ⚙ Backend → FLUX.2 preset → paste …flux2-heroflux2-web.modal.run/{hero_render,region_edit}
```
Cost: the ~70 GB download is one-time (idle Volume storage is cheap); each render ~2–4×
FLUX.1's, on an H200 at ~$4–6/hr (idle = $0, scale-to-zero). **Recommendation:** keep FLUX.1
as the daily driver; deploy FLUX.2 when you want to A/B the quality on a specific hero frame.
