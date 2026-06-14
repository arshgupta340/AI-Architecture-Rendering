import { useEffect, useMemo, useRef } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { RectAreaLightUniformsLib } from "three/examples/jsm/lights/RectAreaLightUniformsLib.js";
import SunCalc from "suncalc";
import { useStore, type SkyState } from "../state/store";

/**
 * Real sun-altitude factor (0 below the horizon → 1 at zenith), computed the SAME
 * way SolarSky drives the actual sun light, so this fill logic stays consistent with
 * the rendered sun rather than guessing from the clock. (The old `tod >= 7 && tod<=18`
 * cutoff wrongly treated a 06:15 summer sunrise as "night" and switched the window
 * emitters to full interior-glow brightness, spilling a glow onto the lit façade.)
 */
function sunUpFactor(sky: SkyState): number {
  const d = new Date(`${sky.date}T00:00:00`);
  d.setHours(Math.floor(sky.timeOfDay), Math.round((sky.timeOfDay % 1) * 60), 0, 0);
  const pos = SunCalc.getPosition(d, sky.lat, sky.lng);
  return Math.max(0, Math.sin(pos.altitude));
}

/**
 * RectAreaLight (LTC) area lights for the WebGL2-GI stage — OWNED BY AGENT B.
 *
 * Why area lights: a single directional "sun" gives hard, point-source shading.
 * Real exteriors are dominated by a huge SOFT source — the sky dome bouncing onto
 * every up-facing/façade surface. A big RectAreaLight overhead approximates that
 * soft sky-fill far better than ambient/hemisphere alone: it has DIRECTION and
 * AREA, so it produces gentle gradient falloff across a façade and soft speculars
 * on glass/metal that read as global illumination. Per-window emitter lights then
 * fake the "interior glow / light spilling from openings" cue.
 *
 * Hard facts (verified on three r0.184):
 *   - RectAreaLight needs RectAreaLightUniformsLib.init() ONCE before use, or it
 *     renders unlit. It only affects MeshStandard/MeshPhysical materials (all of
 *     ours qualify). It casts NO shadows — that's fine; the directional sun in
 *     SolarSky owns the shadows, these only add fill + speculars.
 *   - Intensity is treated as radiance; keep it modest so we ADD a soft lift, not
 *     blow the frame out (Bloom in EffectsGI would then veil it white).
 *
 * Placement is data-driven off the SAME building bbox the rest of the app uses:
 * we recompute it from `meshesBySemantic` (the sun/camera read the identical box
 * in Scene.tsx) and anchor everything to `siteAnchor` (building ground-centre).
 */

// Elements that constitute "the building" — must match Scene.tsx's BUILDING set so
// our bbox equals the one the camera/sun are framed to.
const BUILDING = new Set([
  "wall", "wall_interior", "roof", "window", "door", "floor", "foundation", "trim", "stair",
]);

// Cap window emitters — RectAreaLight is the most expensive light type (LTC eval
// per fragment per light). A dozen is plenty to sell the effect without tanking fps.
const MAX_WINDOW_LIGHTS = 12;

type WindowLight = {
  pos: [number, number, number];
  // normal (outward) used to orient the emitter and offset it off the glass
  normal: [number, number, number];
  size: number;
};

// One-time uniform-lib init (module scope so it runs once even if the component
// remounts across render-mode switches).
let _ltcReady = false;
function ensureLTC() {
  if (_ltcReady) return;
  RectAreaLightUniformsLib.init();
  _ltcReady = true;
}

const _box = new THREE.Box3();
const _b = new THREE.Box3();
const _c = new THREE.Vector3();
const _sz = new THREE.Vector3();
const _n = new THREE.Vector3();

/** A single overhead RectAreaLight that always faces straight down at `target`. */
function DownLight({
  position,
  target,
  width,
  height,
  intensity,
  color,
}: {
  position: [number, number, number];
  target: [number, number, number];
  width: number;
  height: number;
  intensity: number;
  color: string;
}) {
  const ref = useRef<THREE.RectAreaLight>(null);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const l = ref.current;
    if (!l) return;
    l.lookAt(target[0], target[1], target[2]);
    invalidate();
  }, [position, target, invalidate]);
  return (
    <rectAreaLight
      ref={ref}
      position={position}
      width={width}
      height={height}
      intensity={intensity}
      color={color}
    />
  );
}

/** A window emitter RectAreaLight oriented along the window's outward normal. */
function WindowEmitter({ light, intensity, color }: { light: WindowLight; intensity: number; color: string }) {
  const ref = useRef<THREE.RectAreaLight>(null);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const l = ref.current;
    if (!l) return;
    // Look outward from the façade: aim at a point one unit along the normal.
    l.lookAt(
      light.pos[0] + light.normal[0],
      light.pos[1] + light.normal[1],
      light.pos[2] + light.normal[2],
    );
    invalidate();
  }, [light, invalidate]);
  // Nudge the emitter a hair OUTSIDE the glass so it lights the reveal/façade
  // around the opening rather than being co-planar with the pane.
  const p: [number, number, number] = [
    light.pos[0] + light.normal[0] * 0.5,
    light.pos[1] + light.normal[1] * 0.5,
    light.pos[2] + light.normal[2] * 0.5,
  ];
  return (
    <rectAreaLight
      ref={ref}
      position={p}
      width={light.size}
      height={light.size}
      intensity={intensity}
      color={color}
    />
  );
}

export function AreaLights() {
  ensureLTC();
  const ready = useStore((s) => s.ready);
  const anchor = useStore((s) => s.siteAnchor);
  const sky = useStore((s) => s.sky);

  // Recompute the building bbox + window-emitter placements whenever the model
  // becomes ready (meshesBySemantic is populated by Scene.tsx before `ready`).
  const placement = useMemo(() => {
    if (!ready) return null;
    const map = useStore.getState().meshesBySemantic;
    _box.makeEmpty();
    map.forEach((meshes, sem) => {
      if (!BUILDING.has(sem)) return;
      meshes.forEach((m) => {
        if (!m.geometry) return;
        m.geometry.computeBoundingBox();
        if (m.geometry.boundingBox) {
          _box.union(_b.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld));
        }
      });
    });
    if (_box.isEmpty()) return null;
    _box.getCenter(_c);
    _box.getSize(_sz);
    const center: [number, number, number] = [_c.x, _c.y, _c.z];
    const top = _box.max.y;
    const footprint = Math.max(_sz.x, _sz.z);

    // ---- window emitters: one small light per window mesh (centroid + face normal) ----
    const windows = map.get("window") ?? [];
    const lights: WindowLight[] = [];
    const nm = new THREE.Matrix3();
    for (const m of windows) {
      if (lights.length >= MAX_WINDOW_LIGHTS) break;
      if (!m.geometry) continue;
      m.geometry.computeBoundingBox();
      const bb = m.geometry.boundingBox;
      if (!bb) continue;
      const wc = bb.getCenter(new THREE.Vector3()).applyMatrix4(m.matrixWorld);
      // Approximate outward normal from the first vertex normal, world-space.
      const nor = m.geometry.attributes.normal as THREE.BufferAttribute | undefined;
      _n.set(0, 0, 1);
      if (nor && nor.count > 0) {
        nm.getNormalMatrix(m.matrixWorld);
        _n.fromBufferAttribute(nor, 0).applyMatrix3(nm).normalize();
      }
      // Flip to point away from the building centre (outward-facing).
      const toOut = new THREE.Vector3(wc.x - _c.x, 0, wc.z - _c.z);
      if (_n.dot(toOut) < 0) _n.multiplyScalar(-1);
      const wsz = bb.getSize(new THREE.Vector3()).applyMatrix4(new THREE.Matrix4().extractRotation(m.matrixWorld));
      const size = Math.max(2, Math.min(Math.abs(wsz.x), Math.abs(wsz.y), Math.abs(wsz.z)) || 4);
      lights.push({ pos: [wc.x, wc.y, wc.z], normal: [_n.x, _n.y, _n.z], size });
    }

    return {
      center,
      top,
      // Sky-fill: a broad soft panel well above the roof, covering ~1.8× the
      // footprint, aimed straight down at the building centre.
      fill: {
        position: [center[0], top + footprint * 0.9, center[2]] as [number, number, number],
        width: footprint * 1.8,
        height: footprint * 1.8,
      },
      windows: lights,
    };
  }, [ready]);

  if (!placement || !anchor) return null;

  // Drive both fills off the REAL sun altitude (matches the rendered sun) instead of
  // a clock cutoff, so they stay physically consistent with the sky.
  const sunUp = sunUpFactor(sky); // 0 sun below horizon → 1 high sun
  // Cool soft sky-bounce fill — present in day, dimmer (and never warm) at night.
  // Kept low so it lifts the sky bounce without pushing HDR past the bloom threshold.
  const fillColor = "#cfe0ff";
  const fillIntensity = 0.22 + 0.4 * sunUp;
  // Interior-glow emitters: windows only "switch on" as the sun drops to/below the
  // horizon. During the day real windows reflect the sky (handled by the glass +
  // IBL), they do NOT spill light onto the exterior — so ramp these to ~0 in daylight
  // (kills the bright glow on the lit façade/ground). `darkness` hits 0 once the sun
  // is more than a few degrees up, 1 at/below the horizon.
  const darkness = THREE.MathUtils.clamp(1 - sunUp * 6, 0, 1);
  const winColor = "#ffdfb0";
  const winIntensity = 2.2 * darkness;
  const showWindows = winIntensity > 0.03;

  return (
    <group>
      <DownLight
        position={placement.fill.position}
        target={placement.center}
        width={placement.fill.width}
        height={placement.fill.height}
        intensity={fillIntensity}
        color={fillColor}
      />
      {showWindows &&
        placement.windows.map((w, i) => (
          <WindowEmitter key={i} light={w} intensity={winIntensity} color={winColor} />
        ))}
    </group>
  );
}
