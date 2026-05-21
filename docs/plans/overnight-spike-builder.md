# Plan: Overnight scaffolding agent for Spikes 2.5, 3, and 4

> Migrated from `~/.claude/plans/all-right-i-want-zany-blanket.md` on 2026-05-19. Original kept as personal backup. Live status tracker is `spike/TASKS.md`; resume notes are in `spike/REPORTS/RESUME.md`.

## Context

The full project plan is in `~/.claude/plans/i-am-thinking-of-jolly-squirrel.md`. Spike 2.5/B1 (Nano Banana seed-baseline) is essentially done — four renders + scoring rubric live in `spike/outputs/spike2_5/b1/`, just uncommitted. The remaining work for **Spikes 2.5/B2+B3, 3, and 4** is mostly *scaffolding*: writing renderer-client modules, a comparison driver, scoring helpers, a VLM tagging function, and an end-to-end edit driver. None of it actually needs to *run* against paid APIs to be useful — it needs to *exist*, be clean, and be tested with mocks so that tomorrow morning we can plug in API keys and start live testing immediately.

This plan sets up a sandboxed Claude subagent (`spike-builder`) that grinds through a task board overnight on a dedicated branch, writing code and writing per-task reports. Hard constraints:

- **Cost ceiling: $0.05** for the whole night (planned spend: one $0.01 Gemini 3 Pro tag call as a single live smoke test; everything else is mocked).
- **No Modal calls** of any kind (GPU spend is $0.35–0.70 per run — out of budget).
- **No live API calls** to any provider other than the single planned Gemini smoke test.
- **All work on a dedicated branch** (`overnight/spike-builder-2026-05-17`) branched off `renderer-bakeoff` *after* committing the in-progress B1 work.
- **One agent task = one git commit + one report file**, so you can wake up, read 19 short reports, skim 19 commits, and merge selectively.

## Branch + commit strategy

1. On `renderer-bakeoff`, agent's **first** task (T01) commits the in-progress B1 work as a clean checkpoint:
   - `spike/modal_app.py` (uncommitted: added `seed` + `extra_constraints` params)
   - `spike/run_b1_baseline.py` (new untracked file)
   - `spike/outputs/spike2_5/b1/*` (untracked outputs)
2. Then branches `overnight/spike-builder-2026-05-17` off that commit.
3. Every subsequent task commits to `overnight/...` only. **Never to `renderer-bakeoff` or `main`.**
4. No `git push`. No `--no-verify`. No force operations.

In the morning, you review commits one-by-one and either fast-forward `renderer-bakeoff` to the overnight branch or cherry-pick.

## The task board

Lives at `spike/TASKS.md`. Format: GFM checklist, one row per task, each row links to its report. The agent flips `- [ ]` → `- [x]` only after the commit lands and the report is written.

**19 tasks total**, grouped by spike. Sized so each is 5–20 min for the subagent and produces one focused commit. (Note: the second column maps to plan sections in `jolly-squirrel.md` for traceability.)

### Spike 2.5 — multi-renderer bake-off scaffold (12 tasks)

| ID | Task | Files |
|----|------|-------|
| T01 | Commit in-progress B1 work on `renderer-bakeoff`, then create `overnight/spike-builder-2026-05-17` | git only |
| T02 | Renderer-package skeleton: `spike/renderers/__init__.py` + `base.py` with `class Renderer(ABC)` exposing `render(screenshot_path, prompt, *, seed=None) -> bytes` | `spike/renderers/{__init__,base}.py` |
| T03 | `nano_banana.py` — thin adapter that calls existing `render_from_model_view` from `modal_app.py`. Reuse, don't duplicate. | `spike/renderers/nano_banana.py` |
| T04 | `flux_bfl.py` — clients for **FLUX Canny Pro** + **FLUX Kontext Pro** via `api.bfl.ml`. Reads `BFL_API_KEY` from env. No live calls. | `spike/renderers/flux_bfl.py` |
| T05 | `magnific.py` + `recraft.py` — Magnific Relight/Mystic + Recraft V3 native API stubs. Env-gated. | `spike/renderers/{magnific,recraft}.py` |
| T06 | `replicate_models.py` — Qwen-Image-Edit, HiDream-E1, Recraft V3 (Replicate-hosted). `REPLICATE_API_TOKEN`. | `spike/renderers/replicate_models.py` |
| T07 | `spike/scoring.py` — `silhouette_iou()` and `edge_density_delta()` (pure CV, no network) + `count_windows()` stub that *would* call Gemini 3 Pro (env-gated, not invoked) | `spike/scoring.py` |
| T08 | `spike/compare_renderers.py` — B3 driver: fan out to all renderers, build comparison grid + overlay grid + `scores.csv`. Currently every renderer is gated by env-var presence, so running it today does nothing destructive. | `spike/compare_renderers.py` |
| T09 | `spike/run_b2_variants.py` — B2 prompt-variant scaffolds (tightened / higher-res / multi-region / multi-pass). Code only; default dry-run mode prints what *would* be called. | `spike/run_b2_variants.py` |
| T10 | Update `spike/.env.example` with placeholders for `BFL_API_KEY`, `REPLICATE_API_TOKEN`, `FAL_KEY`, `MAGNIFIC_API_KEY`, `RECRAFT_API_TOKEN`. Add `spike/PROVIDERS.md` with one paragraph per provider (signup link, pricing, free tier). | `spike/{.env.example,PROVIDERS.md}` |
| T11 | Pytest fixtures + tests for every renderer client using `responses` or `respx` to mock HTTP. Verifies: env-var lookup, request shape, response parsing, error handling. Zero network. | `spike/tests/test_renderers.py` |
| T12 | Update `spike/requirements.txt` if any new deps were imported (`respx`/`pytest`/etc.); document each | `spike/requirements.txt` |

### Spike 3 — VLM tagging scaffold (4 tasks + 1 smoke test)

| ID | Task | Files |
|----|------|-------|
| T13 | `spike/schemas.py` — Pydantic models for `Region {id, label, bbox, confidence, parent_id?}` and `TagRegionsResponse {regions: list[Region]}`. Used by both Modal-side code and tests. | `spike/schemas.py` |
| T14 | Add `tag_regions()` Modal function in `spike/modal_app.py` — Gemini 3 Pro structured output, returns `TagRegionsResponse`. Code only; not deployed. | `spike/modal_app.py` |
| T15 | Repurpose `segment()` to accept either click point *or* bbox prompt (SAM2 supports both natively). Keep existing signature working via union type / back-compat. | `spike/modal_app.py` |
| T16 | `spike/test_vlm_tagging.py` — driver that loads a render, calls `tag_regions`, draws bboxes + labels with PIL, saves visualization. Defaults to a `--dry-run` mode that uses a fixture JSON instead of a live call. | `spike/test_vlm_tagging.py` |
| **T17** | **SMOKE TEST** — actually call `tag_regions()` once against the existing `outputs/spike2/render.png`. Budget: ≤$0.05. Verify schema parses, save raw JSON to `outputs/spike3/smoke_test.json`, append cost + result to `spike/REPORTS/cost_ledger.md`. **This is the only live API call of the night.** | `spike/outputs/spike3/`, `spike/REPORTS/cost_ledger.md` |

### Spike 4 — end-to-end edit scaffold (3 tasks)

| ID | Task | Files |
|----|------|-------|
| T18 | `spike/cache.py` + `spike/composite.py` — disk cache for depth/normal/mask artifacts; composite helper that takes base render + mask + tile and produces final image. Pure local; no network. | `spike/{cache,composite}.py` |
| T19 | `spike/end_to_end_edit.py` driver — full pipeline wiring: render → tag → SAM2 refine → IP-Adapter+FLUX Fill → composite. Default `--dry-run` mode prints the call graph without invoking Modal. | `spike/end_to_end_edit.py` |
| T20 | Pytest end-to-end mock test for the Spike 4 pipeline. Mocks every Modal function and external API. Verifies the orchestration glue is correct. | `spike/tests/test_end_to_end.py` |

(Total: 20 tasks. The "19 tasks" framing in the strategy section assumed T01 was setup-only; it does deserve its own row.)

## The agent: `spike-builder`

Lives at `.claude/agents/spike-builder.md` (project-local). Invoked by the `/loop` skill or directly by the main Claude session.

### Allowed tools
`Read`, `Glob`, `Grep`, `Edit`, `Write`, `Bash` (constrained — see below), `TodoWrite`.

### Hard boundaries (encoded in the agent's system prompt)

**Filesystem write scope:**
- Allowed: `spike/**`, `spike/REPORTS/**`, `spike/tests/**`, `.claude/agents/spike-builder.md` (self only, for tightening — and only if asked to). Allowed to edit `spike/.env.example` but **never** `spike/.env`.
- Forbidden: anything outside `spike/` and `.claude/agents/spike-builder.md`. Specifically forbidden: `apps/**`, `services/**`, `db/**`, root config files, `.git/**`, `MEMORY.md`, plan files.

**Git scope:**
- Allowed: `git status`, `git diff`, `git log`, `git add <specific files>`, `git commit`, `git checkout -b overnight/...` (T01 only), `git rev-parse`.
- Forbidden: `git push`, `git checkout <other-branch>`, `git reset --hard`, `git rebase`, `git merge`, `git branch -D`, `--no-verify`, `--amend`, `git stash drop`, `git clean`.
- Every commit must be on `overnight/spike-builder-2026-05-17`. The agent verifies this with `git rev-parse --abbrev-ref HEAD` before every commit and aborts the task if it's on the wrong branch.

**Network / spend scope:**
- **Default: zero network calls of any kind.** No `pip install` (deps must already be in `.venv`), no `modal run`, no `modal deploy`, no `curl`, no `wget`, no `requests` invocations in scripts the agent runs.
- **Single exception: T17.** The agent is allowed to invoke `python spike/test_vlm_tagging.py --live` exactly once, only after having written the task's "before" snapshot to its report. The agent must record the actual cost (from API response metadata if available, else conservative estimate $0.05) in `spike/REPORTS/cost_ledger.md`. If the running total exceeds $0.05, the agent aborts and writes a STOP note.

**Process/tool scope:**
- Allowed: `python -m pytest`, `python -m ruff check`, `python -c "import ..."` (offline import sanity), `python script.py --dry-run`.
- Forbidden: anything that would spin up a long-running server, daemon, or browser. No `npm`, no `docker`, no `modal token`, no interactive prompts.

**Failure mode:**
- On any error (test failure, import error, lint failure, branch mismatch, cost-cap hit), the agent marks the task `- [!]` (blocked) in `TASKS.md`, writes a report explaining the failure, **does not commit broken code**, and moves on to the next task.
- If three consecutive tasks fail, the agent stops the entire run and writes a `STOPPED.md` summary at the top of `spike/REPORTS/`.

### Per-task contract (the agent follows this every iteration)

1. Read `spike/TASKS.md`. Pick the first `- [ ]` row.
2. Verify branch (`overnight/spike-builder-2026-05-17`). If not, STOP and write a report.
3. Read the relevant existing code (don't re-read it for every task — be efficient).
4. Implement the change. Run any local checks (`pytest`, import-check) the task calls for.
5. Stage **only** the files listed in the task row + the report file. Never `git add .`.
6. Commit with message `[T<id>] <task title>` and a body listing files changed.
7. Write `spike/REPORTS/T<id>.md` with: what was done, files touched, test/lint output (truncated), any surprises, follow-ups for the human, time elapsed.
8. Update `spike/TASKS.md`: flip `- [ ]` → `- [x]` and append `→ [report](REPORTS/T<id>.md)`.
9. Return.

## Loop driver (how 20 tasks get done while you sleep)

Two equally good options — pick at exit-plan time:

**Option A — `/loop` dynamic (default).** I run `/loop` in dynamic mode tonight with a self-pacing prompt. Each wake (every ~20 min via `ScheduleWakeup`) re-reads `TASKS.md`, spawns `spike-builder` for the next unstarted task, waits for it to finish, then schedules the next wake. The loop self-terminates when `TASKS.md` has no `- [ ]` rows or after 12 hours, whichever first. Recovery if a task hangs: the wake check finds the same `- [ ]` row and re-spawns; if the same task fails twice, it's marked `- [!]` and skipped.

**Option B — single long subagent invocation.** Spawn `spike-builder` once with the whole task list. Faster end-to-end (no wake overhead) but no checkpointing — if it gets stuck, you lose the rest. Reject unless we want speed over safety.

**Recommendation: A.**

## Pre-flight: testing the agent before you sleep

Before kicking off the overnight loop, we run **T01 + T02 manually** as a smoke test of the whole machinery (agent definition, boundaries, task-board update flow, report writing, commit shape).

- T01 is the lowest-risk task: pure git operations, files already exist.
- T02 is the next-lowest: write 2 small Python files with abstract classes, no network, no tests yet.

We invoke `spike-builder` with just those two tasks and watch:
1. Did it commit to the right branch?
2. Did it stage only the files the task said?
3. Are the commit messages clean?
4. Did it write usable reports?
5. Did `TASKS.md` get updated correctly?

If anything is off, we tighten the agent definition before launching the loop. If everything looks right, we say "go" and the loop runs unsupervised.

## Critical files to be created

- `.claude/agents/spike-builder.md` — agent definition with the boundaries above (system prompt, allowed tools, hard rules)
- `spike/TASKS.md` — the 20-row task board
- `spike/REPORTS/README.md` — explains report format + indexes per-task reports
- `spike/REPORTS/cost_ledger.md` — append-only running cost log (starts at $0.00)
- `spike/PROVIDERS.md` — one-paragraph-per-provider quick reference (added by T10)
- `spike/.env.example` — env-var template (extended by T10)

…plus everything the tasks themselves create (`spike/renderers/`, `spike/scoring.py`, `spike/compare_renderers.py`, etc., as listed in the task table).

## Reusable building blocks (don't reinvent)

- `render_from_model_view()` in `spike/modal_app.py:107` — already wraps Nano Banana Pro with the geometry-preservation prompt. T03 wraps this, doesn't duplicate.
- `run_b1_baseline.py:make_comparison_grid()` — image-grid layout helper. T08 (`compare_renderers.py`) reuses it, doesn't reimplement.
- `run_b1_baseline.py:overlay_canny_edges()` — Canny overlay diagnostic. T07 (`scoring.py:edge_density_delta`) reuses this.
- Existing `scoring_rubric.json` schema in `outputs/spike2_5/b1/` — T08 mirrors its rubric structure for the bake-off.
- `outputs/spike2/render.png` — existing render used as fixture by T16 dry-run and T17 live smoke test.
- `test_assets/model_views/building.png` — canonical input image, reused everywhere.
- Existing `google-genai` client in `modal_app.py` — T14 (`tag_regions`) reuses the same client and credential pattern.

## Verification (how you confirm it worked in the morning)

1. `git log overnight/spike-builder-2026-05-17 --oneline` — should show ~20 commits in `[Tnn]` format.
2. `cat spike/TASKS.md` — every row should be `- [x]` or `- [!]`. Count the `[!]` rows.
3. `cat spike/REPORTS/cost_ledger.md` — verify total ≤ $0.05.
4. `ls spike/REPORTS/T*.md` — should be 20 files.
5. `python -m pytest spike/tests/ -v` — all mock tests pass without network.
6. `git diff renderer-bakeoff..overnight/spike-builder-2026-05-17 --stat` — sanity-check the file footprint is what we expect (~20 new files in `spike/`, plus modifications to `modal_app.py`, `.env.example`, `requirements.txt`).
7. Open `spike/REPORTS/T17.md` (the live smoke test) — verify the Gemini call returned a valid schema and the visualization makes sense.
8. If happy: `git checkout renderer-bakeoff && git merge --ff-only overnight/spike-builder-2026-05-17` (or cherry-pick selectively).

## Open follow-ups for the morning (not for the overnight agent)

These are explicitly *out of scope tonight* — you'll do them yourself:
- Fill in remaining seeds/scores in `outputs/spike2_5/b1/scoring_rubric.json` (manual scoring of existing B1 renders).
- Acquire API keys for BFL, Replicate, Magnific, Recraft.
- Run B2 prompt variants live (~$0.16 total).
- Run B3 multi-renderer bake-off live (~$3–5 total).
- Decide the production renderer based on the rubric.
