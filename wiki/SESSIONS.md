---
type: log
updated: 2026-05-19
---

# Session Log

Append-only conversation log. **Newest at top.** One entry per chat session.

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
