import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { WebGLPathTracer } from "three-gpu-pathtracer";
import { useStore } from "./state/store";

/**
 * Progressive path-traced "hero" render — the offline-GI reference.
 *
 * WHY A SEPARATE MODEL: the scene's `house.glb` is meshopt + KHR_mesh_quantization
 * compressed (POSITION:i16_norm etc.). three.js decodes that into a quantized
 * BufferGeometry whose draw-time dequant lives in the vertex shader — but the path
 * tracer reads raw vertex *data* on the CPU to build its BVH, so it intersected the
 * un-dequantized integer positions and the building "vanished" (only the sky/IBL
 * rendered). Dequantizing fixes that. `house_pt.glb` is a plain float32 copy of the
 * exact same geometry (581 meshes / 6543 primitives, identical node `extras`
 * semantics), produced by `gltf-transform dequantize` — no quantization, no meshopt.
 * See UE_LUMEN_RUNBOOK.md / commit message for the provenance.
 *
 * The whole model (incl. a huge site topo) is too heavy to path-trace, so we keep
 * ONLY the building + immediate paving (PT_KEEP) — a small BVH that builds in ~1-2s.
 * We add that dequantized subset to the live scene, hide the compressed originals so
 * they don't double up, and let `setScene` pick up the SolarSky IBL for lighting.
 * useFrame priority 1 takes over rendering so the accumulation blits to the canvas.
 */
const PT_MODEL_URL = "/model/house_pt.glb";
const PT_KEEP = new Set([
  "wall", "wall_interior", "roof", "window", "door", "floor", "foundation", "trim", "stair", "paving",
]);

// Resolve a mesh's element class from the nearest ancestor carrying `semantic`
// (GLTFLoader copies glTF node `extras` onto Object3D.userData).
function semOf(o: THREE.Object3D): string {
  for (let n: THREE.Object3D | null = o; n; n = n.parent) {
    const s = (n.userData as { semantic?: string })?.semantic;
    if (s) return s;
  }
  return "other";
}

// Load the dequantized GLB once; the loader is plain (no DRACO/meshopt needed —
// house_pt.glb carries neither extension).
let _ptGltfPromise: Promise<THREE.Group> | null = null;
function loadPtModel(): Promise<THREE.Group> {
  if (!_ptGltfPromise) {
    const loader = new GLTFLoader();
    _ptGltfPromise = loader
      .loadAsync(PT_MODEL_URL)
      .then((gltf) => gltf.scene)
      .catch((e) => {
        _ptGltfPromise = null; // allow a retry on the next render
        throw e;
      });
  }
  return _ptGltfPromise;
}

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
    const hiddenLive: THREE.Object3D[] = [];
    let ptRoot: THREE.Object3D | null = null;
    const shared = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#cdbfae"),
      roughness: 0.85,
      metalness: 0,
      side: THREE.DoubleSide,
    });

    // Hide the live (compressed) building meshes so the dequantized copy we add
    // below is the only thing in the BVH / on screen — no z-fighting or doubling.
    useStore.getState().meshesBySemantic.forEach((meshes) => {
      meshes.forEach((m) => {
        if (m.visible) {
          m.visible = false;
          hiddenLive.push(m);
        }
      });
    });

    const pt = new WebGLPathTracer(gl);
    pt.renderScale = 0.5;
    pt.bounces = 3;
    pt.dynamicLowRes = false;
    pt.minSamples = 1;
    pt.renderDelay = 0;
    pt.fadeDuration = 0;
    ptRef.current = pt;

    loadPtModel()
      .then((source) => {
        if (disposed) return;
        // Clone so repeated renders never mutate the cached source. Keep ONLY the
        // building + paving; collapse every kept mesh onto ONE shared material
        // (the tracer packs each unique material into GPU structures — thousands of
        // them break it, reading geometry as empty), exactly like the prior design.
        const root = source.clone(true);
        const drop: THREE.Object3D[] = [];
        root.traverse((o) => {
          const m = o as THREE.Mesh;
          if (!m.isMesh) return;
          if (PT_KEEP.has(semOf(m))) {
            m.material = shared;
            m.castShadow = true;
            m.receiveShadow = true;
          } else {
            drop.push(m);
          }
        });
        drop.forEach((m) => m.removeFromParent());
        ptRoot = root;
        scene.add(root);

        const t0 = performance.now();
        pt.setScene(scene, camera);
        ready.current = true;
        lastMatrix.current.copy(camera.matrixWorld);
        setSamples(0);
        invalidate();
        // eslint-disable-next-line no-console
        console.log(
          `[pathtracer] dequantized building BVH built in ${((performance.now() - t0) / 1000).toFixed(1)}s`,
        );
      })
      .catch((e) => {
        // eslint-disable-next-line no-console
        console.error("[pathtracer] load/build failed:", e);
      });

    return () => {
      disposed = true;
      ready.current = false;
      ptRef.current = null;
      if (ptRoot) {
        scene.remove(ptRoot);
        ptRoot.traverse((o) => {
          const m = o as THREE.Mesh;
          if (m.isMesh && m.geometry) m.geometry.dispose();
        });
      }
      shared.dispose();
      hiddenLive.forEach((m) => (m.visible = true));
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
