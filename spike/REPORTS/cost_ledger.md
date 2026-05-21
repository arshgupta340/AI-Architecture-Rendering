# Cost ledger

Append-only log of every paid API call the overnight agent makes.

**Hard cap:** $0.05 total. If running total reaches this, the agent stops.

## Format

`YYYY-MM-DD HH:MM | task | provider | model | est_cost_usd | notes`

## Entries

```
2026-05-17 SETUP | T00 | --- | --- | 0.00 | Initial ledger created
2026-05-19 T17 | T17 | Google | gemini-3-pro-preview | 0.01 | tag_regions smoke test, 49 regions returned
2026-05-20 T21 | T21 | Google | gemini-3-pro-preview | 0.01 | pair 1: spike2 source+render re-test (94 regions)
2026-05-20 T21 | T21 | Google | gemini-3-pro-preview | 0.01 | pair 2: modern interior screenshot (31 regions)
2026-05-20 T21 | T21 | Google | gemini-3-pro-preview | 0.01 | pair 3: traditional/interior dining screenshot (16 regions, first mullion hit)
2026-05-20 T21 | T21 | Google | gemini-3-pro-preview | 0.01 | pair 4: urban exterior screenshot (25 regions, windows missed)
2026-05-20 T21 | T21 | Google | gemini-3-pro-preview | 0.01 | pair 5: complex windows screenshot (97 regions)
```

**Running total: $0.06**

Note: user explicitly authorized $0.05 over the $0.05/session cap for T21, taking total to $0.06.
