---
type: strategy
updated: 2026-05-19
---

# Strategy — Photoshop route vs VLM route

## The frame

Two threads of work appear in the codebase. New readers often ask which one we "really" want. Short answer: **both, in sequence — they're complementary layers, not competing options.**

- **Photoshop route** = the *product*. Direct-manipulation canvas, layer stack, swatch library, click-and-pick UX. Architects don't write prompts.
- **VLM route** = the *plumbing inside the product*. A Vision-Language Model auto-tags every region in the render so "click a wall" resolves to a real region without the user drawing a mask.

Without the VLM, clicking a wall just gives you `(x, y)` and the system has no idea whether that pixel is wall, window, or shadow. Without the Photoshop UX, you have a pile of bboxes and no product.

## Current decision

**Sequential pipeline, both routes required:**

```
[Spike 2.5: pick renderer]  →  [Spike 3: pick tagger]  →  [Spike 4: chain them]  →  [Photoshop UI on top]
```

Spike 2.5 chooses the production renderer (the thing that turns the screenshot into a photorealistic render). Spike 3 chooses the tagger (the thing that labels regions in that render). Spike 4 chains them and adds the material-swap step. The Photoshop canvas wraps all of it once those backend pieces work.

**Why this order:** the tagger only matters if the render is good (you can't tag a bad render usefully). The UI only matters if the backend produces editable outputs. Cheapest-information-first ordering.

## How we got here

See [[DECISIONS]] for the full history. Highlights:

- **Spike 1 → Spike 2 pivot:** we dropped text-to-image + click-segmentation. Two compounding generative steps was the wrong architecture. Architects already have 3D models; using the viewport screenshot as input lets the renderer do *one* job (re-texture preserving geometry) and the tagger do *one* job (label regions). [[DECISIONS#dropped-text-to-image]].
- **Shaded screenshot, not line drawing:** the screenshot carries both edge geometry *and* color discontinuities, so both the renderer (geometry preservation) and the tagger (region boundaries) get useful signal from the same input. [[DECISIONS#shaded-screenshot-input]].
- **VLM tagging, not color-coded mask passes:** baking geometry into the input via material IDs would tie us to one host (Rhino vs SketchUp vs Revit each handle this differently) and break across renderers. A VLM that reads pixels generalizes. [[DECISIONS#vlm-tagging]].
- **Empirical bake-off, not commit-to-one renderer:** Spike 2 showed Nano Banana Pro has critical failures. Rather than betting on one challenger, B3 runs all 8 candidates on the same input and we pick by score. [[DECISIONS#empirical-bake-off]].

## Open strategic questions

These need answers *after* the next gate result, not before. They're logged here so we don't lose them.

### Q1 — If no renderer passes B3's zero-critical-failure gate

Options:

- **(a) Hybrid two-pass.** FLUX Canny for structure-preserving line work + Nano Banana for material/lighting. More API calls per render but each model does what it's best at.
- **(b) User-correction UX.** Accept some critical failures and add a manual mask-refinement step in the canvas. The Photoshop UX already gives us layer-level control — embracing it could turn "fix the bad render" into a feature, not a workaround.
- **(c) Fine-tune.** Beyond budget for the spike phase; defer.

Trigger: B3 results in. Revisit then.

### Q2 — If Gemini 3 Pro tagging stays unreliable on diverse inputs (post-T21)

Options:

- **(a) Per-region click-confirmation.** Show all tagged regions; user clicks to confirm which one they meant. Tagger doesn't have to be perfect — it just has to surface plausible candidates.
- **(b) Color-based seed fallback.** Use color discontinuities in the screenshot as seed regions, VLM only labels them. Shifts the burden from "find regions" (hard) to "label regions" (easier).
- **(c) Swap tagger.** GPT-5V or Claude vision as alternates.

Trigger: T21 (5-screenshot eval) results.

### Q3 — When to prototype the Photoshop UX

Today the canvas is paper-design only. We could:

- **(a) Wait for Spike 4 live success** before any UI work — proves the backend, then build UI on a known foundation.
- **(b) Start UI in parallel** with a mocked backend (canned JSON for `Region[]`, hand-segmented masks). De-risks UX questions earlier but UI gets thrown away if backend reshapes things.

Default position: (a). Revisit once Spike 4 has one passing live run.

## Anti-strategy (what we are NOT doing)

- **Not** building a general-purpose AI image editor. The vertical is architecture; the UX vocabulary is "walls, floors, materials," not "layers, brushes, gradients."
- **Not** asking architects to write prompts. The product hypothesis is direct manipulation over conversational interfaces.
- **Not** building plugins until the web MVP works. Rhino/SketchUp/Revit/Forma each have viewport-capture APIs but plugin distribution is its own product surface.
- **Not** baking material IDs into the 3D model. That would lock us to one host and one workflow.
