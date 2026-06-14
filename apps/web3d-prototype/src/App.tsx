import { useEffect, lazy, Suspense } from "react";
import { Sidebar } from "./ui/Sidebar";
import { NavBar } from "./ui/NavBar";
import { SkyPanel } from "./ui/SkyPanel";
import { Cinematic } from "./Cinematic";
import { useStore } from "./state/store";

// All three stages are code-split with React.lazy. The key win is StageWebGPU,
// which pulls `three/webgpu` + the TSL display addons (~900 kB) and runs
// extend(three/webgpu) at module load — lazy-loading it keeps every WebGL2-only
// user's initial payload free of it (it fetches only when WebGPU mode is selected).
//
// StageWebGL2 is ALSO lazy on purpose: it transitively imports the shared <Scene>
// (~576 kB) + WebGL `three`, so eager-importing it would fold all of that into the
// main chunk (measured: main 1.1 MB → 2.0 MB). Keeping it lazy lets the main chunk
// stay lean so the UI panels (rendered outside <Suspense>) paint immediately; the
// canvas is async regardless because the 6.5 MB model GLB dominates, so the tiny
// stage-chunk hop is negligible and the fallback covers it.
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
 * (panels + Cinematic) are renderer-independent, shared across modes, and render
 * outside the Suspense boundary so they're up while a stage chunk downloads.
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
      {/* Boundary for the lazily-loaded stage chunk (and the stage's own internal
          <Scene> Suspense nests under this). The fallback keeps the viewport from
          going blank on first load / mode switch; the side panels stay up. */}
      <Suspense fallback={<StageLoading />}>
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

/** Shown while a stage chunk / the model is downloading. */
function StageLoading() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "grid",
        placeItems: "center",
        color: "#6b7280",
        font: "13px ui-sans-serif, system-ui",
        letterSpacing: "0.02em",
      }}
    >
      Loading renderer…
    </div>
  );
}
