# Providers

One paragraph per third-party image API the Spike 2.5 bake-off can call. Each
section names the signup URL, the published per-image price (subject to drift
— check the provider before you trust this file), whether there's a free tier,
and which renderer class in `spike/renderers/` consumes the corresponding
environment variable. The `compare_renderers.py` driver iterates every
renderer subclass and only instantiates the ones whose `env_var` is present in
the environment, so you can run a partial bake-off by populating only the
providers you care about.

**Revised May 2026 (post-B3-RUN-1).** The bake-off was consolidated onto three
auth paths after a first live run surfaced several issues: BFL's direct API
deprecated the Canny/Depth/Kontext endpoints that motivated FLUX inclusion in
the first place, Magnific moved hosts and changed body schemas (then we still
hit 401s even after fixing those), and accounts on BFL and Magnific needed
separate top-ups. Replicate hosts all the FLUX variants we want, including
the legacy Canny/Depth Pro endpoints BFL itself removed — so every FLUX call
now goes through Replicate. Magnific has no Replicate equivalent and is no
longer in the field. The eight renderers below reflect the current valid set.

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

## Replicate (FLUX family + Qwen + HiDream)

Replicate is a generic model-hosting platform at https://replicate.com/. Six
of the eight renderers in the bake-off route through Replicate, all sharing
one `REPLICATE_API_TOKEN`. Top up a Replicate account once and every model
below becomes live in the same step.

- `Flux2ProRenderer` → `black-forest-labs/flux-2-pro` (~$0.03/call). General
  image-edit. Schema quirk: input image lives in an array field
  (`input_images`, max 8), not a single string — the renderer wraps the
  encoded data URL in a one-item list.
- `FluxFillProRenderer` → `black-forest-labs/flux-fill-pro` (~$0.05/call).
  Mask-based inpainting, fired here without a mask. Field: `image` + `prompt`.
- `FluxCannyProRenderer` → `black-forest-labs/flux-canny-pro` (~$0.05/call).
  Server-side Canny edge conditioning, the strongest silhouette-preservation
  candidate in the field. Field: `control_image` + `prompt`. BFL's own
  direct API removed this endpoint in 2026; Replicate is the only path.
- `FluxDepthProRenderer` → `black-forest-labs/flux-depth-pro` (~$0.05/call).
  Server-side depth-map conditioning. Same schema as Canny Pro. Also
  Replicate-only after BFL's deprecations.
- `QwenImageEditRenderer` → `qwen/qwen-image-edit` (~$0.03/call).
  Instruction-based image-edit; strong layout preservation.
- `HiDreamE1Renderer` → `prunaai/hidream-e1.1` (~$0.04/call). Natural-language
  prompt instruction-edit. Note the literal period in the slug —
  `hidream-e1-1` returns 404.

All Replicate clients live in `spike/renderers/replicate_models.py` and share
`_ReplicateRendererBase` for the submit-then-poll plumbing. New accounts get
a small free credit; after that you must add a card. Get a token at
https://replicate.com/account/api-tokens.

**Removed:** `RecraftV3ReplicateRenderer` (Replicate's Recraft V3 is
text-only). Use the native Recraft client below for image-to-image.

## Recraft (native API — Recraft V3 image-to-image)

Recraft (https://www.recraft.ai/) exposes its own V3 model at
`https://external.api.recraft.ai/v1/`. The native API is synchronous (no
polling), supports multipart-form uploads, and bills around **$0.04 per image**
for `recraftv3`. New accounts get a small free monthly credit allotment
(Recraft's "Free" plan); paid plans start around $10/month for higher quotas.
Get a token from the profile → API page.
`spike/renderers/recraft.py:RecraftV3Renderer` reads `RECRAFT_API_TOKEN`. Per
Recraft's endpoint table (May 2026), the `/v1/images/imageToImage` endpoint
only accepts `recraftv3` and `recraftv3_vector` as model identifiers — V4 and
V4.1 are text-to-image only and not useful for our screenshot→render flow.

## Removed providers

- **Black Forest Labs (direct).** Replaced by Replicate-routed FLUX clients
  in May 2026. The deprecated Canny/Depth Pro endpoints were the original
  reason FLUX was in scope; since BFL's hosted API removed them, there's no
  practical advantage to keeping a separate BFL auth path for FLUX 2 Pro
  and Fill Pro alone.
- **Magnific (Freepik).** Two iterations of fixes (URL/body schema change,
  then auth header change) still returned 401 with a freshly-issued key, and
  Magnific has no Replicate-hosted equivalent. Out of the bake-off field as
  of B3-RUN-1.
- **fal.ai.** Never wired; reserved `FAL_KEY` removed from documentation.
  Add a `spike/renderers/fal_*.py` client at the point of need.
