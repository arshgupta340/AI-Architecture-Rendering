/**
 * Single source of truth for all product copy + brand identity.
 * Renaming the product later must be a one-file change — every UI string,
 * the logo treatment, and the favicon consume this module.
 *
 * The internal codename "Reve Canvas" cannot ship (upstream vendor trademark);
 * see BRAND.md for the naming decision.
 */

export const BRAND = {
  name: "Strata",
  tagline: "Your render, in layers — swap any material without re-rendering the world",
  accent: "#d98a3a",
  copy: {
    productKind: "architecture-native layer editing",
    landing: {
      eyebrow: "Material intelligence for architecture",
      uploadTitle: "Bring a render into focus.",
      uploadBody: "Drop a viewport screenshot, render, or photo. Strata reads the scene into editable architectural layers.",
      dropIdle: "Drop an image here",
      dropActive: "Release to read the scene",
      chooseImage: "Choose image...",
      sample: "Use sample building",
      accepted: "PNG, JPG, WEBP - your image stays the source of truth.",
    },
    features: ["Element-aware layers", "Geometry-locked edits", "Full version trail"],
    workspace: { layers: "Layers", reset: "Reset", layerHint: "objects - select one to edit its material", facet: "Facet", material: "Material", noMaterials: "No material presets for this object type yet.", currentEdit: "Current edit" },
    materials: { search: "Search materials...", noMatch: "No materials match" },
    canvas: { sceneAlt: "Architectural scene", original: "Original", edited: "Edited", compare: "Compare", split: "Compare split", drift: "outside-edit change" },
    loading: { reading: "Reading the scene...", rendering: "Rendering your edit - ~35s" },
    cost: { session: "session", mock: "MOCK", live: "LIVE", mockSub: "$0", liveSub: "Reve" },
  },
} as const;

/** Quiet, architect-facing value prop used on the landing hero. */
export const VALUE_PROP = BRAND.tagline;

/** Three quiet feature bullets shown under the upload hero. */
export const FEATURES: { title: string; detail: string }[] = [
  { title: "Element-aware layers", detail: "A render is read into named object layers you can select and edit individually." },
  { title: "Geometry-locked edits", detail: "Material swaps pin to the original framing — no drift, no re-render of the world." },
  { title: "Full version trail", detail: "Every edit is batched behind an explicit action and tracked for review." },
];

/** Short mode-descriptor copy (mock vs live) for the header pill. */
export const MODE_COPY = {
  mock: { label: "MOCK", sub: "$0" },
  live: { label: "LIVE", sub: "Reve" },
} as const;

/** Long-form copy for the ~35s live render wait. */
export const WAIT_COPY = {
  reading: "Reading the scene…",
  rendering: "Rendering your edit — ~35s",
} as const;

export const APP_META = {
  title: `${BRAND.name} — layer-based AI editing for architecture`,
  description: BRAND.tagline,
} as const;
