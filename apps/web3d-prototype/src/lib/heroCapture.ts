import { useEffect } from "react";
import { useStore, type HeroCaptureData } from "../state/store";

/**
 * STUB (Phase 0) — filled by the hero-capture agent.
 *
 * Mounted inside the WebGL2 / +GI Stage <Canvas> (NOT WebGPU). Registers a 4-pass
 * capture fn on the store that produces a {@link HeroCaptureData} bundle:
 *   - beauty   : post-processed frame (preserveDrawingBuffer toBlob)
 *   - depth    : MeshDepthMaterial(BasicDepthPacking) → WebGLRenderTarget readback
 *   - idsRgb   : per-mesh flat MeshBasicMaterial color r=id&0xff,g=(id>>8)&0xff,b=0
 *   - canny    : NOT here — server computes Canny ∪ id-edges from beauty+idsRgb
 * plus a `regions` map {id:{semantic}} and the camera pose. Must snapshot+restore
 * every material/overrideMaterial it touches so the live scene is unchanged.
 */
export function HeroCapture() {
  const setHeroCaptureFn = useStore((s) => s.setHeroCaptureFn);
  useEffect(() => {
    // Stub: capture not implemented yet → NavBar shows the "not ready" path.
    setHeroCaptureFn(async (_cfg: { maxEdge: number }): Promise<HeroCaptureData | null> => null);
    return () => setHeroCaptureFn(null);
  }, [setHeroCaptureFn]);
  return null;
}
