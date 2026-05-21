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
2026-05-20 B3-PREP | B3 setup | Google | gemini-2.5-flash-image (NB Pro) | 0.04 | UNINTENDED: compare_renderers.py manifest sanity-check fired a live Nano Banana call once .env BOM was stripped and GOOGLE_API_KEY became visible — script has no --dry-run flag. Output saved at spike/outputs/spike2_5/b3/nano_banana_pro.png; usable as the NB panel for the eventual B3 grid.
2026-05-20 T22 | T22 | Google | nano-banana-pro-preview | 0.04 | render modern interior screenshot (1376x782)
2026-05-20 T22 | T22 | Google | nano-banana-pro-preview | 0.04 | render traditional exterior screenshot (1376x782)
2026-05-20 T22 | T22 | Google | nano-banana-pro-preview | 0.04 | render urban exterior screenshot (1427x736)
2026-05-20 T22 | T22 | Google | nano-banana-pro-preview | 0.04 | render complex windows screenshot (1024x1030)
2026-05-20 T22 | T22 | Google | gemini-3-pro-preview | 0.01 | tag modern_interior (27 regions)
2026-05-20 T22 | T22 | Google | gemini-3-pro-preview | 0.01 | tag traditional_exterior (25 regions, 5 mullions + 11 furniture)
2026-05-20 T22 | T22 | Google | gemini-3-pro-preview | 0.01 | tag urban_exterior (47 regions, malformed JSON with duplicate "y" keys — schema validation failed)
2026-05-20 T22 | T22 | Google | gemini-3-pro-preview | 0.01 | tag complex_windows (118 regions, 103 individual windows)
2026-05-20 T22 | T22 | Google | gemini-3-pro-preview | 0.01 | retry tag urban_exterior (47 regions, SAME malformed JSON — confirmed reproducible)
```

**Running total: $0.31**

Notes:
- T21 user-authorized overage: $0.05 → $0.06.
- B3-PREP $0.04 unintended (no --dry-run on compare_renderers.py manifest mode).
- T22 user-authorized: ~$0.20 (4 × $0.04 render + 4 × $0.01 tag).
- T22 urban_exterior retry: +$0.01 user-authorized to test reproducibility (which it is).
- urban_exterior was salvaged from the raw response via `spike/salvage_urban_tags.py` (no additional API cost) — 44 of 47 regions parsed with the custom JSON hook.
