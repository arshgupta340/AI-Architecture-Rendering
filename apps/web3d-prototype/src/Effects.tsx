import {
  EffectComposer,
  N8AO,
  Bloom,
  ToneMapping,
  BrightnessContrast,
  HueSaturation,
  Vignette,
  SMAA,
} from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";

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
 *   Vignette — subtle framing so the eye lands on the building.
 *   SMAA     — edge anti-alias (Canvas runs antialias:false; SMAA replaces MSAA).
 *   ToneMapping (AgX) — HDR → display; the ONLY tone map (renderer is
 *              NoToneMapping, see App.tsx). AgX handles window blowout well.
 *
 * The @react-three/postprocessing EffectComposer already uses a HalfFloat buffer
 * by default, so bloom + AgX operate on real HDR radiance.
 */
export function Effects() {
  return (
    <EffectComposer>
      <N8AO aoRadius={5} distanceFalloff={1} intensity={2.2} quality="high" halfRes />
      <Bloom mipmapBlur luminanceThreshold={1.1} luminanceSmoothing={0.3} intensity={0.12} radius={0.6} />
      <BrightnessContrast brightness={0} contrast={0.08} />
      <HueSaturation saturation={0.06} />
      <Vignette offset={0.3} darkness={0.4} />
      <SMAA />
      <ToneMapping mode={ToneMappingMode.AGX} />
    </EffectComposer>
  );
}
