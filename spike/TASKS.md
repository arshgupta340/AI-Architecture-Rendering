# Spike-builder overnight task board

Read this top-to-bottom. The agent picks the **first row with `- [ ]`** and works on it. After a successful commit + report, the agent flips the box to `- [x]` and appends ` → [report](REPORTS/T<id>.md)` to the row. On failure the agent flips to `- [!]` and writes a report explaining why.

**Branch:** `overnight/spike-builder-2026-05-17` — verify with `git rev-parse --abbrev-ref HEAD` before every commit. If wrong branch, STOP.

**Cost cap:** $0.05 total across the night. Update `REPORTS/cost_ledger.md` after the single allowed live call (T17). If the running total reaches $0.05, STOP.

**Per-task contract:** see `.claude/agents/spike-builder.md` § "Per-task contract".

**Tonight's environment (2026-05-17, post-repair):** the venv at `spike/.venv/` is healthy (Python 3.13 with PIL, cv2, numpy, pytest, pydantic, respx, modal, google-genai, python-dotenv, requests installed). Use `spike\.venv\Scripts\python.exe` for everything. Runtime import checks and pytest are expected to work. T17 should succeed against the live Gemini API for ~$0.01.

---

## Spike 2.5 — multi-renderer bake-off scaffold

- [x] **T01** — Commit in-progress Spike 2.5/B1 work, then create `overnight/spike-builder-2026-05-17` (done manually by main session; see commit `74fc908`).
  - Files: git only
- [x] **T02** — Renderer-package skeleton: create `spike/renderers/__init__.py` exporting `Renderer` base class, and `spike/renderers/base.py` defining `class Renderer(ABC)` with abstract `render(screenshot_path: Path, prompt: str, *, seed: int | None = None, **kwargs) -> bytes`. Include a `name: ClassVar[str]` and `cost_per_call_usd: ClassVar[float]` for the bake-off scoring. No network. → [report](REPORTS/T02.md) (done by main session as smoke test, commit `518bdcd`)
  - Files: `spike/renderers/__init__.py`, `spike/renderers/base.py`
- [x] **T03** — `spike/renderers/nano_banana.py` — `NanoBananaProRenderer(Renderer)` that wraps the existing `render_from_model_view` Modal function from `spike/modal_app.py`. Import-only at module load (do **not** call modal). The `render()` method should construct the Modal `Function.lookup(...)` call lazily so that import works without modal CLI auth. → [report](REPORTS/T03.md)
  - Files: `spike/renderers/nano_banana.py`
- [x] **T04** — `spike/renderers/flux_bfl.py` — two classes, `FluxCannyProRenderer` and `FluxKontextProRenderer`, both subclasses of `Renderer`. Use `os.environ.get("BFL_API_KEY")`; if missing, `render()` raises a clear `RuntimeError("BFL_API_KEY not set")`. Implement the actual HTTP shape against `https://api.bfl.ml/v1/flux-pro-1.1-canny` and `…/flux-pro-1.1-kontext` per BFL docs (polling on the task `id` is fine). **Do not actually call the API.** Just write the code. → [report](REPORTS/T04.md)
  - Files: `spike/renderers/flux_bfl.py`
- [x] **T05** — `spike/renderers/magnific.py` + `spike/renderers/recraft.py` — `MagnificMysticRenderer` (Magnific Relight/Mystic; env `MAGNIFIC_API_KEY`) and `RecraftV3Renderer` (Recraft native API; env `RECRAFT_API_TOKEN`). Same pattern as T04 — env-gated, no live calls. → [report](REPORTS/T05.md)
  - Files: `spike/renderers/magnific.py`, `spike/renderers/recraft.py`
- [x] **T06** — `spike/renderers/replicate_models.py` — three classes (`QwenImageEditRenderer`, `HiDreamE1Renderer`, `RecraftV3ReplicateRenderer`) all hitting Replicate's HTTP API. Env: `REPLICATE_API_TOKEN`. Same pattern. → [report](REPORTS/T06.md)
  - Files: `spike/renderers/replicate_models.py`
- [x] **T07** — `spike/scoring.py` — pure CV functions: `silhouette_iou(img_a: bytes, img_b: bytes) -> float` (Canny + flood-fill silhouettes, return IoU); `edge_density_delta(img_a: bytes, img_b: bytes, region_bbox: tuple | None = None) -> float` (Canny pixel-count ratio). Plus a `count_windows(render_bytes: bytes) -> int` stub that *would* call Gemini 3 Pro structured output but is env-gated (`GOOGLE_API_KEY`) and not invoked here. Reuse `overlay_canny_edges` from `run_b1_baseline.py` if possible — do not re-implement Canny. → [report](REPORTS/T07.md)
  - Files: `spike/scoring.py`
- [x] **T08** — `spike/compare_renderers.py` — B3 driver. Accepts `--input <screenshot>`. Instantiates every renderer whose env vars are present. Fans out (sequential is fine; parallelism is a future task) and saves results to `spike/outputs/spike2_5/b3/<renderer_name>.png`. Builds a comparison grid (`comparison_grid.png`) and overlay grid (`overlays_grid.png`) using helpers from `run_b1_baseline.py`. Writes `scores.csv` template with one row per renderer and empty rubric columns. Default behavior with **no env vars set**: prints a manifest of which renderers would run, writes nothing, exits 0. → [report](REPORTS/T08.md)
  - Files: `spike/compare_renderers.py`
- [x] **T09** — `spike/run_b2_variants.py` — B2 prompt-variant driver. Four variant configs in code: `tightened_prompt`, `higher_res` (resize input to 1920px long edge before sending), `multi_region_annotated`, `multi_pass` (first call returns regions list, second call adds explicit constraints). Default `--dry-run` mode prints what each call would send. Live mode is gated behind `--live` AND `GOOGLE_API_KEY` presence. → [report](REPORTS/T09.md)
  - Files: `spike/run_b2_variants.py`
- [x] **T10** — Extend `spike/.env.example` with placeholders for `BFL_API_KEY`, `REPLICATE_API_TOKEN`, `FAL_KEY`, `MAGNIFIC_API_KEY`, `RECRAFT_API_TOKEN`. Create `spike/PROVIDERS.md` with one paragraph per provider: signup URL, pricing/image, free tier (if any), which renderer class in `spike/renderers/` uses it. Do not commit `.env`. → [report](REPORTS/T10.md)
  - Files: `spike/.env.example`, `spike/PROVIDERS.md`
- [x] **T11** — `spike/tests/test_renderers.py` — pytest tests for every renderer class. Mock HTTP with `respx` (preferred) or `responses`. Cover: (1) env-var missing → clean RuntimeError; (2) request shape matches provider docs; (3) response parsing returns bytes; (4) HTTP error → propagates. Also `spike/tests/conftest.py` with a `tiny_png` fixture (8×8 solid color, PIL-generated in-memory). → [report](REPORTS/T11.md)
  - Files: `spike/tests/__init__.py`, `spike/tests/conftest.py`, `spike/tests/test_renderers.py`
- [x] **T12** — Update `spike/requirements.txt` adding any new deps the agent introduced (`pytest`, `respx`, `pydantic` for T13). Pin minor versions. Verify the venv at `spike/.venv/` already has them; if not, add `# install: pip install respx pytest` comment but do **not** run pip. → [report](REPORTS/T12.md)
  - Files: `spike/requirements.txt`

## Spike 3 — VLM tagging scaffold

- [x] **T13** — `spike/schemas.py` — Pydantic v2 models: `BBox(x: int, y: int, w: int, h: int)`, `Region(id: str, label: str, bbox: BBox, confidence: float, parent_id: str | None = None)`, `TagRegionsResponse(regions: list[Region])`. Include a `Region.LABELS` ClassVar with the allowed enum (wall, floor, ceiling, window, door, mullion, roof, ground, sky, vegetation, furniture, person, vehicle). → [report](REPORTS/T13.md)
  - Files: `spike/schemas.py`
- [x] **T14** — Add `tag_regions()` Modal function in `spike/modal_app.py`. Inputs: `screenshot_bytes: bytes, render_bytes: bytes`. Calls Gemini 3 Pro (`gemini-3-pro-preview`) with structured-output config, schema = `TagRegionsResponse`. Returns `TagRegionsResponse`. Reuse the existing `google.genai` client wiring pattern. Mark with `@app.function(image=image, secrets=[...])` matching the existing render function. Don't deploy. → [report](REPORTS/T14.md)
  - Files: `spike/modal_app.py`
- [x] **T15** — Repurpose `segment()` in `spike/modal_app.py` to accept either click point OR bbox prompt. SAM2 supports both natively. Add a `prompt: dict` parameter with either `{"type": "point", "x": int, "y": int}` or `{"type": "bbox", "x": int, "y": int, "w": int, "h": int}`. Keep the old positional `x, y` signature working via a deprecation shim. → [report](REPORTS/T15.md)
  - Files: `spike/modal_app.py`
- [x] **T16** — `spike/test_vlm_tagging.py` — driver script. Loads a render PNG, calls `tag_regions` (or loads fixture JSON in `--dry-run` mode), draws bboxes + labels on the render with PIL, saves to `spike/outputs/spike3/tagged_<basename>.png`. Default to `--dry-run` (uses fixture). `--live` triggers actual Modal/Gemini call (still local execution — Modal lookup, not deploy). → [report](REPORTS/T16.md)
  - Files: `spike/test_vlm_tagging.py`, `spike/tests/fixtures/tag_regions_response.json`
- [ ] **T17** — **SMOKE TEST (LIVE).** Run `python spike/test_vlm_tagging.py --live --input spike/outputs/spike2/render.png` ONCE. Verify schema parses. Save raw response JSON to `spike/outputs/spike3/smoke_test.json` and the visualization to `spike/outputs/spike3/tagged_render.png`. Append actual cost (or $0.01 estimate) to `cost_ledger.md`. If running cost would exceed $0.05, STOP and write a STOPPED.md note.
  - Files: `spike/outputs/spike3/smoke_test.json`, `spike/outputs/spike3/tagged_render.png`, `spike/REPORTS/cost_ledger.md`

## Spike 4 — end-to-end edit scaffold

- [ ] **T18** — `spike/cache.py` + `spike/composite.py`. `cache.py` exposes `get_or_compute(key: str, fn: Callable, scope: str = "default") -> bytes` with disk persistence under `spike/.cache/<scope>/<key>.bin`. `composite.py` exposes `paste_tile(base: bytes, mask: bytes, tile: bytes) -> bytes` — alpha-aware PIL composite. Pure local; no network. Reuse existing PIL idioms from `modal_app.py:composite()`.
  - Files: `spike/cache.py`, `spike/composite.py`
- [ ] **T19** — `spike/end_to_end_edit.py` driver. Inputs: `--screenshot`, `--region-label` (e.g., "wall"), `--material` (path to swatch). Pipeline: `render_from_model_view` → `tag_regions` → pick region matching label → `segment` (bbox mode) → `apply_material` → `composite` (uses T18 helper). Default `--dry-run` prints the call graph without invoking anything. Cost estimate per live run: ~$0.50 (printed before execution).
  - Files: `spike/end_to_end_edit.py`
- [ ] **T20** — `spike/tests/test_end_to_end.py` — pytest end-to-end mock test. Mocks every Modal function (`render_from_model_view`, `tag_regions`, `segment`, `apply_material`) using `unittest.mock`. Asserts: pipeline calls things in the right order, region matching picks the right region, output composite is non-empty bytes.
  - Files: `spike/tests/test_end_to_end.py`

---

## Status legend

- `- [ ]` not started
- `- [x]` completed (link to report appended)
- `- [!]` blocked / failed (link to report appended)
- `- [~]` in progress (rare; agent should usually only hold one row in this state)
