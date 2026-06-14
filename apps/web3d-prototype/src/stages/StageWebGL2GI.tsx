import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { Scene } from "../Scene";
import { EffectsGI } from "./EffectsGI";
import { AreaLights } from "./AreaLights";
import { ReflectiveGround } from "./ReflectiveGround";
import { ContactGround } from "./ContactGround";
import { ExportCapture } from "../lib/exportImage";
import { useStore } from "../state/store";

/**
 * RENDER MODE "webgl2gi" — OWNED BY AGENT B.
 *
 * Goal: the best real-GI LOOK achievable on WebGL2, a clear step above StageWebGL2.
 * Implemented (all WebGL2, $0, client-side):
 *   - <AreaLights/> — RectAreaLight (LTC) sky-fill above the building + per-window
 *     warm emitters. RectAreaLightUniformsLib.init() runs once inside it. Soft,
 *     directional sky bounce + interior-glow cue the baseline can't produce.
 *   - <ReflectiveGround/> — drei MeshReflectorMaterial plane at the building base:
 *     real-time planar reflection of building + sky (the "wet plaza" hero look).
 *   - <EffectsGI/> — a tuned fork of Effects.tsx with stronger N8AO; Bloom kept
 *     subtle + AgX tonemap LAST (procedural sky blows out the HDR buffer otherwise).
 * Boundaries honoured: only this file + the three NEW sibling files were touched.
 * Camera / Scene / sun behaviour is IDENTICAL to StageWebGL2 (same <Canvas> props,
 * same shared <Scene/>) so the A/B is fair — the new lights/ground/post are pure
 * additions layered on top.
 *
 * Gotchas avoided (verified on three r0.184): no drei <SoftShadows>/PCSS (emits the
 * removed unpackRGBAToDepth → white-out); RectAreaLight casts no shadows (sun owns
 * them); Bloom held low so the bright sky + reflections don't veil the frame white.
 */
export function StageWebGL2GI() {
  const select = useStore((s) => s.select);
  const mode = useStore((s) => s.mode);
  const rendering = useStore((s) => s.rendering);
  const geoEnabled = useStore((s) => s.geo.enabled);
  return (
    <Canvas
      shadows="variance"
      dpr={[1, 2]}
      gl={{ antialias: false, preserveDrawingBuffer: true }}
      frameloop={mode === "walk" || rendering || geoEnabled ? "always" : "demand"}
      onPointerMissed={() => select(null)}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.NoToneMapping;
      }}
    >
      <Suspense fallback={null}>
        <Scene />
        {/* GI additions render alongside the shared Scene. Suspended with it so the
            reflector/lights only mount once the model + bbox exist. Hidden during a
            path-trace pass (PathTracer owns the frame then). */}
        {!rendering && <AreaLights />}
        {!rendering && <ReflectiveGround />}
        {!rendering && <ContactGround />}
      </Suspense>
      {!rendering && <EffectsGI />}
      <ExportCapture />
    </Canvas>
  );
}
