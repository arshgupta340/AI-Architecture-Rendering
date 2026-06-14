import { useMemo } from "react";
import { ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { useStore } from "../state/store";

/**
 * Soft contact-shadow catcher under the building + entourage — the single biggest
 * "not floating" grounding cue. drei <ContactShadows> renders the scene with a depth
 * material into an FBO and blurs it onto a transparent plane at the building base.
 *
 * WebGL2 stages ONLY: on the WebGPU node renderer drei's MeshDepthMaterial logs
 * "not compatible" and renders a black square (R3F #3458), so this is never mounted
 * in StageWebGPU (which keeps its VSM cast shadows + SSGI AO instead).
 *
 * Baked once (frames={1}) and re-baked via `key` when the sun moves or entourage
 * changes, so it stays cheap in the demand-rendered WebGL2 stages. Hidden when real
 * geo tiles are on (the real terrain owns the ground then).
 */
export function ContactGround() {
  const anchor = useStore((s) => s.siteAnchor);
  const ready = useStore((s) => s.ready);
  const on = useStore((s) => s.contactShadows);
  const geoEnabled = useStore((s) => s.geo.enabled);
  const tod = useStore((s) => s.sky.timeOfDay);
  const entCount = useStore((s) => s.entourage.length);

  const dims = useMemo(() => {
    if (!ready) return { span: 800, far: 200 };
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
    if (box.isEmpty()) return { span: 800, far: 200 };
    const s = new THREE.Vector3();
    box.getSize(s);
    return {
      span: THREE.MathUtils.clamp(Math.max(s.x, s.z) * 2.6, 200, 4000),
      far: THREE.MathUtils.clamp(s.y * 1.3, 40, 1200),
    };
  }, [ready]);

  if (!anchor || !on || geoEnabled || !ready) return null;

  return (
    <ContactShadows
      key={`${Math.round(tod * 2)}|${entCount}|${dims.span}`}
      position={[anchor[0], anchor[1] + 0.06, anchor[2]]}
      scale={dims.span}
      resolution={1024}
      blur={2.6}
      far={dims.far}
      opacity={0.5}
      color="#15120c"
      frames={1}
      raycast={() => null}
    />
  );
}
