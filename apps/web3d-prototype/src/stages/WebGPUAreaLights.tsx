import { useMemo } from "react";
import * as THREE from "three/webgpu";
import { useStore } from "../state/store";

/**
 * LTC RectAreaLight fill for the WebGPU stage. Area lights add soft, physically
 * plausible fill that SSGI's contact darkening reads against — together they sell
 * the "real GI" look without the punchy hard shadows the sun already provides.
 *
 * RectAreaLight on WebGPU is enabled via RectAreaLightTexturesLib + setLTC (done
 * once in StageWebGPU). Notes from three's docs: no shadow support, PBR materials
 * only, intensity is physical. We keep the count tiny (3 lights) — area lights are
 * not cheap and per-window lights would balloon the cost.
 *
 * Placement is derived from the building's bounding box (union of the building
 * meshes the store already tracks), so it scales with whatever model is loaded
 * and stays in FEET world units like the rest of the scene.
 */

const BUILDING = new Set([
  "wall",
  "wall_interior",
  "roof",
  "window",
  "door",
  "floor",
  "foundation",
  "trim",
  "stair",
]);

function buildingBounds(meshesBySemantic: Map<string, THREE.Mesh[]>) {
  const box = new THREE.Box3();
  meshesBySemantic.forEach((meshes, sem) => {
    if (!BUILDING.has(sem)) return;
    meshes.forEach((m) => {
      if (!m.geometry) return;
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      const bb = m.geometry.boundingBox;
      if (bb) box.union(bb.clone().applyMatrix4(m.matrixWorld));
    });
  });
  return box;
}

export function WebGPUAreaLights() {
  // Recompute when the model becomes ready (meshes populate the store then).
  const ready = useStore((s) => s.ready);

  const lights = useMemo(() => {
    const map = useStore.getState().meshesBySemantic;
    const box = buildingBounds(map);
    if (box.isEmpty()) return null;

    const center = box.getCenter(new THREE.Vector3());
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const r = sphere.radius || 100;
    const top = box.max.y;

    return {
      center: center.toArray() as [number, number, number],
      // Big sky-fill panel overhead, facing down — soft ambient-sky bounce.
      sky: {
        pos: [center.x, top + r * 1.4, center.z] as [number, number, number],
        size: [r * 3, r * 3] as [number, number],
        target: [center.x, center.y, center.z] as [number, number, number],
        intensity: 0.9,
        color: "#bcd2ff",
      },
      // Two cool side fills (camera-ish front-left / front-right) to open up the
      // shaded façades the single sun leaves dark.
      fillL: {
        pos: [center.x - r * 1.6, center.y + r * 0.3, center.z + r * 1.4] as [
          number,
          number,
          number,
        ],
        size: [r * 1.6, r * 1.6] as [number, number],
        intensity: 0.45,
        color: "#e8eefc",
      },
      fillR: {
        pos: [center.x + r * 1.6, center.y + r * 0.3, center.z + r * 1.4] as [
          number,
          number,
          number,
        ],
        size: [r * 1.6, r * 1.6] as [number, number],
        intensity: 0.35,
        color: "#fff3e6",
      },
    };
  }, [ready]);

  if (!lights) return null;

  return (
    <group>
      <rectAreaLight
        position={lights.sky.pos}
        width={lights.sky.size[0]}
        height={lights.sky.size[1]}
        intensity={lights.sky.intensity}
        color={lights.sky.color}
        // RectAreaLight emits from one face — aim it at the building centre.
        onUpdate={(self: THREE.RectAreaLight) => self.lookAt(...lights.sky.target)}
      />
      <rectAreaLight
        position={lights.fillL.pos}
        width={lights.fillL.size[0]}
        height={lights.fillL.size[1]}
        intensity={lights.fillL.intensity}
        color={lights.fillL.color}
        onUpdate={(self: THREE.RectAreaLight) => self.lookAt(...lights.center)}
      />
      <rectAreaLight
        position={lights.fillR.pos}
        width={lights.fillR.size[0]}
        height={lights.fillR.size[1]}
        intensity={lights.fillR.intensity}
        color={lights.fillR.color}
        onUpdate={(self: THREE.RectAreaLight) => self.lookAt(...lights.center)}
      />
    </group>
  );
}
