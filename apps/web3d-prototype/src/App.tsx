import { useEffect, lazy, Suspense } from "react";
import { Sidebar } from "./ui/Sidebar";
import { NavBar } from "./ui/NavBar";
import { SkyPanel } from "./ui/SkyPanel";
import { Cinematic } from "./Cinematic";
import { useStore } from "./state/store";

// Lazy-load each Stage so its renderer + post stack is only fetched when selected.
// Critically this keeps `three/webgpu` (a large bundle, pulled in by StageWebGPU)
// out of the WebGL2 users' payload — it loads only when WebGPU mode is chosen.
const StageWebGL2 = lazy(() =>
  import("./stages/StageWebGL2").then((m) => ({ default: m.StageWebGL2 })),
);
const StageWebGL2GI = lazy(() =>
  import("./stages/StageWebGL2GI").then((m) => ({ default: m.StageWebGL2GI })),
);
const StageWebGPU = lazy(() =>
  import("./stages/StageWebGPU").then((m) => ({ default: m.StageWebGPU })),
);

/**
 * The render-mode switch. Each mode is a self-contained Stage owning its own
 * <Canvas> + renderer + post, all rendering the shared <Scene>. The DOM overlays
 * (panels + Cinematic) are renderer-independent and shared across modes.
 */
export default function App() {
  const renderMode = useStore((s) => s.renderMode);

  // Re-apply persisted per-swatch texture scales to the material engine on load.
  useEffect(() => {
    const { swatchScale, setSwatchScale } = useStore.getState();
    Object.entries(swatchScale).forEach(([id, v]) => setSwatchScale(id, v));
  }, []);

  return (
    <div style={{ position: "fixed", inset: 0 }}>
      <Suspense fallback={null}>
        {renderMode === "webgpu" ? (
          <StageWebGPU />
        ) : renderMode === "webgl2gi" ? (
          <StageWebGL2GI />
        ) : (
          <StageWebGL2 />
        )}
      </Suspense>
      <SkyPanel />
      <Sidebar />
      <NavBar />
      <Cinematic />
    </div>
  );
}
