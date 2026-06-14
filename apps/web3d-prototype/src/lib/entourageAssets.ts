// Single source of truth for the real CC0 entourage assets shipped under
// public/entourage/**. The <Entourage> component reads this list, loads each GLB
// once, and instances it. `kind` maps to the three NavBar place-buttons
// (tree / bush / person) — placed items of a kind are deterministically spread
// across all defs of that kind for visual variety with no UI change.
//
// `baseHeightFt` = the real-world height (feet) this species should render at when
// entHeight[kind] equals baseHeightFt and item.scale == 1. The GLB's measured
// model-unit height (scripts/measure_glb.py) is folded into the per-species unit
// scale at runtime via `glbHeightUnits`, so all species share one feet scale.
//
// `glbBaseY` = the GLB bbox ymin in model units (Quaternius models dip slightly
// below y=0); subtracting it seats each instance's base exactly on the click point.

export type EntKind = "tree" | "bush" | "person";

export type EntourageDef = {
  id: string;
  kind: EntKind;
  /** public/ URL of the GLB (trees/bushes) — undefined for procedural people. */
  url?: string;
  /** Real-world height in feet at entHeight==baseHeightFt and item-scale 1. */
  baseHeightFt: number;
  /** Measured GLB bbox Y-extent in model units (from scripts/measure_glb.py). */
  glbHeightUnits?: number;
  /** Measured GLB bbox ymin in model units (base offset to seat on ground). */
  glbBaseY?: number;
  /** Approx footprint diameter in feet (informational; not used for placement). */
  footprintFt?: number;
  license: string;
  attribution: string;
};

const POLY = "Quaternius — Stylized Nature MegaKit (poly.pizza)";
const CC0 = "CC0 1.0 (public domain)";

// Leafy trees (5) + dead/bare trees (3). Real trees ~25 ft; dead trees a touch
// shorter. Measured units come straight from scripts/measure_glb.py output.
export const TREES: EntourageDef[] = [
  { id: "tree-oak", kind: "tree", url: "/entourage/trees/Tree.glb", baseHeightFt: 26, glbHeightUnits: 9.425, glbBaseY: -0.243, footprintFt: 12, license: CC0, attribution: POLY },
  { id: "tree-round", kind: "tree", url: "/entourage/trees/Tree_YWjGDJ.glb", baseHeightFt: 26, glbHeightUnits: 9.438, glbBaseY: -0.243, footprintFt: 11, license: CC0, attribution: POLY },
  { id: "tree-bushy", kind: "tree", url: "/entourage/trees/Tree_aVOxaH.glb", baseHeightFt: 22, glbHeightUnits: 7.643, glbBaseY: -0.243, footprintFt: 12, license: CC0, attribution: POLY },
  { id: "tree-broad", kind: "tree", url: "/entourage/trees/Tree_qZtx0A.glb", baseHeightFt: 21, glbHeightUnits: 7.265, glbBaseY: -0.243, footprintFt: 13, license: CC0, attribution: POLY },
  { id: "tree-small", kind: "tree", url: "/entourage/trees/Tree_t9Kbsf.glb", baseHeightFt: 20, glbHeightUnits: 7.006, glbBaseY: -0.243, footprintFt: 11, license: CC0, attribution: POLY },
  { id: "tree-dead-a", kind: "tree", url: "/entourage/trees/Dead_Tree.glb", baseHeightFt: 24, glbHeightUnits: 12.771, glbBaseY: -0.336, footprintFt: 15, license: CC0, attribution: POLY },
  { id: "tree-dead-b", kind: "tree", url: "/entourage/trees/Dead_Tree_MlmK54.glb", baseHeightFt: 20, glbHeightUnits: 9.495, glbBaseY: -0.336, footprintFt: 12, license: CC0, attribution: POLY },
  { id: "tree-dead-c", kind: "tree", url: "/entourage/trees/Dead_Tree_oM95bD.glb", baseHeightFt: 25, glbHeightUnits: 13.280, glbBaseY: -0.336, footprintFt: 12, license: CC0, attribution: POLY },
];

// Shrubs / ground cover (4). Real bushes ~4 ft; clover/ground-cover lower.
export const BUSHES: EntourageDef[] = [
  { id: "bush-plain", kind: "bush", url: "/entourage/bushes/Bush.glb", baseHeightFt: 4.0, glbHeightUnits: 1.582, glbBaseY: -0.235, footprintFt: 5, license: CC0, attribution: POLY },
  { id: "bush-flowers", kind: "bush", url: "/entourage/bushes/Bush_with_Flowers.glb", baseHeightFt: 4.0, glbHeightUnits: 1.582, glbBaseY: -0.235, footprintFt: 5, license: CC0, attribution: POLY },
  { id: "bush-clover-a", kind: "bush", url: "/entourage/bushes/Clover.glb", baseHeightFt: 2.0, glbHeightUnits: 1.145, glbBaseY: -0.013, footprintFt: 2, license: CC0, attribution: POLY },
  { id: "bush-clover-b", kind: "bush", url: "/entourage/bushes/Clover_u5SOgB.glb", baseHeightFt: 2.2, glbHeightUnits: 1.264, glbBaseY: -0.002, footprintFt: 2, license: CC0, attribution: POLY },
];

// People — procedural cutout (no committed PNGs; see ATTRIBUTIONS.md followup).
// `baseHeightFt` matches the procedural canvas person's natural height at scale 1.
// Variants are picked by hash in Entourage.tsx (no separate defs needed here).
export const PEOPLE: EntourageDef[] = [
  { id: "person-proc", kind: "person", baseHeightFt: 6, footprintFt: 1.5, license: "n/a (procedural)", attribution: "Procedural cutout (this project)" },
];

export const ENTOURAGE: EntourageDef[] = [...TREES, ...BUSHES, ...PEOPLE];

/** Defs for one kind, in stable order (used for deterministic species spread). */
export function defsForKind(kind: EntKind): EntourageDef[] {
  return ENTOURAGE.filter((d) => d.kind === kind);
}

/** Stable string hash (FNV-1a) → non-negative int. Used to spread placed items
 *  across the species of their kind deterministically by item.id. */
export function hashId(id: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}
