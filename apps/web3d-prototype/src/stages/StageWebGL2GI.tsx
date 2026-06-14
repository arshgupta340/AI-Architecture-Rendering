import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { Scene } from "../Scene";
import { EffectsGI } from "./EffectsGI";
import { ReflectiveGround } from "./ReflectiveGround";
import { ContactGround } from "./ContactGround";
import { ExportCapture } from "../lib/exportImage";
import { useStore } from "../state/store";

/**
 * RENDER MODE "webgl2gi".
 *
 * Goal: the best real-GI LOOK achievable on WebGL2, a clear step above StageWebGL2.
 * Lighting is IDENTICAL to every other mode — the single SolarSky sun + slight ambient
 * (the old fake RectAreaLight fills were removed; they double-lit the scene and broke
 * sun-direction consistency). What distinguishes this stage is the RENDERING, not the
 * lights:
 *   - <ReflectiveGround/> — drei MeshReflectorMaterial plane at the building base:
 *     real-time planar reflection of building + sky (the "wet plaza" hero look).
 *   - <ContactGround/> — soft contact-shadow catcher grounding the building.
 *   - <EffectsGI/> — a tuned fork of Effects.tsx with stronger N8AO (deeper occlusion
 *     reads as GI); Bloom kept subtle + AgX tonemap LAST.
 *
 * Gotchas avoided (verified on three r0.184): no drei <SoftShadows>/PCSS (emits the
 * removed unpackRGBAToDepth → white-out); Bloom held low so the bright sky + reflections
 * don't veil the frame white.
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
        {/* GI additions render alongside the shared Scene. The fake RectAreaLight fills
            were removed — lighting is now the single SolarSky sun + slight ambient, same
            as every mode; this stage's "GI" is the reflective ground + stronger N8AO
            (real occlusion/reflection cues), not extra light sources. */}
        {!rendering && <ReflectiveGround />}
        {!rendering && <ContactGround />}
      </Suspense>
      {!rendering && <EffectsGI />}
      <ExportCapture />
    </Canvas>
  );
}
