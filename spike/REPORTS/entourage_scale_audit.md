# Entourage scale audit — "trees read slightly small"

Wiki NEXT #5. Audit of entourage asset scaling in `apps/web3d-prototype/`.

## What was checked

- `src/lib/entourageAssets.ts` — the 12 GLB defs (8 trees, 4 bushes) + procedural person, with per-species `baseHeightFt`, `glbHeightUnits`, `glbBaseY`.
- `src/Entourage.tsx` — instancing + scale math (`SpeciesInstances`, `GlbKind`, `ProceduralKind`, `PersonBillboard`).
- `src/state/store.ts` — `DEFAULT_ENT_HEIGHT`, `EntItem.scale`, placement.
- `src/Scene.tsx` — placement (`addEnt`, per-item `scale`), house.glb load (no scale applied), world-unit convention.
- World-unit ↔ feet convention: `Scene.tsx` box-projected UVs "in feet", `GeoTiles.tsx` (`M_TO_FT = 1/0.3048`, map tiles are metres → scaled to feet), `Walk.tsx` ("speed in world units (feet)/sec"), `swatches.ts` (`tileFeet`). Scene world unit = 1 foot.
- `scripts/measure_glb.py` — the tool that produced `glbHeightUnits`/`glbBaseY`; walks node world matrices and transforms POSITION accessor min/max corners (so node scale IS accounted for).
- Rhino export (`spike/rhino_export_gltf.py`): `MapZToY=True` (Z-up→Y-up), records `doc.ModelUnitSystem`; house.glb is loaded via `useGLTF` with no scale prop, so 1 GLB unit = 1 world unit = 1 foot (Rhino model in feet).

## The scale chain (trees)

```
treeFt        = entHeight.tree            (store default 18; slider range [3,30])
unitScale     = treeFt / glbHeightUnits   (Entourage.tsx:127)
s             = unitScale * item.scale    (item.scale = 0.8 + rand*0.5 → 0.8–1.3)
world height  = s * glbHeightUnits = treeFt * item.scale   (feet, since world unit = 1 ft)
```

Per-species native height IS measured and divided out via `glbHeightUnits` — there is **no** assumption of a normalized 1-unit asset, and **no** metres↔feet factor anywhere in the tree/bush path (the 3.28084 factor lives only in `GeoTiles.tsx` for map tiles, correctly isolated).

### Independent verification of the hardcoded numbers (parsed GLB JSON chunks directly, stdlib-free)

Bush.glb — POSITION accessor min/max, both nodes `scale:[1,1,1]` (identity):
- Y extent = 1.34709 − (−0.234695) = **1.5818** vs hardcoded `glbHeightUnits: 1.582` ✓
- ymin = **−0.2347** vs hardcoded `glbBaseY: -0.235` ✓

Tree.glb (tree-oak) — first POSITION accessor (trunk) ymin = **−0.24277** vs hardcoded `glbBaseY: -0.243` ✓; trunk maxY = 7.978, foliage accessor extends to ≈9.18, giving total Y extent ≈ 9.18 − (−0.243) = **9.42** vs hardcoded `glbHeightUnits: 9.425` ✓. FBX2glTF identity-scale nodes.

Both spot-checks match to 3 decimals. Because `measure_glb.py` and three.js `extractSubMeshes` both compose node world matrices identically, the normalization is self-consistent regardless of any node scale — measure and runtime cannot disagree.

Representative rendered heights at the current defaults (world unit = 1 ft):
- Tree, default `treeFt=18`, item.scale 0.8–1.3 → **14.4–23.4 ft** (mean ≈ 19 ft).
- Bush, default `bushFt=3`, `glbHeightUnits 1.582` → 3 ft × 0.8–1.3 → **2.4–3.9 ft**.
- Person billboard, `personFt=5.7`, `BASE_HEIGHT.person=6` → plane height 5.7 × item.scale ≈ **4.6–7.4 ft**.

## Verdict: NO provable unit bug

The unit/normalization chain is correct and self-consistent: per-species native bbox height is measured and normalized, world units are feet, no lost or doubled 3.28 factor. The verified numbers rule out a per-asset normalization error and a metres↔feet factor.

"Trees read slightly small" is a **default-value + slider-range + design-flattening perception issue**, not a math bug:

1. **Default `treeFt = 18 ft`** (`store.ts:84 DEFAULT_ENT_HEIGHT.tree`). A tree beside a 1–2 storey house reads at ~25–40 ft; 18 ft (mean ≈19 ft after item.scale) is genuinely on the small side. This is the single biggest contributor.
2. **Slider capped at 30 ft** (`Entourage.tsx:26 ENT_RANGE.tree = [3,30]`). Users cannot dial a mature-tree height (40–60 ft) even manually.
3. **Per-species `baseHeightFt` is dead at render time.** `SpeciesInstances` scales every species to the single global `treeFt`; `def.baseHeightFt` (20–26) is never read in the render path. So the intended variety (tall oak vs short sapling) collapses — every placed tree is exactly `treeFt` tall, and none of the "26 ft" species ever renders taller than the flat 18 ft default. The header comment in `entourageAssets.ts` describes a ratio design that the code does not implement (it applies `entFt` directly, not `entFt/baseHeightFt`).

None of these is a unit bug, so per the task's "fix ONLY if a unit bug is proven with numbers" rule, **no code change was made.** If the team wants trees to read larger, the minimal, defensible levers are: raise `DEFAULT_ENT_HEIGHT.tree` (e.g. 18 → 24, matching `BASE_HEIGHT.tree`), and/or raise `ENT_RANGE.tree` max (30 → ~50). Restoring per-species height variety would require multiplying by `def.baseHeightFt/BASE_HEIGHT.tree` in `SpeciesInstances` — a design change, not a bug fix.

## Fix

None. No unit bug exists to fix; the numbers prove the normalization is correct.
