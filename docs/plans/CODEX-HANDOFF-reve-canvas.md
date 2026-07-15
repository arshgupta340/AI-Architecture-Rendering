# Codex handoff — build "Reve Canvas" (Track 2)

> **Paste this whole file to Codex as the opening instruction, or run Codex in the repo and say "read `docs/plans/CODEX-HANDOFF-reve-canvas.md` and begin."** It is written to be self-contained: it tells you where everything lives, how to orient, what to build, and which config files to generate for yourself.

---

## 0. Who you are and what you're building

You are Codex, taking over development of **Reve Canvas** — a web app that wraps **Reve 2.x's layout API** (an image model whose internal scene representation is an editable JSON "layout" of labeled regions) in an **architecture-native layer management system**. Architects upload a viewport screenshot / draft render / photo, get an auto-generated layer panel of every architectural element (walls, glazing, roof, vegetation, sky…), swap materials and objects per layer non-destructively with full version history, and re-render. It is the fast-to-market **2D sibling** of an existing 3D "mesh-first" product in the same repo.

**The complete specification already exists — read it, do not re-derive it:** [`docs/plans/PRD-reve-canvas.md`](PRD-reve-canvas.md). Your job is to execute that PRD, starting with the validation gate, not to redesign it. If you believe something in the PRD is wrong, raise it as a question before changing course.

Your working environment: **Codex CLI, locally, on the user's Windows machine, inside the existing monorepo, on branch `track/reve-canvas`** (already checked out, PRD + spike already committed there).

---

## 1. Orient first — read these, in this order

Do not write code until you have read these. They are the single source of truth; answer "what/why/where/next" from them, not from guessing.

1. **[`CLAUDE.md`](../../CLAUDE.md)** (repo root) — project overview, hard rules, repo layout, canonical commands, the **session-log protocol** (mandatory — you must follow it too). This is the other agent's instruction file; **do not edit it**. You will generate your own `AGENTS.md` (see §4) that coexists with it.
2. **[`wiki/README.md`](../../wiki/README.md)** and **[`wiki/STATE.md`](../../wiki/STATE.md)** — the wiki is the project's working memory. STATE has a **"Track 2 — Reve Canvas"** section describing exactly where this track stands.
3. **[`wiki/DECISIONS.md`](../../wiki/DECISIONS.md)** — read the top entry `{#reve-canvas-track}` (why this product exists, alternatives rejected, revisit-triggers) and `{#mesh-first-prd}` (the sibling 3D track).
4. **[`docs/plans/PRD-reve-canvas.md`](PRD-reve-canvas.md)** — THE spec. §2 architecture invariant, §3 features F1–F7, §4 economics, §5 roadmap phases, §6 gates, §9 risks, and the **Reve API appendix at the bottom** (verified endpoint/schema facts). Read all of it.
5. **[`spike/reve/run_reve_spike.py`](../../spike/reve/run_reve_spike.py)** — the validation harness you will run first (§3). Its docstring restates the Reve request shapes and the pass/fail criteria C1–C6.
6. **Convergence references** (the layer model you build must stay compatible with the 3D track):
   - [`apps/web3d-prototype/src/state/store.ts`](../../apps/web3d-prototype/src/state/store.ts) — the `HeroLayer` and `Layer` types. Your `CanvasLayer` mirrors these (same `semantic` strings, `regionKeys` ↔ `regionIds`, base/region split).
   - [`apps/web3d-prototype/src/lib/swatches.ts`](../../apps/web3d-prototype/src/lib/swatches.ts) — the 29 CC0 ambientCG PBR materials. You re-express these as **prompt scaffolds with the same `id`s** in `packages/arch-taxonomy`.
   - [`spike/schemas.py`](../../spike/schemas.py) — the legacy 13-label region vocabulary your taxonomy is a superset of.

**The Reve research is not a separate file** — its findings are captured verbatim in the PRD appendix, the DECISIONS entry, and the spike docstring. Treat those three as your Reve reference. For exact request field names, also consult the official SDK: **github.com/reve-ai/reve-sdk** (see §3, first live call).

---

## 2. Your environment and the non-negotiable repo rules

**Platform:** Windows. Shell is PowerShell (primary); Git Bash is available for POSIX scripts. Use Windows paths.

**Python (for the spike only):** always `spike\.venv\Scripts\python.exe`. Never bare `python`. Deps (`httpx`, `numpy`, `Pillow`, `respx`, `pytest`) are already installed in that venv.

**Hard rules inherited from `CLAUDE.md` (these bind you too):**
- **Cost discipline.** The repo's default cap is **$0.05/session**. The user has **explicitly raised this to $5.00 for the Reve validation spike only** (§3). No other paid API calls — no Modal, no Gemini/BFL/Replicate, nothing — without a fresh explicit ask. The app build itself must spend **$0** (mocks + fixtures).
- **Never commit `.env`, API keys, or service-account JSON.** `.gitignore` covers them; do not override. The user manages `spike/.env`; **do not read, print, echo, or move it** — load the key only through the helper already in the spike script.
- **Branch model.** Work on `track/reve-canvas` (already checked out). Never commit to `main`. Never `git push` without an explicit ask. Never `--no-verify`, never force-push, never `--amend` shared history.
- **Session-log protocol (load-bearing).** At the end of every working session, update the wiki: prepend a dated entry to [`wiki/SESSIONS.md`](../../wiki/SESSIONS.md); if you made a non-obvious/irreversible choice, prepend to [`wiki/DECISIONS.md`](../../wiki/DECISIONS.md); if repo state changed, overwrite the relevant part of [`wiki/STATE.md`](../../wiki/STATE.md). Templates are in `CLAUDE.md` under "Session-log protocol."
- **Stay in your lane.** Touch only Track 2 surfaces: `apps/reve-canvas/`, `packages/arch-taxonomy/`, `spike/reve/`, `spike/REPORTS/reve_spike.md`, `spike/REPORTS/cost_ledger.md`, `docs/plans/PRD-reve-canvas.md`, and the wiki. **Do not modify the 3D app (`apps/web3d-prototype/`), the other spikes, or `CLAUDE.md`.**

---

## 3. STEP 0 — Run the validation gate BEFORE building anything

The entire product is gated on a ≤$5 live spike. **Do this first. Do not scaffold the app until it passes.**

1. **Confirm the key.** The user has purchased Reve credits ($10 min pack) and placed `REVE_API_KEY=...` in `spike/.env`. Verify presence *without printing the value*: run the dry-run (below) — it will error clearly if the key is missing. If missing, stop and ask the user.
2. **De-risk the request shapes first (cheap).** The layout endpoints are **experimental**; a field rename wastes a paid call. Before any live call, read the official SDK (github.com/reve-ai/reve-sdk — the `Layout`/`Region` types and the `extract_layout`/`render_layout`/`create` request bodies) and cross-check them against the payloads in `run_reve_spike.py` (`ReveClient._post` and the `extract_layout`/`render_layout`/`create` methods). Fix any field mismatch in the script.
3. **Dry-run (spends $0):**
   ```
   spike\.venv\Scripts\python.exe spike/reve/run_reve_spike.py
   ```
   Confirms fixtures resolve and prints the exact call plan (~$1.37 planned, $5 hard cap).
4. **Live, cheapest step first ($0.32):**
   ```
   spike\.venv\Scripts\python.exe spike/reve/run_reve_spike.py --live --steps S1
   ```
   This validates that the request shapes are correct against the real API before spending more. Inspect `spike/reve/outputs/S1_*_raw.json`.
5. **Full live run:**
   ```
   spike\.venv\Scripts\python.exe spike/reve/run_reve_spike.py --live
   ```
   Raw responses save to `spike/reve/outputs/` before any parsing; scores land in `spike/reve/outputs/spike_results.json`.
6. **Score and record.** Write **`spike/REPORTS/reve_spike.md`** (a new report, following the style of other `spike/REPORTS/*.md`): tabulate C1–C6 with the numbers from `spike_results.json` and your visual judgment of the output PNGs (C2 warping / C3 quality / C5 photorealization need eyes on the images at full zoom). Append the paste-ready cost lines the script prints to **`spike/REPORTS/cost_ledger.md`** and update its running total.
7. **The gate decision:**
   - **C1 (extraction sanity) AND C2 (geometry preservation, <5% drift outside the edited bbox — the KILL GATE) both pass → proceed to §4/§5.**
   - **C2 fails → STOP.** Do not build. Prepend a kill/redirect entry to `wiki/DECISIONS.md`, update `wiki/STATE.md`, and report to the user. Sunk cost stays ≤$5. This is a designed, acceptable outcome — respect it.

---

## 4. Generate your own config files (your equivalent of CLAUDE.md)

Once the gate passes, generate the configuration you need to work well in this repo. Codex reads `AGENTS.md` files hierarchically, so create:

**A) `/AGENTS.md` (repo root)** — check whether one already exists; if so, extend it rather than clobbering. It must capture, in your own words, the repo-wide guardrails from `CLAUDE.md` §2 above so that *any* Codex session in this repo is safe: cost discipline, `.env` handling, the `spike\.venv\Scripts\python.exe` rule, the branch model, and the mandatory session-log protocol. Add a short orientation pointing Track-2 work to `apps/reve-canvas/` and its scoped file. Note that `CLAUDE.md` is the parallel instruction file for the other agent and must not be edited.

**B) `/apps/reve-canvas/AGENTS.md` (scoped)** — the app's working manual: the stack and versions; how to install/run/test/lint/build/deploy; the architecture invariants from PRD §2 (Reve key server-side only; snapshots immutable/append-only; every Reve response stored verbatim; exactly one stochastic engine; taxonomy is shared IP); the layer data model (§5 here); the guardrails in §6 here; and a "definition of done per phase" checklist. Keep it current as you build — it is the file the next session reads first.

**C) Supporting config** as the stack needs it: `apps/reve-canvas/.env.example` (documenting every required var — `REVE_API_KEY`, Supabase URL/anon/service-role, etc. — **with placeholder values only**), `.gitignore` additions for `.env.local`/build output, `README.md`, TypeScript/ESLint/Prettier config, and Supabase project config. Never write real secrets into any tracked file.

---

## 5. Build phases (from PRD §5) — deliver in order, review between each

You are authorized to **provision the backend infrastructure yourself** (the user chose "Codex provisions everything"): create the Supabase project and Vercel project via their CLIs, wire secrets into the platform secret stores (never into git), and use **free tiers** — if any provisioning step would incur a charge, stop and ask first.

**Stack (decided in the PRD): Next.js + Supabase.** Latest stable Next.js (App Router, TypeScript). Supabase for auth (magic-link), Postgres, storage, and **Edge Functions** (the render worker — the only place the Reve key ever lives). Stripe is deferred (gate G2); billing in V1 is manual credit grants.

- **P2 — Skeleton.** Next app in `apps/reve-canvas/`; Supabase project + `supabase/migrations/0001_init.sql` (tables `profiles, projects, images, snapshots, layers, edits, jobs, credit_ledger, device_tokens`; owner-scoped RLS; ledger insert via RPC only). Job pattern = Postgres `jobs` table + Supabase Edge Function worker (`supabase/functions/render-worker/` — **the sole Reve-key touchpoint**, key in function secrets) + client polling. Ship the vertical slice: **upload → `extract_layout` job → region overlay renders on the image.**
- **P3 — Layer engine (the core IP).** Build `packages/arch-taxonomy/` (semantic vocabulary + `ALIASES` matcher + `REGION_TYPE_HINTS` + the 29 swatch prompt scaffolds, ids matching `swatches.ts`). Build the model in §5 below: auto-layerize on extract; per-layer edit surfaces (material swatch grid ported from the web3d Sidebar pattern, lighting/sky presets, object add/remove/move via layout `commands`); edits **batch** behind an explicit Render button (one `render_layout` call carries N layer changes); the debit-before-dispatch credit path.
- **P4 — History & trust.** Snapshot-DAG version tree; variant branching; client-side diff overlay + **drift-score badge** (% pixels changed outside edited regions — zero API cost); replay/rebuild; export + metered upscale.
- **P5 — Rhino bridge (thin).** `apps/rhino-bridge/push_to_canvas.py` using the `CaptureToBitmap` pattern in [`spike/rhino_capture.py`](../../spike/rhino_capture.py) → POST to `/api/ingest` with a hashed device token. The local Rhino MCP is reachable from this machine for live end-to-end testing.
- **P6 — Beta hardening.** Manual credit-grant admin path; server-side queue smoothing against the founder-key rate limits (10/min, 200/hr, 2,000/day); error taxonomy; deploy to Vercel + Supabase.

**Out of V1 (do not build):** Stripe, SAM/mask refinement, any user-visible multi-model, Photoshop plugin, create-from-prompt as a primary mode, teams, mobile, video. (PRD §3 "Out of scope" + §6 gates.)

---

## 6. The layer model and the guardrails that make this product honest

**The honest framing (put this in your `AGENTS.md`):** Reve returns **one flat image + a layout of bounding-box regions** per render. There are **no pixel masks and no separable image layers.** Therefore a "layer" here is a *named, typed, persistent handle onto a set of layout regions, carrying an edit stack whose results are immutable `(image, layout)` snapshots in a DAG.* Photoshop mental model on the surface; git underneath. See PRD §2–§3 for the full model and the TypeScript types (`Snapshot`, `CanvasLayer`, `Edit`, `RegionKey`).

**Guardrails — these are product-defining, not style preferences:**
- **The Reve API key never reaches the browser or the Next.js bundle.** Every credit-spending call goes: client → Next API route (auth + ledger debit) → Supabase Edge Function (holds the key) → Reve. No exceptions.
- **No user-visible multi-model selection, ever.** Reve's API license prohibits aggregator UX. Any provider abstraction is internal only.
- **Honest UI.** Regions render as rectangles/outlines, never as "pixel-perfect masks." Layer visibility is a render-input flag with an explicit "Rebuild replays N edits ≈ \$X" confirmation — not free compositing. Market it as element-aware editing, not masking.
- **Every Reve response stored verbatim** (raw JSON + image) before parsing.
- **No unlimited-render tier.** Every render is metered ledger spend.
- **RegionKey identity:** encode stable ids into Reve's free-form `label` (`${semantic}.${slug}#${idx}`). The spike's C6 tells you whether they round-trip verbatim; if not, implement the IoU re-matching fallback (PRD §3 R1.3).

---

## 7. Verification (do not ask the user to check manually)

- **Spike:** dry-run must print the plan at $0 before any live call; reconcile spent credits against the Reve console.
- **App:** verify each phase in a real browser preview — upload→overlay (P2); wall-swap → re-render → undo in <3 min ≈ $0.22 (P3); variant branch + diff badge (P4). Check `read_console_messages`/network for errors. Test Supabase RLS with a second user account (owner isolation). Confirm the key is absent from all client bundles (grep the built output).
- **Tests:** mocks only, never real network. Reuse the repo's discipline — `respx` for HTTP, fixtures for Reve responses (save real ones from the spike as fixtures). App: component/integration tests as the stack supports.
- **Cost:** after any live spend, the `cost_ledger.md` total must reconcile with the Reve console balance.

---

## 8. Definition of done for the first handoff back to the user

1. `spike/REPORTS/reve_spike.md` written; C1–C6 scored; gate decision recorded in the wiki; `cost_ledger.md` updated.
2. If the gate passed: `apps/reve-canvas/` P2 skeleton running locally with the upload→extract→overlay slice working end-to-end against your provisioned Supabase, plus `packages/arch-taxonomy/` started; your `AGENTS.md` files generated; a clean commit history on `track/reve-canvas`.
3. Wiki updated per the session-log protocol.
4. A short status message to the user: what passed, what you built, what you provisioned (with any accounts created), and what you need next.

---

## 9. Surface these to the user — do not guess

- **User-facing brand name.** "Reve Canvas" is an internal placeholder; shipping a product with "Reve" in the name invites trademark trouble. Use `reve-canvas` as the package/dir placeholder, but ask the user for the real name before anything public (repo description, UI chrome, deploy URL).
- **Any provisioning step that would incur a charge** beyond free tiers (Supabase paid tier, Vercel Pro, storage overages at 4K image scale).
- **Interior fixture:** the spike's S3 needs a founder-supplied interior photo at `spike/reve/fixtures/interior.png` (skips gracefully if absent) — ask if you want interior coverage in the gate.
- Anything in the PRD you think is wrong — raise it, don't silently deviate.

**Begin with §1 (orient), then §3 (the gate). Do not scaffold the app before the gate passes.**
