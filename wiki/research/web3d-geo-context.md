---
type: research
topic: real-world geo context from coordinates for the web3d tool
agent: "Sonnet research agent (V3 phase, 2026-06-13)"
---

# Real-world site context from coordinates (three.js / R3F)

> Sonnet web-research agent. Verbatim-faithful synthesis. (Not yet built — next-up roadmap pillar.)

## Recommended: Google Photorealistic 3D Tiles via `3d-tiles-renderer`
- [NASA-AMMOS/3DTilesRendererJS](https://github.com/NASA-AMMOS/3DTilesRendererJS) (`npm: 3d-tiles-renderer`, v0.4.28+, Apache-2.0) loads Google's planet-wide photogrammetry meshes **into our existing three.js scene**. First-class R3F integration (`3d-tiles-renderer/r3f`): `<TilesRenderer>`, `<TilesPlugin plugin={GoogleCloudAuthPlugin} args={{apiToken}}/>`, `<GlobeControls/>`, **`<TilesAttributionOverlay/>` (mandatory per Google ToS)**.
- **Georeference our model:** the tiles are ECEF. Use `WGS84_ELLIPSOID.EastNorthUpFrame(lat, lon, matrix4)` (built into the lib) → apply Rhino **true-north** rotation → scale model units→meters → `object.matrix = ENU`, `matrixAutoUpdate=false` → raycast-snap to terrain. For IFC/Rhino exports, `IfcSite.RefLatitude/RefLongitude/RefElevation` + `WorldCoordinateSystem.TrueNorth` is the source of truth. `proj4` for local-grid CRS.
- **Cost/licensing:** ~**$6 / 1,000 sessions** + $0.20/1k tile requests (Google PAYG); **interactive-only — you may NOT bake Google pixels into a downloaded render**, no AI/ML on tiles, no tracing geometry from tiles (your own model on top is explicitly allowed). EEA billing restrictions since 2025-07-08. Session token 3 h (auto-refresh).

## Alternatives
- **Cesium / Resium:** wrong architecture for an R3F-first app (own context/loop). Cesium ion bundles Google P3DT ($149–499/mo). Skip unless you want a Cesium globe.
- **Mapbox GL JS:** satellite imagery + **Terrain-RGB DEM** (`elev = -10000 + (R*65536+G*256+B)*0.1`) + OSM 3D buildings + custom-layer three.js. $5/1k loads (50k free). **threebox is abandoned** (v2 only) — use Mapbox custom layer directly, or **MapLibre GL JS** (BSD-2, free) + AWS Terrain Tiles + OSM.
- **Raw self-assembled:** satellite drape on PlaneGeometry + AWS/USGS DEM + OSM footprints (Overpass→earcut). `three-geo`/`geo-three` exist but are stale (2022–23) — call tile APIs directly (~30 lines).

## Recommendation for us
Primary: **Google P3DT via 3d-tiles-renderer** (needs a Google Maps API key; factor session cost into pricing). Free fallback: **MapLibre + AWS DEM + OSM footprints + satellite** (lower fidelity, no lock-in, fine for dev). Do NOT use Cesium/threebox/three-geo/geo-three.

Key links: [3DTilesRendererJS R3F README](https://github.com/NASA-AMMOS/3DTilesRendererJS/blob/master/src/r3f/README.md) · [Google P3DT overview](https://developers.google.com/maps/documentation/tile/3d-tiles-overview) · [billing](https://developers.google.com/maps/documentation/tile/usage-and-billing) · [policies](https://developers.google.com/maps/documentation/tile/policies) · [Mapbox Terrain-DEM](https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-dem-v1/) · [MapLibre](https://github.com/maplibre/maplibre-gl-js).

> **Since-built:** the "not yet built" note above is stale — `GeoTiles.tsx` ships the Google P3DT path ([[STATE]]); it needs the user's Google Maps key to validate live.

**See also:** [[DECISIONS#web3d-geo-context]] · [[web3d-rhino-gltf]] (georeference reuses the Rhino units + true-north) · [[STATE]].
