import { useMemo } from "react";
import { MeshReflectorMaterial } from "@react-three/drei";
import * as THREE from "three";
import { useStore } from "../state/store";

/**
 * Reflective ground plane for the WebGL2-GI stage — OWNED BY AGENT B.
 *
 * A large plane seated at the building base (y = siteAnchor[1]) with drei's
 * MeshReflectorMaterial. Real-time planar reflections of the building + sky are a
 * strong "expensive render" cue — they ground the model and add the wet-plaza /
 * polished-stone look that screenshots of archviz hero shots always have.
 *
 * Placement: the Rhino model already ships an opaque paving/site surface around
 * the building base. We seat the reflector a hair (≈0.5") ABOVE siteAnchor[1] so
 * it renders on top of that paving (no z-fight) and catches the reflection, while
 * still sitting BELOW every piece of building geometry (whose lowest faces are at
 * the base) so it never clips a wall. We only show it when real-world geo tiles
 * are OFF — with tiles on, the Rhino site is hidden and a flat mirror would fight
 * the actual terrain.
 *
 * Tuning (per the stage brief): resolution 1024, roughness ~0.8 (blurry, matte-ish
 * reflection — not a sharp mirror), blur [300,100], mixStrength ~1.5, mirror ~0.4.
 */
export function ReflectiveGround() {
  const anchor = useStore((s) => s.siteAnchor);
  const ready = useStore((s) => s.ready);
  const geoEnabled = useStore((s) => s.geo.enabled);

  // Size the plane off the building bbox so it reads as a generous plaza but does
  // not need to be absurdly huge (reflection cost scales with the rendered area).
  const span = useMemo(() => {
    if (!ready) return 2000;
    const map = useStore.getState().meshesBySemantic;
    const box = new THREE.Box3();
    const tmp = new THREE.Box3();
    map.forEach((meshes) =>
      meshes.forEach((m) => {
        if (!m.geometry) return;
        m.geometry.computeBoundingBox();
        if (m.geometry.boundingBox) box.union(tmp.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld));
      }),
    );
    if (box.isEmpty()) return 2000;
    const s = new THREE.Vector3();
    box.getSize(s);
    // ~6× the footprint, clamped, so reflections extend to the horizon line.
    return THREE.MathUtils.clamp(Math.max(s.x, s.z) * 6, 600, 8000);
  }, [ready]);

  if (!anchor || geoEnabled) return null;

  const y = anchor[1] + 0.04; // ~0.5" above the Rhino paving to avoid z-fighting

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[anchor[0], y, anchor[2]]}
      // Reflector renders the scene from a mirrored camera; exclude it from raycasts
      // so clicks still hit the real ground/building underneath for material picks.
      raycast={() => null}
    >
      <planeGeometry args={[span, span]} />
      <MeshReflectorMaterial
        resolution={1024}
        blur={[300, 100]}
        mixBlur={1}
        mixStrength={1.5}
        mirror={0.4}
        roughness={0.8}
        metalness={0.2}
        color="#9a9690"
        depthScale={1.1}
        minDepthThreshold={0.3}
        maxDepthThreshold={1.4}
      />
    </mesh>
  );
}
