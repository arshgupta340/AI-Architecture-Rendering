import type * as THREE from "three";

/**
 * STUB (Phase 0) — filled by the splat agent.
 *
 * "Convert our scene → splat": orbit the camera through N posed views, render each,
 * and build a nerfstudio transforms.json (three.js -Z forward == OpenGL, so the
 * camera.matrixWorld maps directly; fl_y = h/(2·tan(vFOV/2)), fl_x = fl_y·aspect,
 * cx=w/2, cy=h/2). POST the images + transforms.json to the Modal `splat_bake`
 * endpoint, poll for the trained .ply, and return its object URL for SplatContext.
 */
export type SplatBakeOptions = {
  bakeUrl: string;
  secret: string;
  azimuthSteps?: number; // default ~14
  elevationSteps?: number; // default ~3
  maxEdge?: number; // capture resolution cap
  onProgress?: (msg: string) => void;
};

export async function bakeSceneToSplat(
  _gl: THREE.WebGLRenderer,
  _scene: THREE.Scene,
  _camera: THREE.PerspectiveCamera,
  _opts: SplatBakeOptions,
): Promise<string | null> {
  // Stub — render-to-splat pipeline lands in Track A phase 2.
  return null;
}
