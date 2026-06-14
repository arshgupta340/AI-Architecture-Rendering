import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { Scene } from "../Scene";
import { Effects } from "../Effects";
import { ContactGround } from "./ContactGround";
import { ExportCapture } from "../lib/exportImage";
import { useStore } from "../state/store";

/**
 * RENDER MODE "webgl2" — the baseline, known-good path: WebGL2 renderer + VSM soft
 * shadows + the N8AO/Bloom/AgX post stack (Effects.tsx). The other two stages
 * (StageWebGL2GI, StageWebGPU) build on / diverge from this. Do not regress it.
 */
export function StageWebGL2() {
  const select = useStore((s) => s.select);
  const mode = useStore((s) => s.mode);
  const rendering = useStore((s) => s.rendering);
  const geoEnabled = useStore((s) => s.geo.enabled);
  return (
    <Canvas
      shadows="variance"
      dpr={[1, 2]}
      // preserveDrawingBuffer lets the high-res "Export still" read the post-processed
      // frame via toBlob (the WebGL buffer is otherwise cleared after compositing).
      gl={{ antialias: false, preserveDrawingBuffer: true }}
      frameloop={mode === "walk" || rendering || geoEnabled ? "always" : "demand"}
      onPointerMissed={() => select(null)}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.NoToneMapping;
      }}
    >
      <Suspense fallback={null}>
        <Scene />
        {!rendering && <ContactGround />}
      </Suspense>
      {!rendering && <Effects />}
      <ExportCapture />
    </Canvas>
  );
}
