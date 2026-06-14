import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { WebGLPathTracer } from "three-gpu-pathtracer";
import { useStore } from "./state/store";

/**
 * Progressive path-traced "hero" render.
 *
 * The whole model (6.5k primitives incl. a huge site topo) is far too heavy to
 * path-trace — a synchronous BVH build froze the tab for minutes ("nothing
 * changed"), and the async path needs a BVH web-worker. So we path-trace ONLY
 * the building + immediate paving (the generator skips invisible meshes), which
 * builds a small BVH in ~1-2s. useFrame priority 1 takes over rendering so the
 * accumulation blits to the canvas; the HDRI still lights + backgrounds it.
 */
const PT_KEEP = new Set([
  "wall", "wall_interior", "roof", "window", "door", "floor", "foundation", "trim", "stair", "paving",
]);

export function PathTracer() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const invalidate = useThree((s) => s.invalidate);
  const setSamples = useStore((s) => s.setSamples);

  const ptRef = useRef<WebGLPathTracer | null>(null);
  const ready = useRef(false);
  const lastMatrix = useRef(new THREE.Matrix4());
  const frame = useRef(0);

  useEffect(() => {
    let disposed = false;
    // Hide the heavy site topo / misc so the BVH stays small.
    const hidden: THREE.Object3D[] = [];
    useStore.getState().meshesBySemantic.forEach((meshes, sem) => {
      if (!PT_KEEP.has(sem)) {
        meshes.forEach((m) => {
          if (m.visible) {
            m.visible = false;
            hidden.push(m);
          }
        });
      }
    });

    // Collapse the thousands of per-mesh "original" material clones onto ONE
    // shared material — the path tracer packs every unique material into GPU
    // structures, and 6k+ of them break it (geometry reads as empty). Meshes
    // that carry a swatch keep it (only a handful of unique swatch materials).
    const shared = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#cdbfae"),
      roughness: 0.85,
      metalness: 0,
      side: THREE.DoubleSide,
    });
    const swapped: { m: THREE.Mesh; mat: THREE.Material | THREE.Material[] }[] = [];
    useStore.getState().meshesBySemantic.forEach((meshes, sem) => {
      if (!PT_KEEP.has(sem)) return;
      meshes.forEach((m) => {
        if (m.material === (m.userData as { originalMat?: THREE.Material }).originalMat) {
          swapped.push({ m, mat: m.material });
          m.material = shared;
        }
      });
    });
    // eslint-disable-next-line no-console
    console.log(`[pathtracer] collapsed ${swapped.length} meshes onto a shared material`);

    const pt = new WebGLPathTracer(gl);
    pt.renderScale = 0.5;
    pt.bounces = 3;
    pt.dynamicLowRes = false;
    pt.minSamples = 1;
    pt.renderDelay = 0;
    pt.fadeDuration = 0;
    ptRef.current = pt;

    // Defer the blocking sync build one frame so the "Building…" indicator paints.
    const raf = requestAnimationFrame(() => {
      if (disposed) return;
      try {
        const t0 = performance.now();
        pt.setScene(scene, camera);
        ready.current = true;
        lastMatrix.current.copy(camera.matrixWorld);
        setSamples(0);
        // eslint-disable-next-line no-console
        console.log(`[pathtracer] built building-only BVH in ${((performance.now() - t0) / 1000).toFixed(1)}s`);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("[pathtracer] build failed:", e);
      }
    });

    return () => {
      disposed = true;
      ready.current = false;
      ptRef.current = null;
      cancelAnimationFrame(raf);
      hidden.forEach((m) => (m.visible = true));
      swapped.forEach(({ m, mat }) => (m.material = mat));
      shared.dispose();
      invalidate();
    };
  }, [gl, scene, camera, setSamples, invalidate]);

  useFrame(() => {
    const pt = ptRef.current;
    if (!pt || !ready.current) return;
    if (!camera.matrixWorld.equals(lastMatrix.current)) {
      lastMatrix.current.copy(camera.matrixWorld);
      pt.updateCamera();
    }
    gl.setRenderTarget(null); // ensure the blit lands on the canvas, not a stray target
    pt.renderSample();
    frame.current++;
    if (frame.current % 8 === 0) setSamples(Math.round((pt as unknown as { samples: number }).samples));
  }, 1);

  return null;
}
