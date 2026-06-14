# Entourage asset attributions

All 3D assets below are **CC0 1.0 (public domain)** — no attribution legally
required, free for commercial use. Credited here as good practice.

## Trees — `trees/`

Source pack: **Stylized Nature MegaKit** by **Quaternius**, via
[poly.pizza](https://poly.pizza/bundle/Stylized-Nature-MegaKit-T34GZFA0fm).
License: CC0 1.0. Author: Quaternius (https://quaternius.com).

| File | Model | poly.pizza page | CDN url |
| --- | --- | --- | --- |
| `Tree.glb` | Tree | https://poly.pizza/m/QVOop92WmG | https://static.poly.pizza/… |
| `Tree_YWjGDJ.glb` | Tree | https://poly.pizza/m/YWjGDJ9F7g | https://static.poly.pizza/… |
| `Tree_aVOxaH.glb` | Tree | https://poly.pizza/m/aVOxaHRPWe | https://static.poly.pizza/… |
| `Tree_qZtx0A.glb` | Tree | https://poly.pizza/m/qZtx0AHhcy | https://static.poly.pizza/… |
| `Tree_t9Kbsf.glb` | Tree | https://poly.pizza/m/t9KbsfYdXz | https://static.poly.pizza/… |
| `Dead_Tree.glb` | Dead Tree | https://poly.pizza/m/n8FhMgMldD | https://static.poly.pizza/… |
| `Dead_Tree_MlmK54.glb` | Dead Tree | https://poly.pizza/m/MlmK5488ou | https://static.poly.pizza/… |
| `Dead_Tree_oM95bD.glb` | Dead Tree | https://poly.pizza/m/oM95bD8buf | https://static.poly.pizza/… |

## Bushes / ground cover — `bushes/`

Same pack / author / license (Quaternius, Stylized Nature MegaKit, CC0 1.0).

| File | Model | poly.pizza page |
| --- | --- | --- |
| `Bush.glb` | Bush | https://poly.pizza/m/EoTERLq3z2 |
| `Bush_with_Flowers.glb` | Bush with Flowers | https://poly.pizza/m/U1ymDy8tbY |
| `Clover.glb` | Clover | https://poly.pizza/m/IQ9NVyVpUw |
| `Clover_u5SOgB.glb` | Clover | https://poly.pizza/m/u5SOgBFiut |

## People — `people/` (procedural)

No third-party people assets are committed. Cutout people are generated
procedurally at runtime (`src/Entourage.tsx` → `personTexture()`): a
properly-proportioned standing/walking figure on a 256×512 canvas with 4 color
palettes and 2 pose variants, picked deterministically per placed item.

This was a deliberate licensing choice — we did **not** commit any
license-unclear people PNGs. If genuinely-CC0 cutout people are wanted later
(e.g. OpenGameArt CC0 sets or tonytextures "Architecture People" free-commercial
packs), drop the PNGs into `people/` and add `kind:"person"` entries with `url`
to `src/lib/entourageAssets.ts`; `personTexture()` already supports loading real
textures by extending the variant list.

## How these were fetched

`scripts/fetch_entourage.py` scrapes the bundle page for `/m/{slug}` model
links, GETs each model page, regexes the real `https://static.poly.pizza/{uuid}.glb`
CDN url, downloads it, and validates the `glTF` magic bytes.
`scripts/measure_glb.py` measures each GLB's world-space bbox (used to set the
real-world feet normalization in `entourageAssets.ts`).
