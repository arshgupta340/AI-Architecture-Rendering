import { useMemo } from "react";
import * as THREE from "three";
import SunCalc from "suncalc";
import { useStore } from "./state/store";

/**
 * Sun-path overlay — the architect's solar diagram.
 *
 * Two curves, both sampled from the *real* SunCalc sun at the site (store.sky
 * lat/lng + date), and mapped to a direction with the SAME spherical formula
 * SolarSky uses for the directional light:
 *     new THREE.Vector3().setFromSphericalCoords(R, Math.PI/2 - altitude, azimuth)
 * so the arc passes exactly through where the sun light comes from.
 *
 *  - DAY ARC: the sun's track across the selected day (sampled every ~20 min,
 *    above-horizon points only). Hour ticks mark whole local hours.
 *  - ANALEMMA: solar position at solar noon on the 21st of each month — the
 *    figure-eight that shows seasonal swing for the site.
 *
 * Rendered with PLAIN three primitives (<line>/<lineBasicMaterial>,
 * <points>/<pointsMaterial>) which are node-safe on the WebGPU renderer — drei's
 * <Line>/Line2 is a ShaderMaterial that breaks the WebGPU node renderer, so it's
 * deliberately avoided here. Lines are depth-tested off so the diagram reads as an
 * overlay floating around the building rather than getting clipped by it.
 */

const DAY_ARC_COLOR = "#ffd27a"; // warm, like a sun streak
const ANALEMMA_COLOR = "#7ab8ff"; // cool, distinct from the day arc
const TICK_COLOR = "#fff0c8";

function dateAt(dateStr: string, hours: number): Date {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setHours(Math.floor(hours), Math.round((hours % 1) * 60), 0, 0);
  return d;
}

/** Map a (azimuth, altitude) sun position to a world direction * R — identical to
 * SolarSky's `setFromSphericalCoords(R, Math.PI/2 - altitude, azimuth)`. */
function sunDir(altitude: number, azimuth: number, R: number): THREE.Vector3 {
  return new THREE.Vector3().setFromSphericalCoords(R, Math.PI / 2 - altitude, azimuth);
}

export function SunPath({ radius }: { radius: number }) {
  const lat = useStore((s) => s.sky.lat);
  const lng = useStore((s) => s.sky.lng);
  const date = useStore((s) => s.sky.date);

  const { dayPositions, hourTicks, analemmaPositions } = useMemo(() => {
    const R = radius * 3; // same arc radius as the SolarSky directional light

    // --- Day arc: every 20 min, keep above-horizon samples ---
    const day: number[] = [];
    const ticks: number[] = [];
    let prevAbove = false;
    for (let mins = 0; mins <= 24 * 60; mins += 20) {
      const t = mins / 60;
      const p = SunCalc.getPosition(dateAt(date, t), lat, lng);
      const above = p.altitude > 0;
      if (above) {
        const v = sunDir(p.altitude, p.azimuth, R);
        day.push(v.x, v.y, v.z);
        // Hour tick at (or just after) each whole local hour the sun is up.
        if (Number.isInteger(t)) ticks.push(v.x, v.y, v.z);
      } else if (prevAbove) {
        // Drop a final point near the horizon so the arc ends cleanly.
        const v = sunDir(0, p.azimuth, R);
        day.push(v.x, v.y, v.z);
      }
      prevAbove = above;
    }

    // --- Analemma: solar noon on the 21st of each month ---
    const ana: number[] = [];
    const year = new Date(`${date}T00:00:00`).getFullYear();
    for (let m = 0; m < 12; m++) {
      const noon = new Date(year, m, 21, 12, 0, 0, 0);
      const noonPos = SunCalc.getTimes(noon, lat, lng).solarNoon ?? noon;
      const p = SunCalc.getPosition(noonPos, lat, lng);
      // Only meaningful when the noon sun is above the horizon (polar sites aside).
      if (p.altitude > 0) {
        const v = sunDir(p.altitude, p.azimuth, R);
        ana.push(v.x, v.y, v.z);
      }
    }
    // Close the analemma loop for a continuous figure-eight.
    if (ana.length >= 6) ana.push(ana[0], ana[1], ana[2]);

    return {
      dayPositions: new Float32Array(day),
      hourTicks: new Float32Array(ticks),
      analemmaPositions: new Float32Array(ana),
    };
  }, [lat, lng, date, radius]);

  return (
    <group renderOrder={10}>
      {dayPositions.length >= 6 && (
        <line>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[dayPositions, 3]} />
          </bufferGeometry>
          <lineBasicMaterial
            color={DAY_ARC_COLOR}
            transparent
            opacity={0.9}
            depthTest={false}
            toneMapped={false}
          />
        </line>
      )}

      {analemmaPositions.length >= 6 && (
        <line>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[analemmaPositions, 3]} />
          </bufferGeometry>
          <lineBasicMaterial
            color={ANALEMMA_COLOR}
            transparent
            opacity={0.65}
            depthTest={false}
            toneMapped={false}
          />
        </line>
      )}

      {hourTicks.length >= 3 && (
        <points>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[hourTicks, 3]} />
          </bufferGeometry>
          <pointsMaterial
            color={TICK_COLOR}
            size={Math.max(2, radius * 0.06)}
            sizeAttenuation
            transparent
            opacity={0.95}
            depthTest={false}
            toneMapped={false}
          />
        </points>
      )}
    </group>
  );
}
