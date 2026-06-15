import * as THREE from "three";
import { useStore } from "../state/store";

/**
 * "Convert our scene → splat": orbit the camera through N posed views, render each
 * (raw lit scene, NO screen-space post so the views are mutually consistent), and
 * build a nerfstudio `transforms.json`. three.js is -Z-forward == OpenGL/nerfstudio,
 * so `camera.matrixWorld` IS the camera-to-world transform (transposed to row-major
 * for the JSON). POST the images + transforms to the Modal `splat_bake` endpoint,
 * poll for the trained `.ply`, and return its object URL for SplatContext to load.
 *
 * Modal `splat_bake` contract (see spike/modal_splat.py):
 *   POST  { secret, transforms: <nerfstudio json>, images: [{name, b64(jpeg)}], iterations? }
 *   200   { ply_b64 }  |  { ply_url }  |  { job_id }   (job_id → poll `${bakeUrl}?job=<id>`)
 */

export type SplatBakeOptions = {
  bakeUrl: string;
  secret: string;
  azimuthSteps?: number; // default 14
  elevationSteps?: number; // default 3
  maxEdge?: number; // capture resolution cap (default 1024)
  iterations?: number; // training iters (default 20000)
  onProgress?: (msg: string) => void;
};

// ---- bake-context registry: SplatContext (inside the Canvas) registers the live
//      renderer/scene/camera; SplatPanel (a DOM panel) calls requestBake(). --------
type BakeCtx = { gl: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera };
let _ctx: BakeCtx | null = null;
export function setBakeContext(ctx: BakeCtx | null) {
  _ctx = ctx;
}
export async function requestBake(opts: SplatBakeOptions): Promise<string | null> {
  if (!_ctx) throw new Error("Open a WebGL2 / + GI render mode first — the baker needs the live renderer.");
  return bakeSceneToSplat(_ctx.gl, _ctx.scene, _ctx.camera, opts);
}

function buildingSphere(meshesBySemantic: Map<string, THREE.Mesh[]>): THREE.Sphere {
  const box = new THREE.Box3();
  const tmp = new THREE.Box3();
  meshesBySemantic.forEach((meshes) =>
    meshes.forEach((m) => {
      if (!m.geometry) return;
      if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
      if (m.geometry.boundingBox) box.union(tmp.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld));
    }),
  );
  const sphere = new THREE.Sphere();
  if (box.isEmpty()) sphere.set(new THREE.Vector3(), 100);
  else box.getBoundingSphere(sphere);
  return sphere;
}

/** three.js matrixWorld (column-major elements) → row-major nested 4x4 for nerfstudio. */
function toRowMajor(m: THREE.Matrix4): number[][] {
  const e = m.elements;
  return [
    [e[0], e[4], e[8], e[12]],
    [e[1], e[5], e[9], e[13]],
    [e[2], e[6], e[10], e[14]],
    [e[3], e[7], e[11], e[15]],
  ];
}

export async function bakeSceneToSplat(
  gl: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  opts: SplatBakeOptions,
): Promise<string | null> {
  const log = opts.onProgress ?? (() => {});
  const azN = opts.azimuthSteps ?? 14;
  const elN = opts.elevationSteps ?? 3;
  const maxEdge = opts.maxEdge ?? 1024;

  const sphere = buildingSphere(useStore.getState().meshesBySemantic);
  const center = sphere.center;
  const dist = sphere.radius * 2.3; // framing distance

  // Render resolution (square-ish, capped, /2 rounded for cleanliness).
  const aspect = gl.domElement.width / Math.max(1, gl.domElement.height);
  const H = Math.min(maxEdge, 1024);
  const W = Math.round(H * aspect);
  const fovDeg = camera.fov;
  const f = H / 2 / Math.tan(THREE.MathUtils.degToRad(fovDeg) / 2);

  const rt = new THREE.WebGLRenderTarget(W, H, {
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    format: THREE.RGBAFormat,
    type: THREE.UnsignedByteType,
    colorSpace: THREE.SRGBColorSpace, // training images are display-referred sRGB
    depthBuffer: true,
  });

  // Snapshot camera + renderer state.
  const prevPos = camera.position.clone();
  const prevQuat = camera.quaternion.clone();
  const prevAspect = camera.aspect;
  const prevTarget = gl.getRenderTarget();
  const prevClear = new THREE.Color();
  gl.getClearColor(prevClear);
  const prevAlpha = gl.getClearAlpha();

  const frames: { file_path: string; transform_matrix: number[][] }[] = [];
  const images: { name: string; b64: string }[] = [];

  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = W;
  tmpCanvas.height = H;
  const tctx = tmpCanvas.getContext("2d")!;
  const buf = new Uint8Array(W * H * 4);

  try {
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    // Sky-blue clear so the background reads as sky (helps training vs pure black).
    gl.setClearColor(0x8fb4e0, 1);

    let i = 0;
    for (let e = 0; e < elN; e++) {
      // Elevations from ~12° to ~55° above horizon.
      const elev = THREE.MathUtils.degToRad(12 + (43 * e) / Math.max(1, elN - 1));
      for (let a = 0; a < azN; a++) {
        const az = (a / azN) * Math.PI * 2;
        const x = center.x + dist * Math.cos(elev) * Math.cos(az);
        const y = center.y + dist * Math.sin(elev);
        const z = center.z + dist * Math.cos(elev) * Math.sin(az);
        camera.position.set(x, y, z);
        camera.lookAt(center);
        camera.updateMatrixWorld(true);

        gl.setRenderTarget(rt);
        gl.clear(true, true, true);
        gl.render(scene, camera);

        gl.readRenderTargetPixels(rt, 0, 0, W, H, buf);
        // Flip GL bottom-up rows → top-down for the image.
        const flipped = new Uint8ClampedArray(W * H * 4);
        const rb = W * 4;
        for (let row = 0; row < H; row++) flipped.set(buf.subarray((H - 1 - row) * rb, (H - 1 - row) * rb + rb), row * rb);
        tctx.putImageData(new ImageData(flipped, W, H), 0, 0);
        const jpeg = tmpCanvas.toDataURL("image/jpeg", 0.9).split(",")[1];

        const name = `r_${String(i).padStart(3, "0")}.jpg`;
        images.push({ name, b64: jpeg });
        frames.push({ file_path: `images/${name}`, transform_matrix: toRowMajor(camera.matrixWorld) });
        i++;
        log(`Rendering view ${i}/${azN * elN}…`);
        // Yield so the UI can paint the progress.
        await new Promise((r) => setTimeout(r, 0));
      }
    }
  } finally {
    // Restore camera + renderer.
    camera.position.copy(prevPos);
    camera.quaternion.copy(prevQuat);
    camera.aspect = prevAspect;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    gl.setRenderTarget(prevTarget);
    gl.setClearColor(prevClear, prevAlpha);
    rt.dispose();
  }

  const transforms = {
    camera_model: "OPENCV",
    fl_x: f,
    fl_y: f,
    cx: W / 2,
    cy: H / 2,
    w: W,
    h: H,
    frames,
  };

  log(`Uploading ${images.length} views + poses to the trainer…`);
  const res = await fetch(opts.bakeUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret: opts.secret, transforms, images, iterations: opts.iterations ?? 20000 }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Auth failed — check the shared secret.");
    if (res.status === 404) throw new Error("splat_bake endpoint not found — deploy spike/modal_splat.py and set its URL.");
    throw new Error(`Trainer error ${res.status}`);
  }
  let data = (await res.json()) as { ply_b64?: string; ply_url?: string; job_id?: string };

  // Async-job polling: re-POST {secret, job_id} until the .ply is ready.
  let polls = 0;
  while (data.job_id && !data.ply_b64 && !data.ply_url && polls < 360) {
    await new Promise((r) => setTimeout(r, 5000));
    polls++;
    log(`Training… (~${Math.round((polls * 5) / 60)} min)`);
    const pr = await fetch(opts.bakeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret: opts.secret, job_id: data.job_id }),
    });
    if (pr.ok) data = await pr.json();
    else if (pr.status === 500) throw new Error("Training failed on the server.");
  }

  if (data.ply_b64) {
    const bin = atob(data.ply_b64);
    const arr = new Uint8Array(bin.length);
    for (let k = 0; k < bin.length; k++) arr[k] = bin.charCodeAt(k);
    log("Splat ready.");
    return URL.createObjectURL(new Blob([arr], { type: "application/octet-stream" }));
  }
  if (data.ply_url) {
    log("Splat ready.");
    return data.ply_url;
  }
  throw new Error("Trainer returned no .ply (timed out or bad response).");
}
