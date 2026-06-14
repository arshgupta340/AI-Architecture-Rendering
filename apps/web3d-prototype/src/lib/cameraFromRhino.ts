import * as THREE from "three";

/** camera.json produced by spike/rhino_export_gltf.py (mirrors rhino_capture). */
export type RhinoCam = {
  location: [number, number, number];
  target: [number, number, number];
  up: [number, number, number];
  lens_35mm: number;
  frustum_raw: number[]; // [ok, left, right, bottom, top, near, far]
  size_px: [number, number];
  projection: string;
};

/**
 * Rhino is Z-up; we export the GLB with MapZToY=True (a -90deg rotation about X),
 * so geometry is Y-up. Map the camera coords the same way: (x, y, z) -> (x, z, -y).
 */
const zUpToY = (p: number[]): [number, number, number] => [p[0], p[2], -p[1]];

/**
 * Point a three.js PerspectiveCamera at the exact Rhino view. Vertical FOV comes
 * from the frustum (fovY = 2*atan(top/near)); near/far are widened so distant
 * site geometry never clips. Returns the (Y-up) look-at target for OrbitControls.
 */
export function applyRhinoCamera(
  camera: THREE.PerspectiveCamera,
  cam: RhinoCam,
  aspect: number,
): THREE.Vector3 {
  const fr = cam.frustum_raw; // [ok, l, r, b, t, n, f]
  const near = fr[5];
  const top = fr[4];
  const fovY = THREE.MathUtils.radToDeg(2 * Math.atan(top / near));

  camera.fov = fovY;
  camera.aspect = aspect;
  camera.near = 0.1;
  camera.far = 8000;

  const pos = zUpToY(cam.location);
  const tgt = zUpToY(cam.target);
  camera.position.set(pos[0], pos[1], pos[2]);
  camera.up.set(0, 1, 0);
  camera.lookAt(tgt[0], tgt[1], tgt[2]);
  camera.updateProjectionMatrix();

  return new THREE.Vector3(tgt[0], tgt[1], tgt[2]);
}
