import {
  EffectComposer,
  N8AO,
  Bloom,
  ToneMapping,
  BrightnessContrast,
  HueSaturation,
  Vignette,
  Noise,
  SMAA,
} from "@react-three/postprocessing";
import { ToneMappingMode, BlendFunction } from "postprocessing";
import { useStore } from "../state/store";

/**
 * Post stack for the WebGL2-GI stage — OWNED BY AGENT B. A tuned fork of the
 * shared Effects.tsx (NOT a mutation of it — the baseline stage must stay put for
 * a fair A/B). Passes run top → bottom; tone mapping is ALWAYS last.
 *
 * Differences vs the baseline Effects.tsx, and why:
 *   - N8AO pushed harder: intensity 3.0 (was 2.2) + a slightly larger aoRadius and
 *     more aoSamples. With the new RectAreaLight sky-fill lifting mid-tones, the
 *     scene can take — and benefits from — deeper contact occlusion in eaves,
 *     reveals and the building/ground contact line. This is the cheapest, most
 *     legible "GI" cue on WebGL2, so this stage leans into it.
 *   - Bloom stays deliberately subtle (intensity 0.12, luminanceThreshold 1.1).
 *     VERIFIED GOTCHA on this build: the procedural sky is extremely bright in the
 *     HalfFloat HDR buffer, so an aggressive bloom veils the whole frame white.
 *     The reflective ground + window emitters add more bright highlights, which is
 *     exactly why we do NOT raise bloom here.
 *   - Grade nudged a touch richer (contrast 0.10, saturation 0.08) to match the
 *     deeper AO without crushing.
 *   - AgX ToneMapping LAST — the only tone map (renderer is NoToneMapping). AgX
 *     handles the window/sky blowout gracefully.
 */
export function EffectsGI() {
  const grade = useStore((s) => s.grade);
  const gradeStrength = useStore((s) => s.gradeStrength);
  const s = grade ? gradeStrength : 0;

  return (
    <EffectComposer>
      <N8AO
        aoRadius={6}
        distanceFalloff={1}
        intensity={3.0}
        aoSamples={24}
        denoiseSamples={8}
        denoiseRadius={12}
        quality="high"
        halfRes
      />
      <Bloom mipmapBlur luminanceThreshold={1.1} luminanceSmoothing={0.3} intensity={0.12 + 0.06 * s} radius={0.6} />
      <BrightnessContrast brightness={-0.01 * s} contrast={0.1 + 0.13 * s} />
      <HueSaturation saturation={0.08 + 0.12 * s} />
      <Vignette offset={0.3} darkness={0.42 + 0.4 * s} />
      <Noise premultiply blendFunction={BlendFunction.OVERLAY} opacity={0.06 * s} />
      <SMAA />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
