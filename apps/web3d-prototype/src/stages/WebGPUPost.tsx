import { useEffect, useMemo, useRef } from "react";
import { useThree, useFrame } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import {
  pass,
  mrt,
  output,
  diffuseColor,
  normalView,
  velocity,
  directionToColor,
  colorToDirection,
  sample,
  add,
  vec4,
} from "three/tsl";
import { ssgi } from "three/addons/tsl/display/SSGINode.js";
import { ao } from "three/addons/tsl/display/GTAONode.js";
import { traa } from "three/addons/tsl/display/TRAANode.js";
import { bloom } from "three/addons/tsl/display/BloomNode.js";

/**
 * WebGPU TSL post-processing node graph — the headline of the "webgpu" render mode.
 *
 * Composition (matches three's official r184 webgpu_postprocessing_ssgi example):
 *
 *   scenePass = pass(scene, camera)
 *   scenePass.MRT = { output, diffuseColor, normal: directionToColor(normalView), velocity }
 *   sceneNormal  = colorToDirection(normal)              // unpack RGBA8 → view normal
 *   giPass = ssgi(beauty, depth, sceneNormal, camera)    // GI in .rgb, AO in .a
 *   composite = beauty.rgb*ao + diffuse.rgb*gi           // indirect diffuse + AO
 *   composite = composite + bloom(composite)             // subtle HDR glow
 *   output    = traa(composite, depth, velocity, camera) // temporal AA + SSGI denoise
 *
 * SSGI already produces ground-truth-style AO in its alpha channel, so it is the
 * primary AO source here — a standalone GTAO pass would be redundant work. The
 * GTAO node is still imported and wired as the fallback AO when SSGI is disabled
 * (see `USE_SSGI`), so both code paths are real.
 *
 * Driven by RenderPipeline.render() inside useFrame(..., 1). renderPriority 1
 * disables R3F's auto-render (so we own the single pipeline — avoids the
 * frame-accumulation/ghosting seen when the node pipeline's render() is mixed with
 * R3F's own render, three.js issue #32535) and runs AFTER every other useFrame so
 * the scene + OrbitControls are fully updated before the beauty pass is taken.
 *
 * AgX tone-mapping + sRGB output are applied by RenderPipeline on the final
 * outputNode (outputColorTransform=true uses renderer.toneMapping = AgX, set in
 * StageWebGPU). The beauty pass + every effect run in linear HDR; the tone map
 * happens once at the very end — parity with StageWebGL2's trailing AgX post pass.
 *
 * NB: the task spec said `THREE.PostProcessing` — in r184 that class is deprecated
 * (since r183) and simply warns + delegates to `RenderPipeline`. We use the
 * non-deprecated `RenderPipeline` directly; it is behaviourally identical and is
 * what every official r184 webgpu_postprocessing_* example uses.
 *
 * TSL nodes are dynamically typed (the upstream examples are plain JS and chain
 * `.rgb` / `.mul` / `.add` freely); we type the graph locals as `any` to match,
 * rather than fighting partial `.d.ts` coverage with casts at every node.
 */

// SSGI gives both GI and AO; flip to false to fall back to a standalone GTAO-only
// path (AO without indirect bounce) — kept wired so both branches compile + run.
const USE_SSGI = true;

export function WebGPUPost() {
  const gl = useThree((s) => s.gl) as unknown as THREE.WebGPURenderer;
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);

  const postRef = useRef<THREE.RenderPipeline | null>(null);

  // Build the node graph once per (scene, camera, renderer). The TSL nodes capture
  // live references to scene/camera, so they keep tracking changes without a rebuild.
  const post = useMemo(() => {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const scenePass: any = pass(scene, camera);

    // MRT: beauty + diffuse-only color + packed view normal (RGBA8) + velocity
    // (for TRAA). Depth is free from the default pass — no MRT slot needed.
    scenePass.setMRT(
      mrt({
        output: output,
        diffuseColor: diffuseColor,
        normal: directionToColor(normalView),
        velocity: velocity,
      }),
    );

    const beauty: any = scenePass.getTextureNode("output");
    const diffuse: any = scenePass.getTextureNode("diffuseColor");
    const depth: any = scenePass.getTextureNode("depth");
    const packedNormal: any = scenePass.getTextureNode("normal");
    const sceneVelocity: any = scenePass.getTextureNode("velocity");

    // Unpack the RGBA8-packed normal back into a view-space direction for the AO/GI
    // samplers (matches the official example's `sample(... colorToDirection ...)`).
    const sceneNormal: any = sample((uv: any) => colorToDirection(packedNormal.sample(uv)));

    let composite: any;

    if (USE_SSGI) {
      // ssgi(beauty, depth, normal, camera): .rgb = indirect diffuse GI, .a = AO.
      const giPass: any = ssgi(beauty, depth, sceneNormal, camera);
      // Low preset (sliceCount 1 * stepCount 12 * 2 = 24 samples/px) — temporal
      // filtering (TRAA) cleans the residual noise. Cost = sliceCount*stepCount*2.
      giPass.sliceCount.value = 1;
      giPass.stepCount.value = 12;
      giPass.useTemporalFiltering = true; // paired with the TRAA pass below
      giPass.giIntensity.value = 6; // calmer than the default 10 for archviz
      giPass.radius.value = 12; // world units (FEET) — building-scale bounce radius

      const gi = giPass.rgb;
      const aoTerm = giPass.a;
      // beauty already contains direct + IBL; multiply by AO, then ADD indirect
      // diffuse bounce (gi modulated by the surface's own diffuse color).
      composite = vec4(add(beauty.rgb.mul(aoTerm), diffuse.rgb.mul(gi)), beauty.a);
    } else {
      // Fallback: GTAO-only (no indirect bounce). ao(depth, normal, camera).
      const aoPass: any = ao(depth, sceneNormal, camera);
      const aoTerm = aoPass.getTextureNode().r;
      composite = beauty.mul(vec4(aoTerm, aoTerm, aoTerm, 1));
    }

    // Subtle HDR bloom on the brightest highlights (sun glints / blown windows).
    // bloom(input, strength, radius, threshold): high threshold so it veils glints,
    // not the whole frame — the procedural sky is very bright in the HDR buffer.
    const bloomPass: any = bloom(composite, 0.12, 0.6, 1.0);
    const withBloom: any = composite.add(bloomPass);

    // Temporal reprojection AA — also the SSGI denoiser. Must be the last pass and
    // consumes the scene velocity from the MRT (auto-jitters the camera via the
    // PostProcessing pre/post hooks in r184; no setTRAANode call needed).
    const traaPass: any = traa(withBloom, depth, sceneVelocity, camera);

    const p = new THREE.RenderPipeline(gl);
    // outputColorTransform defaults to true → the pipeline applies the renderer's
    // tone mapping (AgX) + sRGB to this final node. Everything upstream is linear HDR.
    p.outputNode = traaPass;

    return p;
    /* eslint-enable @typescript-eslint/no-explicit-any */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, camera, gl]);

  // Stash the live instance + dispose on teardown.
  useEffect(() => {
    postRef.current = post;
    return () => {
      postRef.current = null;
      try {
        post.dispose();
      } catch {
        // dispose is best-effort; ignore teardown races.
      }
    };
  }, [post]);

  // Keep the post pipeline's internal targets in step with the canvas size. The
  // pass + effect nodes also resize themselves in updateBefore, but flagging an
  // update on resize avoids a stale first frame after a viewport change.
  useEffect(() => {
    if (postRef.current) postRef.current.needsUpdate = true;
  }, [size.width, size.height]);

  // Drive the whole pipeline. renderPriority 1 turns OFF R3F's own render.
  useFrame(() => {
    const p = postRef.current;
    if (p) p.render();
  }, 1);

  return null;
}
