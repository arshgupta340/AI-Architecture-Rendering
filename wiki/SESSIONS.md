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
