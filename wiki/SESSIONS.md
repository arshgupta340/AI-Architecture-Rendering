---
type: log
updated: 2026-05-19
---

# Session Log

Append-only conversation log. **Newest at top.** One entry per chat session.

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
