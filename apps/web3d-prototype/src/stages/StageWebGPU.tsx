import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { Scene } from "../Scene";
import { Effects } from "../Effects";
import { useStore } from "../state/store";

/**
 * RENDER MODE "webgpu" — OWNED BY AGENT A. REPLACE this whole file with a real
 * three.js WebGPU implementation. This placeholder renders the scene via the
 * WebGL2 path so the mode is never broken before you build it.
 *
 * Target implementation:
 *   import * as THREE from "three/webgpu";
 *   import { extend } from "@react-three/fiber";  // extend(THREE) for WebGPU node els
 *   <Canvas
 *     gl={async (props) => { const r = new THREE.WebGPURenderer({ ...props, antialias: false });
 *                            await r.init(); r.toneMapping = THREE.NoToneMapping; return r; }}>
 *   then drive post via three's native PostProcessing node graph in a useFrame(...,1):
 *     pass(scene,camera) MRT(output/depth/normal) → ao()/GTAONode → ssgi()/SSGINode
 *     → TRAANode (also denoises SSGI) → bloom() → AgX output. Add RectAreaLight area lights.
 * Boundaries: edit ONLY this file + NEW files you create (prefix WebGPU*). Do NOT edit
 *   StageWebGL2/StageWebGL2GI/Scene.tsx/Effects.tsx/App.tsx. MeshStandardMaterial +
 *   drei Sky/Environment/OrbitControls work on WebGPU; shadows="variance" should too —
 *   verify and replace any helper that doesn't. Keep camera/scene/sun identical to
 *   StageWebGL2 so the 3-way comparison is fair.
 * NOTE: WebGPU only renders on a real GPU — the headless preview has navigator.gpu but
 *   no adapter (renders black). Verify build+typecheck+no-fatal-init-errors; the main
 *   agent does the visual confirmation on the user's RTX.
 */
export function StageWebGPU() {
  const select = useStore((s) => s.select);
  const mode = useStore((s) => s.mode);
  const rendering = useStore((s) => s.rendering);
  const geoEnabled = useStore((s) => s.geo.enabled);
  return (
    <Canvas
      shadows="variance"
      dpr={[1, 2]}
      gl={{ antialias: false }}
      frameloop={mode === "walk" || rendering || geoEnabled ? "always" : "demand"}
      onPointerMissed={() => select(null)}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.NoToneMapping;
      }}
    >
      <Suspense fallback={null}>
        <Scene />
      </Suspense>
      {!rendering && <Effects />}
    </Canvas>
  );
}
