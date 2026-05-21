---
type: spike
status: rejected
budget: n/a
gate: n/a
---

# Spike 1 — Text-to-image + click-segmentation (rejected)

**Status:** rejected, historical only. Architecture replaced by [[spike-2]] onward.

## Original hypothesis

User describes a building in text → text-to-image model generates a photorealistic render → user clicks regions in the render → segmentation model identifies what was clicked (wall / window / etc.) → user picks material → model re-renders with new material.

## Why it failed

**Two compounding generative steps.** The text-to-image step invents geometry that the segmentation step then has to identify. When the renderer hallucinates an extra balcony or merges two windows, the segmenter has no ground truth to fall back on — it just segments whatever's there. Errors compound multiplicatively.

**Architects don't start from prompts.** They already have a 3D model. Asking them to abandon the model and re-describe the building in words throws away the most useful structural information they have. The product hypothesis ("direct manipulation") collapses to "still typing prompts."

**No geometry anchor.** Each prompt iteration produces a new building. Layer/undo semantics ("change that one wall back, keep everything else") don't work when the underlying geometry shifts every render.

## What we kept

- The notion that a VLM can read semantic regions from a rendered image. That's still in [[spike-3]] — but applied to a render *anchored to user geometry*, not a generated one.
- The material-swap UX vocabulary (click region → pick swatch → re-render the region only). That's the [[spike-4]] target.

## What we dropped

- Text-to-image as the primary input modality.
- Click-segmentation as a first-class step (now folded into VLM tagging + SAM2).
- Any expectation that the model "creates" geometry.

## See also

- [[DECISIONS#dropped-text-to-image]] — the pivot decision and reasoning.
- [Master plan § Pivots](../../docs/plans/master-plan.md) — full design context.
