import * as THREE from "three";

/**
 * Reproject-from-3D — the consistency engine for the multi-view hero (approach "C").
 *
 * Rendering each angle with an INDEPENDENT FLUX pass gives inconsistent lighting/materials
 * (proven: experiments A + B). Fix: use the REAL 3D geometry (exactly consistent from every
 * angle) to carry already-rendered photoreal pixels onto new views — so materials + lighting
 * are identical BY CONSTRUCTION. Only regions no source camera saw (disocclusions) or that are
 * badly stretched (grazing) are gaps, which a light FLUX inpaint fills (via /region_edit).
 *
 * For a full 360° turntable we CHAIN: render view 0 as a full hero, then build each next view
 * by reprojecting its already-rendered NEIGHBOURS (quality-weighted: prefer the source whose
 * camera most squarely faces each surface) and inpainting the rest. Appearance propagates
 * smoothly around the circle.
 *
 * Technique: projective texture mapping with linear-eye-depth shadow-map occlusion + a
 * per-fragment quality = max(0, dot(worldNormal, dirToSourceCamera)). Quality 0 = occluded /
 * outside the source frame / behind / edge-on. Multi-source = keep the highest-quality sample.
 */

export type ReprojPose = { pos: [number, number, number]; target: [number, number, number]; fov: number };
export type ReprojSource = { imageB64: string; pose: ReprojPose };
export type ReprojectedView = {
  reproj: string; // bare b64 PNG — sources' pixels reprojected to this view (gaps = black)
  gapMask: string; // bare b64 PNG (L) — WHITE where no source covered well (to inpaint)
  coverage: number; // fraction of building pixels covered (quality >= threshold)
  width: number;
  height: number;
};

const round16 = (n: number) => Math.max(16, Math.floor(n / 16) * 16);
// A pixel is "covered" if ANY source projected onto it validly (passed occlusion + frustum).
// The grazing-angle quality (dot(normal,dirToSource)) is ONLY used to pick the BEST source
// per pixel when several cover it — NOT to decide gaps (a flat ground at a grazing angle
// reprojects fine; penalising it as a gap wrongly blackens the ground). Valid samples write a
// tiny epsilon quality so they always beat the 0 background. True gaps = disocclusion/frustum.
const QUALITY_GAP = 0.001;

function makePerspective(pose: ReprojPose, aspect: number, near: number, far: number): THREE.PerspectiveCamera {
  const cam = new THREE.PerspectiveCamera(pose.fov, aspect, near, far);
  cam.position.set(...pose.pos);
  cam.up.set(0, 1, 0);
  cam.lookAt(new THREE.Vector3(...pose.target));
  cam.updateMatrixWorld(true);
  cam.updateProjectionMatrix();
  return cam;
}

// Linear eye-depth (distance from the rendering camera) → a float target's .r.
const EYE_DEPTH_MATERIAL = new THREE.ShaderMaterial({
  vertexShader: `varying float vEye; void main(){ vec4 mv=modelViewMatrix*vec4(position,1.0); vEye=-mv.z; gl_Position=projectionMatrix*mv; }`,
  fragmentShader: `varying float vEye; void main(){ gl_FragColor=vec4(vEye,0.0,0.0,1.0); }`,
  side: THREE.DoubleSide,
});

// Projective material: sample the SOURCE image where this fragment was visible to the source
// camera; alpha = quality (grazing-aware). Output to a FLOAT target so we can blend precisely.
function makeProjectiveMaterial(srcTex: THREE.Texture, srcDepthTex: THREE.Texture): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uSrcTex: { value: srcTex },
      uSrcDepth: { value: srcDepthTex },
      uSrcView: { value: new THREE.Matrix4() },
      uSrcProj: { value: new THREE.Matrix4() },
      uSrcPos: { value: new THREE.Vector3() },
      uBias: { value: 0.5 },
    },
    vertexShader: /* glsl */ `
      varying vec3 vWorld;
      varying vec3 vNormal;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorld = wp.xyz;
        vNormal = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */ `
      precision highp float;
      uniform sampler2D uSrcTex; uniform sampler2D uSrcDepth;
      uniform mat4 uSrcView; uniform mat4 uSrcProj; uniform vec3 uSrcPos; uniform float uBias;
      varying vec3 vWorld; varying vec3 vNormal;
      void main() {
        vec4 srcEye = uSrcView * vec4(vWorld, 1.0);
        vec4 srcClip = uSrcProj * srcEye;
        if (srcClip.w <= 0.0) { gl_FragColor = vec4(0.0); return; }
        vec3 ndc = srcClip.xyz / srcClip.w;
        vec2 uv = ndc.xy * 0.5 + 0.5;
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) { gl_FragColor = vec4(0.0); return; }
        float fragEye = -srcEye.z;
        float storedEye = texture2D(uSrcDepth, uv).r;
        if (fragEye > storedEye + uBias) { gl_FragColor = vec4(0.0); return; }   // occluded
        vec3 dirToSrc = normalize(uSrcPos - vWorld);
        float q = max(0.0, dot(normalize(vNormal), dirToSrc));                   // grazing quality (source ranking)
        vec3 col = texture2D(uSrcTex, vec2(uv.x, 1.0 - uv.y)).rgb;               // PNG top-left origin
        gl_FragColor = vec4(col, 0.05 + 0.95 * q);                              // valid sample always > background 0
      }`,
    side: THREE.DoubleSide,
  });
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
  const s = new THREE.Sphere();
  box.isEmpty() ? s.set(new THREE.Vector3(), 100) : box.getBoundingSphere(s);
  return s;
}

function texFromB64(b64: string): Promise<THREE.Texture> {
  return new Promise((res, rej) =>
    new THREE.TextureLoader().load(
      `data:image/png;base64,${b64}`,
      (t) => { t.colorSpace = THREE.SRGBColorSpace; t.needsUpdate = true; res(t); },
      undefined,
      () => rej(new Error("texture load failed")),
    ),
  );
}

async function pngB64(arr: Uint8ClampedArray, w: number, h: number): Promise<string> {
  const c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(w, h) : Object.assign(document.createElement("canvas"), { width: w, height: h });
  const ctx = (c as HTMLCanvasElement).getContext("2d")!;
  ctx.putImageData(new ImageData(new Uint8ClampedArray(arr), w, h), 0, 0);
  const blob = c instanceof OffscreenCanvas ? await c.convertToBlob({ type: "image/png" }) : await new Promise<Blob>((r) => (c as HTMLCanvasElement).toBlob((b) => r(b!), "image/png"));
  const url = await new Promise<string>((r) => { const fr = new FileReader(); fr.onload = () => r(fr.result as string); fr.readAsDataURL(blob); });
  return url.slice(url.indexOf(",") + 1);
}

/**
 * Reproject one or more SOURCE renders (each from its own pose) onto `targetPose`, keeping the
 * highest-quality sample per pixel. Returns the blended reprojection + a gap mask (white where
 * no source covered well) + coverage. Engine-side, exact. The output feeds /region_edit for gaps.
 */
export async function reprojectSourcesToTarget(
  gl: THREE.WebGLRenderer,
  scene: THREE.Scene,
  meshesBySemantic: Map<string, THREE.Mesh[]>,
  sources: ReprojSource[],
  targetPose: ReprojPose,
  W: number,
  H: number,
): Promise<ReprojectedView> {
  const w = round16(W), h = round16(H);
  const sphere = buildingSphere(meshesBySemantic);
  const near = Math.max(0.05, sphere.radius * 0.05);
  const far = sphere.radius * 20 + 10;
  const aspect = w / h;
  const bias = Math.max(0.1, sphere.radius * 0.02);

  // hide non-building renderables
  const building = new Set<THREE.Object3D>();
  meshesBySemantic.forEach((ms) => ms.forEach((m) => building.add(m)));
  const keep = new Set<THREE.Object3D>();
  building.forEach((m) => { let n: THREE.Object3D | null = m; while (n) { keep.add(n); n = n.parent; } });

  const prevTarget = gl.getRenderTarget();
  const prevOverride = scene.overrideMaterial;
  const prevClear = new THREE.Color(); gl.getClearColor(prevClear);
  const prevAlpha = gl.getClearAlpha();
  const prevAutoClear = gl.autoClear;
  const hidden: THREE.Object3D[] = [];

  const depthRT = new THREE.WebGLRenderTarget(w, h, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, format: THREE.RGBAFormat, type: THREE.FloatType, depthBuffer: true });
  const outRT = new THREE.WebGLRenderTarget(w, h, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, format: THREE.RGBAFormat, type: THREE.FloatType, depthBuffer: true });
  const targetCam = makePerspective(targetPose, aspect, near, far);
  const best = new Float32Array(w * h * 4); // rgb (0..1) + best quality in .a
  const textures: THREE.Texture[] = [];

  try {
    scene.traverse((o) => {
      const r = (o as THREE.Mesh).isMesh || (o as THREE.InstancedMesh).isInstancedMesh || (o as THREE.Points).isPoints || (o as THREE.Line).isLine || (o as THREE.Sprite).isSprite;
      if (r && o.visible && !keep.has(o)) { hidden.push(o); o.visible = false; }
    });
    gl.autoClear = true;
    const fbuf = new Float32Array(w * h * 4);

    for (const src of sources) {
      const tex = await texFromB64(src.imageB64);
      textures.push(tex);
      const srcCam = makePerspective(src.pose, aspect, near, far);
      // source eye-depth
      scene.overrideMaterial = EYE_DEPTH_MATERIAL;
      gl.setRenderTarget(depthRT); gl.setClearColor(0x000000, 1); gl.clear(true, true, true);
      gl.render(scene, srcCam);
      // projective pass from the TARGET camera
      const pm = makeProjectiveMaterial(tex, depthRT.texture);
      pm.uniforms.uSrcView.value.copy(srcCam.matrixWorldInverse);
      pm.uniforms.uSrcProj.value.copy(srcCam.projectionMatrix);
      pm.uniforms.uSrcPos.value.copy(srcCam.position);
      pm.uniforms.uBias.value = bias;
      scene.overrideMaterial = pm;
      gl.setRenderTarget(outRT); gl.setClearColor(0x000000, 0); gl.clear(true, true, true);
      gl.render(scene, targetCam);
      gl.readRenderTargetPixels(outRT, 0, 0, w, h, fbuf);
      pm.dispose();
      // keep the highest-quality sample per pixel
      for (let i = 0; i < w * h; i++) {
        const a = fbuf[i * 4 + 3];
        if (a > best[i * 4 + 3]) {
          best[i * 4] = fbuf[i * 4]; best[i * 4 + 1] = fbuf[i * 4 + 1]; best[i * 4 + 2] = fbuf[i * 4 + 2]; best[i * 4 + 3] = a;
        }
      }
    }
  } finally {
    for (const o of hidden) o.visible = true;
    scene.overrideMaterial = prevOverride;
    gl.setRenderTarget(prevTarget);
    gl.setClearColor(prevClear, prevAlpha);
    gl.autoClear = prevAutoClear;
    depthRT.dispose(); outRT.dispose();
    textures.forEach((t) => t.dispose());
  }

  // float buffer (GL bottom-up) → top-down 8-bit RGB + gap mask
  const rgb = new Uint8ClampedArray(w * h * 4);
  const mask = new Uint8ClampedArray(w * h * 4);
  let covered = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const si = ((h - 1 - y) * w + x) * 4;
      const di = (y * w + x) * 4;
      const q = best[si + 3];
      const ok = q >= QUALITY_GAP;
      rgb[di] = ok ? Math.round(best[si] * 255) : 0;
      rgb[di + 1] = ok ? Math.round(best[si + 1] * 255) : 0;
      rgb[di + 2] = ok ? Math.round(best[si + 2] * 255) : 0;
      rgb[di + 3] = 255;
      const gap = ok ? 0 : 255;
      mask[di] = gap; mask[di + 1] = gap; mask[di + 2] = gap; mask[di + 3] = 255;
      if (ok) covered++;
    }
  }
  return { reproj: await pngB64(rgb, w, h), gapMask: await pngB64(mask, w, h), coverage: covered / (w * h), width: w, height: h };
}

/** Convenience: reproject ONE hero to many targets (used by the DEV debug hook). */
export async function reprojectHeroToViews(
  gl: THREE.WebGLRenderer,
  scene: THREE.Scene,
  meshesBySemantic: Map<string, THREE.Mesh[]>,
  heroImageB64: string,
  heroPose: ReprojPose,
  targetPoses: ReprojPose[],
  W: number,
  H: number,
): Promise<ReprojectedView[]> {
  const out: ReprojectedView[] = [];
  for (const tp of targetPoses) {
    out.push(await reprojectSourcesToTarget(gl, scene, meshesBySemantic, [{ imageB64: heroImageB64, pose: heroPose }], tp, W, H));
  }
  return out;
}
