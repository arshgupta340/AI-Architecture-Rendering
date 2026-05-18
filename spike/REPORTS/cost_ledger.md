# Cost ledger

Append-only log of every paid API call the overnight agent makes.

**Hard cap:** $0.05 total. If running total reaches this, the agent stops.

## Format

`YYYY-MM-DD HH:MM | task | provider | model | est_cost_usd | notes`

## Entries

```
2026-05-17 SETUP | T00 | --- | --- | 0.00 | Initial ledger created
```

**Running total: $0.00**
