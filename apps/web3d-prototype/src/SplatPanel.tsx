import { useStore } from "./state/store";

/**
 * STUB (Phase 0) — filled by the splat agent.
 *
 * Left/side panel for the Gaussian-splat backdrop: a source toggle (drop-in file vs
 * Modal scene-bake), the splat URL / "Bake this scene" action, and alignment sliders
 * (posY / scale / heading / yaw / exposure) mirroring the GeoTiles seat controls.
 * Only meaningful in WebGL2 / +GI render modes.
 */
export function SplatPanel() {
  const renderMode = useStore((s) => s.renderMode);
  // Splats are WebGL2-only; hide the panel in WebGPU mode.
  if (renderMode === "webgpu") return null;
  return null; // stub — real panel lands next
}
