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
- [x] **T17** — **SMOKE TEST (LIVE).** Run `python spike/test_vlm_tagging.py --live --input spike/outputs/spike2/render.png` ONCE. Verify schema parses. Save raw response JSON to `spike/outputs/spike3/smoke_test.json` and the visualization to `spike/outputs/spike3/tagged_render.png`. Append actual cost (or $0.01 estimate) to `cost_ledger.md`. If running cost would exceed $0.05, STOP and write a STOPPED.md note. → [report](REPORTS/T17.md)
  - Files: `spike/outputs/spike3/smoke_test.json`, `spike/outputs/spike3/tagged_render.png`, `spike/REPORTS/cost_ledger.md`

## Spike 4 — end-to-end edit scaffold

- [x] **T18** — `spike/cache.py` + `spike/composite.py`. `cache.py` exposes `get_or_compute(key: str, fn: Callable, scope: str = "default") -> bytes` with disk persistence under `spike/.cache/<scope>/<key>.bin`. `composite.py` exposes `paste_tile(base: bytes, mask: bytes, tile: bytes) -> bytes` — alpha-aware PIL composite. Pure local; no network. Reuse existing PIL idioms from `modal_app.py:composite()`. → [report](REPORTS/T18.md)
  - Files: `spike/cache.py`, `spike/composite.py`
- [x] **T19** — `spike/end_to_end_edit.py` driver. Inputs: `--screenshot`, `--region-label` (e.g., "wall"), `--material` (path to swatch). Pipeline: `render_from_model_view` → `tag_regions` → pick region matching label → `segment` (bbox mode) → `apply_material` → `composite` (uses T18 helper). Default `--dry-run` prints the call graph without invoking anything. Cost estimate per live run: ~$0.50 (printed before execution). → [report](REPORTS/T19.md)
  - Files: `spike/end_to_end_edit.py`
- [x] **T20** — `spike/tests/test_end_to_end.py` — pytest end-to-end mock test. Mocks every Modal function (`render_from_model_view`, `tag_regions`, `segment`, `apply_material`) using `unittest.mock`. Asserts: pipeline calls things in the right order, region matching picks the right region, output composite is non-empty bytes. → [report](REPORTS/T20.md)
  - Files: `spike/tests/test_end_to_end.py`

## Spike 3 — proper evaluation (follow-up from T17)

- [x] **T21** — Proper Spike 3 gate evaluation. T17 was a smoke-test pass but exposed substantive quality issues with `tag_regions` output (see `REPORTS/T17.md` "Quality findings"). Required work: → [report](REPORTS/T21.md)
- [x] **T22** — Production-shape gate eval. T21 within budget could only test 1 of 5 pairs in the production (screenshot, photoreal render) shape — the other 4 were screenshot-only and one (urban_exterior) failed badly because raw screenshots underperform. T22 renders the 4 new screenshots via Nano Banana Pro and re-tags each (screenshot, render) pair, completing the 5-pair gate sample. Cost: ~$0.20 + $0.01 retry. → [report](REPORTS/T22.md)
  - Files: `spike/run_t22.py`, `spike/salvage_urban_tags.py`, `spike/outputs/spike3/t22/<slug>/`
- [x] **T23** — Promote defensive tag_regions response handling into production. T22 lost no data only because we wrote `_save_raw_response` and `salvage_urban_tags.py` ad-hoc. Move both into `spike/schemas.py` (`save_raw_response` helper + `TagRegionsResponse.parse_tolerant` classmethod), then have `test_vlm_tagging.py:_call_live` and `end_to_end_edit.py:_run_tag_regions` use them so every production path saves raw before validation and survives Gemini's duplicate-`y` bbox bug. Add pytest coverage for the parser. No API cost. → [report](REPORTS/T23.md)
  - Files: `spike/schemas.py`, `spike/test_vlm_tagging.py`, `spike/end_to_end_edit.py`, `spike/run_t22.py`, `spike/salvage_urban_tags.py`, `spike/tests/test_schemas.py`
- [x] **T24** — First live Spike 4 end-to-end run. Pre-populate render + tags cache from spike2 photoreal + T21 pair 1 (free), then run `end_to_end_edit.py --live` with region=wall, material=travertine. Cost: ~$0.45 ($0.05 SAM2 + $0.40 SD Inpaint on A10G). Validates the full pipeline runs end-to-end on real data. → [report](REPORTS/T24.md)
  - Files: `spike/outputs/spike4/first_live/{edit_result,mask,tile,render}.png`
- [x] **T25** — Swap SD Inpaint for FLUX Fill (Replicate) as a second `apply_material` backend. Add `--inpainter {sd_inpaint, flux_fill_replicate}` flag to `end_to_end_edit.py`; route the FLUX path through Replicate's `black-forest-labs/flux-fill-pro` (image + mask + text prompt). Live test on the spike2 photoreal pair (cache reused from T24). Cost: $0.05/call vs T24's $0.40, and runs at native resolution rather than SD's 512×512. → [report](REPORTS/T25.md)
  - Files: `spike/end_to_end_edit.py`, `spike/tests/test_end_to_end.py`, `spike/outputs/spike4/flux_fill_first/`, `spike/outputs/spike4/sd_vs_flux_wall_crop_comparison.png`
  1. **Coordinate fix.** Gemini returns bboxes in 0–1000 normalized space, not pixel coords. Either (a) scale bboxes to actual pixel dimensions in `test_vlm_tagging.py:_draw_regions` and in `end_to_end_edit.py` before passing to SAM2, OR (b) update the `tag_regions` prompt in `modal_app.py` to require actual pixel coordinates AND verify the model complies (VLMs often ignore this instruction).
  2. **Prompt revision.** Tighten `tag_regions` to: ask for tight bboxes per architectural element (not per-facade); clarify that `parent_id` means geometric containment, not spatial overlap; add explicit "do not invent a 'door' inside a 'window'" guidance.
  3. **Multi-render test set.** Per the plan, evaluate on **5 diverse screenshots** (modern interior, traditional exterior, mixed materials, complex window patterns, urban exterior with people/cars/trees).
  4. **Manual scoring.** Score each screenshot against the actual Spike 3 gate: ≥80% of major elements (wall/window/mullion/floor/ceiling/door) **correctly labeled** with **tight, pixel-accurate bboxes**.
  5. **Cost estimate:** ~$0.05 (5 Gemini calls @ $0.01). Brings running total to $0.06 — **exceeds the $0.05 session cap; needs user authorization before running.**
  - Files: `spike/modal_app.py` (tag_regions prompt), `spike/test_vlm_tagging.py` (coord scaling), `spike/end_to_end_edit.py` (coord scaling if used), `spike/test_assets/model_views/` (4 new screenshots), `spike/outputs/spike3/` (new tagged_*.png + scored_rubric.json)

---

## Status legend

- `- [ ]` not started
- `- [x]` completed (link to report appended)
- `- [!]` blocked / failed (link to report appended)
- `- [~]` in progress (rare; agent should usually only hold one row in this state)
