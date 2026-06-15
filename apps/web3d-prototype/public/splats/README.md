# Gaussian-splat environment assets

Drop a `.spz` or `.ply` Gaussian splat here, then point the app's **Splat env** panel
(WebGL2 / + GI modes only) at it, e.g. `/splats/context.ply`. Rendered in-browser via
`@sparkjsdev/spark`, composited around the editable polygon building.

Two ways to get one:

1. **Drop-in context** (surroundings we have no geometry for):
   - **World Labs Marble** ($20/mo Standard unlocks export) — text/photo → 360° world,
     export **Splats (.spz)**, drop the file here. Marble is OpenCV (Y-down): the loader
     auto-flips `.spz`. Use the panel sliders (height / scale / heading / yaw) to seat it.
   - Any CC0 photogrammetry/`.ply` (Polycam, Luma, Postshot, nerfstudio).

2. **Bake our own scene** ("convert geometry → splat") — the panel's **Bake our scene**
   tab orbits ~42 posed views and trains a 3DGS on Modal (`spike/modal_splat.py`,
   `splatfacto`, ~15–25 min, ~$0.30–0.50). Photoreal, navigable, but **bakes** materials
   (a one-way "publish" — keep the polygon scene as the live editor).

`*.spz` / `*.ply` here are gitignored (large, per-project). This README is committed.
