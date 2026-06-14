import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { WebGLPathTracer } from "three-gpu-pathtracer";
import { useStore } from "./state/store";
import { swatchMaterial } from "./lib/swatches";
import { hdriUrlFor } from "./SolarSky";

/**
 * Progressive path-traced "hero" render — the offline-GI reference.
 *
 * WHY A DEDICATED SCENE: the path tracer's BVH builder + MaterialsTexture read raw
 * vertex data and `material.color.{r,g,b}` on the CPU. Two things broke the old
 * code that fed it the LIVE scene:
 *   1. The live scene's drei <Sky> is a ShaderMaterial with NO `.color` →
 *      MaterialsTexture.updateFrom crashed on `m.color.r`.
 *   2. `house.glb` is meshopt + KHR_mesh_quantization compressed; its quantized
 *      integer positions are only dequantized in the draw-time vertex shader, so
 *      the CPU-side BVH intersected garbage and the building "vanished".
 * FIX: build a private `ptScene`, load the dequantized `house_pt.glb` (plain
 * float32, same geometry/semantics), add ONLY the building root, mirror the user's
 * chosen swatch materials onto it, give windows real glass, assign the selected
 * HDRI to `ptScene.environment`, and defensively guarantee every material has a
 * `.color` before `setScene`. Path-trace only runs in webgl2/webgl2gi (NavBar
 * guards it out of webgpu), so a WebGL renderer is assumed.
 */
const PT_MODEL_URL = "/model/house_pt.glb";
const PT_KEEP = new Set([
  "wall", "wall_interior", "roof", "window", "door", "floor", "foundation", "trim", "stair", "paving",
]);

// Resolve a mesh's element class from the nearest ancestor carrying `semantic`
// (GLTFLoader copies glTF node `extras` onto Object3D.userData) — same walk as
// Scene.semOf so swatch layers resolve to the identical element classes.
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

// HDRI environment cache keyed by slug, so toggling render on/off doesn't re-decode.
const _hdrCache = new Map<string, Promise<THREE.DataTexture>>();
function loadHdri(slug: string): Promise<THREE.DataTexture> {
  let p = _hdrCache.get(slug);
  if (!p) {
    const loader = new HDRLoader();
    p = loader.loadAsync(hdriUrlFor(slug)).then((tex) => {
      tex.mapping = THREE.EquirectangularReflectionMapping;
      return tex;
    });
    _hdrCache.set(slug, p);
  }
  return p;
}

// Build the shared architectural glass for the path-traced windows. A defined
// `.color` (THREE.Color) is REQUIRED — MaterialsTexture reads color.{r,g,b}.
function makeGlass(): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    transmission: 1,
    ior: 1.5,
    roughness: 0.07,
    metalness: 0,
    thickness: 0.2,
    color: new THREE.Color("#e9eff1"),
    side: THREE.DoubleSide,
  });
}

// Defensive: ensure a material the tracer will pack has a real `.color`. Covers any
// exotic material that slipped through (the MaterialsTexture crash class).
function ensureColor(mat: THREE.Material): void {
  const m = mat as THREE.Material & { color?: THREE.Color };
  if (!m.color || !(m.color as THREE.Color).isColor) {
    m.color = new THREE.Color("#cdbfae");
  }
}

export function PathTracer() {
  const gl = useThree((s) => s.gl);
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
    // Track what we create so cleanup can dispose it.
    let ptRoot: THREE.Object3D | null = null;
    const ownedMaterials: THREE.Material[] = [];
    const ptScene = new THREE.Scene();
    const glass = makeGlass();
    ownedMaterials.push(glass);

    // Hide the live (compressed) building meshes so the on-screen accumulation isn't
    // doubled by the rasterised scene underneath the path-traced blit.
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

    const hdriPreset = useStore.getState().hdriPreset;

    Promise.all([loadPtModel(), loadHdri(hdriPreset)])
      .then(([source, hdr]) => {
        if (disposed) return;

        // Snapshot the user's CURRENT swatch assignments so the hero render shows the
        // architect's chosen materials, not GLTF/default ones. Map semantic → swatch.
        const layers = useStore.getState().layers;
        const swatchBySem = new Map<string, string>();
        layers.forEach((l) => {
          if (l.visible) swatchBySem.set(l.semantic, l.swatch);
        });

        // Clone so repeated renders never mutate the cached source. Keep ONLY the
        // building + paving subset (small BVH). Mirror swatch materials per element;
        // windows get real glass; everything else gets either the chosen swatch
        // material or a neutral fallback. Every material is color-guarded.
        const fallback = new THREE.MeshStandardMaterial({
          color: new THREE.Color("#cdbfae"),
          roughness: 0.85,
          metalness: 0,
          side: THREE.DoubleSide,
        });
        ownedMaterials.push(fallback);

        const root = source.clone(true);
        const drop: THREE.Object3D[] = [];
        root.traverse((o) => {
          const m = o as THREE.Mesh;
          if (!m.isMesh) return;
          const sem = semOf(m);
          if (!PT_KEEP.has(sem)) {
            drop.push(m);
            return;
          }
          let mat: THREE.Material;
          if (sem === "window") {
            mat = glass;
          } else {
            const swatch = swatchBySem.get(sem);
            // swatchMaterial returns a cached shared instance — fine for tracing.
            mat = swatch ? swatchMaterial(swatch, sem) : fallback;
          }
          ensureColor(mat);
          m.material = mat;
          m.castShadow = true;
          m.receiveShadow = true;
        });
        drop.forEach((m) => m.removeFromParent());

        ptRoot = root;
        ptScene.add(root);

        // Image-based lighting from the selected HDRI; a soft gradient-ish color
        // background (the env still drives reflections/GI). Intensity left at 1 so
        // the offline reference is a clean, unattenuated IBL.
        ptScene.environment = hdr;
        ptScene.background = new THREE.Color("#aec3df");

        // Final defensive sweep: guarantee EVERY material the tracer will pack has a
        // `.color` (the MaterialsTexture.updateFrom crash class).
        ptScene.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (!mesh.isMesh || !mesh.material) return;
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          mats.forEach(ensureColor);
        });

        const t0 = performance.now();
        pt.setScene(ptScene, camera);
        ready.current = true;
        lastMatrix.current.copy(camera.matrixWorld);
        setSamples(0);
        invalidate();
        // eslint-disable-next-line no-console
        console.log(
          `[pathtracer] dedicated ptScene BVH built in ${((performance.now() - t0) / 1000).toFixed(1)}s`,
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
        ptRoot.traverse((o) => {
          const m = o as THREE.Mesh;
          if (m.isMesh && m.geometry) m.geometry.dispose();
        });
        ptScene.remove(ptRoot);
      }
      // Dispose only materials we created; swatchMaterial()/cached HDRIs are shared
      // and owned elsewhere, so leave them alone.
      ownedMaterials.forEach((m) => m.dispose());
      ptScene.environment = null;
      ptScene.background = null;
      hiddenLive.forEach((m) => (m.visible = true));
      invalidate();
    };
  }, [gl, camera, setSamples, invalidate]);

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
