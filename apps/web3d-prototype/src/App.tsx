import { useEffect } from "react";
import { StageWebGL2 } from "./stages/StageWebGL2";
import { StageWebGL2GI } from "./stages/StageWebGL2GI";
import { StageWebGPU } from "./stages/StageWebGPU";
import { Sidebar } from "./ui/Sidebar";
import { NavBar } from "./ui/NavBar";
import { SkyPanel } from "./ui/SkyPanel";
import { Cinematic } from "./Cinematic";
import { useStore } from "./state/store";

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
      {renderMode === "webgpu" ? (
        <StageWebGPU />
      ) : renderMode === "webgl2gi" ? (
        <StageWebGL2GI />
      ) : (
        <StageWebGL2 />
      )}
      <SkyPanel />
      <Sidebar />
      <NavBar />
      <Cinematic />
    </div>
  );
}
