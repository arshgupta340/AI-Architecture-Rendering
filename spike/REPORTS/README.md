# Spike-builder reports

This directory holds one report per task that the overnight `spike-builder`
agent (see `.claude/agents/spike-builder.md`) completes. Filenames are
`T<id>.md` matching the task IDs in `../TASKS.md`.

## Report format

Every report follows this skeleton:

```markdown
# T<id> — <task title>

- **Task:** one-line description (copied from TASKS.md row)
- **Commit:** <short SHA> (set after commit lands)
- **Started:** ISO timestamp
- **Finished:** ISO timestamp
- **Status:** done | blocked | skipped

## What was done
<2–6 sentences>

## Files changed
- `path/to/file.py` — what changed
- ...

## Checks run
- `pytest spike/tests/test_x.py` → 4 passed, 0 failed (truncated output)
- `python -c "import spike.renderers.flux_bfl"` → ok

## Surprises / notes for the human
<anything the agent thinks the human should know>

## Follow-ups
<list of TODOs that came out of the task — usually for the human, not for
 future overnight tasks>
```

## Read order in the morning

1. `cost_ledger.md` — total spend ≤ $0.05?
2. `STOPPED.md` (if it exists) — did the agent halt the whole run?
3. `T01.md` through `T20.md` — skim in order.
4. Anything marked `Status: blocked` deserves a closer look.
