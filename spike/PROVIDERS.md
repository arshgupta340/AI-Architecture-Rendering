# Providers

One paragraph per third-party image API the Spike 2.5 bake-off can call. Each
section names the signup URL, the published per-image price (subject to drift
— check the provider before you trust this file), whether there's a free tier,
and which renderer class in `spike/renderers/` consumes the corresponding
environment variable. The `compare_renderers.py` driver iterates every
renderer subclass and only instantiates the ones whose `env_var` is present in
the environment, so you can run a partial bake-off by populating only the
providers you care about.

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

## Black Forest Labs (FLUX Pro 1.1 — Canny & Kontext)

Black Forest Labs is the company behind FLUX. Their hosted API at
https://api.bfl.ml/ exposes the closed-weights Pro variants we care about for
geometry preservation. Sign up at the dashboard (https://api.bfl.ml/auth/profile)
and top up — there is **no free tier**, pricing is approximately
**$0.05 per image** for both `flux-pro-1.1-canny` (geometry-preserving via
server-side Canny conditioning) and `flux-pro-1.1-kontext` (instruction-edit
image-to-image). Both endpoints use a submit-then-poll flow.
`spike/renderers/flux_bfl.py` defines `FluxCannyProRenderer` and
`FluxKontextProRenderer`, both reading `BFL_API_KEY` from the environment.

## Replicate (Qwen-Image-Edit, HiDream-E1, Recraft V3)

Replicate is a generic model-hosting platform at https://replicate.com/. We
use it as a single entry point for three different image-edit models we don't
want to host ourselves: `qwen/qwen-image-edit`, `prunaai/hidream-e1`, and
`recraft-ai/recraft-v3`. Pricing is per-model and metered to the second of GPU
time; the bake-off uses rough per-image estimates of **$0.03** (Qwen),
**$0.04** (HiDream-E1), and **$0.04** (Recraft V3 on Replicate) — see the
`cost_per_call_usd` attribute on each class for the value of record. New
accounts get a small free credit; after that you must add a card. Get a token
at https://replicate.com/account/api-tokens.
`spike/renderers/replicate_models.py` defines `QwenImageEditRenderer`,
`HiDreamE1Renderer`, and `RecraftV3ReplicateRenderer`, all sharing
`REPLICATE_API_TOKEN`.

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

## Magnific (Freepik / Magnific.ai — Mystic / Relight)

Magnific (https://magnific.ai/, now owned by Freepik) sells "Mystic" image
generation and the older "Relight" image-conditioned upscaler/restyler. API
access is currently **invite / waitlist-gated**; Freepik Premium accounts can
also call equivalent endpoints via the Freepik API. Pricing on the Mystic
endpoint is roughly **$0.10 per image** (the most expensive renderer in the
bake-off, but the one with the strongest "architectural visualization" prior).
No free tier through the API. `spike/renderers/magnific.py:MagnificMysticRenderer`
reads `MAGNIFIC_API_KEY` and posts to `https://api.magnific.ai/v1/mystic`.

## Recraft (native API — Recraft V3 image-to-image)

Recraft (https://www.recraft.ai/) exposes its own V3 model at
`https://external.api.recraft.ai/v1/`, separate from the Replicate-hosted copy.
The native API is synchronous (no polling), supports multipart-form uploads,
and bills around **$0.04 per image** for `recraftv3`. New accounts get a small
free monthly credit allotment (Recraft's "Free" plan); paid plans start around
$10/month for higher quotas. Get a token from the profile -> API page.
`spike/renderers/recraft.py:RecraftV3Renderer` reads `RECRAFT_API_TOKEN`. Note
that `RecraftV3ReplicateRenderer` (above) calls the same underlying model
through Replicate's infrastructure — the bake-off includes both so we can
compare the native and Replicate-hosted code paths for latency and quality
drift.
