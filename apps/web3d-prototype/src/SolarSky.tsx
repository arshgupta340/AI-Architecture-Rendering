import { useMemo } from "react";
import { Sky, Environment } from "@react-three/drei";
import * as THREE from "three";
import SunCalc from "suncalc";
import { useStore, type SkyState } from "./state/store";

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
  };
}

export function SolarSky({ radius }: { radius: number }) {
  const sky = useStore((s) => s.sky);
  const c = useMemo(() => computeSky(sky), [sky]);
  const lp = c.lightPos.clone().multiplyScalar(radius * 3);
  // Re-bake the IBL env only when the sun/clouds/date meaningfully change (coarse
  // key) so glass + metal reflections track time-of-day, without re-baking every
  // frame. drei <Environment frames={1}> otherwise bakes once and never updates.
  const envKey = `${Math.round(sky.timeOfDay * 2)}|${Math.round(sky.cloudCover * 10)}|${sky.date}`;

  return (
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
      {/* same sky baked to an env map so reflective/metal/glass surfaces read
          correctly; re-baked on `envKey` so reflections track the sun. */}
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
