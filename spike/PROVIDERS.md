# Providers

One paragraph per third-party image API the Spike 2.5 bake-off can call. Each
section names the signup URL, the published per-image price (subject to drift
— check the provider before you trust this file), whether there's a free tier,
and which renderer class in `spike/renderers/` consumes the corresponding
environment variable. The `compare_renderers.py` driver iterates every
renderer subclass and only instantiates the ones whose `env_var` is present in
the environment, so you can run a partial bake-off by populating only the
providers you care about.

**Revised May 2026.** Several provider APIs changed since the original T03–T06
client scaffolding: BFL deprecated `flux-pro-1.1-canny` and `flux-pro-1.1-kontext`
in favor of `flux-2-pro`, moved its base host from `api.bfl.ml` to `api.bfl.ai`,
and removed the public Depth Pro endpoint; Magnific (now Freepik-owned) moved
to `api.magnific.com` with a new auth header and `structure_reference` body
field; Recraft's Replicate listing for V3 is text-to-image only with no
image-to-image variant, so the `RecraftV3ReplicateRenderer` class has been
removed (use the native Recraft API instead). The seven renderers below
reflect the current valid set.

## Google (Nano Banana Pro via Modal)

Google AI Studio hosts Gemini 2.5 Flash Image (aka "Nano Banana Pro"), the
image-edit model that powered Spike 2 and is our incumbent. The key lives in
Google AI Studio at https://aistudio.google.com/apikey — free tier exists but
is heavily rate-limited; paid usage is billed through Google Cloud at roughly
**$0.039 per output image** (1024×1024 equivalent). We don't hit the Google
API directly from the host; instead `spike/renderers/nano_banana.py:NanoBananaProRenderer`
gates on `GOOGLE_API_KEY` locally and calls the existing Modal function
`render_from_model_view`, which in turn reads the real key from a Modal Secret.
Modal CLI auth (`modal token new`, or `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET`)
is required at call time but is not checked at import.

## Black Forest Labs (FLUX 2 Pro + FLUX Fill Pro)

Black Forest Labs is the company behind FLUX. As of May 2026 the canonical
base URL is `https://api.bfl.ai/v1/` (the older `api.bfl.ml` host still
resolves but is no longer documented). Sign up at https://dashboard.bfl.ai/
and top up — there is **no free tier**. The two BFL renderers in the bake-off:

- `Flux2ProRenderer` calls `POST /v1/flux-2-pro`. This is the current
  recommended image-edit endpoint; it replaces both the deprecated
  `flux-pro-1.1-canny` and `flux-pro-1.1-kontext` paths. Listed at
  approximately **$0.03 per image**. The screenshot is sent in `input_image`
  (base64); optional inputs include `seed`, `width`, `height`,
  `safety_tolerance`, `output_format`.
- `FluxFillProRenderer` calls `POST /v1/flux-pro-1.0-fill`. Mask-based
  inpainting endpoint, fired without a mask in B3 to characterize what FLUX
  Fill produces in this configuration. Listed at approximately
  **$0.05 per image**. The screenshot is sent in `image`; `mask` is omitted.

Both endpoints use a submit-then-poll flow: the submit response includes a
`polling_url` we GET until `status == "Ready"`, with the result PNG URL at
`result.sample`. Both classes read `BFL_API_KEY` from the environment and
authenticate via the `x-key` header. Both live in `spike/renderers/flux_bfl.py`.

## Replicate (Qwen-Image-Edit, HiDream-E1.1)

Replicate is a generic model-hosting platform at https://replicate.com/. We
use it as a single entry point for two image-edit models we don't want to host
ourselves: `qwen/qwen-image-edit` and `prunaai/hidream-e1-1`. Pricing is
per-model and metered to the second of GPU time; the bake-off uses rough
per-image estimates of **$0.03** (Qwen) and **$0.04** (HiDream-E1.1) — see the
`cost_per_call_usd` attribute on each class for the value of record. The
HiDream pin moved from `hidream-e1` to `hidream-e1-1` because e1.1 accepts
natural-language prompts directly (e1.0 required structured prompt formatting
our defaults don't follow). New accounts get a small free credit; after that
you must add a card. Get a token at https://replicate.com/account/api-tokens.
`spike/renderers/replicate_models.py` defines `QwenImageEditRenderer` and
`HiDreamE1Renderer`, both sharing `REPLICATE_API_TOKEN`.

**Removed:** `RecraftV3ReplicateRenderer` was deleted in May 2026 because
Replicate's `recraft-ai/recraft-v3` endpoint is text-to-image only — its
`input` schema has no `image` field. Use the native Recraft client below.

## fal.ai (reserved)

fal.ai (https://fal.ai/) is another GPU-hosting platform that exposes FLUX,
Recraft, and a long tail of community models behind a unified HTTP API. We do
**not** currently ship a fal-backed renderer class, but the bake-off plan
reserves `FAL_KEY` so a future `spike/renderers/fal_*.py` can drop in without
forcing another `.env` edit on the architect. Sign up at
https://fal.ai/dashboard/keys; pricing is per-model and roughly competitive
with Replicate (a few cents per FLUX-class image). No free tier worth relying
on. **No renderer class consumes `FAL_KEY` today** — leave it blank unless
you're prototyping a new client.

## Magnific (Freepik / Magnific.ai — Mystic)

Magnific (https://magnific.com/, owned by Freepik since late 2024) sells
"Mystic" image generation through a public API. The endpoint as of May 2026 is
`POST https://api.magnific.com/v1/ai/mystic`; the older `api.magnific.ai` host
is no longer the documented path. Authentication is via the
`x-magnific-api-key` header (not `Authorization: Bearer`). Pricing is roughly
**$0.10 per image** for the Mystic endpoint — the most expensive renderer in
the bake-off, but the one with the strongest "architectural visualization"
prior. A small free credit allotment ships with new accounts.
`spike/renderers/magnific.py:MagnificMysticRenderer` reads `MAGNIFIC_API_KEY`
and sends the screenshot in `structure_reference` (base64, shape-conditioning
input) alongside `prompt`. Submit returns
`{"data": {"task_id": "<uuid>", "status": "CREATED", "generated": []}}`; we
poll `GET /v1/ai/mystic/<task_id>` until `data.status == "COMPLETED"`, at
which point the result URL lives at `data.generated[0]`.

## Recraft (native API — Recraft V3 image-to-image)

Recraft (https://www.recraft.ai/) exposes its own V3 model at
`https://external.api.recraft.ai/v1/`. The native API is synchronous (no
polling), supports multipart-form uploads, and bills around **$0.04 per image**
for `recraftv3`. New accounts get a small free monthly credit allotment
(Recraft's "Free" plan); paid plans start around $10/month for higher quotas.
Get a token from the profile → API page.
`spike/renderers/recraft.py:RecraftV3Renderer` reads `RECRAFT_API_TOKEN`. Per
Recraft's endpoint table (May 2026), the `/v1/images/imageToImage` endpoint
only accepts `recraftv3` and `recraftv3_vector` as model identifiers — the
newer V4 and V4.1 models are text-to-image only and live on
`/v1/images/generations`. There is no image-to-image V4 variant.
