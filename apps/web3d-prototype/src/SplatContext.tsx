import { useStore } from "./state/store";

/**
 * STUB (Phase 0) — filled by the splat agent.
 *
 * Gaussian-splat "context backdrop". Mounted inside the WebGL2 / +GI Stage <Canvas>
 * (Spark is WebGLRenderer-only — never WebGPU). When `splatEnabled`, loads
 * `splatUrl` (.ply/.spz) via @sparkjsdev/spark, wraps it in an outer group seated on
 * the building (siteAnchor + splatTransform, reusing the GeoTiles strategy), and adds
 * a ShadowMaterial catcher so the SolarSky sun grounds the building on the splat.
 */
export function SplatContext() {
  const enabled = useStore((s) => s.splatEnabled);
  const url = useStore((s) => s.splatUrl);
  if (!enabled || !url) return null;
  return null; // stub — real Spark loader lands next
}
