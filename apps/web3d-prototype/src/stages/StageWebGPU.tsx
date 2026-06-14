import { Canvas, extend } from "@react-three/fiber";
import { Suspense, useMemo } from "react";
import * as THREE from "three/webgpu";
import { RectAreaLightTexturesLib } from "three/addons/lights/RectAreaLightTexturesLib.js";
import { Scene } from "../Scene";
import { useStore } from "../state/store";
import { WebGPUPost } from "./WebGPUPost";
import { WebGPUAreaLights } from "./WebGPUAreaLights";

/**
 * RENDER MODE "webgpu" — OWNED BY AGENT A. The realism ceiling.
 *
 * Renders the SHARED <Scene/> with three.js WebGPURenderer and a native TSL
 * post-processing node graph (SSGI + GTAO + Bloom + TRAA), plus LTC RectAreaLight
 * area lights. WebGL stages stay untouched; the only files this mode owns are this
 * one + WebGPUPost.tsx + WebGPUAreaLights.tsx.
 *
 * Pipeline (built in WebGPUPost):
 *   pass(scene,camera) with MRT { output, diffuseColor, normal(packed), velocity }
 *     → ssgi(beauty, depth, normal, camera)   // GI in .rgb, AO in .a (one node = GI+AO)
 *     → composite: beauty*ao + diffuse*gi
 *     → bloom(composite)                       // subtle HDR glow on sun glints
 *     → traa(composite, depth, velocity)       // temporal AA + denoises SSGI
 *   driven by PostProcessing.render() in useFrame(...,1) (R3F auto-render disabled).
 *
 * WebGPU-on-r184 notes:
 *  - Canvas gl is an async factory: new WebGPURenderer → await init() → set tone map.
 *    Missing await = silent black. We set AgXToneMapping on the renderer: the node
 *    RenderPipeline keeps scene+effects in linear HDR and applies tone map + sRGB
 *    once as the final output transform, so this matches StageWebGL2's trailing AgX
 *    post pass (it is not a double tone-map — see WebGPUPost for the detail).
 *  - bloom/ao/ssgi/traa live in three/addons/tsl/display/* (NOT three/tsl).
 *  - RectAreaLight on WebGPU needs RectAreaLightTexturesLib (NOT the WebGL
 *    RectAreaLightUniformsLib) — initialised once below.
 *  - frameloop is "always": TRAA + SSGI temporal filtering need continuous frames
 *    to converge (the other two stages stay on-demand; this is the quality mode).
 *  - WebGPU only paints on a real GPU/adapter; a headless/no-adapter context renders
 *    black — the build/typecheck is the bar here, the RTX visual check is the main
 *    agent's. We guard navigator.gpu so a non-WebGPU browser shows a hint, not a crash.
 */

// Register three/webgpu's classes (incl. node materials) as R3F JSX intrinsics.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
extend(THREE as any);

// One-time: feed the LTC (linearly-transformed cosine) lookup textures to the WebGPU
// RectAreaLight node so area lights shade correctly. Safe + idempotent at module load.
try {
  // setLTC may already be primed by another mount; init() is cheap + cached.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (THREE.RectAreaLightNode as any).setLTC(RectAreaLightTexturesLib.init());
} catch {
  // Non-fatal: area lights degrade gracefully if LTC priming fails.
}

const hasWebGPU = typeof navigator !== "undefined" && "gpu" in navigator;

export function StageWebGPU() {
  const select = useStore((s) => s.select);
  const rendering = useStore((s) => s.rendering);

  // Stable async renderer factory. R3F awaits the returned promise before the first
  // frame, so init() finishes before anything renders. Props are typed loosely:
  // R3F's DefaultGLProps.powerPreference ("default") isn't in WebGPURendererParameters,
  // so we widen to satisfy the GLProps callback signature (the WebGPU example does the
  // same with `props as any`).
  const glFactory = useMemo(
    () =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      async (props: any) => {
        const renderer = new THREE.WebGPURenderer({ ...props, antialias: false });
        await renderer.init();
        // AgX tone mapping, the WebGPU way: the node RenderPipeline keeps the beauty
        // pass + all effects in LINEAR HDR and applies the renderer's tone mapping +
        // sRGB ONCE as the final output transform (outputColorTransform=true). So
        // setting AgX here is the exact equivalent of StageWebGL2's trailing AgX post
        // pass — NOT a double tone-map. (NoToneMapping here would blow out the bright
        // sky/windows and break the 3-way comparison.)
        renderer.toneMapping = THREE.AgXToneMapping;
        return renderer;
      },
    [],
  );

  if (!hasWebGPU) {
    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          color: "#9aa4b2",
          font: "14px ui-sans-serif, system-ui",
          textAlign: "center",
          padding: 24,
        }}
      >
        WebGPU is not available in this browser. Switch render mode, or use a
        WebGPU-capable browser (Chrome / Edge) to see the SSGI render path.
      </div>
    );
  }

  return (
    <Canvas
      shadows="variance"
      dpr={[1, 2]}
      gl={glFactory}
      // Temporal post (TRAA + SSGI temporal filtering) needs continuous frames to
      // converge, so this stage always renders rather than on-demand.
      frameloop="always"
      onPointerMissed={() => select(null)}
    >
      <Suspense fallback={null}>
        <Scene />
      </Suspense>
      {/* Area lights are skipped during the path-traced "render" pass to keep the
          PT result identical to the other stages. */}
      {!rendering && <WebGPUAreaLights />}
      {!rendering && <WebGPUPost />}
    </Canvas>
  );
}
