---
type: log
updated: 2026-07-16
---

# Session Log

Append-only conversation log. **Newest at top.** One entry per chat session.

## 2026-07-16 — Overnight: commit triage + entourage scale audit (no unit bug) + KTX2 blocked

**Scope:** Unattended overnight run on new branch `overnight/2026-07-16` (from `track/reve-canvas` HEAD): triage the ~11 uncommitted Reve-spike-aftermath changes into logical commits, run the test suite, execute the wiki NEXT queue (KTX2, entourage scale), $0 spend.
**Decisions:** none (housekeeping gitignore additions only).
**Tried:** File-by-file diff review before committing — found and repaired a `§`→backtick text corruption in 6 places across [[DECISIONS]]/[[SESSIONS]]/[[STATE]] that the 2026-07-15 session's edits had introduced; the corruption never entered history. Checked for the KhronosGroup `ktx` CLI (absent → KTX2 encode skipped per plan). Entourage audit parsed raw GLB POSITION accessors to independently verify the hardcoded `glbHeightUnits`/`glbBaseY` values (Bush 1.582/−0.235 exact; Tree ymin −0.243 exact). The queued full-360 research memo turned out to already exist ([[research/full360-options]], committed 2026-07-13) — not duplicated.
**Outcome:** 5 commits on `overnight/2026-07-16`: `b13db5f` wiki kill-gate bookkeeping (§-repaired), `b417750` Reve spike report + cost ledger ($2.43 running total), `d3de035` raw Reve evidence (JSONs + overlays), `68cb20f` gitignore agent-runtime state + June glb intermediates + .hermes.md, `75614e1` entourage scale audit report. Tests 87/87 pass. **Entourage verdict: NO unit bug** — world unit is feet everywhere, per-species GLB heights are measured and normalized correctly; trees read small because `DEFAULT_ENT_HEIGHT.tree = 18 ft`, the slider caps at 30 ft, and per-species `baseHeightFt` is dead code at render (all species collapse to the flat global `treeFt`). Levers documented in `spike/REPORTS/entourage_scale_audit.md`. Live API spend: $0.
**Follow-ups:** KTX2 still blocked on installing KTX-Software (steps in `apps/web3d-prototype/scripts/encode_ktx2.mjs` header + tonight's digest). Optional entourage polish (not a bug): raise tree default 18→24 ft, cap 30→~50 ft, restore per-species height ratios. Merge: `main` fast-forwards cleanly to `overnight/2026-07-16`; all `worktree-agent-*` branches are fully merged and safe to delete. Digest: `C:\Users\arshg\overnight\digests\2026-07-16-rendering.md`.

## 2026-07-15 — Reve Canvas live spike → C2 kill gate failed; product stopped

**Scope:** Pick up `docs/plans/CODEX-HANDOFF-reve-canvas.md`, validate its assumptions against the live checkout/current official Reve SDK, and execute the cheapest decisive portion of the Phase-0 gate before any app build.
**Decisions:** [[DECISIONS#reve-canvas-killed]] — stop the Reve Canvas product after the C2 kill gate failed; do not scaffold the app or spend on the remaining spike steps.
**Tried:** Read the required repo/wiki/PRD/spike/convergence sources and shared Reve Canvas memory; confirmed branch `track/reve-canvas`; cross-checked request bodies against the current official `reve-ai/reve-sdk`; ran the $0 plan and 87/87 mocked tests; verified `REVE_API_KEY` through the script helper without reading/printing `spike/.env`; recovered from an initial zero-cost HTTP 402 after the user funded the API Budget; ran two baseline extracts, one targeted architectural-region refinement, and one keyed wall→travertine render. Raw JSON was saved before parsing and the source/output was inspected undistorted and at building scale.
**Outcome:** Spent 320 credits ($0.4267 exact pack value; balance 7,500→7,180). Strict C1 failed: baseline match rates were 66.7% exterior / 70.0% viewport; a refinement prompt recovered roof + siding but reached 77.8%, below the 80% threshold. C2 failed decisively: 7.1% measured drift outside the edited bbox vs <5%, source 1504×656 reframed to 5440×3072, composition shifted, and the requested travertine did not visibly replace the shingle siding. C6 RegionKey round-trip passed once. C4/C5 were not run because the gate says stop on C2. Full report: [`spike/REPORTS/reve_spike.md`](../spike/REPORTS/reve_spike.md). No app scaffolding began.
**Follow-ups:** Preserve the raw responses and taxonomy findings, but redirect product effort to the mesh-first geometry-locked track. Revisit Reve only if its API gains reliable source-frame preservation and genuinely region-confined architectural edits that pass <5% outside-region drift on these fixtures.

## 2026-07-16 — Reve Canvas: overturned the kill (mechanism error), building the slice

**Scope:** User redirected from a Codex handoff to "build it yourself per the PRD" (Reve key in `spike/.env`). Ran the live spike, discovered the prior kill was a false negative, reconciled the record, started the build.
**Decisions:** [[DECISIONS#reve-canvas-revived]] — overturn the 2026-07-15 kill to CONDITIONAL PASS (supersedes [[DECISIONS#reve-canvas-killed]]).
**Tried:** Validated Reve request shapes against the official SDK (github.com/reve-ai/reve-sdk `reve/v2/types.py`+`image.py`) — my harness matched exactly, no wasted calls. Live spike: `render_layout` prompt-rewrite (what the prior session used) over-preserves the reference → material never changes (the false negative). Found the real edit path = `create_layout` **`change` command** → `render_layout(ref=image)`: swapped shingle→travertine with geometry pixel-locked (1.34% drift, C6 verbatim). Consulted Opus (`/advice`): reframing is a registration detail (composite masked delta onto source), object-level regions → "click an object, edit material facets", interiors are the top unknown. Spend this session ~$1.07 (cumulative Reve gate ~$1.50 of $5).
**Outcome:** Branch `build/reve-canvas`. Superseding DECISIONS entry (kept the kill note with a forward-pointer — honest reject→confound→retest→reverse record). Rewrote `spike/REPORTS/reve_spike.md`; new spike scripts (`run_edit_mechanic/primitives/gate_closeout.py`). **Confirmation battery ran GREEN** — interior room → 27 regions (floor/ceiling/walls + furniture → GENERAL scope, not exteriors-only), facet isolation (wall→travertine, roof stable), framing pinnable. Then **BUILT the thin vertical slice**: `packages/arch-taxonomy/` (shared vocab + 29 material scaffolds, matchSemantic 12/12) + `apps/reve-canvas/` (Next.js 16/React 19/Tailwind 4, port 5182). Core loop verified end-to-end LIVE through the UI: upload/sample → extract (14 typed layers) → click building → cladding facet → travertine → change-command edit → 6144×2688 aspect-pinned render → before/after. Server-only Reve client + mock mode ($0 dev). Reve spend this session ~$2.45 (gate+app), cumulative ledger $4.87 of $5. Commits: overturn, battery, taxonomy, app.
**Follow-ups:** NEXT phase = Supabase auth + snapshot/edit-graph persistence + credit metering + job queue; masked-delta composite-back onto source; version tree/variants/drift-badge; Rhino bridge. PRD §4 economics = ~$0.21/edit (2-call) — update. Decide user-facing brand name (avoid "Reve"). Un-vendor arch-taxonomy once monorepo workspace wiring lands. Attended review + merge `build/reve-canvas`.

## 2026-07-14 — Reve deep-dive → Track 2 launched: Reve Canvas PRD + validation-spike harness

**Scope:** User discovered Reve 2.x's layout API (layered/region-addressable image generation) and asked for deep research + a PRD for a fast-to-market architecture wrapper while the 3D track continues.
**Decisions:** [[DECISIONS#reve-canvas-track]] — new sibling 2D product track, spike-gated (≤$5 authorized).
**Tried:** Two-agent research pass — (a) repo/wiki synthesis, (b) Reve deep-dive (docs are a JS SPA; schemas extracted from the `v2-shared-docs-*.js` bundles). Key findings: layouts = labeled bbox regions with hierarchy + region_type, NOT pixel masks; output is always one flat image + layout JSON; extract/create/render_layout ≈ $0.11 each, experimental, direct-API only (no aggregator carries them); renders 40–80 s; no fine-tuning offering exists (closed weights) — "architecture fine-tuning" must be taxonomy + prompt scaffolds + workflow; API license permits embedding, prohibits user-visible multi-model aggregation; rate limits 10/min / 200/hr / 2,000/day per key; official Python SDK exists (github.com/reve-ai/reve-sdk). Quality: Reve 2.1 #2 on the arena, best-in-class layout control + iterative-edit stability, but arch-viz photorealism unbenchmarked (one review saw melting building windows at zoom) → hence the spike gate. One founder-LinkedIn page contained embedded prompt-injection text; discarded as untrusted content.
**Outcome:** New branch `track/reve-canvas` (off `overnight/2026-07-13`). Wrote [PRD-reve-canvas.md](../docs/plans/PRD-reve-canvas.md) (mirrors mesh-first structure: F1–F7 scope, unit economics at $19/29/mo vs ~$0.11/render COGS, evidence gates G1–G4, ranked risks) + this wiki set. Built the Phase-0 spike harness `spike/reve/run_reve_spike.py` (dry-run default, `--live` opt-in, ≤$5 cap, criteria C1–C6; fixtures: `spike/outputs/e2_house/renders/flux_depth.png` photoreal + `spike/outputs/e2_house/beauty.png` shaded viewport + user-supplied interior). User decisions locked via Q&A: sibling product/shared brand · upload-first loop · web + thin Rhino bridge · credits SaaS on founder key · Next.js + Supabase · solo/small-firm $19–29/mo · $5 spike authorized.
**Follow-ups:** user buys the $10 Reve credit pack (api.reve.com/console) + drops `REVE_API_KEY` into `spike/.env` → run the live spike → score C1–C6 → C1∧C2 pass gates the `apps/reve-canvas/` build (P2 skeleton: Supabase schema + job pipeline + upload→extract→overlay slice). Decide user-facing brand name (shipping with "Reve" in the name invites trademark trouble). Prior open items unchanged (HF-token rotation, full-360 Candidate-A, overnight-branch merge review).

## 2026-07-13 — Overnight: commit-triage of the multi-view arc + full-360 research memo + entourage audit

**Scope:** Unattended overnight run (orchestrator + subagents): triage/commit ~41 uncommitted changes from the multi-view hero arc, verify tests, KTX2 audit, entourage scale check, full-360 consistency research memo.
**Decisions:** none — the full-360 recommendation is seeded in [[research/full360-options]] for an attended decision.
**Tried:** KTX2 encode (skipped — no KhronosGroup `ktx` CLI on PATH; exact install steps in the overnight digest); entourage unit-bug hunt (measured every GLB — no bug exists to fix); EXA MCP was permission-blocked for the research agent (WebSearch fallback used); the claude-mem plugin worker was down all session (hook noise; also blocked the Read tool — worth restarting/fixing).
**Outcome:** New branch `overnight/2026-07-13` (from `overnight/spike-builder-2026-05-17` HEAD): 9 triage commits (`a9f9c92`…`fdd16ec`) — env-configured FLUX.1 hero endpoint (zero-setup connect), deterministic material-proxy default in multiview+canvas (FLUX.2 opt-in), Rhino glTF export + post-process + CC0 ingest scripts, capture fixtures + diagnostic overlays, mesh-first PRD v1 + 17-agent research docs, showcase page, wiki, .claude config — plus `efcf915` = [[research/full360-options]] (3 candidates + recommendation: texture-space synchronized diffusion, FLUX-hero-seeded-UV hybrid, first; MV-Adapter fallback; orbit-video only as baseline). **Full test suite 87/87 green** on the committed work. Entourage audit verdict: slider-feet → world-feet math is EXACT (all 12 GLB normalization constants match measured bounding boxes to stored precision; world unit = feet, proven from Scene/GeoTiles/rhino_export); "trees read small" is a design-default issue — 18 ft default height, 30 ft slider cap, and per-species `baseHeightFt` unused by the scale code (no size variety) — and comments in `Entourage.tsx`/`entourageAssets.ts` overstate what the code does.
**Follow-ups:** attended review + merge decision (main can fast-forward to `overnight/2026-07-13`; the three `worktree-agent-*` branches are patch-equivalent to HEAD → deletable); run the full-360 Candidate-A experiment per [[research/full360-options]]; entourage design pass (raise tree default/slider cap, wire `baseHeightFt` for per-species variety, reconcile stale comments); install the `ktx` CLI then run `scripts/encode_ktx2.mjs` (NEXT #4); `spike/outputs/web3d_house/house*.glb` (2×14 MB) left uncommitted — decide git-lfs or regenerate; rotate the exposed HF token (still open from 2026-06-15).

## 2026-07-03 — Grand-idea research fleet (17 agents) → mesh-first PRD v1

**Scope:** User brought the "Model Insight" Lovable lab (engine/splat bake-off) + the grand idea (AI entourage → Seedance/Kling video fly-through → world-model editable splat env → embedded copilot, plus Enscape/V-Ray/Lumion integration) and asked for a multi-agent stress-test + production PRD.
**Decisions:** [[DECISIONS#mesh-first-prd]] — the mesh is the product; V1 = model-locked non-destructive re-rendering as a Rhino/Food4Rhino plugin; video/editable-splats/mutating-copilot deferred behind evidence gates.
**Tried:** 17-agent workflow (`wf_f03d1538-42b`): 7 Sonnet 5 EXA researchers (video-flythrough, world-models-splats, entourage, incumbent-integration, competitive-market, copilot-agent, pipeline-economics) → 7 Opus 4.8 adversarial stress-testers → 2 cross-cutting red teams → 1 synthesis architect. All 7 dimensions verdict "viable-with-changes"; red teams + synthesis converged unanimously.
**Key findings:** Veras (Nano Banana Pro) is now FREE-bundled in every Chaos tier (85/100 top firms) → zero model-layer moat; AI video warps building geometry across camera motion (all hosted models; geometry-true V2V = research, no hosted API); editable/relightable splats = research-stage AND Chaos already shipped splat relighting+clip (V-Ray 7 U3/Vantage 3.3.0); mutating copilots run 42–74% success (Figma data); the app lacks a global undo bus — "non-destructive" is a claim without a mechanism until it exists. The one defensible seam: true 3D-model-native geometry lock (semantic IDs from the mesh, not VLM tags on a screenshot) that survives "move the window 2 ft". Nuit = nearest thesis rival (non-destructive branching, but text/image-first, no model binding — primary watch item).
**Outcome:** [PRD v1 "mesh-first"](../docs/plans/PRD-v1-mesh-first.md) written (V1 scope = command/undo bus + Rhino capture plugin + productized hero + still turntable + labeled static splat backdrop + light-coherent entourage + read-only copilot; $29–39/mo; Food4Rhino GTM; evidence gates G1–G4 for video/splat-edit/copilot-mutation/gen-entourage). Full evidence: `docs/plans/research/grand-idea-2026-07/` (7 dimension reports + stress-tests + 2 red teams + synthesis).
**Follow-ups:** founder review of the PRD; week-1 Nuit teardown; rotate the exposed HF token (still open from 2026-06-15); Phase-0 build order = F1 bus → F2 plugin → F3 auth/cost-gating; semantic-ID stability spike (R2.2); nothing committed to git yet (PRD + research files are untracked — commit after review).

## 2026-06-15 — Multi-view hero: shipped per-view set; A/B/C consistency R&D (reproject built, full-360 partial)

**Scope:** Build a multi-view-consistent hero turntable. Shipped the per-view set, then — after the user (rightly) caught that independent FLUX per view is NOT 3D-consistent — ran a measured A/B/C investigation into true consistency.

**Decisions:** [[DECISIONS#web3d-reproject-consistency]] — true multi-view consistency must come from the REAL 3D (reproject the hero's pixels onto the mesh), not per-view diffusion.

**Built + shipped:** **(1)** the **per-view turntable** (`heroCaptureViewsFn` orbits N poses → renders each base-locked, same seed; gallery + Export all + bake-bridge `bakeFromHeroViews`), hardened via an adversarial-review workflow (13 confirmed fixes: object-URL leaks, null-controls bake target, mvBusy race, resolution clamp, resilient error handling). **(2)** UX polish from the prior entry stayed.

**A/B/C investigation (measured, not guessed):**
- **A — tighten the ControlNet lock:** edge-alignment 74.5% → **93.1%** (consistent across views) — fixes GEOMETRY but NOT lighting/material drift. Quantified with the project's canny∪id-edge metric (cv2).
- **B — IP-Adapter reference conditioning:** **BLOCKED** — diffusers 0.32.2's `FluxControlNetPipeline` has no `load_ip_adapter` (the FLUX IP-Adapter mixin is on the plain pipeline only). Implemented guarded (`ip_used:false`, base unaffected); testing it needs a risky diffusers bump + the XLabs adapter needs CFG 0.32.2 lacks.
- **C — reproject-from-3D** (the principled fix): `lib/reproject.ts` projective-texture-maps the hero's pixels onto the real mesh from each target camera (linear-eye-depth shadow-map occlusion + grazing-quality multi-source blend), gaps → `/region_edit` inpaint; chained around the circle. **Core VERIFIED** (single-hero reproject = perfect material/lighting consistency for nearby angles).

**QA caught (my own bugs, via rigorous inspection):** (a) the normal-quality metric blackened the flat ground at grazing (coverage 0.69 vs 0.19 non-black) → quality ranks sources only, coverage = any valid sample; (b) the FloatType-RT rewrite **darkened every reprojection** (sRGB→linear sampled, read back un-encoded) → raw passthrough (NoColorSpace + ColorManagement off), verified luminance ratio 0.99; (c) heroes rendered dark from the "golden-hour" prompt → bright-daylight prompt + moderate lock fixed exposure.

**Outcome:** reproject CORE correct + committed (`bb2b259`, `b2cdaae`); per-view set + polish committed. **The full 360° CHAINED turntable is NOT production-quality yet** — after fixing ground + color + exposure, the building still **dissolves into the ground in the back views** (chained gap-fill doesn't reconstruct the building for angles the hero never saw). Evidence: `spike/outputs/web3d_house/expC_turntable_N12.jpg`.

**Follow-ups (the focused next session):** debug the chained gap-fill building loss in back views (the `/region_edit` mask/fill for disoccluded building regions, or grazing smear); likely needs multi-hero anchors (front+back full renders) rather than a pure forward chain; then a loop-closure pass + UI integration. The single-hero reproject (nearby angles) is the solid usable core today.

## 2026-06-15 — Hero UX polish (keep-warm, model switch) + FLUX.2 backend (deploy-gated)

**Scope:** After the live FLUX.1 hero was verified (entry below), the user chose two follow-ups: (1) add FLUX.2 as a switchable "experimental" model, (2) polish the hero UX. Built + verified the polish; researched + wrote the FLUX.2 backend (deploy-gated).

**Decisions:** [[DECISIONS#web3d-flux2-experimental]] — FLUX.1 stays the live default; FLUX.2 is a SEPARATE, deploy-gated app (H200 + VideoX-Fun), not a flag.

**Tried / built:** **(polish)** a cheap `/warm` route on the FLUX.1 backend + a header **🔥 Keep warm** toggle that pings it every 240 s so an editing session skips the ~40–60 s cold start; a last-render **⚡ timing badge**; a warm/cold-aware busy overlay; a **backend-model badge** (reads the model id from `/warm`); and a **FLUX.1/FLUX.2 preset switch** in the Backend setup card that rewrites the endpoint host between the two Modal apps. **(FLUX.2)** researched the real constraints (EXA): FLUX.2-dev is **32B + Mistral-24B → BF16 needs an H200**, and its only canny/depth ControlNet (`alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`) runs through **VideoX-Fun, not diffusers**; wrote `spike/modal_flux2.py` (H200, same CORS `/hero_render`+`/region_edit`+`/warm` contract, canny∪id-edge lock, **native inpaint** region edits) with the VideoX-Fun loader block marked for first-deploy validation, plus `spike/REPORTS/flux2_feasibility.md`.

**QA caught:** the model badge stayed "FLUX.1" after switching to FLUX.2 when the base-URL field was blank — `model` was derived from `base` only; fixed to `modelOfUrl(base || region)`. Verified in preview: selector highlights + hint swap + URL host rewrite all correct.

**Outcome (verified):** `tsc` + `npm run build` green; redeployed `modal_flux.py` (additive `/warm`, render paths byte-identical → no regression); the **keep-warm toggle settled to "🔥 Warm" in ~18 s live**, badge read `flux1-dev-union`. Commits `cbb6df9` (polish + FLUX.2), `c2ef5d4` (prior live-verify docs). Container toggled back off → scale-to-zero.

**Follow-ups:** **multi-view-consistent hero** (orbit/saved-view capture → same-seed renders → a strip that feeds the splat bake) and **region_edit v2 true inpaint on FLUX.1** are the remaining hero polish — both deferred (need live multi-render verification / a new pipeline I couldn't GPU-test without more spend), documented not shipped half-done. FLUX.2 live deploy is user-gated (~70 GB download + H200 spend).

## 2026-06-15 — Hero FLUX backend DEPLOYED + live-verified through the real app UI

**Scope:** Continuation of the build session below. Took the (mock-QA'd) hero pipeline live: deployed `spike/modal_flux.py` to a real Modal A100-80GB, guided the user through HF token + `HERO_SHARED_SECRET` setup, brought the backend up, and verified **both endpoints end-to-end by clicking the actual app buttons** (not just `eval`).

**Decisions:** none new — confirms [[DECISIONS#web3d-hero-splat]] (FLUX.1-dev over FLUX.2 stands: FLUX.2's only depth/canny ControlNet is a local 80 GB checkpoint, no hosted Union equivalent). FLUX.2-dev-Fun ControlNet as a switchable "experimental" model is an offered follow-up, not yet built.

**Tried / live-debug fixes (in order, each surfaced by a real 4xx/5xx/ERR against the live GPU):** (a) FastAPI missing from the Modal image (1.4+) → add `fastapi[standard]`, and **pin a known-good FLUX dep combo** (diffusers 0.32.2 / transformers 4.49 / accelerate 1.1.1 — unpinned pulled diffusers 0.38/transformers 5.x and broke load); (b) **CORS** — Modal's per-endpoint decorator only CORS-es the OPTIONS preflight, not the POST response → rewrote as ONE `@modal.asgi_app()` FastAPI app + `CORSMiddleware` (both routes under `…heroflux-web.modal.run`); (c) `negative_prompt`/`true_cfg_scale` don't exist on 0.32.2's pipeline → add only if `inspect.signature` supports them; (d) "expected 3 channels, got 1" → `.convert("RGB")` on canny+depth; (e) **"shape invalid for input of size …" (the blocker)** — a bare 2-image list batched on a single ControlNet → wrap as `FluxMultiControlNetModel([union, union])` with `control_mode=[0,2]`; (f) **warm container kept serving OLD code after redeploy** → must `modal app stop arch-rendering-flux -y` before `modal deploy`; (g) Windows console crashes on Modal's ✓ glyphs → prefix `PYTHONUTF8=1`.

**Outcome (live, verified through the UI against the deployed A100):** all three live hits returned **200** — `/hero_render` 14.9 s warm → a **photoreal golden-hour house with every window / porch / stair / roof gable / wood-trim matching the 3D geometry (zero hallucination)**; `/hero_render` 58.3 s cold (boot included); `/region_edit` 21.0 s warm → a masked roof region layer composited over a byte-stable base. The full Photoshop modal flow (capture → base layer → add region → Run region → masked composite → 2/24 counter) works against the real backend. Idle = $0 (scale-to-zero, 300 s window). Live endpoint: `…--arch-rendering-flux-heroflux-web.modal.run` (`/hero_render` + `/region_edit`). Runbook + gotchas: `spike/REPORTS/modal_flux.md` (commit `33211cd`).

**Follow-ups:** (1) **rotate the HF token** — the user pasted it in plaintext during setup; it's now in Modal's `arch-flux` secret, fine to rotate the exposed copy. (2) FLUX.2-dev-Fun ControlNet as a switchable "experimental/high-quality" model. (3) `region_edit` v2 = true `FluxControlNetInpaintPipeline` (vs full-pass+composite). (4) splat-bake (`spike/modal_splat.py`) still deploy-gated — gsplat CUDA build + 20k-iter training untested live. (5) generate a real Marble env `.spz` to seat the building in (the live hero invents its own desert/coastal context — the splat env is what grounds it in a chosen site).

## 2026-06-15 — Hero diffusion render (FLUX on Modal) + Gaussian-splat env — built + deep QA

**Scope:** Build the three forked-thread asks to *production* quality (user explicitly raised the QA bar — "no longer an MVP"): (1) a Gaussian-splat environment, (2) a depth+canny-locked diffusion "hero render" off the Export flow with a Photoshop layer system, (3) self-host FLUX on our Modal GPU. Plan approved via plan-mode ([[DECISIONS#web3d-hero-splat]]). The 4 parallel build agents hit a session rate-limit mid-run (2 of 4 files landed); I took direct ownership, finished the rest, and did a real QA/QC pass.

**Decisions:** [[DECISIONS#web3d-hero-splat]] — self-host FLUX.1-dev+ControlNet on Modal (not fal); GPU = **A100-80GB BF16** (one-line const); **skip Ideogram** (no ControlNet → can't geometry-lock); splat = Spark loader fed by drop-in Marble/CC0 **or** a Modal scene-bake (render-to-3DGS, no COLMAP since three -Z == OpenGL).

**Tried / QA caught (the load-bearing part):** Reviewed the agent-written `modal_flux.py` + `heroCapture.ts` as an engineer, not a checkbox — found + fixed **real bugs**: (a) Modal auth was broken (FastAPI `Header` never injected) → moved the secret to the request body; (b) the smoke test ran locally (no GPU) → proper `@modal.method().remote()`; (c) `negative_prompt` silently ignored → added `true_cfg_scale`; (d) FLUX /16 dim constraint unenforced; (e) canny resized bilinear (blurs the lock) → NEAREST; (f) **depth was wrong** (MeshDepthMaterial = non-linear, far=white) → rewrote as a LINEAR eye-space shader, NEAR=white (verified the FLUX/MiDaS convention via primary sources); (g) **the id buffer was corrupted** — sky/entourage bled into it (only the 12 semantic meshes were painted) → hide all non-painted renderables + one id PER SEMANTIC (cleaner canny edges, 12 not 6543 materials) + ColorManagement-safe byte-exact encoding.

**Outcome (verified in-browser against a GPU-free mock that runs the real conditioning):** depth near=white linear gradient ✓; ids byte-exact (b=0, all valid) ✓; **canny ∪ id-edges trace every window/mullion/trim/roof** (the geometry lock, visualized) ✓; full hero modal flow base→region-mask→layers→composite→visibility→save ✓ (region green tint lands ONLY on walls — byte-stable elsewhere); scene fully restored post-capture ✓; **Spark renders a real `.spz` composited with the building** ✓; zero console errors; `tsc` + `npm run build` green. Commits `4032595` (Phase-0 scaffold) → `f398ae3` (impl + QA).

**Follow-ups (deploy-gated, untested-here):** the live FLUX inference (`modal deploy spike/modal_flux.py` + HF token + `HERO_SHARED_SECRET` — runbook in `spike/REPORTS/modal_flux.md`) and the splat training (`modal_splat.py`; gsplat CUDA build is the first-deploy risk). Also: region_edit v2 = true `FluxControlNetInpaintPipeline`; WebGPU hero capture (async readback); a real Marble env splat to replace the butterfly test asset; multi-view-consistent hero → feed the scene-bake for a photoreal walkthrough.

## 2026-06-14 — Client-ready render push: materials@scale + real entourage + atmosphere + export (ultracode, 10 agents)

**Scope:** Take the minimal 3-mode web3d base to a **client-ready, sendable render**. Two ultracode Workflow phases: (1) a 7-agent research sweep (6 tracks + synthesis, EXA + deep_researcher), (2) a 3-agent parallel build on disjoint files, then a hand-integrated output layer + full preview verification.

**Decisions:** [[DECISIONS#web3d-clientready-composition]] — the client-ready image is the **WebGPU realtime Stage made presentable + captured high-res**, not a new route; splat-env (T3) + diffusion-hero (T4) are paid/renderer-forking → **scaffold/deferred**, documented not built. Research bible: [[research/web3d-clientready]].

**Tried:** Pre-edited `store.ts` with every new slice FIRST so the 3 parallel build agents only *read* it (eliminated the store merge-collision) → same-tree, file-disjoint agents merged with zero conflicts, whole-tree `tsc` clean on first try. De-risked all asset downloads up front (ambientCG zip, PolyHaven HDRI, poly.pizza page→uuid→glb scrape all verified before fan-out). Kept the delicate WebGPU node graph low-risk (vignette-only grade behind a uniform) and verified it on the headless AMD adapter.

**Outcome (all verified in preview):**
- **Materials 5→29** CC0 ambientCG PBR (correct per-category metric `tileFeet`), **searchable swatch grid** (search + category pills + albedo thumbnails). KTX2 encode script written; jpg ships ($0, no `ktx` binary in env).
- **Real entourage**: 12 CC0 Quaternius GLBs (8 trees, 4 bushes) instanced per-species behind the unchanged scatter-paint UX; improved-procedural people (licensing-safe). Procedural placeholders gone.
- **Atmosphere**: 4 golden-hour CC0 HDRI presets, sun-path arc (node-safe line/points), drei clouds (WebGL2-gated).
- **Path tracer FIXED** (was fully broken): isolated `ptScene` + `house_pt.glb` + live-swatch mirroring + glass + HDRI env + `.color` guard → building path-traces with the architect's chosen materials + HDRI GI (verified at 46 spp).
- **Output layer (hand-integrated)**: high-res **Export still** (verified 2620×1474 16:9 JPEG, non-black, 2× supersample + aspect crop, preserveDrawingBuffer), **Presentation mode** (hides all panels), **Cinematic grade** (WebGL2 contrast/sat/vignette/grain + WebGPU vignette), **ContactShadows** grounding (WebGL2 only), NavBar moved off the Sky panel.
- All 3 render modes verified (WebGPU not black on AMD adapter); production `npm run build` green; `tsc` clean.

**Follow-ups:** (1) WebGPU emits 6 benign `NodeBuilder: ShaderMaterial not compatible` warnings — pre-existing, = the 6-face equirect→cube PMREM of the HDRI `scene.environment`; render is correct. (2) KTX2 encode (needs `ktx` CLI + sharp). (3) CC0 cutout-people PNGs (license call) to replace procedural people. (4) Verify entourage real-world scale (trees read slightly small). (5) Scaffold T4 depth+canny capture / T3 Spark splat-context per [[research/web3d-clientready]]. (6) Optional takram physically-based atmosphere (ECEF rebasing).

## 2026-06-14 — Graphify the wiki: cross-link research pages + de-stale pre-pivot pages

**Scope:** Ran `/graphify` on `wiki/` (knowledge-graph build — 84 nodes, 150 edges, 12 communities) to audit links + staleness, then acted on the findings.

**Tried:** One semantic-extraction subagent → community detection. The graph cleanly split into a **web3d era** and the prior **2D-pipeline era**, and flagged that the nine `research/` pages were the graph's god nodes yet carried **zero** internal `[[wikilinks]]` (orphaned).

**Outcome:** Added "See also" cross-link footers to all research pages (wired to each other + [[STATE]] + the relevant [[DECISIONS]] anchors, per the graph's `semantically_similar_to` edges); fixed a broken link in [[research/web3d-ue-browser]] (`[[../STATE|web3d-realism]]` → `[[web3d-realism]]`); de-staled [[GLOSSARY]] (two-pivots banner + a new "web3d terms (current)" section), [[ROADMAP]] + [[STRATEGY]] (engine-first-web3d superseded banners, they were a pivot behind); added "since-built" notes to research pages that still called WebGPU "rough" / geo-context "not yet built" / the env map 128px. All `[[DECISIONS#anchor]]` targets verified. Commit `ccb019d`; `graphify-out/` (graph.html + GRAPH_REPORT.md) is gitignored.

**Follow-ups:** none new — NEXT-step direction unchanged ([[../docs/HANDOFF-web3d.md]] §Next-steps). Re-run `/graphify wiki --update` to refresh the graph after future wiki edits.

## 2026-06-14 — 3-way render comparison: WebGPU SSGI + WebGL2-GI + path-trace/Twinmotion (3 parallel Opus agents)

**Scope:** User goal: build three rendering paths in parallel to "see and compare" quality on the RTX — (1) three.js **WebGPU**, (2) a **WebGL2 GI** stack, (3) **UE5/Lumen** quality. Scaffolded a `renderMode` toggle (3 self-contained Stage components), committed the app, dispatched 3 worktree-isolated Opus agents, integrated + verified on the user's hardware.

**Decisions:** extends [[DECISIONS#web3d-realism-tiers]] — the WebGPU tier is now BUILT (not just a future spike); UE5/Lumen #3 is delivered via **Twinmotion** (installed), not an agent (an autonomous agent can't drive UE's GUI).

**Built (`apps/web3d-prototype`, branch overnight/…, commits d99d8ae→7299b38):**
- **Scaffold:** `store.renderMode` (`webgl2`|`webgl2gi`|`webgpu`) + NavBar segmented toggle; `App` lazy-loads the 3 Stages (so `three/webgpu` loads only in WebGPU mode); path-trace button guarded out of WebGPU mode. Committed the previously-untracked app so worktrees could branch.
- **Agent A — WebGPU** (`stages/StageWebGPU.tsx`+`WebGPUPost.tsx`+`WebGPUAreaLights.tsx`): three.js `WebGPURenderer` + native TSL post graph (**SSGI** + GTAO + TRAA + Bloom) + LTC area lights; AgX on the renderer (WebGPU applies it via `outputColorTransform`). **Renders — verified on the integrated build with a real WebGPU context; SSGI gives softer/warmer GI than the WebGL2 baseline.**
- **Agent B — WebGL2 GI** (`stages/StageWebGL2GI.tsx`+`AreaLights`+`ReflectiveGround`+`EffectsGI`): RectAreaLight (LTC) sky-fill + per-window emitters, `MeshReflectorMaterial` plaza, stronger N8AO. Verified (headless). Softened sky-fill 1.6→0.55 (was competing with the sun).
- **Agent C — path-trace reference + machine scout** (`PathTracer.tsx` on dequantized `public/model/house_pt.glb`, `UE_LUMEN_RUNBOOK.md`): scout → **Twinmotion 2025.1 + Lumion 2024 Student installed, RTX 4070; UE5/Blender/D5 not**. Path-trace geometry fixed (dequantized), but a **material-color crash remains** (deferred — task chip).

**Gotchas / verification:**
- WebGPU mode needed a fix: the shared drei `<Sky>`/`<Environment>` GLSL **ShaderMaterials don't compile on the WebGPU node renderer** → `SolarSky` is now render-mode-aware (node-safe color sky + lights in WebGPU; HDRI IBL there is a follow-up).
- **Capture trap:** Claude-in-Chrome screenshots can't grab the GPU canvas (shows black) and `canvas.toDataURL` is black without `preserveDrawingBuffer` — but the **headless preview has an AMD WebGPU adapter**, so it can screenshot WebGPU. Also lost time because the headless preview had drifted onto a **stale agent-worktree dev server (`:5196`)**; the integrated build is **`:5181`**.
- Path-tracer crash: `MaterialsTexture.updateFrom` reads `.r` of an undefined material color (glass/material without a color) — deferred.

**Outcome:** 3 working render modes behind one `renderMode` toggle on the live app, $0/client-side. 3 agent branches merged + integrated (commits `d99d8ae`→`4a3cbc2`).

**Post-build refinements (same session):**
- **Bundle:** all 3 stages `React.lazy` + Suspense fallback (`App.tsx`) — `three/webgpu` (~900 kB) loads only in WebGPU mode; main chunk ~920 → **306 kB gzip**. (Tried eager `StageWebGL2` — it folds the shared `Scene`+three into main, 1.1→2.0 MB; reverted.)
- **WebGPU IBL DONE:** node-safe equirect HDRI on `scene.environment` (`SolarSky.WebGPUEnv`), PMREM-filtered internally by the WebGPU renderer (no GLSL ShaderMaterial); fill lights dialed to 35% in WebGPU mode. Verified reflections on the AMD-adapter headless preview. [[research/web3d-webgpu]]
- **WebGPU shadows VERIFIED real:** VSM cast shadows from the suncalc sun (NOT mimicked from WebGL2) — confirmed via three.js source (VSM landed r169 #29225, acne fixed r183 #32705) + cast shadows visibly shifting midday→golden-hour. WebGPU VSM = single shadow-casting light (our sun = fine).
- New research doc [[research/web3d-webgpu]]; new `apps/web3d-prototype/README.md`; wiki index ([[README]]) repointed to the web3d direction.

**Follow-ups (→ NEXT, for ultracode):** the **decked-out client-ready render** push — material library at scale + scale-aware input, real entourage (Twinmotion/low-poly quality, not gimmicky), **Gaussian-splat environment generation**, **consistency-locked diffusion hero** (depth+canny ControlNet, reusing [[DECISIONS#render-mask-registration]]), lighting/atmosphere polish. Full paste-in prompt in [[../docs/HANDOFF-web3d.md]] §NEXT-STEPS. Also: fix the deferred path-tracer material crash; kill the stale `:5196` dev server + prune leftover `.claude/worktrees/` dirs.

## 2026-06-13 — web3d realism pass (WebGL2 post stack + glass + soft shadows) + UE-in-browser research

**Scope:** Make the web3d graphics dramatically more realistic ("Enscape/Lumion/Twinmotion but front-end"). Researched the realism landscape (5 parallel web agents), then mid-session the user surfaced **client-side UE5-in-browser** (Wonder Interactive / SimplyStream) — researched via **EXA** (new standing preference). Then banked the cheap WebGL2 realism wins, verifying each in the browser.

**Decisions:** [[DECISIONS#web3d-realism-tiers]] — stay WebGL2 for the live tool and bank the post-stack/glass/shadow wins now; treat client-side UE5 (SimplyStream) as a low-commitment parallel *spike* for a "Cinematic" hero toggle, not a product bet (it's baked archviz — **no Lumen/Nanite in-browser** — and needs a per-model UE build); WebGPU three.js = later staged spike.

**Tried / built (each verified in preview):**
- **Post-processing stack** (`src/Effects.tsx`, NEW): `<EffectComposer>` = **N8AO** (the big AO win) + tamed **Bloom** + BrightnessContrast/HueSaturation + Vignette + SMAA + **AgX ToneMapping** last. `App.tsx`: renderer → `NoToneMapping` + `antialias:false` (the AgX *effect* owns tone mapping; double-mapping was the first washout). `vite.config`: added `@react-three/postprocessing`+drei to `dedupe`/`optimizeDeps` (Invalid-hook-call fix).
- **Real glass windows** (`Scene.tsx`): ONE shared `MeshPhysicalMaterial` (transmission 1, ior 1.5, roughness 0.07) across all `window` meshes, castShadow off — replaces the flat opaque panels (the #1 "toy model" tell).
- **Lighting** (`SolarSky.tsx`): baked-sky env 128→**256px** + a re-bake `key` so glass/metal reflections track time-of-day; **VSM soft shadows** (`shadows="variance"` + `shadow-radius`/`blurSamples`).
- **Anisotropy** 8→16 on swatch textures (sharper brick at grazing angles).
- Research: 5 web agents extend [[research/web3d-realism]]; **EXA deep-research → [[research/web3d-ue-browser]]** (UE-in-browser feasibility / toggle architecture / licensing).

**Dead ends / gotchas (load-bearing):**
- drei `<SoftShadows>` (PCSS) **breaks on three r0.184** — emits `unpackRGBAToDepth`, which r184 removed → shader won't compile → every MeshStandardMaterial fails → washout. **Use `shadows="variance"` (VSM) instead.**
- Default **Bloom veils the whole frame white** (procedural sky is very bright in the HalfFloat HDR buffer) — tamed to intensity 0.12 / threshold 1.1 / radius 0.6.
- Pre-existing harmless console noise: 3d-tiles `'content'` + "Invalid hook call" (geo r3f) and stale SoftShadows shader errors — the preview CDP buffer doesn't flush on `console.clear()`; the *render* is the reliable signal.

**Outcome:** `apps/web3d-prototype/` markedly more realistic on the live WebGL2 stack (AO depth, real glass, soft VSM sun shadows, AgX grade). NEW `Effects.tsx`; edited `App`/`Scene`/`SolarSky`/`swatches`/`vite.config`. **$0** (one EXA deep-research call on the user's EXA quota, not the Anthropic budget). New memory: prefer EXA for research.

**UE toggle — also BUILT this session:** `src/Cinematic.tsx` + NavBar "◆ Cinematic (UE5)" button + store `cinematic`/`cinematicUrl`. Full-screen overlay embeds a SimplyStream UE5 WebGPU build in an `<iframe>` deep-linked with current materials+sun; setup card + runbook when no URL; Open-in-tab / Change-build / Exit. **Verified in preview:** SimplyStream **allows iframe embedding** (`garage.cjponyparts.com` streamed to 100% in-app); the UE render itself needs a real WebGPU GPU (headless preview is black). Remaining = the user's own UE build (Datasmith→bake→variant configurator→upload) + a camera-sync TODO.

**Follow-ups:** user produces a SimplyStream UE build of the house + pastes the URL; camera-sync into the Cinematic deep-link; ground/reflective-floor + detail-map anti-tiling; WebGPU three.js staged spike (SSGI/GTAO/TRAA); optional real-HDRI IBL (trades dynamic-sky consistency for richer reflections); the app is still git-untracked — commit it.

## 2026-06-13 — web3d geo-context pillar: Google Photorealistic 3D Tiles + georeference

**Scope:** Built roadmap pillar #3 — enter lat/long → load **Google Photorealistic 3D Tiles** (via `3d-tiles-renderer`) around the model and **georeference** the Rhino model into the real site. `apps/web3d-prototype/`, still **$0 until a key is present** (tiles only fetch/bill when enabled + keyed).

**Decisions:** [[DECISIONS#web3d-geo-context]] — "bring the city to the model" coordinate strategy (ReorientationPlugin recenters tiles to the site origin; outer group scales metres→feet so every existing feet-based system is untouched; site lat/lng shared with the sun; `enabled` never persisted so reload can't auto-bill).

**Tried / built:**
- Researched the (version-churny) `3d-tiles-renderer` API against the **0.4.28 source** before writing a line: confirmed r3f exports (`TilesRenderer`/`TilesPlugin`/`TilesAttributionOverlay`/`EastNorthUpFrame`), `ReorientationPlugin{lat,lon (radians),height,recenter}`, `GoogleCloudAuthPlugin{apiToken}`, and that **Google tiles need a `DRACOLoader` via `GLTFExtensionsPlugin`** (geometry is Draco; textures JPEG, no KTX2) — `useRecommendedSettings` only sets `errorTarget=20`, it does NOT auto-wire decoders.
- New `src/GeoTiles.tsx`: TilesRenderer + GoogleCloudAuth + GLTFExtensions(draco) + Reorientation + TileCompression + Fade + AttributionOverlay, wrapped in an outer group `position=siteAnchor+groundOffset, scale=3.2808, rotation-y=heading`. `key` on apiKey/lat/lng/height for clean reload.
- Store `geo` slice (`enabled`/`apiKey`/`height`/`heading`/`groundOffset`/`hideRhinoSite`) + runtime `siteAnchor` (building ground-centre, set on model prep). `enabled` forced false in `partialize`.
- Scene wires `<GeoTiles>` (only when enabled + key), hides non-`BUILDING` semantics when geo on, sets `siteAnchor`. App `frameloop="always"` while geo on (tiles must stream).
- SkyPanel "Real-world context" section: API-key field (persist-local + `.env.local` `VITE_GOOGLE_MAPS_API_KEY` fallback), enable button (gated on key), elevation/seat/heading sliders, hide-site toggle, cost/attribution note. Added `.gitignore` + `.env.example` + `vite-env.d.ts` (the app had none — `node_modules`/`.env.local` were untracked-but-unignored).

**Verified (preview, no key):** typecheck clean; app loads error-free; new section renders with correct no-key disabled state; entering a key enables controls; **clicking Load mounts GeoTiles without crashing — all plugins construct and the Google auth request fires with the correct URL** (bad key → 400, non-fatal lib log, app stays alive). Restored clean state. **Could NOT verify actual tile imagery / georeference fidelity — needs the user's valid key** (expected split).

**Outcome:** geo-context pillar built; `apps/web3d-prototype/` gains `GeoTiles.tsx`, `vite-env.d.ts`, `.gitignore`, `.env.example`, +`3d-tiles-renderer@0.4.28` dep; store/Scene/App/SkyPanel edited. $0 spent. App still untracked (not committed).

**Follow-ups:** user validates with a real key (set elevation≈site m, then Seat/Heading sliders to align); bad/expired key logs a non-fatal lib error (could add a `load-error` toast); raycast auto-snap to terrain (replace manual Seat slider); pull Rhino true-north into `heading` automatically; remaining pillars — diffusion-hero add-in, real entourage assets, PMREM env-from-sky.

## 2026-06-13 — Arcway teardown → web3d engine-first pivot → MVP+V2+V3 built

**Scope:** Reverse-engineered competitor **arcway.ai** (Unreal pixel-streaming), then pivoted to an **engine-first web 3D rendering tool** and built it end-to-end in `apps/web3d-prototype/` (Vite+React+R3F).
**Decisions:** [[DECISIONS#web3d-pivot]] (engine-first; 2D diffusion → future add-in).
**Tried / built:** Rhino→semantic-glTF pipeline (`spike/rhino_export_gltf.py`, `gltf_postprocess.py`); R3F configurator (click element → PBR swap, layers, persistence); V2 (local→procedural lighting, box-projected metric UVs + scale slider, walk mode + saved views, meshopt compression 14.5→6.5 MB); V3 (entourage Tree/Bush/Person with real-ft height sliders; **Sky & Sun** panel with suncalc solar position + mood/time/date/intensity/cloud presets). 9 research/Explore agents (6 web-research docs under `wiki/research/`).
**Dead ends:** in-browser **path tracer** — runs but renders only sky; `three-gpu-pathtracer` incompatible with our meshopt/KHR_mesh_quantization geometry. Recommend diffusion hero instead.
**Outcome:** working $0 client-side tool at localhost:5181; new direction captured in [[STATE]]; handoff in [[../docs/HANDOFF-web3d.md]]; pip unblocked (removed deny rule).
**Follow-ups:** geo-context (Google 3D Tiles) pillar; diffusion-hero add-in; real entourage assets; PMREM env-from-sky + sun-path arc; fix or replace path tracer.

## 2026-06-13 — Brick lock honest metric (v3) + apply-engine unify (1 bg agent + foreground)

**Scope:** Two parallel candidate-next-steps the user picked: (A, foreground, paid-call-controlled) push the textured-material lock to actually beat naive; (B, background `general-purpose` agent) consolidate the single-view apply path onto the shared `multiview_apply` engine. Partitioned by disjoint file sets so they couldn't collide (A owns `run_multiview_lock_v3.py`+report+outputs and treats `multiview_apply.py` read-only; B owns `multiview_apply.py`+`server.py`+tests).

**Decisions:** [[DECISIONS#multiview-honest-metric]] — illuminant-invariant chroma is the cross-view consistency bar; A2 already beats naive for brick; A4 rejected; the smooth-material strategy ([[DECISIONS#multiview-material-class]]) is **reopened** as an open product question.

**Tried:**
- **A (`483cfe8`):** built `run_multiview_lock_v3.py` with an honest metric — de-light each view by its own trim illuminant, compare (a*,b*). FREE re-score of cached v1/v2 composites: **red_brick A2 honest dE_ab 1.59 vs naive 4.41 (−64%, BEATS naive)**; A1 2.92. Verified the metric (illuminants sane: ANCHOR warm RGB(1.10,1.00,0.90), FRONT cool (0.99,0.99,1.02); ~49k trim px in both views → no grey-world fallback; intrinsic-chroma mechanism — A2 (12.4,21.5) matches anchor (13.9,20.9), naive drifts red a*=18.2). Hypothesised A4 (chroma-preserving neutral ref); built it, **refuted offline** (A4-ref a*=23.2 redder than anchor 13.9 → would regress). **$0 spent.** Surfaced the travertine lit/honest tension (v1-raw is lit-best but honest-worst, 12.86).
- **B (`bca016b`):** extracted `materialize_view()` in `multiview_apply` (the anchor stage), moved `SWATCH_PROMPTS` there as the sole def + `material_desc_for()`; `server.apply_material` now delegates. API shapes, no-spend travertine path, and `MAX_LIVE_CALLS` guard all preserved. **75 → 82 tests.** Reviewed the diff myself; the one real change is the single-view live prompt now using the engine's `anchor_prompt` (one-comma difference, semantically identical).

**Outcome:** 2 commits on `overnight/spike-builder-2026-05-17`. 82 tests green. `REPORTS/multiview_v3.md` + sidebyside evidence + `metrics_v3.json`. Total fal spend unchanged at **≈ $1.99** (this session $0). **B additionally re-verified end-to-end on a fresh PORT-8766 server ($0, no live calls):** `verify_api` 22/22 + `verify_multiview_api` 15/15 (HTTP-level, beyond the 82 pytest), forcing the no-spend layer to regenerate through `materialize_view` by clearing its cache first. Measured nuance the suites don't assert: the unified no-spend travertine layer now soft-composites the precomputed image via `paste_tile` (like the multi-view anchor) instead of direct-masking, so feather edges blend slightly toward base — inside-mask mean|diff| 75.1→74.3 (~1%); interior, response shape, cost, and cache unchanged.

**Follow-ups:** **user product call** on the smooth-material lock strategy (route smooth → A2, or keep raw-anchor for perceptual sameness); optional ~$0.12 stochastic-robustness re-run of brick naive/A2 (prove the win is seed-stable); wire the honest metric into the canvas if it ever surfaces a consistency number; material library; Revit add-in.

## 2026-06-13 — Grasshopper "Send to Canvas" + multi-view lock v2 (2 parallel Opus agents, round 2)

**Scope:** Second parallel round — Grasshopper button (agent owned Rhino) + multi-view lock v2 & canvas wiring (Rhino-free agent).

**Outcome:**
- **P3.4 Grasshopper component (`22caf8d`):** real Rhino 8 GhPython "Send to Canvas" wrapping `capture_and_send`; authored live on the GH canvas via `g1_` MCP + GH SDK; validated against a mock receiver (render=False, $0): 92.9% decode, rising-edge + error paths. Files in `spike/grasshopper/` (incl. prebuilt `send_to_canvas.gh`).
- **P3.5 multi-view v2 + canvas (`92659ea`):** textured-material lock fixed by branching on material class (travertine raw-anchor; brick A2 neutral-reference = trim white-balance + luminance-flatten). v1 brick backfire resolved (texture-energy 25.9→9.5). Canvas shipped "one swatch → all views": view tabs, `/api/apply_material_all`, `/api/views`, reusable `spike/multiview_apply.py`. 75 tests; 21/21 + 22/22 back-compat. $0.30.

**Decisions:** material-class branching for the lock (smooth=raw-anchor, textured=neutral-reference); chroma-only dE_ab is the honest cross-view consistency metric.

**Follow-ups:** material library; consolidate single-view apply onto `multiview_apply` engine; Revit add-in; push neutral-ref further for brick.

## 2026-06-13 — Capture repeatability root-fix + multi-view material lock (2 parallel Opus agents)

**Scope:** Two parallel agents — fix capture in-session repeatability (A, owned Rhino) and build the multi-view material lock (B, no Rhino, on pre-captured views).

**Outcome:**
- **A (`0f49c7a`):** root-caused the "only first capture decodes, rest → 0.3%" bug — it was the bare `CaptureToBitmap(size)` overload returning a stale default-lit frame in headless Rhino (byte-identical across modes, fg median 157). Fix = `CaptureToBitmap(size, displayMode)` overload → median 191, ~97%. `capture()` now idempotent in-session (no reopen). Added white-pass health gate + `doc_path` retry; 69 tests. **Reverses the old E1 finding** (corrected `host_probe_rhino.py` #5). Main session independently re-validated: 2 captures/1 session → 90.5% & 92.9%.
- **B (`2cfbc55`):** multi-view material lock via anchor-reference (3rd FLUX.2 Edit ref = anchor's edited result). Travertine ΔE 7.43→4.14 (−44%, win); red brick backfired (baked-shadow/sun-direction mismatch) — finding: color-dominated materials lock, textured ones need lighting normalized first. $0.38.

**Decisions:** capture's reliable path is the mode-arg overload (not bare); multi-view lock works material-class-dependently (lighting normalization is the v2 unlock for textured materials).

**Follow-ups:** Grasshopper "Send to Canvas" component (capture is reliable now); multi-view lock v2 (lighting normalize) + canvas wiring; material library.

## 2026-06-12 — Capture→canvas wiring (P3.3) + warm polish + edge feather

**Scope:** Make "capture in Rhino → canvas updates" one motion; recover warm render look; feather composite seams.

**Tried/Outcome:**
- **Polish (no re-drift):** warmth was a prompt issue — a warm/specific prompt on the same canny+depth lock recovers terracotta/golden-hour while edge align holds 98.2%. `server._mask_png` now +1px dilate + ~1.1px feather. `warm_w1.png` promoted to base.
- **Wiring:** refactored the locked render into reusable `run_e2b_registration.render_locked()` (warm prompt baked in, reads native size from camera.json); `prepare_data.write_web_project()` extracted; new `apps/canvas-prototype/ingest.py:build_project` chains decode→render→prep; server gains `POST /api/ingest` + `GET /api/version`; `rhino_capture.capture_and_send()` is the Rhino-push button body; app.js polls version and auto-reloads. Validated live on a NEW camera view through `/api/ingest`: decode 92.9%, 98.5% edge align, version bumped, round trip via `capture_and_send` confirmed.
- **Two bugs surfaced + fixed:** (1) over-unhiding all layers blew out the camera frustum (fixed by fresh reopen + keeping the model's saved layer state); (2) **a long-idle/churned Rhino session returns a dim white-reference pass → 0.3% decode**; fresh reopen restores 90.5%. Added a guard: `build_project` rejects captures decoding <50% *before* the paid render. Also forced flat-unlit shading in `_ensure_id_display_mode`.

**Spend:** ~$0.22 (warm render + travertine regen + new-view ingest render). 62 tests green. Canvas restored to known-good e2_house_v2.

**Follow-ups:** in-Rhino auto-retry on dim white pass; real Grasshopper component; multi-view material lock (now cheap via the wiring).

## 2026-06-12 — Masking registration fix (E2b)

**Scope:** User reported the canvas prototype's region masking was inaccurate (brick over windows, smudged pillars). Diagnosed and fixed.

**Decisions:** Production render recipe changed from depth-only to **depth+canny ControlNetUnion** with a ground-truth-derived line drawing as the canny control; captures must be at the render's native (mult-of-16) size. See [[DECISIONS]] if promoted.

**Tried:** Overlaid GT boundaries on beauty (perfect — control) vs flux_depth render (5–25px drift) → root cause = depth can't pin coplanar openings + a 1514×659 vs 1504×656 resize mismatch. Re-captured e2_house at native 1504×656 (`e2_house_v2`, 90.5% decode); built canny = `Canny(beauty) ∪ instance-boundaries`; rendered via fal `flux-general` union (canny@0.8 + depth@0.5). Edge alignment 51.7% → 98.5% ≤2px. Validated brick-on-walls (clean windows/posts) and the app-path wall highlight.

**Outcome:** `spike/run_e2b_registration.py`, `spike/outputs/e2_house_v2/`, prototype repointed (prepare_data + server), layer-cache auto-clear added. ~$0.20 spend (ledger ≈ $2.54). 62 tests green; API smoke + regeneration confirmed. [REPORTS/E2b.md].

**Follow-ups:** bake `out_size` into `rhino_capture.capture()`; optional low-denoise flux-pro polish over the locked structure (measure for re-drift); 1–2px composite feather; flux-general (dev) render is slightly desaturated vs flux-pro.

---

## 2026-06-12 — Experiment ladder executed end-to-end + Phase 3 first builds

**Scope:** Ran the full E1–E6 ladder in one day, then built the Rhino capture module and the canvas layer-model prototype via two parallel agents.

**Decisions:** Production recipes locked — render = FLUX depth ControlNet on the true z-buffer (only candidate that registers pixel-for-pixel; criterion: geometry preservation = mask registration); apply-material = FLUX.2 Edit multi-ref(render, swatch) composited through the host mask ($0.06/swap; MatSwap contingency unnecessary for v1). Input model switched mid-stream from SFUrban (site-scale, linework noise) to kCs_SampleHouseProject (CSI layers) after staging review.

**Tried:** E1 ($0, SFUrban): 93.1% exact decode, 257 mullion instances — required white-reference pass (Rhino "unlit" = 0.7-slope headlight) + atomic capture. E6 ($0): ground-truth mask → paste_tile, zero leakage. E4 ($0.13): prompted Nano Banana segmentation = semantically right, geometrically redrawn (mullion IoU 0.003) — Veras's edge is the non-public tuning. E5 (~$0.50): hosted Grounded-SAM mullion IoU 0.02 on raw screenshots; re-test on photoreal pending. E2 (~$0.40, house model): depth wins the edge-overlay audit; fal canny pool dead; explicit image_size required. E3 (~$0.30): travertine gate passed; IP-Adapter/Kontext/Fill-text all failed as research predicted.

**Outcome:** All gates decided at ≈$2.28 of the $50 budget. Phase 3 deliverables: `spike/rhino_capture.py` (90.5% decode live verification, 62 tests) and `apps/canvas-prototype/` (hover/click/swatch/layers on real data, 22/22 checks, live brick call $0.06). ~15 commits on `overnight/spike-builder-2026-05-17`.

**Follow-ups:** capture→canvas direct wiring; material library + tile-scale control; multi-view material lock; E5 photoreal re-score; FAL_KEY placeholder in `.env.example` + fal paragraph in PROVIDERS.md.

Entry template (also in `CLAUDE.md` § Session-log protocol):

```
## YYYY-MM-DD — <short scope>
**Scope:** one sentence.
**Decisions:** bullets — link to [[DECISIONS]] entries created.
**Tried:** what was attempted (incl. dead ends).
**Outcome:** what changed in the repo / state.
**Follow-ups:** open items, blocked work, things to revisit.
```

---

## 2026-06-12 — Foundational pressure test → plugin-first pivot

**Scope:** Pressure-tested the screenshot-first architecture end-to-end via four Sonnet research agents (native host extraction, competitive landscape, generative SOTA, Vision Banana); decided a full plugin-first pivot with the screenshot pipeline retained as fallback tier.

**Decisions:**
- [[DECISIONS#plugin-first-pivot]] — plugin-first, two-tier architecture. Host plugins export beauty/ID-mask/depth/objects.json; tag+segment stages deleted on the plugin tier.
- User-confirmed: Rhino plugin first (MCP bridge available), hosted material path first (MatSwap on Modal only as contingency), public-launch ambition, ~$50 experiment budget for this phase.

**Tried:**
- Research agent 1 (host extraction): Rhino has true depth (ZBufferCapture) + ID masks (DisplayConduit workaround) + material R/W, ~2wk plugin. Revit has best semantics (native `OST_CurtainWallMullions`) + clean ID masks, no depth API. SketchUp: ID masks via material-swap only, no depth buffer. Forma: nothing — screenshot tier only.
- Research agent 2 (competition): the click-region + swatch-library + non-destructive-layers loop is unshipped anywhere as of mid-2026. Veras (Chaos-owned since Feb 2025) is closest, est. 6–12 months out; their v4.5 Smart Selection is selection-only, still prompt-driven after the click.
- Research agent 3 (generative SOTA): BFL deprecated Canny/Depth Pro endpoints (Oct 2025) — validates the Replicate consolidation; fal.ai flux-general is the canonical multi-ControlNet host. FLUX.2 [pro] Edit multi-ref is the best hosted swatch conditioner; MatSwap (self-hosted, takes true normals) is the fidelity ceiling. Florence-2→SAM 3 decisively beats Gemini→SAM 2 for the fallback tier.
- Research agent 4 (Vision Banana): verified real (DeepMind, arXiv 2604.20329) — Nano Banana Pro instruction-tuned into one-call open-vocab segmentation; beats SAM 3 on semantic/referring seg, loses on instance seg. NOT publicly available; Veras's use confirmed via EvolveLAB forum = partner access. Base model is public → cheap prompting probe possible.

**Outcome:**
- Plan approved: Phase 0 housekeeping → Phase 1 doc suite (docs/plans/research/*, master-plan v2) → Phase 2 experiment ladder E1–E6 (Rhino MCP extraction probe is the $0 keystone) → Phase 3 build.
- Committed the pending B3 renderer consolidation (`9fe1b40`).
- Plan of record: `~/.claude/plans/okay-now-i-want-floating-feigenbaum.md` (to be folded into docs/plans/ in Phase 1).

**Follow-ups:** User to provide FAL_KEY for E2/E3; E4/E5 runnable next; watch Gemini API changelog for a public Vision Banana endpoint.

**Same-session execution (Phases 0–2 partial):** B3 consolidation committed (`9fe1b40`); doc suite + wiki pivot committed (`06fd790`); **E1 PASSED** (`391669b`) — Rhino MCP extraction on the real SFUrban model, 93.1% exact pixel decode, 257 mullion instances pixel-accurate, true depth; required a white-reference pass (Rhino "unlit" = 0.7-slope headlight) and atomic capture; **E6 PASSED** (`0d368c9`) — ground-truth wall mask through `composite.paste_tile`, exact-instance edit, tag+segment bypassed. Keystone validated on day one of the pivot.

---

## 2026-06-11 — Side-project cleanup (masterplan/siteplan renders deleted)

**Scope:** Deleted all studio-side-project rendering work (masterplan perspective/elevation renders via Nano Banana/GPT-image/agy/codex, siteplan colorizer + PSD) at user request; preserved all Spike 2.5/3/4 work.

**Decisions:** none (cleanup only; user classified the work as disposable studio output, not product signal).

**Tried:**
- Audited git status before deleting: confirmed the uncommitted *tracked* changes (flux_bfl/magnific deletions, replicate_models consolidation, --skip-existing) were legitimate B3 spike work, NOT side-project — left untouched.
- Deleted untracked/ignored side-project files only: `render_masterplan.py`, `render_openai.py`, `colorize_siteplan.py`, `siteplan_regions.json`, `outputs/masterplan_renders/` (~100+ renders), `outputs/siteplan_*`, `build_siteplan.jsx`, `README_photoshop.md`. Verified zero leftovers via `git status --ignored` grep.

**Outcome:** Working tree reduced to pure spike work. 52/52 tests green. Note: one technique from the deleted work is worth remembering — the anchor-reference material-consistency trick (render aerial first, feed as reference to other views) is now cited in the roadmap as the multi-view material lock approach.

**Follow-ups:** none.

---

## 2026-05-22 — T25 FLUX Fill (Replicate) as a second apply_material backend

**Scope:** Add `--inpainter {sd_inpaint, flux_fill_replicate}` to `spike/end_to_end_edit.py`. Wire a direct call to `black-forest-labs/flux-fill-pro` via Replicate for the FLUX path. Live test on the spike2 photoreal pair (reusing T24's cache) and compare to T24's SD output. No IP-Adapter yet — text-only conditioning, same as SD path.

**Decisions:**
- FLUX Fill Pro via Replicate selected over (a) BFL API direct (account unfunded per B3-RUN-1) and (b) full Modal-hosted FLUX + IP-Adapter (multi-hour, multi-risk). Replicate path is single-day, no GPU mgmt, $0.05/call.
- Separate cache scope per inpainter (`tile` vs `tile_flux`) so T24's cached SD result is preserved and the two backends can be compared on the same warm (render, tag, mask) inputs.

**Tried:**
- Direct call (bypassing the `FluxFillProRenderer` class in `spike/renderers/replicate_models.py`) because that class takes file paths and B3 fires without a mask. Reused the polling pattern.
- Added `python-dotenv` import to `end_to_end_edit.py` so `spike/.env` provides `REPLICATE_API_TOKEN` without manual sourcing. Falls back gracefully if dotenv isn't installed.
- First live run hit `RuntimeError: REPLICATE_API_TOKEN not set` because the script wasn't loading `.env`. Fixed and re-ran — second attempt succeeded.
- 4 new pytest tests covering: full pipeline with FLUX inpainter (asserting Replicate URL + data URL encoding + prompt shape + Modal apply_material NOT called), missing-token-raises-clean, invalid `--inpainter` rejected by argparse, dry-run prints lower estimate. 52/52 pass.
- Built a 3-up crop comparison of the masked wall region from original / SD / FLUX composites. Confirms FLUX wins on resolution + edge fidelity; both still struggle on material conditioning (no IP-Adapter).

**Outcome:**
- Spike 4 pipeline now supports two inpainters via CLI flag. T24's $0.40-per-call cost dropped to $0.05.
- FLUX tile is 1259×848 native (vs SD's 512×512 forced downsample). 3.4× bytes, dramatically sharper window cuts and balconies.
- Material conditioning gap unchanged: without IP-Adapter, the swatch image isn't used; both inpainters work from the material *name* text token only. FLUX produces a slightly sharper cream surface, not distinctive travertine.
- Spike 4 status: pipeline integration solid, inpainter quality acceptable at the resolution/edge level, material conditioning still pending IP-Adapter.
- Cost ledger: $0.84 → $0.89. T25 marginal $0.05 under the $0.30–0.50 authorized budget — leaves $0.25–0.45 headroom for additional FLUX comparisons.

**Follow-ups:**
- IP-Adapter for FLUX (the remaining v1 piece): either find a Replicate model wrapping FLUX Fill + IP-Adapter, or build it on Modal. Replicate path preferred if available.
- More cheap FLUX comparisons: floor/ceiling on the interior dining pair, wall on the complex_windows tower, etc. Cache is warm; each new combo is ~$0.05.
- Cache pre-pop helper: T24 + T25 both did it manually. Worth a small reusable script.

---

## 2026-05-22 — T24 first live Spike 4 end-to-end run

**Scope:** Drive the full Spike 4 pipeline end-to-end on real data for the first time. Pre-populate render + tags cache (free), then run segment + apply_material live on Modal A10G.

**Decisions:**
- T24 user-authorized $0.45 spend for the first live Spike 4 run. Pre-cache pre-populated to skip the $0.06 of Gemini + Nano Banana that we already paid for in T21/T22.
- Spike 4 integration: PASSES. Pipeline runs end-to-end without errors; material quality limited by SD Inpaint 1.5, which is exactly why the master plan calls for FLUX Fill + IP-Adapter for v1.

**Tried:**
- Wrote a one-shot Python snippet to pre-populate `spike/.cache/render/` and `spike/.cache/tags/` from `spike/outputs/spike2/render.png` and `spike/outputs/spike3/t21/tagged_render.json`. T23's `parse_tolerant` round-tripped the tags cleanly into canonical post-parse JSON.
- Ran `spike/end_to_end_edit.py --live --screenshot spike/outputs/spike2/source.png --region-label wall --material spike/test_assets/travertine.jpeg --output spike/outputs/spike4/first_live/edit_result.png`.
- All 6 stages completed: render (cache hit) → tag (cache hit, 94 regions) → pick wall_1 (conf 0.95, bbox_norm (655,0,204,574) → bbox_px (825,0,257,487)) → SAM2 segment (mask 8.2% coverage, 3.4 KB) → SD Inpaint apply_material (tile 448 KB, 512×512) → paste_tile composite (1.6 MB output).
- Initially misread the thumbnail and thought the composite had transformed the entire image; on closer inspection only the masked wall region (upper-right facade) was modified — `Image.composite` is working correctly.
- Considered re-running with a tighter bbox or different material; deferred to keep the report focused.

**Outcome:**
- First live Spike 4 run on record. End-to-end orchestration confirmed working.
- Travertine swap *applied* but doesn't visibly *read* as travertine — SD Inpaint 1.5 has no material conditioning. Known limitation, addressed by FLUX Fill + IP-Adapter in v1.
- Cost ledger updated: $0.31 → $0.76.
- Report: [`spike/REPORTS/T24.md`](../spike/REPORTS/T24.md). spike-4 page status flipped to "T24 done".
- Cache state: render + tags + mask + tile for this specific (screenshot, wall, travertine) combo now warm. Re-running this exact combo is $0.00. Re-running with a different region or material is ~$0.45.

**Follow-ups:**
- Swap SD Inpaint 1.5 for FLUX Fill + IP-Adapter (the v1 stack) so material conditioning actually uses the swatch image. This is the biggest single quality win still on the table.
- Try other (region, material) combos using the warm cache to map out the failure surface for ~$0.45 each.
- Tighten wall bboxes from `tag_regions` so SAM2 doesn't receive bboxes that span sky/background.

---

## 2026-05-20 — T23 promote defensive tag_regions handling into production

**Scope:** Move the ad-hoc `_save_raw_response` and the duplicate-`y`-bbox JSON repair hook out of T22's one-off scripts (`spike/run_t22.py`, `spike/salvage_urban_tags.py`) and into `spike/schemas.py`. Wire production paths (`test_vlm_tagging.py`, `end_to_end_edit.py`) to use them so Spike 4 integration inherits the defensiveness.

**Decisions:** none new. Implements the existing [[DECISIONS#gemini-bbox-malformed-json]] policy in production code.

**Tried:**
- Added `save_raw_response(out_dir, raw, *, filename)` and `TagRegionsResponse.parse_tolerant(raw)` to `spike/schemas.py`. The latter takes `str`, `bytes`, `list`, `dict`, or an existing instance and survives Gemini's duplicate-`y` malformation via a JSON `object_pairs_hook`.
- Rewrote `test_vlm_tagging.py:_call_live` and `end_to_end_edit.py:_run_tag_regions` to take an optional `raw_save_dir` and use `parse_tolerant`. Both surface any dropped region IDs to the operator.
- Consolidated `run_t22.py` and `salvage_urban_tags.py` to route through the shared helpers — net code reduction, one source of truth for the parser.
- Added `spike/tests/test_schemas.py` with 16 tests across `save_raw_response`, `_bbox_pairs_hook`, and `parse_tolerant`. The duplicate-`y` regression test uses the exact byte sequence Gemini produced on urban_exterior so any future refactor breaking duplicate-key handling fails CI.
- Considered making `_dropped_region_ids` a real Pydantic field — deferred as cosmetic; `__dict__` stash works.

**Outcome:**
- 50/50 tests pass (34 pre-existing + 16 new).
- Salvage script reruns produce **bit-identical** result to T22 (44 salvaged, 3 dropped on urban_exterior). Behavior-preserving refactor confirmed.
- Spike 4 live integration is now safe to attempt — `_run_tag_regions` defends against the duplicate-`y` bug and persists raw data before validation.
- Report: [`spike/REPORTS/T23.md`](../spike/REPORTS/T23.md).

**Follow-ups:**
- Mullion-on-grid prompt iteration on complex_windows (~$0.01).
- Rename the two mislabeled SketchUp screenshots.
- Promote `_dropped_region_ids` to a real model field if it becomes load-bearing (cosmetic for now).

---

## 2026-05-20 — T22 production-shape Spike 3 eval + house-keeping commits

**Scope:** Render the 4 new screenshots via Nano Banana Pro, then tag each (screenshot, render) pair via Gemini 3 Pro to close the loop on T21's load-bearing finding. Also commit a backlog of untracked work: wiki bootstrap, project CLAUDE.md, docs/plans/, spike2.5/B2 outputs, .claude/ settings.

**Decisions:**
- Spike 3 gate is now considered PASSING for the purposes of integrating with Spike 4. Production-shape eval clears 4 of 5 pairs; the 5th (complex_windows) is a partial due to mullion miss on a dense grid, not a categorical failure.
- New finding: Gemini 3 Pro can produce malformed bbox JSON with duplicate `y` keys (`{x, y, w, y}` instead of `{x, y, w, h}`) — recorded as [[DECISIONS#gemini-bbox-malformed-json]]. Mitigation: defensive raw-response saving + tolerant parser; one-off salvage script `spike/salvage_urban_tags.py` recovered 44 of 47 regions on urban_exterior.
- Confirmed [[DECISIONS#tag-regions-needs-photoreal]] empirically: urban_exterior went from 0 windows (T21 screenshot-only) to 10 windows (T22 photoreal pair) on the same screenshot.

**Tried:**
- Built `spike/run_t22.py` driver (render + tag + visualize) with `--only` and `--reuse-render` flags. Dry-run first, then `--live`.
- 3 of 4 pairs completed cleanly on first try. Urban_exterior failed pydantic validation: every bbox had duplicate `y` key, no `h`. Saved raw response defensively (patched driver mid-run), retried with `--reuse-render` to avoid double-spending the render — same failure (reproducible).
- Wrote `spike/salvage_urban_tags.py` to parse the malformed raw JSON with `object_pairs_hook` that preserves duplicate keys and promotes the second `y` to `h`. 44/47 regions recovered.
- Considered re-rendering at a different size or with a tweaked prompt to dodge the JSON malformation; rejected as scope creep.
- Considered promoting the salvage hook into `test_vlm_tagging.py` in this session; deferred to a follow-up so T22 commits stay focused.

**Outcome:**
- 4 new (screenshot, render) pairs landed under `spike/outputs/spike3/t22/<slug>/`.
- Per-pair `meta.json` and root `scored_rubric.json` capture verdicts.
- Report: [`spike/REPORTS/T22.md`](../spike/REPORTS/T22.md).
- All 4 T22 pairs improved meaningfully over T21's screenshot-only versions; the urban_exterior improvement (0→10 windows) is the decisive proof point.
- Cost ledger updated: pre-T22 baseline was $0.10 (T17 + T21 + B3-PREP unintended); T22 added $0.21 (4 renders + 4 tags + 1 retry); session running total **$0.31**.
- Backlog commits landed: `81c9524` (wiki + docs + project CLAUDE.md), `97f3bb2` (spike2.5/B2 outputs), `4238de3` (.claude/ settings).

**Follow-ups:**
- **T23 candidate:** promote `_save_raw_response` + tolerant JSON parser into `spike/test_vlm_tagging.py:_call_live`. No API cost. Prevents future paid-data loss.
- **Mullion-on-grid prompt iteration** on complex_windows (~$0.01 per attempt). Low-cost optimization, deferred.
- The two SketchUp screenshot filenames are mislabeled (`modern interior.jpg` is exterior; `traditional exterior.jpg` is interior). Worth renaming when convenient.
- T22 driver should be merged into a "production-shape gate driver" usable for future Spike 3 regressions; for now `run_t22.py` is task-scoped.

---

## 2026-05-20 — T21 prompt revision + 5-image Spike 3 eval

**Scope:** Implement the T17 follow-ups (coord-space fix + prompt revision + multi-image eval) and re-score against the Spike 3 gate.

**Decisions:**
- [[DECISIONS#tag-regions-needs-photoreal]] — `tag_regions` should run on the photoreal render, never on raw 3D-model screenshots. Empirically demonstrated by T21's 5-image eval where the screenshot-only pairs missed major elements that the photoreal-render pair caught.
- Adopted Gemini's 0–1000 normalized coord output as the contract (matches what the model returns anyway); scaling to pixel dims is now consumer-side responsibility — implemented in both `test_vlm_tagging.py` and `end_to_end_edit.py`. Confirms [[DECISIONS#coord-space-consumer]].
- Budget exception: user authorized $0.05 over the standing $0.05/session cap to run T21. Running total $0.06.

**Tried:**
- Revised the `tag_regions` prompt with explicit coord-space declaration, tight-bbox rules, strict `parent_id` semantics, label discipline (door ≠ balcony glazing, mullion only when visible), and primary-building focus.
- Added `_scale_bbox_to_pixels` (`test_vlm_tagging.py`) and `_bbox_norm_to_pixels` (`end_to_end_edit.py`) — kept the two intentionally symmetric.
- Bumped test_end_to_end.py fixture render size to 1000×1000 so existing fixture bbox values still map 1:1 after scaling.
- Modal redeployed with revised prompt.
- 5 Gemini 3 Pro calls: pair 1 = existing T17 photoreal pair re-test; pairs 2–5 = 4 new screenshots, each passed as both screenshot+render (budget would not stretch to $0.20 of Nano Banana renders).
- Considered modifying `tag_regions` to accept a single-image mode for pairs 2–5; rejected as a contract change in service of a budget workaround.

**Outcome:**
- Code: 3 source files edited, 34/34 tests pass. Modal redeployed.
- Eval results: 2 PASS (pair 1 photoreal, pair 3 traditional/interior dining), 2 PARTIAL (modern exterior, complex windows), 1 FAIL (urban exterior — windows entirely missed).
- All 5 T17 quality issues (A–E) moved: A (coord-space) fixed, C (loose walls) fixed (per-window bbox count 0 → 77 on pair 1), D (door mislabel) fixed, E (parent_id misuse) fixed. B (flat confidence) unchanged — likely a Gemini limitation.
- First successful mullion detection (4 mullions on traditional/interior pair).
- Outputs: `spike/outputs/spike3/t21/tagged_*.png/json` (5 each) + `scored_rubric.json`.
- Report: [`spike/REPORTS/T21.md`](../spike/REPORTS/T21.md).
- Cost ledger updated: $0.01 → $0.06 (5 × $0.01 T21 entries).
- Spike 3 gate verdict: passes on the production-shape (screenshot + photoreal render) pair, fails on raw screenshots. Empirical proof that photoreal rendering is a prerequisite for tagging quality.

**Follow-ups:**
- **T22 (not yet created in TASKS.md):** when GPU/API budget allows ~$0.25, run Nano Banana on the 4 new screenshots (~$0.16) and re-tag (~$0.04) to validate the gate on production-shape pairs.
- Mullion detection still inconsistent — hit on traditional interior, missed on complex-windows facade. Prompt iteration needed for tightly-spaced mullion grids.
- The 4 new screenshots dropped by user: filenames `modern interior.jpg` and `traditional exterior.jpg` are mislabeled (the former is actually a modern *exterior* house view; the latter is a modern *interior* dining room). Worth renaming when convenient.

---

## 2026-05-19 — Wiki bootstrap

**Scope:** Stand up a Karpathy-style single-source-of-truth wiki at `wiki/`, append session-log + orientation protocol to `CLAUDE.md`, backfill key past decisions.

**Decisions:**
- [[DECISIONS#wiki-ssot]] — `wiki/` at repo root with cross-links rather than `docs/wiki/` consolidation or Obsidian-vault commit.
- [[DECISIONS#coord-space-consumer]] — formalized: coordinate rescaling owned by consumer code, not the VLM prompt. Documented in [[references/coordinate-systems]].
- Session-log protocol now codified in `CLAUDE.md` so every future agent maintains the wiki the same way.

**Tried:**
- Explored existing documentation (`docs/plans/master-plan.md`, `spike/TASKS.md`, `spike/REPORTS/T*.md`, `PROVIDERS.md`) and code structure (`spike/renderers/`, drivers, Modal app) via parallel Explore subagents.
- Considered consolidating into `docs/wiki/` — rejected because it breaks existing links in `CLAUDE.md` and `REPORTS/`.
- Considered committing `.obsidian/` config — rejected to keep git clean; wiki is still openable as a vault.
- Considered full backfill of one SESSIONS entry per T-report — rejected as duplicative of `REPORTS/` content. Backfilled decisions only.

**Outcome:**
- Created `wiki/` with: `README.md`, `STATE.md`, `GLOSSARY.md`, `STRATEGY.md`, `ROADMAP.md`, `DECISIONS.md` (8 entries backfilled), `SESSIONS.md` (this entry), per-spike pages under `spikes/`, `references/coordinate-systems.md`.
- Appended "Orient first" section + "Session-log protocol" section to `CLAUDE.md`. Hard rules untouched.
- No code touched. No tests touched. `spike/TASKS.md`, `spike/REPORTS/`, `docs/plans/` untouched.

**Follow-ups:**
- Verify Obsidian opens `wiki/` cleanly and the graph view renders cross-links (user-action; not blocking).
- First test of the session-log protocol is the *next* session — confirm an agent following `CLAUDE.md` instructions actually appends a SESSIONS entry without being prompted.
- T21 (Spike 3 gate eval) is still the highest-value next milestone — see [[ROADMAP#M1]]. Needs user cost-cap authorization.
