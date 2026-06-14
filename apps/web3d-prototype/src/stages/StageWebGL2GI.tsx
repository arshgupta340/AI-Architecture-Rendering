import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { Scene } from "../Scene";
import { Effects } from "../Effects";
import { useStore } from "../state/store";

/**
 * RENDER MODE "webgl2gi" — OWNED BY AGENT B.
 *
 * Goal: the best real-GI look achievable on WebGL2, a clear step above StageWebGL2.
 * This file starts as a functional copy of StageWebGL2 so the mode is never broken;
 * ENHANCE it here. Boundaries:
 *   - Edit ONLY this file + NEW files you create (e.g. EffectsGI.tsx, AreaLights.tsx,
 *     ReflectiveGround.tsx). Do NOT edit StageWebGL2/StageWebGPU/Scene.tsx/Effects.tsx
 *     /SolarSky.tsx (shared) — add your lights/ground/post as siblings of <Scene/>.
 * Planned techniques (implement what lifts realism most on WebGL2):
 *   - RectAreaLight (LTC) area lights — sky-fill + per-window glow. Needs
 *     RectAreaLightUniformsLib.init() (three/addons/lights/RectAreaLightUniformsLib.js).
 *   - MeshReflectorMaterial reflective ground plane (drei) for floor/wet reflections.
 *   - Tuned/stronger N8AO + your own post composer (don't mutate shared Effects.tsx).
 *   - Optional: GTAOPass alternative, contact shadows, color-grade tweaks.
 * Keep the camera/scene/sun behavior identical to StageWebGL2 so modes A/B compare fairly.
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
      {/* AGENT B: add <AreaLights/>, <ReflectiveGround/>, and your <EffectsGI/> here. */}
      {!rendering && <Effects />}
    </Canvas>
  );
}
