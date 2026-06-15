import * as THREE from "three";

/**
 * Reproject-from-3D — the consistency engine for the multi-view hero (approach "C").
 *
 * Problem: rendering each orbit angle with an INDEPENDENT FLUX pass gives inconsistent
 * lighting/materials (proven: experiments A + B). Fix: render the hero ONCE, then use the
 * REAL 3D geometry (which is exactly consistent from every angle) to carry the hero's
 * photoreal pixels to the other views — so materials + lighting are identical BY
 * CONSTRUCTION. Only the regions the hero camera couldn't see (disocclusions) are gaps,
 * which a light FLUX inpaint fills (via the existing /region_edit endpoint, mask = gaps).
 *
 * Technique: projective texture mapping with shadow-map occlusion.
 *   1. Render a LINEAR eye-depth map of the building FROM the hero camera (heroDepthRT).
 *   2. Render the building FROM each target camera with a projective shader: each fragment
 *      projects its world position into the hero camera, and IF it is the surface the hero
 *      actually saw (its eye-distance-from-hero matches heroDepthRT within a bias) it samples
 *      the hero image; otherwise it is a gap (alpha = 0).
 *   3. Read back → reprojected RGB + a gap mask (white = gap to inpaint).
 *
 * Everything here is engine-side (free, exact). The output feeds /region_edit for the gaps.
 */

export type ReprojPose = { pos: [number, number, number]; target: [number, number, number]; fov: number };
export type ReprojectedView = {
  reproj: string; // bare b64 PNG — hero pixels reprojected to this view (gaps = black)
  gapMask: string; // bare b64 PNG (L) — WHITE where the hero couldn't see (to inpaint)
  coverage: number; // fraction of building pixels covered by the hero (0..1)
  width: number;
  height: number;
};

const round16 = (n: number) => Math.max(16, Math.floor(n / 16) * 16);

function makePerspective(pose: ReprojPose, aspect: number, near: number, far: number): THREE.PerspectiveCamera {
  const cam = new THREE.PerspectiveCamera(pose.fov, aspect, near, far);
  cam.position.set(...pose.pos);
  cam.up.set(0, 1, 0);
  cam.lookAt(new THREE.Vector3(...pose.target));
  cam.updateMatrixWorld(true);
  cam.updateProjectionMatrix();
  return cam;
}

// Linear eye-depth (distance from the rendering camera), written to a float target's .r.
const HERO_DEPTH_MATERIAL = new THREE.ShaderMaterial({
  vertexShader: /* glsl */ `
    varying float vEye;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vEye = -mv.z;
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: /* glsl */ `
    varying float vEye;
    void main() { gl_FragColor = vec4(vEye, 0.0, 0.0, 1.0); }`,
  side: THREE.DoubleSide,
});

// Projective material: sample the hero image where this fragment was visible to the hero.
function makeProjectiveMaterial(heroTex: THREE.Texture, heroDepthTex: THREE.Texture): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uHeroTex: { value: heroTex },
      uHeroDepth: { value: heroDepthTex },
      uHeroView: { value: new THREE.Matrix4() }, // hero matrixWorldInverse
      uHeroProj: { value: new THREE.Matrix4() }, // hero projectionMatrix
      uBias: { value: 0.5 }, // eye-distance tolerance (world units); tuned per scene scale
    },
    vertexShader: /* glsl */ `
      varying vec3 vWorld;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorld = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }`,
    fragmentShader: /* glsl */ `
      precision highp float;
      uniform sampler2D uHeroTex;
      uniform sampler2D uHeroDepth;
      uniform mat4 uHeroView;
      uniform mat4 uHeroProj;
      uniform float uBias;
      varying vec3 vWorld;
      void main() {
        vec4 heroEye = uHeroView * vec4(vWorld, 1.0);
        vec4 heroClip = uHeroProj * heroEye;
        if (heroClip.w <= 0.0) { gl_FragColor = vec4(0.0); return; }     // behind hero
        vec3 ndc = heroClip.xyz / heroClip.w;
        vec2 uv = ndc.xy * 0.5 + 0.5;
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) { gl_FragColor = vec4(0.0); return; } // outside hero frame
        float fragEye = -heroEye.z;                                     // this fragment's distance from hero
        float storedEye = texture2D(uHeroDepth, uv).r;                  // closest surface the hero saw there
        if (fragEye > storedEye + uBias) { gl_FragColor = vec4(0.0); return; } // occluded behind something
        vec3 col = texture2D(uHeroTex, vec2(uv.x, 1.0 - uv.y)).rgb;     // hero PNG is top-left origin
        gl_FragColor = vec4(col, 1.0);                                  // alpha 1 = valid (hero pixel)
      }`,
    side: THREE.DoubleSide,
  });
}

/** Building bounding sphere (for camera near/far + bias scale). */
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

async function rtToPngB64(gl: THREE.WebGLRenderer, rt: THREE.WebGLRenderTarget, w: number, h: number, alphaToMask: boolean): Promise<{ rgb: string; mask: string; coverage: number }> {
  const buf = new Uint8Array(w * h * 4);
  gl.readRenderTargetPixels(rt, 0, 0, w, h, buf);
  const rgb = new Uint8ClampedArray(w * h * 4);
  const mask = new Uint8ClampedArray(w * h * 4);
  const rb = w * 4;
  let valid = 0;
  for (let y = 0; y < h; y++) {
    const src = (h - 1 - y) * rb; // GL bottom-up → top-down
    const dst = y * rb;
    for (let x = 0; x < w; x++) {
      const s = src + x * 4;
      const d = dst + x * 4;
      const a = buf[s + 3];
      rgb[d] = buf[s]; rgb[d + 1] = buf[s + 1]; rgb[d + 2] = buf[s + 2]; rgb[d + 3] = 255;
      // gap mask: WHITE where NOT covered (alpha 0). Only meaningful over the building;
      // background stays 0 (we don't inpaint sky).
      const gap = a < 128 ? 255 : 0;
      mask[d] = gap; mask[d + 1] = gap; mask[d + 2] = gap; mask[d + 3] = 255;
      if (a >= 128) valid++;
    }
  }
  const toB64 = async (arr: Uint8ClampedArray) => {
    const c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(w, h) : Object.assign(document.createElement("canvas"), { width: w, height: h });
    const ctx = (c as HTMLCanvasElement).getContext("2d")!;
    ctx.putImageData(new ImageData(new Uint8ClampedArray(arr), w, h), 0, 0);
    const blob = c instanceof OffscreenCanvas ? await c.convertToBlob({ type: "image/png" }) : await new Promise<Blob>((res) => (c as HTMLCanvasElement).toBlob((b) => res(b!), "image/png"));
    const dataUrl = await new Promise<string>((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result as string); fr.readAsDataURL(blob); });
    return dataUrl.slice(dataUrl.indexOf(",") + 1);
  };
  return { rgb: await toB64(rgb), mask: await toB64(mask), coverage: valid / (w * h) };
}

/**
 * Reproject a hero render (taken from heroPose) onto the building, as seen from each
 * targetPose. Returns one ReprojectedView per target (hero pixels + gap mask + coverage).
 * Only the building meshes (meshesBySemantic) are reprojected; everything else is hidden.
 */
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
  const w = round16(W), h = round16(H);
  const sphere = buildingSphere(meshesBySemantic);
  const near = Math.max(0.05, sphere.radius * 0.05);
  const far = sphere.radius * 20 + 10;
  const aspect = w / h;

  // hero image → texture
  const heroTex = await new Promise<THREE.Texture>((res, rej) => {
    new THREE.TextureLoader().load(
      `data:image/png;base64,${heroImageB64}`,
      (t) => { t.colorSpace = THREE.SRGBColorSpace; t.needsUpdate = true; res(t); },
      undefined,
      () => rej(new Error("hero texture load failed")),
    );
  });

  const heroCam = makePerspective(heroPose, aspect, near, far);

  // 1) hero eye-depth (float RT)
  const heroDepthRT = new THREE.WebGLRenderTarget(w, h, {
    minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
    format: THREE.RGBAFormat, type: THREE.FloatType, depthBuffer: true,
  });
  const projMat = makeProjectiveMaterial(heroTex, heroDepthRT.texture);
  projMat.uniforms.uBias.value = Math.max(0.1, sphere.radius * 0.02);

  // hide all non-building renderables (sky/entourage) for both depth + projective passes
  const building = new Set<THREE.Object3D>();
  meshesBySemantic.forEach((ms) => ms.forEach((m) => building.add(m)));
  const keep = new Set<THREE.Object3D>();
  building.forEach((m) => { let n: THREE.Object3D | null = m; while (n) { keep.add(n); n = n.parent; } });

  // snapshot renderer state
  const prevTarget = gl.getRenderTarget();
  const prevOverride = scene.overrideMaterial;
  const prevClear = new THREE.Color(); gl.getClearColor(prevClear);
  const prevAlpha = gl.getClearAlpha();
  const prevAutoClear = gl.autoClear;
  const hidden: THREE.Object3D[] = [];

  const out: ReprojectedView[] = [];
  try {
    scene.traverse((o) => {
      const r = (o as THREE.Mesh).isMesh || (o as THREE.InstancedMesh).isInstancedMesh || (o as THREE.Points).isPoints || (o as THREE.Line).isLine || (o as THREE.Sprite).isSprite;
      if (r && o.visible && !keep.has(o)) { hidden.push(o); o.visible = false; }
    });
    gl.autoClear = true;

    // hero depth pass
    scene.overrideMaterial = HERO_DEPTH_MATERIAL;
    gl.setRenderTarget(heroDepthRT);
    gl.setClearColor(0x000000, 1);
    gl.clear(true, true, true);
    gl.render(scene, heroCam);

    // projective pass per target
    projMat.uniforms.uHeroView.value.copy(heroCam.matrixWorldInverse);
    projMat.uniforms.uHeroProj.value.copy(heroCam.projectionMatrix);
    scene.overrideMaterial = projMat;

    const outRT = new THREE.WebGLRenderTarget(w, h, {
      minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
      format: THREE.RGBAFormat, type: THREE.UnsignedByteType, colorSpace: THREE.SRGBColorSpace, depthBuffer: true,
    });
    try {
      for (const tp of targetPoses) {
        const tcam = makePerspective(tp, aspect, near, far);
        gl.setRenderTarget(outRT);
        gl.setClearColor(0x000000, 0); // transparent → gaps where nothing renders
        gl.clear(true, true, true);
        gl.render(scene, tcam);
        const { rgb, mask, coverage } = await rtToPngB64(gl, outRT, w, h, true);
        out.push({ reproj: rgb, gapMask: mask, coverage, width: w, height: h });
      }
    } finally {
      outRT.dispose();
    }
  } finally {
    for (const o of hidden) o.visible = true;
    scene.overrideMaterial = prevOverride;
    gl.setRenderTarget(prevTarget);
    gl.setClearColor(prevClear, prevAlpha);
    gl.autoClear = prevAutoClear;
    heroDepthRT.dispose();
    heroTex.dispose();
    projMat.dispose();
  }
  return out;
}
