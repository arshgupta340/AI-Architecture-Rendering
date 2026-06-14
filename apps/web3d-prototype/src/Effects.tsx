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
import { useStore } from "./state/store";

/**
 * Post-processing stack — the single biggest realism jump for a WebGL2 archviz
 * scene. Passes run top → bottom; tone mapping is ALWAYS last.
 *
 *   N8AO     — ground-truth-style ambient occlusion. Darkens eaves, window
 *              reveals, wall/roof junctions and the contact line. aoRadius is in
 *              WORLD units — our world is in feet (Scene.boxProjectUVs).
 *   Bloom    — VERY subtle HDR glow on sun glints. Kept low + high-threshold
 *              because the procedural sky is extremely bright in the HalfFloat
 *              HDR buffer; an aggressive bloom veils the whole frame in white.
 *   grade    — gentle contrast + saturation lift (merges into one cheap pass).
 *              The "Cinematic grade" toggle (store.grade / gradeStrength) dials
 *              this up + adds subtle film grain for the "money shot" look.
 *   Vignette — subtle framing so the eye lands on the building.
 *   SMAA     — edge anti-alias (Canvas runs antialias:false; SMAA replaces MSAA).
 *   ToneMapping (AgX) — HDR → display; the ONLY tone map (renderer is
 *              NoToneMapping, see App.tsx). AgX handles window blowout well.
 *
 * The grade is kept tasteful (archviz, not Instagram): contrast/saturation/vignette
 * scale gently with strength and grain stays ≤0.06 so the building reads sharp.
 */
export function Effects() {
  const grade = useStore((s) => s.grade);
  const gradeStrength = useStore((s) => s.gradeStrength);
  const s = grade ? gradeStrength : 0;

  return (
    <EffectComposer>
      <N8AO aoRadius={5} distanceFalloff={1} intensity={2.2} quality="high" halfRes />
      <Bloom mipmapBlur luminanceThreshold={1.1} luminanceSmoothing={0.3} intensity={0.12 + 0.06 * s} radius={0.6} />
      <BrightnessContrast brightness={-0.01 * s} contrast={0.08 + 0.13 * s} />
      <HueSaturation saturation={0.06 + 0.12 * s} />
      <Vignette offset={0.3} darkness={0.4 + 0.4 * s} />
      <Noise premultiply blendFunction={BlendFunction.OVERLAY} opacity={0.06 * s} />
      <SMAA />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
