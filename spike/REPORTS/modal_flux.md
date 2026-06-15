# Hero render backend — Modal FLUX + splat-bake deploy runbook

Two self-hosted Modal apps power the web3d hero features:
- **`spike/modal_flux.py`** — FLUX.1-dev + ControlNet-Union-Pro-2.0 (canny+depth) → the
  geometry-locked **Hero render** (asks 2 + 3).
- **`spike/modal_splat.py`** — nerfstudio `splatfacto` → **bake our scene → 3DGS** (ask 1).

Both reuse the existing `arch-rendering-weights` Volume + `arch-flux` secret; both are
separate apps (deploying them never rebuilds the frozen `spike/modal_app.py`).

## One-time setup
1. **Accept the FLUX.1-dev license** at https://huggingface.co/black-forest-labs/FLUX.1-dev,
   create an HF token (read).
2. **Add two keys to the `arch-flux` Modal secret:**
   - `HF_TOKEN` — the HuggingFace token (FLUX.1-dev is gated).
   - `HERO_SHARED_SECRET` — any string; the app sends it in the request body, both
     endpoints 401 on mismatch.
   ```
   modal secret create arch-flux HF_TOKEN=hf_xxx HERO_SHARED_SECRET=yyy
   ```
   (Dedicated secret so it doesn't clobber `arch-spike`'s GOOGLE_API_KEY.)

## Deploy the FLUX hero backend
```
modal run    spike/modal_flux.py::warm_weights   # one-time: prefetch ~24 GB FLUX + ControlNet to the Volume
modal deploy spike/modal_flux.py                 # publish both endpoints
modal run    spike/modal_flux.py                 # OPTIONAL local smoke (needs spike/outputs/web3d_house/{beauty,depth,instance_ids}.png) → outputs/hero_smoke.png
```
`modal deploy` prints two URLs, e.g.:
- `https://<workspace>--arch-rendering-flux-heroflux-hero-render.modal.run`
- `https://<workspace>--arch-rendering-flux-heroflux-region-edit.modal.run`

In the app: click **✦ Hero render** (WebGL2 / + GI mode) → the setup card → paste both URLs
+ your `HERO_SHARED_SECRET`.

- GPU: `A100-80GB` BF16 (one-line `GPU` const; swap to `H100` for ~2× speed or `A10G` for cost).
- Cost: ~$0.01–0.02 / render warm; idle = $0 (`min_containers=0`, `scaledown_window=300`).
  First call after idle cold-starts (~30–90 s: container + load the cached weights).

### hero_render contract  (POST, JSON; images are BARE base64 PNG)
```
{ secret, beauty, depth, ids_rgb, canny?, prompt?, negative_prompt?,
  width?, height?, seed?, steps?, guidance_scale?, true_cfg_scale?,
  canny_scale?, canny_end?, depth_scale?, depth_end? }
→ { image: <b64 png>, seed, ms }
```
- `depth` is LINEAR, **NEAR=white / FAR=black** (the verified FLUX depth-ControlNet
  convention); the web capture already produces this.
- `canny` is computed server-side = `cv2.Canny(beauty,70,160) ∪ instance-id boundaries`
  (the proven 98.5%-edge-alignment recipe) unless you pass a precomputed `canny`.
- `true_cfg_scale > 1` enables the negative prompt (the app sets ~4.0 when a negative is
  present; default 1.0 ignores it = faster). `width/height` are rounded down to /16.

### region_edit contract
```
{ ...hero_render fields..., base, region_ids:[int], mask? }
→ { image: <b64 full frame, region composited over base>, mask, seed, ms }
```
Same seed + controls as the base, masked to `region_ids` (untouched pixels = base → byte-stable).

## Deploy the splat-bake backend
```
modal deploy spike/modal_splat.py     # publish the bake endpoint
```
Paste the `…splatbake-bake.modal.run` URL into the Splat panel → **Bake our scene**.
- GPU `A100-80GB`; ~15–25 min / ~42 views @ 20k iters; ~$0.30–0.50.
- **Build risk to verify on first deploy:** the image compiles `gsplat` CUDA kernels
  (CUDA-devel base). If the build is flaky, pin a prebuilt `gsplat` wheel for the
  torch/CUDA combo.
- Async: the endpoint `spawn`s training and returns `{job_id}`; the client re-POSTs
  `{secret, job_id}` until `{ply_b64}` is ready.

## Local QA without a GPU (no Modal / no spend)
`spike/mock_hero_server.py` mocks both endpoints using the REAL `prep_canny`/`prep_depth`,
returning a visible canny∪id-edge overlay + depth inset (so you can confirm the geometry
lock is correct). Run `spike\.venv\Scripts\python.exe spike/mock_hero_server.py` (:5999),
paste `http://127.0.0.1:5999/hero_render` + `/region_edit` + secret `test` into the setup card.

## QA status (this build)
Capture + conditioning + the full hero UI flow (base → region mask → layers → composite →
visibility → save) were verified end-to-end against the mock (depth near=white linear;
byte-exact per-semantic ids; canny ∪ id-edges aligned to every window/mullion/trim). The
splat loader was verified rendering a real `.spz` composited with the building. The live
FLUX inference + the splat training are the only deploy-gated (untested-here) steps.
