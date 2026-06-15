import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useStore, type HeroCaptureData } from "../state/store";

/**
 * HeroCapture — 4-pass capture of the LIVE WebGL2 / +GI scene for the hero render.
 *
 * Mounted inside StageWebGL2 + StageWebGL2GI <Canvas> (NOT WebGPU). On mount it
 * registers `heroCaptureFn` on the store; the NavBar "Hero render" button calls it.
 * The fn renders aligned passes at one common (W,H) — rounded to a multiple of 16
 * (FLUX VAE constraint) — without disturbing the live scene, and returns a
 * {@link HeroCaptureData} bundle:
 *
 *   - beauty : the on-screen post-processed frame (preserveDrawingBuffer toBlob),
 *              captured FIRST so beauty == what the user sees, then downscaled to (W,H).
 *   - depth  : a LINEAR eye-space depth pass (custom shader) normalized over the
 *              BUILDING's depth range and written NEAR=white / FAR=black — the
 *              convention FLUX/MiDaS depth ControlNets expect (verified). Using a
 *              linear, range-fitted depth (not MeshDepthMaterial's non-linear
 *              gl_FragCoord.z, which is ~all-white for distant geometry) gives a
 *              usable gradient across the facade.
 *   - idsRgb : every mesh in meshesBySemantic gets a stable integer id, painted with
 *              a flat MeshBasicMaterial whose color packs id as r=id&0xff, g=(id>>8)&0xff,
 *              b=0. Rendered with THREE.ColorManagement OFF + a NoColorSpace target so
 *              the bytes round-trip EXACTLY (no sRGB gamma mangling) — the server
 *              decodes id = r | g<<8.
 *   - regions: { id : { semantic } } built alongside the id assignment.
 *   - camera : pos / target (real OrbitControls target if present) / fov.
 *
 * Restore discipline (try/finally): scene.overrideMaterial, every swapped per-mesh
 * material reference, the bound render target, clear color, autoClear and
 * THREE.ColorManagement.enabled are all restored to EXACTLY their pre-capture values.
 *
 * Back-end / Modal contract (must match spike/modal_flux.py):
 *   - Images are BARE base64 PNG — NO `data:` prefix.
 *   - idsRgb packs id as r | g<<8 (b always 0). Decode: id = r + (g<<8).
 *   - depth is NEAR=white, FAR=black, linear; the server percentile-normalizes it.
 *   - all buffers share the width/height returned in the bundle (both /16).
 */

const raf = () => new Promise<void>((r) => requestAnimationFrame(() => r()));
const round16 = (n: number) => Math.max(16, Math.floor(n / 16) * 16);

// Linear eye-space depth, NEAR=white / FAR=black, normalized over [uNear, uFar]
// (the building's depth range). One shared instance; uniforms set per capture.
const DEPTH_MATERIAL = new THREE.ShaderMaterial({
  uniforms: { uNear: { value: 0.1 }, uFar: { value: 1000 } },
  vertexShader: /* glsl */ `
    varying float vEyeDepth;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vEyeDepth = -mv.z;                 // distance from camera along the view axis
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: /* glsl */ `
    uniform float uNear;
    uniform float uFar;
    varying float vEyeDepth;
    void main() {
      float t = clamp((vEyeDepth - uNear) / max(uFar - uNear, 1e-4), 0.0, 1.0);
      float v = 1.0 - t;                 // near = white (1.0), far = black (0.0)
      gl_FragColor = vec4(v, v, v, 1.0);
    }`,
  side: THREE.DoubleSide,
});

/** Blob → bare base64 (no `data:` prefix). */
async function blobToB64(blob: Blob): Promise<string> {
  const dataUrl = await new Promise<string>((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result as string);
    fr.onerror = () => rej(fr.error ?? new Error("FileReader failed"));
    fr.readAsDataURL(blob);
  });
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

function makeCanvas(w: number, h: number): OffscreenCanvas | HTMLCanvasElement {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(w, h);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

async function canvasToB64(c: OffscreenCanvas | HTMLCanvasElement): Promise<string> {
  const blob =
    c instanceof OffscreenCanvas
      ? await c.convertToBlob({ type: "image/png" })
      : await new Promise<Blob>((res, rej) =>
          (c as HTMLCanvasElement).toBlob((b) => (b ? res(b) : rej(new Error("toBlob failed"))), "image/png"),
        );
  return blobToB64(blob);
}

/** Read an RGBA8 render target back, flip GL bottom-up rows to top-down, → base64 PNG. */
async function rtToPngB64(
  gl: THREE.WebGLRenderer,
  rt: THREE.WebGLRenderTarget,
  w: number,
  h: number,
): Promise<string> {
  const buf = new Uint8Array(w * h * 4);
  gl.readRenderTargetPixels(rt, 0, 0, w, h, buf);
  const flipped = new Uint8ClampedArray(w * h * 4);
  const rowBytes = w * 4;
  for (let y = 0; y < h; y++) {
    const src = (h - 1 - y) * rowBytes;
    flipped.set(buf.subarray(src, src + rowBytes), y * rowBytes);
  }
  const c = makeCanvas(w, h);
  const ctx = c.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null;
  if (!ctx) throw new Error("2D context unavailable");
  ctx.putImageData(new ImageData(flipped, w, h), 0, 0);
  return canvasToB64(c);
}

/** World-space bounding sphere of all loaded meshes → a tight building depth range. */
function buildingDepthRange(
  meshesBySemantic: Map<string, THREE.Mesh[]>,
  camera: THREE.PerspectiveCamera,
): { near: number; far: number } {
  const box = new THREE.Box3();
  const tmp = new THREE.Box3();
  meshesBySemantic.forEach((meshes) =>
    meshes.forEach((m) => {
      if (!m.geometry) return;
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      if (m.geometry.boundingBox) box.union(tmp.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld));
    }),
  );
  if (box.isEmpty()) return { near: Math.max(0.1, camera.near), far: camera.far };
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const d = camera.position.distanceTo(sphere.center);
  return { near: Math.max(0.1, d - sphere.radius * 1.05), far: d + sphere.radius * 1.05 };
}

export function HeroCapture() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as { target?: THREE.Vector3 } | null;
  const invalidate = useThree((s) => s.invalidate);
  const setHeroCaptureFn = useStore((s) => s.setHeroCaptureFn);

  useEffect(() => {
    const fn = async (cfg: { maxEdge: number }): Promise<HeroCaptureData | null> => {
      const persp = camera as THREE.PerspectiveCamera;
      if (!persp.isPerspectiveCamera) return null;

      const cw = gl.domElement.width;
      const ch = gl.domElement.height;
      if (cw < 2 || ch < 2) return null;
      // Cap the long edge to maxEdge, then round both dims to /16 (FLUX VAE).
      const maxEdge = Math.max(16, cfg.maxEdge | 0);
      const longEdge = Math.max(cw, ch);
      const s = longEdge > maxEdge ? maxEdge / longEdge : 1;
      const W = round16(cw * s);
      const H = round16(ch * s);

      // ---- 1) BEAUTY — read the on-screen composited frame FIRST, downscale to (W,H). ----
      let beautyBlob = await new Promise<Blob | null>((res) =>
        gl.domElement.toBlob((b) => res(b), "image/png"),
      );
      if (!beautyBlob || beautyBlob.size < 64) {
        await raf();
        beautyBlob = await new Promise<Blob | null>((res) => gl.domElement.toBlob((b) => res(b), "image/png"));
      }
      if (!beautyBlob) return null;
      const bmp = await createImageBitmap(beautyBlob);
      const bc = makeCanvas(W, H);
      const bctx = bc.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null;
      if (!bctx) {
        bmp.close();
        return null;
      }
      bctx.drawImage(bmp, 0, 0, W, H);
      bmp.close();
      const beauty = await canvasToB64(bc);

      // ---- shared RGBA8 render target for depth + ids. NoColorSpace so the bytes
      //      we read back are exactly what the shader/material wrote (no encoding). ----
      const rt = new THREE.WebGLRenderTarget(W, H, {
        minFilter: THREE.NearestFilter,
        magFilter: THREE.NearestFilter,
        format: THREE.RGBAFormat,
        type: THREE.UnsignedByteType,
        colorSpace: THREE.NoColorSpace,
        depthBuffer: true,
        stencilBuffer: false,
      });

      // Snapshot all renderer/scene/global state we touch.
      const prevTarget = gl.getRenderTarget();
      const prevOverride = scene.overrideMaterial;
      const prevAutoClear = gl.autoClear;
      const prevClearColor = new THREE.Color();
      gl.getClearColor(prevClearColor);
      const prevClearAlpha = gl.getClearAlpha();
      const prevColorMgmt = THREE.ColorManagement.enabled;

      const tempMaterials: THREE.Material[] = [];
      let depth = "";
      let idsRgb = "";
      const regions: Record<string, { semantic: string }> = {};

      try {
        gl.autoClear = true;
        gl.setClearColor(0x000000, 1);

        // ---- 2) DEPTH — linear eye-space, near=white, fit to the building range. ----
        const range = buildingDepthRange(useStore.getState().meshesBySemantic, persp);
        DEPTH_MATERIAL.uniforms.uNear.value = range.near;
        DEPTH_MATERIAL.uniforms.uFar.value = range.far;
        scene.overrideMaterial = DEPTH_MATERIAL;
        gl.setRenderTarget(rt);
        gl.clear(true, true, true);
        gl.render(scene, persp);
        depth = await rtToPngB64(gl, rt, W, H);
        scene.overrideMaterial = prevOverride;

        // ---- 3) IDS — one flat color PER SEMANTIC (12 ids, not per-mesh). The
        //      id-edges then fall on architectural element boundaries (window/wall/
        //      roof/trim) — exactly the lines the canny lock needs — instead of noisy
        //      mesh-vs-mesh seams within one element. Byte-exact via ColorManagement
        //      OFF + the NoColorSpace target. CRITICAL: hide every NON-painted
        //      renderable (sky dome, entourage) first, else they fill the background
        //      with their real materials and corrupt the id bytes. ----
        THREE.ColorManagement.enabled = false;
        const meshesBySemantic = useStore.getState().meshesBySemantic;
        const swapped: Array<{ mesh: THREE.Mesh; mat: THREE.Material | THREE.Material[] }> = [];
        const painted = new Set<THREE.Object3D>();
        let id = 1; // 0 reserved for background
        meshesBySemantic.forEach((meshes, semantic) => {
          const thisId = id++;
          regions[String(thisId)] = { semantic };
          const col = new THREE.Color();
          col.setRGB((thisId & 0xff) / 255, ((thisId >> 8) & 0xff) / 255, 0);
          const idMat = new THREE.MeshBasicMaterial({ color: col, toneMapped: false, side: THREE.DoubleSide, fog: false });
          tempMaterials.push(idMat);
          meshes.forEach((mesh) => {
            swapped.push({ mesh, mat: mesh.material });
            mesh.material = idMat;
            painted.add(mesh);
          });
        });
        // Keep painted meshes + their ancestors; hide every other renderable.
        const keep = new Set<THREE.Object3D>();
        painted.forEach((m) => {
          let n: THREE.Object3D | null = m;
          while (n) {
            keep.add(n);
            n = n.parent;
          }
        });
        const hidden: THREE.Object3D[] = [];
        scene.traverse((o) => {
          const r = (o as THREE.Mesh).isMesh || (o as THREE.InstancedMesh).isInstancedMesh || (o as THREE.Points).isPoints || (o as THREE.Line).isLine || (o as THREE.Sprite).isSprite;
          if (r && o.visible && !keep.has(o)) {
            hidden.push(o);
            o.visible = false;
          }
        });
        try {
          gl.setRenderTarget(rt);
          gl.setClearColor(0x000000, 1); // id 0 = background
          gl.clear(true, true, true);
          gl.render(scene, persp);
          idsRgb = await rtToPngB64(gl, rt, W, H);
        } finally {
          for (const o of hidden) o.visible = true;
          for (const sw of swapped) sw.mesh.material = sw.mat;
        }
      } finally {
        // ---- restore EVERYTHING ----
        scene.overrideMaterial = prevOverride;
        gl.setRenderTarget(prevTarget);
        gl.setClearColor(prevClearColor, prevClearAlpha);
        gl.autoClear = prevAutoClear;
        THREE.ColorManagement.enabled = prevColorMgmt;
        for (const m of tempMaterials) m.dispose();
        rt.dispose();
      }

      // ---- 4) CAMERA pose (real OrbitControls target if available). ----
      const pos: [number, number, number] = [persp.position.x, persp.position.y, persp.position.z];
      let target: [number, number, number];
      if (controls && controls.target) {
        target = [controls.target.x, controls.target.y, controls.target.z];
      } else {
        const dir = new THREE.Vector3();
        persp.getWorldDirection(dir).multiplyScalar(100).add(persp.position);
        target = [dir.x, dir.y, dir.z];
      }

      // Refresh the on-screen frame (demand-mode stages won't auto-redraw otherwise).
      invalidate();

      return { width: W, height: H, beauty, depth, idsRgb, regions, camera: { pos, target, fov: persp.fov } };
    };

    setHeroCaptureFn(fn);
    return () => setHeroCaptureFn(null);
  }, [gl, scene, camera, controls, invalidate, setHeroCaptureFn]);

  return null;
}
