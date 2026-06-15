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
modal deploy spike/modal_flux.py                 # publish the web endpoint
```
The backend is ONE ASGI app (FastAPI + CORS) with two routes. `modal deploy` prints:
- `https://<workspace>--arch-rendering-flux-heroflux-web.modal.run`

In the app: click **✦ Hero render** (WebGL2 / + GI mode) → the setup card → paste:
- Base render URL: `…heroflux-web.modal.run/hero_render`
- Region edit URL: `…heroflux-web.modal.run/region_edit`
- Secret: your `HERO_SHARED_SECRET`

- GPU: `A100-80GB` BF16 (one-line `GPU` const; swap to `H100` for ~2× speed or `A10G` for cost).
- VERIFIED LIVE: 1024×688 @ 28 steps ≈ **13 s** warm (cold start ~40 s: container + load cached weights);
  geometry-locked photoreal output (every window/trim/roof preserved). Cost ~$0.01–0.02/render; idle = $0.

### Gotchas hit while bringing it up (so you don't re-learn them)
- **Windows console**: prefix every `modal` command with `PYTHONUTF8=1` (Modal's ✓ progress glyphs crash cp1252).
- **After a CODE change, the warm container keeps serving the OLD code.** Run
  `modal app stop arch-rendering-flux -y` before `modal deploy`, else the next request still hits stale code.
- **diffusers 0.32.2 multi-control**: a bare list of 2 control images on a single `FluxControlNetModel`
  batches them (latent-shape error). FIX (in `load()`): wrap the Union in `FluxMultiControlNetModel([cn, cn])`.
- **Control images must be 3-channel RGB** (`prep_*` return 1-ch 'L' → `.convert("RGB")`).
- **`negative_prompt`/`true_cfg_scale`** don't exist on 0.32.2's `FluxControlNetPipeline` — added only if the
  installed diffusers supports them (the code inspects the signature). Bump diffusers later to enable them.
- **CORS**: Modal's `@modal.fastapi_endpoint` CORS-es only the OPTIONS preflight, not the response → the browser
  POST fails with "Failed to fetch". FIX: a real FastAPI app + `CORSMiddleware` via `@modal.asgi_app()` (done).
- FastAPI must be in the image (`fastapi[standard]`) for Modal 1.4+; deps are pinned to a known-good FLUX combo.

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

### /warm  (cheap keep-alive — no render)
```
{ secret } → { warm: true, model: "flux1-dev-union", pipe_loaded: bool }
```
Hitting any route resets the 300 s scaledown timer; `/warm` does it WITHOUT a render. The
app's header **🔥 Keep warm** toggle pings this every 240 s so an active editing session
never pays the ~40–60 s cold start. (First ping still cold-boots the container to load the
pipe — ~18 s observed live — then it stays warm.)

## FLUX.2 — the experimental sibling backend
`spike/modal_flux2.py` (app `arch-rendering-flux2`) serves the SAME contract on **FLUX.2-dev +
alibaba-pai Fun-Controlnet-Union (H200, via VideoX-Fun)** — switchable in the app's Backend
card by URL preset. Deploy-gated (32B model, ~70 GB download, VideoX-Fun loader to validate on
first deploy). FLUX.1 stays the default. Full feasibility + deploy steps: `spike/REPORTS/flux2_feasibility.md`.

## Experiment B (IP-Adapter) — attempted, BLOCKED on the pinned stack
Goal: let multi-view renders inherit the hero view's materials/lighting via an XLabs FLUX
IP-Adapter (reference image) on top of the canny+depth geometry lock. Implemented GUARDED
in `HeroFlux.load()` + `_run_pipe` (request fields `ref_image`, `ip_scale`).
**Definitive finding (live):** on the pinned **diffusers 0.32.2**, `FluxControlNetPipeline`
has **no `load_ip_adapter`** (`AttributeError`) — the FLUX IP-Adapter mixin shipped on the
plain `FluxPipeline` first; the ControlNet variant only got it in a later release. So the
adapter loads-fail-safe and every render falls back to geometry-only (`ip_used:false`); the
base render is unaffected (the guard). To actually run B you must bump diffusers to a version
whose ControlNet pipeline includes the IP-Adapter mixin **and** re-verify the multi-controlnet
base (the 0.32.2 `FluxMultiControlNetModel` batching workaround may change), and the XLabs
adapter additionally needs real CFG that 0.32.2's ControlNet pipeline lacks. **Recommendation:
prefer the reproject-from-3D approach (true geometry+material consistency) over an IP-Adapter
bump.** Edge-alignment data: tightening the lock (canny 1.0 / depth 0.85) raised geometry
adherence 74.5% → 93.1% (consistent across views), but does NOT fix lighting/material drift —
which is why reproject (carry the hero's exact pixels onto the real mesh) is the principled fix.

## Deploy the splat-bake backend
```
modal deploy spike/modal_splat.py     # publish the bake endpoint
```
Paste the `…splatbake-web.modal.run/bake` URL into the Splat panel → **Bake our scene**.
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
splat loader was verified rendering a real `.spz` composited with the building.

**LIVE-VERIFIED through the real app UI (2026-06-15):** the FLUX backend is deployed and both
routes were exercised by clicking the actual Hero modal buttons against the warm A100 —
- `/hero_render`: **200**, 14.9 s warm (58.3 s cold) → photoreal golden-hour house, every
  window/porch/stair/roof-gable/wood-trim matching the 3D geometry (zero hallucination).
- `/region_edit`: **200**, 21.0 s warm → masked roof region layer composited byte-stable over
  the base; the modal's render counter incremented 1 → 2/24.
The **splat training** (`spike/modal_splat.py`) is the only remaining deploy-gated/untested step.
