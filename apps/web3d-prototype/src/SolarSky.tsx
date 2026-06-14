import { useEffect, useMemo } from "react";
import { useLoader, useThree } from "@react-three/fiber";
import { Sky, Environment } from "@react-three/drei";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import * as THREE from "three";
import SunCalc from "suncalc";
import { useStore, type SkyState } from "./state/store";

/**
 * Equirect HDRI sky presets. `id` is the filename slug under `public/hdri/<id>.hdr`
 * (2k Radiance, CC0 from Poly Haven). `sky` is the existing analytic-sky fallback
 * HDRI kept as the Default; the rest are mood/golden-hour skies downloaded this
 * session. The store's `hdriPreset` (default "sky") selects which one drives the
 * WebGPU IBL + path-traced hero environment. */
export const HDRI_PRESETS: { id: string; label: string }[] = [
  { id: "sky", label: "Default" },
  { id: "spruit_sunrise", label: "Sunrise" },
  { id: "qwantani_puresky", label: "Clear noon" },
  { id: "kloofendal_48d_partly_cloudy_puresky", label: "Overcast" },
  { id: "the_sky_is_on_fire", label: "Dusk" },
];

const HDRI_PRESET_IDS = new Set(HDRI_PRESETS.map((p) => p.id));
/** Resolve a stored preset slug to a safe `public/hdri/<slug>.hdr` URL. */
export function hdriUrlFor(slug: string): string {
  return `/hdri/${HDRI_PRESET_IDS.has(slug) ? slug : "sky"}.hdr`;
}

function dateFor(sky: SkyState): Date {
  const d = new Date(`${sky.date}T00:00:00`);
  d.setHours(Math.floor(sky.timeOfDay), Math.round((sky.timeOfDay % 1) * 60), 0, 0);
  return d;
}

/**
 * Physically-grounded daylight — ONE key light (the sun) + a slight sky-diffuse
 * ambient, both derived from the real sun altitude + cloud cover. The SAME model
 * feeds all three render modes (this component is shared); only the rendering
 * technique (N8AO / SSGI / reflections) differs, never the light sources.
 *
 * SUN — a directional light whose intensity is the direct-NORMAL illuminance, dimmed
 * and reddened at low altitude by atmospheric extinction (Kasten-Young air mass +
 * Beer–Lambert), and cut by cloud. It is NOT pre-scaled by sin(altitude): N·L on each
 * surface does the geometric projection, so a low sun still rakes brightly across a
 * façade facing it (the sunset look), while the shadow map — NOT ambient occlusion —
 * handles occlusion (per iquilezles.org/articles/outdoorslighting). Cloud thickens the
 * optical depth so an overcast sky extinguishes the beam and shadows fade (CIE overcast).
 *
 * AMBIENT — the env map (IBL) is the real sky-bounce ambient in every mode (LearnOpenGL
 * IBL: the environment replaces the flat ambient constant); these `ambientLight` +
 * `hemisphereLight` are only a SMALL, daylight-scaled floor on top so AO-dark areas
 * aren't pure black and the base reads identically across modes. Colours track measured
 * daylight CCT: warm low sun → neutral high; blue clear sky → grey overcast.
 */
function computeSky(sky: SkyState) {
  const pos = SunCalc.getPosition(dateFor(sky), sky.lat, sky.lng);
  const vec = new THREE.Vector3().setFromSphericalCoords(1, Math.PI / 2 - pos.altitude, pos.azimuth);
  const sinH = Math.sin(pos.altitude); // < 0 below the horizon
  const sunUp = Math.max(0, sinH); // 0 below horizon, 1 at zenith
  const hDeg = (pos.altitude * 180) / Math.PI;
  const cc = THREE.MathUtils.clamp(sky.cloudCover, 0, 1);
  const mult = sky.sunIntensity;

  // Smooth horizon / day-amount / warmth factors reused across the model.
  const horizonFade = THREE.MathUtils.smoothstep(sinH, -0.04, 0.06); // sun crossing the horizon
  const dayAmount = THREE.MathUtils.smoothstep(sinH, -0.1, 0.22); // 0 night → 1 day
  const warmth = THREE.MathUtils.clamp(1 - sunUp * 2.2, 0, 1); // 1 low sun → 0 high

  // ---- DIRECT SUN: atmospheric extinction over air mass (Kasten-Young) ----
  const airMass = sinH > 0.001 ? 1 / (sinH + 0.50572 * Math.pow(hDeg + 6.07995, -1.6364)) : 38;
  // Optical depth ~0.12 on a clear day; cloud thickens it so overcast kills the beam.
  const opticalDepth = 0.12 + 1.4 * cc;
  const transmittance = Math.exp(-opticalDepth * airMass); // 0 … ~0.9
  // Direct-normal illuminance (HDR, pre-AgX); N·L does the surface geometry.
  const dirIntensity = mult * 3.2 * transmittance * horizonFade * (1 - 0.9 * cc);
  // Sun colour: ~2200K orange at the horizon → ~6000K neutral-warm high (measured CCT).
  const sunColor = new THREE.Color("#fff3e4").lerp(new THREE.Color("#ff7a2a"), warmth);

  // ---- SKY DIFFUSE: the slight, consistent ambient floor (IBL is the real ambient) ----
  const overcastLift = 1 + 0.6 * cc; // an overcast dome scatters a little more diffuse
  const ambientI = (0.045 + 0.1 * dayAmount) * overcastLift; // tiny flat floor
  const hemiI = (0.08 + 0.2 * dayAmount) * overcastLift; // sky/ground gradient
  // Colours: blue clear → warm near the horizon → grey under cloud.
  const skyCol = new THREE.Color("#aecbff")
    .lerp(new THREE.Color("#ffc89a"), warmth * 0.7)
    .lerp(new THREE.Color("#c4c8cc"), cc * 0.8);
  const groundCol = new THREE.Color("#564b3c");
  const ambCol = new THREE.Color("#dfe6f5")
    .lerp(new THREE.Color("#ffe2c4"), warmth * 0.5)
    .lerp(new THREE.Color("#cdd0d3"), cc * 0.7);

  // ---- visible sky dome (drei <Sky>) params ----
  const turbidity = 2 + 9 * cc;
  const rayleigh = 1 + 2 * cc + 1.6 * warmth;
  // ---- IBL env-map strength: tracks daylight, dimmed by heavy cloud. Applied the
  // SAME way in every mode (scene.environmentIntensity / <Environment intensity>). ----
  const envIntensity = mult * (0.15 + 0.85 * dayAmount) * (1 - 0.45 * cc);

  return {
    sunPos: [vec.x, vec.y, vec.z] as [number, number, number],
    lightPos: vec,
    dirIntensity,
    sunColor,
    ambientI,
    ambCol,
    hemiI,
    skyCol,
    groundCol,
    turbidity,
    rayleigh,
    envIntensity,
  };
}

/**
 * WebGPU-safe image-based lighting. drei's <Sky>/<Environment> (and PMREMGenerator
 * on WebGL) pre-filter the env with GLSL ShaderMaterials, which the WebGPU node
 * renderer can't compile. Assigning an equirect HDRI straight to scene.environment
 * lets the WebGPU renderer PMREM-filter it internally (node-based) — so glass + metal
 * get real reflections in WebGPU mode with no ShaderMaterial. environmentIntensity
 * tracks daylight so the static HDRI doesn't keep the scene bright at night.
 */
function WebGPUEnv({ intensity }: { intensity: number }) {
  const hdriPreset = useStore((s) => s.hdriPreset);
  const hdr = useLoader(HDRLoader, hdriUrlFor(hdriPreset));
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    hdr.mapping = THREE.EquirectangularReflectionMapping;
    const prev = scene.environment;
    scene.environment = hdr;
    return () => {
      scene.environment = prev;
    };
  }, [hdr, scene]);
  useEffect(() => {
    scene.environmentIntensity = intensity;
  }, [scene, intensity]);
  return null;
}

/**
 * WebGL2 reflections from a real HDRI file (only used when a non-default preset is
 * selected). drei <Environment files=...> PMREM-filters the equirect HDR on the
 * WebGL renderer and assigns it to scene.environment, so glass/metal reflect the
 * chosen mood sky while the analytic <Sky> dome stays the *visible* backdrop
 * (background={false}). On the default "sky" preset we keep the all-analytic path. */
function WebGL2HdriEnv({ slug, intensity }: { slug: string; intensity: number }) {
  return (
    <Environment files={hdriUrlFor(slug)} background={false} resolution={256} environmentIntensity={intensity} />
  );
}

export function SolarSky({ radius }: { radius: number }) {
  const sky = useStore((s) => s.sky);
  const renderMode = useStore((s) => s.renderMode);
  const hdriPreset = useStore((s) => s.hdriPreset);
  const c = useMemo(() => computeSky(sky), [sky]);
  const lp = c.lightPos.clone().multiplyScalar(radius * 3);
  // Re-bake the IBL env only when the sun/clouds/date meaningfully change (coarse
  // key) so glass + metal reflections track time-of-day, without re-baking every
  // frame. drei <Environment frames={1}> otherwise bakes once and never updates.
  const envKey = `${Math.round(sky.timeOfDay * 2)}|${Math.round(sky.cloudCover * 10)}|${sky.date}`;

  return (
    <>
      {renderMode === "webgpu" ? (
        // Node-safe sky for WebGPU: a dynamic color background (tracks time-of-day)
        // + an equirect HDRI on scene.environment for real glass/metal reflections
        // (WebGPUEnv — PMREM-filtered internally by the WebGPU renderer, no shader).
        <>
          <color attach="background" args={[`#${c.skyCol.getHexString()}`]} />
          <WebGPUEnv intensity={c.envIntensity} />
        </>
      ) : (
        <>
          {/* crisp visible sky dome */}
          <Sky
            sunPosition={c.sunPos}
            turbidity={c.turbidity}
            rayleigh={c.rayleigh}
            mieCoefficient={0.005}
            mieDirectionalG={0.8}
            distance={45000}
          />
          {/* Reflections env. Default preset ("sky"): bake the analytic <Sky> to an
              env map so reflective/metal/glass surfaces track the sun (re-baked on
              `envKey`). A non-default mood HDRI preset instead drives reflections
              from that real HDR file, while the visible dome above stays analytic. */}
          {hdriPreset === "sky" ? (
            <Environment key={envKey} frames={1} resolution={256} environmentIntensity={c.envIntensity}>
              <Sky
                sunPosition={c.sunPos}
                turbidity={c.turbidity}
                rayleigh={c.rayleigh}
                mieCoefficient={0.005}
                mieDirectionalG={0.8}
                distance={45000}
              />
            </Environment>
          ) : (
            <WebGL2HdriEnv slug={hdriPreset} intensity={c.envIntensity} />
          )}
        </>
      )}

      {/* The env map (IBL) is the real sky ambient in every mode; these flat fills are
          only a slight, daylight-scaled floor — kept identical across modes (no per-mode
          dialing) so the base lighting is consistent everywhere. */}
      <ambientLight intensity={c.ambientI} color={c.ambCol} />
      <hemisphereLight intensity={c.hemiI} color={c.skyCol} groundColor={c.groundCol} />
      <directionalLight
        position={[lp.x, lp.y, lp.z]}
        intensity={c.dirIntensity}
        color={c.sunColor}
        castShadow
        shadow-mapSize={[4096, 4096]}
        shadow-radius={7}
        shadow-blurSamples={20}
        shadow-bias={-0.0002}
        shadow-normalBias={0.04}
        shadow-camera-near={1}
        shadow-camera-far={radius * 8}
        shadow-camera-left={-radius * 1.6}
        shadow-camera-right={radius * 1.6}
        shadow-camera-top={radius * 1.6}
        shadow-camera-bottom={-radius * 1.6}
      />
    </>
  );
}
