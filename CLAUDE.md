# AI Architecture Rendering — project guide for Claude

## Project

**Photoshop-for-Architects.** A canvas where AI is invisible plumbing behind direct-manipulation tools — click a wall, pick a material from a swatch library, the surface re-renders coherently. Architects don't think in prompts; they think *"that wall, in travertine."* Non-destructive: every region→material assignment is a re-editable layer, not baked pixels.

Web MVP first; Rhino / SketchUp / Revit / Forma plugins follow (every host already exposes a viewport-bitmap API). Input is a shaded 3D-model viewport screenshot — Nano Banana Pro renders it photorealistically while preserving geometry, Gemini 3 Pro tags every region (wall, window, mullion, door, floor, …), SAM 2 refines bboxes into pixel masks, IP-Adapter + FLUX Fill swaps materials per region.

Full vision: [docs/plans/master-plan.md](docs/plans/master-plan.md).

## Orient first

Before doing anything substantive, read **[wiki/README.md](wiki/README.md)** and **[wiki/STATE.md](wiki/STATE.md)**. The `wiki/` directory is the single source of truth — it has the current state, glossary (B1/B2/B3, what each spike is), strategy (Photoshop route vs VLM route), roadmap, decision log, and session log. The master plan is still the design document; the wiki is synthesis + working memory.

If the user asks "what is X", "why did we do X", "what's next", or "where are we" — answer from the wiki, not from re-deriving the answer.

## Current phase

**Spike phase.** All code lives under `spike/`. No production app exists yet. Three spikes in flight:

- **Spike 2.5** — multi-renderer bake-off (Nano Banana variants, FLUX Canny/Kontext Pro, Magnific, Qwen-Image-Edit, HiDream-E1, Recraft V3). Goal: pick the production renderer by lowest critical-failure count.
- **Spike 3** — VLM region tagging (Gemini 3 Pro structured output → `Region[]`).
- **Spike 4** — end-to-end edit pipeline (render → tag → segment → apply material → composite).

Scaffolding plan: [docs/plans/overnight-spike-builder.md](docs/plans/overnight-spike-builder.md). Live task board: [spike/TASKS.md](spike/TASKS.md). Per-task reports: [spike/REPORTS/](spike/REPORTS/). Resume notes: [spike/REPORTS/RESUME.md](spike/REPORTS/RESUME.md).

## Repo layout

- `spike/` — all current code: `renderers/`, `scoring.py`, `modal_app.py`, `compare_renderers.py`, `run_b2_variants.py`, `end_to_end_edit.py`, `cache.py`, `composite.py`, `schemas.py`, `tests/`, `outputs/`.
- `spike/TASKS.md` — overnight task board, source of truth for what's done (`[x]` complete, `[!]` blocked, `[ ]` pending).
- `spike/REPORTS/` — one report per completed task + `cost_ledger.md` + `RESUME.md`.
- `spike/.venv/` — Python 3.13 venv. **Always use** `spike\.venv\Scripts\python.exe`. Never bare `python`.
- `docs/plans/` — master plan + overnight scaffolding plan (this file links them).

## Hard rules

- **Cost cap: $0.05 per session** unless the user explicitly raises it. Read [spike/REPORTS/cost_ledger.md](spike/REPORTS/cost_ledger.md) before any live API call. If the call would push total over $0.05, stop and ask.
- **No Modal calls by default.** GPU spend is $0.35–0.70 per run, out of budget. Modal functions exist in code (`spike/modal_app.py`) but should not be invoked.
- **No live API calls** to any provider (Gemini / BFL / Replicate / Magnific / Recraft) unless the user explicitly authorizes. Renderer clients in `spike/renderers/` are env-gated and raise a clean `RuntimeError` when keys are missing — that is the intended behavior, not a bug to "fix."
- **Dry-run defaults.** `compare_renderers.py`, `run_b2_variants.py`, `test_vlm_tagging.py`, `end_to_end_edit.py` all default to dry-run / mocked / manifest-only. `--live` is opt-in.
- **Tests use mocks.** `respx` for HTTP, `unittest.mock` for Modal functions. Never hit network from tests.
- **Branch model.** Overnight scaffolding lives on `overnight/spike-builder-2026-05-17`. Merges into `renderer-bakeoff` only after the user reviews. Never commit directly to `main`. Never `git push` without explicit ask. Never `--no-verify`, never force ops, never `--amend` on shared history.
- **Per-task contract.** One row in `spike/TASKS.md` = one implementation commit + one `spike/REPORTS/T<id>.md` + one "mark complete" commit flipping `- [ ]` → `- [x]`. See `.claude/agents/spike-builder.md` for the full contract.

## Canonical commands

- Run tests: `spike\.venv\Scripts\python.exe -m pytest spike/tests/ -v`
- Dry-run the bake-off (prints manifest, writes nothing): `spike\.venv\Scripts\python.exe spike/compare_renderers.py --input spike/test_assets/model_views/building.png`
- Dry-run a B2 prompt variant: `spike\.venv\Scripts\python.exe spike/run_b2_variants.py --variant tightened_prompt --dry-run`
- Dry-run VLM tagging (uses fixture): `spike\.venv\Scripts\python.exe spike/test_vlm_tagging.py --dry-run`
- Dry-run the end-to-end edit: `spike\.venv\Scripts\python.exe spike/end_to_end_edit.py --screenshot <path> --region-label wall --material <swatch> --dry-run`
- Resume the overnight loop: see [spike/REPORTS/RESUME.md](spike/REPORTS/RESUME.md).

## Conventions

- Reuse existing helpers — `overlay_canny_edges` and `make_comparison_grid` in `spike/run_b1_baseline.py`, the `google-genai` client wiring in `spike/modal_app.py`, the `composite()` PIL idioms — rather than reimplementing.
- Renderer classes subclass `spike/renderers/base.py:Renderer` and expose `name`, `cost_per_call_usd`, and `render(screenshot_path, prompt, *, seed=None) -> bytes`. Import must not require API keys; failures surface only when `render()` is actually called.
- Outputs go under `spike/outputs/<spike>/<sub>/`. `.gitignore` excludes raw `.png/.jpg` outputs but **allows** diagnostic visualizations (`*overlay*`, `*sidebyside*`, `*comparison*`, `edges.png`).
- Never commit `.env`, API keys, or service-account JSON. `.gitignore` covers these — don't override.

## Session-log protocol

The wiki is only useful if it stays current. Every session must update it. Treat this as load-bearing, not optional.

**At session end** (or when the user says "log this", "session handoff", "wrap up", or similar), do the following:

1. **Prepend a new entry to [wiki/SESSIONS.md](wiki/SESSIONS.md)** using this template:

   ```
   ## YYYY-MM-DD — <short scope>

   **Scope:** one sentence.
   **Decisions:** bullets — link to [[DECISIONS]] entries created (or "none").
   **Tried:** what was attempted, including dead ends.
   **Outcome:** what changed in the repo / state.
   **Follow-ups:** open items, blocked work, things to revisit.
   ```

2. **If the session made a non-obvious or non-reversible choice, also prepend an entry to [wiki/DECISIONS.md](wiki/DECISIONS.md)** using this template:

   ```
   ## YYYY-MM-DD — <decision title>       {#kebab-case-anchor}

   **Decision:** the choice, in one sentence.
   **Context:** what prompted it.
   **Alternatives considered:** 1–3 bullets.
   **Reasoning:** why this over the alternatives.
   **Revisit if:** what would invalidate this.
   ```

3. **If repo state changed** (task done / blocked / new, costs spent, gate result), **overwrite [wiki/STATE.md](wiki/STATE.md)** — it is a snapshot, not a log.

4. **If a spike progressed**, update the relevant `wiki/spikes/<spike>.md` page so its status and findings reflect reality.

Use plain markdown with `[[wikilinks]]` for cross-references inside the wiki, and plain links for files outside it. Newest entries go on top in both `SESSIONS.md` and `DECISIONS.md`.

If you don't write to the wiki, the next session loses context. The cost of one extra paragraph at the end of a chat is much smaller than the cost of re-deriving the project state.
