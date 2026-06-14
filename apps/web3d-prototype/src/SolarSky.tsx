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

/** Derive sun direction + lighting from lat/long + date/time + cloud/intensity. */
function computeSky(sky: SkyState) {
  const pos = SunCalc.getPosition(dateFor(sky), sky.lat, sky.lng);
  const vec = new THREE.Vector3().setFromSphericalCoords(1, Math.PI / 2 - pos.altitude, pos.azimuth);
  const sunUp = Math.max(0, Math.sin(pos.altitude)); // 0 below horizon, 1 at zenith
  const cc = sky.cloudCover;
  const warmth = 1 - Math.min(1, sunUp * 2.2); // 1 near horizon, 0 high

  const dirIntensity = sky.sunIntensity * (0.15 + 2.7 * sunUp) * (1 - 0.78 * cc);
  const sunColor = new THREE.Color("#ff8a4d").lerp(new THREE.Color("#fff3e0"), Math.min(1, sunUp * 2));
  const ambientI = 0.1 + 0.5 * cc + 0.18 * sunUp;
  const hemiI = 0.22 + 0.65 * cc + 0.22 * sunUp;
  const skyCol = new THREE.Color("#aecbff").lerp(new THREE.Color("#ffb27a"), warmth);
  const groundCol = new THREE.Color("#5a4f3e");
  const ambCol = new THREE.Color("#dfe6f5").lerp(new THREE.Color("#ffd9b0"), warmth * 0.6);

  const turbidity = 2 + 9 * cc;
  const rayleigh = 1 + 2 * cc + 1.6 * warmth;
  // WebGPU IBL strength tracks daylight (the static HDRI env would otherwise keep
  // the scene lit at night) and dims with cloud the same way the sun does.
  const envIntensity = sky.sunIntensity * (0.18 + 0.95 * Math.min(1, sunUp * 1.4)) * (1 - 0.5 * cc);

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
function WebGL2HdriEnv({ slug }: { slug: string }) {
  return <Environment files={hdriUrlFor(slug)} background={false} resolution={256} />;
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
            <Environment key={envKey} frames={1} resolution={256}>
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
            <WebGL2HdriEnv slug={hdriPreset} />
          )}
        </>
      )}

      {/* In WebGPU mode the HDRI env supplies image-based ambient, so the flat
          ambient/hemisphere fills are dialed back to avoid double-lighting. */}
      <ambientLight intensity={renderMode === "webgpu" ? c.ambientI * 0.35 : c.ambientI} color={c.ambCol} />
      <hemisphereLight
        intensity={renderMode === "webgpu" ? c.hemiI * 0.35 : c.hemiI}
        color={c.skyCol}
        groundColor={c.groundCol}
      />
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
