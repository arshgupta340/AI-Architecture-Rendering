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
2026-05-22 T24 | T24 | Modal | SAM2 (A10G) | 0.05 | segment wall bbox on spike2 photoreal (mask 8.2% coverage, ~30s cold)
2026-05-22 T24 | T24 | Modal | SD Inpaint 1.5 (A10G) | 0.40 | apply_material "travertine" at 512x512 (~60s incl. cold start + 1.7GB weight download)
2026-05-22 B3-RUN-1 | B3 first live | Google | gemini-2.5-flash-image (NB Pro) | 0.04 | building.png re-render via compare_renderers.py seed=42, ok in 24s
2026-05-22 B3-RUN-1 | B3 first live | Recraft | recraftv3 | 0.04 | building.png via /v1/images/imageToImage, ok in 70s
2026-05-22 B3-RUN-1 | B3 first live | BFL | flux-2-pro + flux-pro-1.0-fill | 0.00 | both 402 Payment Required (BFL key valid, account has no balance — top up at dashboard.bfl.ai)
2026-05-22 B3-RUN-1 | B3 first live | Replicate | flux-canny-pro + flux-depth-pro + qwen-image-edit | 0.00 | all 402 Payment Required (Replicate token valid, account needs credit)
2026-05-22 B3-RUN-1 | B3 first live | Magnific | mystic | 0.00 | 401 Unauthorized at api.magnific.com (key value not accepted; likely Freepik-issued vs Magnific-native key)
2026-05-22 B3-RUN-1 | B3 first live | Replicate | hidream-e1-1 (wrong slug) | 0.00 | 404 Not Found — correct slug is prunaai/hidream-e1.1 with literal period; client fixed
2026-05-22 T25 | T25 | Replicate | black-forest-labs/flux-fill-pro | 0.05 | apply_material "travertine" via FLUX Fill (1259x848 native res tile, 1.5 MB)
2026-06-03 USER | masterplan-render | Google | nano-banana-pro-preview | 0.36 | user-authorized one-shot render of 8 masterplan views (mixed materiality, blue glass, bright midday); 8 renders + 1 re-render of perspective 3 (camera-lock fix) = 9 NB Pro calls @ ~$0.04
2026-06-12 E4 | E4 | Google | nano-banana-pro-preview | 0.13 | Vision-Banana-style color-coded segmentation probe on E1 beauty.png; semantically coherent, geometrically drifted (mullion IoU 0.003) � see REPORTS/E4.md
2026-06-12 E5 | E5 | Replicate | grounding-dino + sam-2 + grounded_sam | 0.50 | est. ~35 small predictions incl. detours/retries; discriminative tier-2 probe vs E1 ground truth � see REPORTS/E5.md
2026-06-12 E2 | E2 | fal.ai + Google | flux-pro/v1/depth x2, flux-2-pro/edit, nano-banana-pro | 0.40 | render conditioning shootout on house frame; flux_depth wins on mask registration � see REPORTS/E2.md
2026-06-12 E3 | E3 | fal.ai | flux-pro/v1/fill, flux-general/inpainting+ip-adapter, flux-2-pro/edit, kontext/max/multi | 0.30 | swatch-conditioning shootout; flux2_multiref + mask composite passes the travertine gate � see REPORTS/E3.md
2026-06-12 CANVAS | canvas-prototype | fal.ai | flux-2-pro/edit | 0.06 | live-path proof through apps/canvas-prototype server: red_brick swatch on all 10 wall instances, layer 7b61fe91bded9f89.png; travertine path served no-spend from E3 precompute
2026-06-12 E2b | E2b | fal.ai | flux-general union (canny+depth) x1, flux-2-pro/edit x2 | 0.20 | render-mask registration fix: depth+canny lock, 51.7%->98.5% edge align <=2px; brick+travertine demo on aligned base � see REPORTS/E2b.md
```

**Running total: $1.31**

Notes:
- T21 user-authorized overage: $0.05 → $0.06.
- B3-PREP $0.04 unintended (no --dry-run on compare_renderers.py manifest mode).
- T22 user-authorized: ~$0.20 (4 × $0.04 render + 4 × $0.01 tag).
- T22 urban_exterior retry: +$0.01 user-authorized to test reproducibility (which it is).
- urban_exterior was salvaged from the raw response via `spike/salvage_urban_tags.py` (no additional API cost) — 44 of 47 regions parsed with the custom JSON hook.
- T24 user-authorized: ~$0.45 for first live Spike 4 end-to-end run (segment + apply_material on Modal A10G; render + tag stages hit pre-populated cache for $0).
- B3-RUN-1 user-authorized: ~$0.43 marginal budget; actual marginal spend was $0.08 (2 of 9 renderers succeeded, 7 failed with 4xx errors that don't bill). See `spike/outputs/spike2_5/b3/scores.csv` for per-renderer status.
- T25 user-authorized $0.30–0.50 for FLUX-vs-SD comparison budget; actual marginal spend was $0.05 for one comparison run. 4–9 more runs in budget if we want to map further (region, material) combos via FLUX.
- 2026-06-03 user-authorized ~$1.20 for an 8-view masterplan render (separate from the spike bake-off); actual spend ~$0.36 across 9 NB Pro calls. Outputs in `spike/outputs/masterplan_renders/`.
