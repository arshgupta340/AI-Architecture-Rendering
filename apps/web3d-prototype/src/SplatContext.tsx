import { useEffect, useMemo, useState } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { SparkRenderer as SparkRendererT, SplatMesh as SplatMeshT } from "@sparkjsdev/spark";
import { useStore } from "./state/store";
import { setBakeContext } from "./lib/splatBake";

/**
 * Gaussian-splat "context backdrop". Mounted inside the WebGL2 / +GI Stage <Canvas>
 * (Spark is WebGLRenderer-only — never WebGPU). When `splatEnabled` + a `splatUrl`,
 * it lazy-loads @sparkjsdev/spark (≈heavy, so it only downloads when splats are
 * actually used), renders the splat seated on the building (siteAnchor + the
 * splatTransform sliders, mirroring the GeoTiles strategy), and lays a transparent
 * ShadowMaterial catcher under it so the SolarSky sun grounds the building on the
 * splat.
 *
 * Coordinate convention: Inria/.ply (nerfstudio, our scene-bake) is Y-up → no flip;
 * World Labs Marble .spz is OpenCV (Y-down) → flip X by π. The remaining alignment
 * is the user's job via the SplatPanel sliders.
 */

// Tight-ish shadow plane span from the building bbox (fallback to a generous default).
function buildingSpan(meshesBySemantic: Map<string, THREE.Mesh[]>): number {
  const box = new THREE.Box3();
  const tmp = new THREE.Box3();
  meshesBySemantic.forEach((meshes) =>
    meshes.forEach((m) => {
      if (!m.geometry) return;
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      if (m.geometry.boundingBox) box.union(tmp.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld));
    }),
  );
  if (box.isEmpty()) return 1500;
  const s = new THREE.Vector3();
  box.getSize(s);
  return THREE.MathUtils.clamp(Math.max(s.x, s.z) * 5, 400, 6000);
}

export function SplatContext() {
  const gl = useThree((s) => s.gl) as THREE.WebGLRenderer;
  const invalidate = useThree((s) => s.invalidate);
  const ready = useThree((s) => s.scene); // ensure scene exists
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const enabled = useStore((s) => s.splatEnabled);
  const url = useStore((s) => s.splatUrl);
  const source = useStore((s) => s.splatSource);
  const tf = useStore((s) => s.splatTransform);
  const exposure = useStore((s) => s.splatExposure);
  const anchor = useStore((s) => s.siteAnchor);
  const readyFlag = useStore((s) => s.ready);

  // Register the live renderer/scene/camera so the SplatPanel "Bake scene → splat"
  // button (a DOM panel outside the Canvas) can drive the orbit-capture. This runs
  // unconditionally (before the early return) so baking works even before a splat
  // URL exists.
  useEffect(() => {
    setBakeContext({ gl, scene: ready, camera });
    return () => setBakeContext(null);
  }, [gl, ready, camera]);

  // Lazy-load the Spark module (keeps ~Spark out of the stage chunk until used).
  const [mod, setMod] = useState<{
    SparkRenderer: typeof SparkRendererT;
    SplatMesh: typeof SplatMeshT;
  } | null>(null);
  useEffect(() => {
    if (!enabled || mod) return;
    let alive = true;
    import("@sparkjsdev/spark")
      .then((m) => alive && setMod({ SparkRenderer: m.SparkRenderer, SplatMesh: m.SplatMesh }))
      .catch((e) => console.error("[splat] failed to load @sparkjsdev/spark", e));
    return () => {
      alive = false;
    };
  }, [enabled, mod]);

  // One SparkRenderer per GL context — added to the scene root; auto-updates the
  // gsplat sort each render. onDirty re-invalidates so demand-mode picks up the
  // async sort/LoD completions.
  const spark = useMemo<SparkRendererT | null>(() => {
    if (!mod || !gl) return null;
    try {
      const sr = new mod.SparkRenderer({ renderer: gl, encodeLinear: true });
      sr.onDirty = () => invalidate();
      return sr;
    } catch (e) {
      console.error("[splat] SparkRenderer init failed", e);
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mod, gl]);

  // The SplatMesh — recreated when the URL changes; disposed on cleanup.
  const [splat, setSplat] = useState<SplatMeshT | null>(null);
  useEffect(() => {
    if (!mod || !enabled || !url) {
      setSplat(null);
      return;
    }
    let mesh: SplatMeshT | null = null;
    try {
      mesh = new mod.SplatMesh({
        url,
        onLoad: () => invalidate(),
      });
      setSplat(mesh);
    } catch (e) {
      console.error("[splat] SplatMesh load failed for", url, e);
    }
    return () => {
      try {
        mesh?.dispose();
      } catch {
        /* best-effort */
      }
      setSplat(null);
    };
  }, [mod, enabled, url, invalidate]);

  // Exposure → Spark `recolor` (a per-splat RGB multiplier).
  useEffect(() => {
    if (!splat) return;
    try {
      splat.recolor = new THREE.Color(exposure, exposure, exposure);
      invalidate();
    } catch {
      /* recolor unsupported on this build — ignore */
    }
  }, [splat, exposure, invalidate]);

  const span = useMemo(
    () => (readyFlag ? buildingSpan(useStore.getState().meshesBySemantic) : 1500),
    [readyFlag],
  );

  if (!ready || !enabled || !url || !anchor || !spark || !splat) return null;

  // Marble .spz = OpenCV (Y-down) → flip X; Inria .ply (incl. our scene-bake) is Y-up.
  const flipX = source === "file" && url.toLowerCase().endsWith(".spz");
  const baseY = anchor[1] + tf.posY;

  return (
    <>
      {/* SparkRenderer at the scene root (it accumulates splats globally). */}
      <primitive object={spark} />
      {/* The splat, seated on the building. Outer = world placement; inner = up-axis
          correction + yaw. */}
      <group
        position={[anchor[0], baseY, anchor[2]]}
        rotation={[0, THREE.MathUtils.degToRad(tf.heading), 0]}
        scale={tf.scale}
      >
        <group rotation={[flipX ? Math.PI : 0, THREE.MathUtils.degToRad(tf.yaw), 0]}>
          <primitive object={splat} />
        </group>
      </group>
      {/* Transparent shadow-catcher so the sun grounds the building on the splat. */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[anchor[0], baseY + 0.05, anchor[2]]}
        receiveShadow
        raycast={() => null}
      >
        <planeGeometry args={[span, span]} />
        <shadowMaterial opacity={0.4} transparent />
      </mesh>
    </>
  );
}
