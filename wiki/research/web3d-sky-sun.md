---
type: research
topic: sky / sun / time-of-day for the web3d tool
agent: "Sonnet research agent (V3 phase, 2026-06-13)"
---

# Sky, Sun & Time-of-Day for three.js / R3F arch-viz

> Sonnet web-research agent. Verbatim-faithful synthesis.

## Sky models
- **Tier 1 — three.js built-in `Sky`** (Preetham 1999). `import { Sky } from 'three/addons/objects/Sky.js'`; drei wraps it as `<Sky>` with `turbidity / rayleigh / mieCoefficient / mieDirectionalG / sunPosition`. Zero deps, runs anywhere. Weak: overshoots blue below ~15° sun altitude; no clouds (until r183 FBM clouds: `cloudCoverage/cloudDensity/cloudElevation` uniforms). **This is what we use.**
- **Tier 2 — `@takram/three-atmosphere`** (Bruneton precomputed scattering, v0.19.1): physically correct at all sun angles incl. twilight, aerial perspective, volumetric clouds companion. Bigger bundle; used in the official three.js 3D-tiles example.
- **Tier 3 — `tsl-sky`** (Hillaire EGSR 2020, WebGPU-only, three ≥0.184): first-class lat/long/timeOfDay inputs + NOAA solar + auto PMREM env. Newest/riskiest.

## Sun position from lat/long + date/time
**`suncalc` v1.9.0** (BSD-2, 0 deps) — `SunCalc.getPosition(date, lat, lng)` → `{altitude, azimuth}` (radians). Drive both the directional light AND the sky sun:
```js
const { altitude, azimuth } = SunCalc.getPosition(date, lat, lng);
const sunVec = new THREE.Vector3().setFromSphericalCoords(1, Math.PI/2 - altitude, azimuth);
dirLight.position.copy(sunVec.multiplyScalar(R));
sky.material.uniforms.sunPosition.value.copy(sunVec); // or drei <Sky sunPosition={sunVec}/>
```
`astronomy-engine` if you need moon/orbital accuracy. Real solar = enables **shadow studies**.

## IBL from the sky (keep materials consistent)
Render the Sky to a CubeCamera → `PMREMGenerator.fromCubemap()` → `scene.environment`. **Don't re-bake every frame** — update every ~1–2 s or only when the time slider moves; cross-fade. (`tsl-sky` auto-manages this on WebGPU.)

## Clouds / fog / mood
Procedural sky for shadow-study (must animate) vs fixed HDRI for hero shots. r183 FBM clouds suffice for arch-viz; `@takram/three-clouds` for volumetric (WebGPU). drei `<fog>`/`<fogExp2>` for distance haze; full aerial perspective needs tsl-sky/takram (overkill at building scale).

## Shadow studies (what architects expect)
Sun scrubber (0–24h), tight ortho shadow frustum + `PCFSoftShadowMap` @2048/4096, **sun-path arc** (CatmullRom through hourly suncalc positions + compass rose), **solstice/equinox presets** (Jun 21 / Dec 21 / Mar 20 / Sep 22), shadow-accumulation heat map. Reference OSS: [SeanWong17/building-sunlight-simulator](https://github.com/SeanWong17/building-sunlight-simulator).

## What we built (MVP)
`src/SolarSky.tsx` + `src/ui/SkyPanel.tsx` (left panel): drei `<Sky>` driven by `suncalc` from store `sky{lat,lng,date,timeOfDay,sunIntensity,cloudCover,mood}`; sun directional + hemisphere + ambient derived from altitude/cloud/intensity; sky baked to a 128² env map for reflections; **mood presets** (sunny/overcast/golden/dusk/night) + time slider + equinox/solstice date presets + lat/long. Cloud cover is simulated via sun-dimming + ambient-lift + turbidity (no volumetric clouds yet).

## Key libs
`suncalc` ^1.9.0, `three` ≥0.177 (r183+ for clouds), drei `<Sky>/<Environment>/<AccumulativeShadows>`.

> **Since-built:** the env map now bakes at **256²** (not 128²); the WebGPU render mode swaps drei `<Sky>`/`<Environment>` (which don't compile on the WebGPU node renderer) for a node-safe HDRI on `scene.environment` — [[web3d-webgpu]]. Note: drei `<SoftShadows>`/`<AccumulativeShadows>` broke on three r184 → VSM shadows instead ([[STATE]]).

**See also:** [[web3d-webgpu]] (node-safe HDRI IBL + real VSM cast shadows) · [[web3d-realism]] · [[STATE]].
