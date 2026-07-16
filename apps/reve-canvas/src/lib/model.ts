/**
 * Reve Canvas domain model. A CanvasLayer is a named handle onto ONE Reve object
 * region (PRD §3 F1 — object-level, per the validated spike). Editing a layer is
 * a change-command on its region description. Shape-compatible with the web3d
 * HeroLayer (semantic strings; base/region split) for 3D-track convergence.
 */
import {
  matchSemantic, isBuildingLabel, LAYER_TYPE_DEFAULTS, ENVELOPE_FACETS,
  materialsFor, FACET_LABEL,
  type SemanticClass, type LayerType, type EnvelopeFacet, type MaterialScaffold,
} from "@/lib/taxonomy";
import type { ReveLayout, ReveRegion } from "./reve/types";

export interface CanvasLayer {
  id: string; // RegionKey — encoded into the Reve label so it round-trips
  reveLabel: string; // current label in the layout (== id after relabel)
  name: string; // human display name
  semantic: SemanticClass;
  type: LayerType;
  bbox: ReveRegion["bbox"];
  prompt: string; // the region's current description
  parentId?: string;
  isBuilding: boolean; // envelope region → facet editing
  facets: EnvelopeFacet[]; // material facets when isBuilding
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32) || "r";
}

export function regionKey(semantic: string, label: string, idx: number): string {
  return `${semantic}.${slug(label)}#${String(idx).padStart(3, "0")}`;
}

function displayName(label: string): string {
  // "<lounge_chairs 2>" -> "Lounge Chairs 2"
  return label.replace(/[<>]/g, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).trim();
}

/** Rewrite region labels to RegionKeys (so our ids round-trip through render_layout)
 * and return the keyed layout. Parent refs follow the rename. */
export function relabelWithRegionKeys(layout: ReveLayout): { layout: ReveLayout; idByOld: Record<string, string> } {
  const idByOld: Record<string, string> = {};
  const out: ReveLayout = JSON.parse(JSON.stringify(layout));
  out.regions.forEach((r, i) => {
    const sem = matchSemantic(r.label) ?? "context";
    const key = regionKey(sem, r.label, i);
    idByOld[r.label] = key;
    r.label = key;
  });
  for (const r of out.regions) {
    if (r.parent && idByOld[r.parent]) r.parent = idByOld[r.parent];
  }
  return { layout: out, idByOld };
}

/** Auto-layerize: one CanvasLayer per Reve region, taxonomy-typed. Sorted with
 * the building/structure first, then by area (largest → most editable). */
export function autoLayerize(keyedLayout: ReveLayout, originalLabels: Record<string, string>): CanvasLayer[] {
  const invert: Record<string, string> = {};
  for (const [oldL, key] of Object.entries(originalLabels)) invert[key] = oldL;

  const layers: CanvasLayer[] = keyedLayout.regions.map((r) => {
    const orig = invert[r.label] ?? r.label;
    const semantic = matchSemantic(orig) ?? "context";
    const building = isBuildingLabel(orig);
    return {
      id: r.label,
      reveLabel: r.label,
      name: displayName(orig),
      semantic,
      type: LAYER_TYPE_DEFAULTS[semantic],
      bbox: r.bbox,
      prompt: r.prompt,
      parentId: r.parent,
      isBuilding: building,
      facets: building ? [...ENVELOPE_FACETS] : [],
    };
  });

  const area = (l: CanvasLayer) => (l.bbox.x1 - l.bbox.x0) * (l.bbox.y1 - l.bbox.y0);
  return layers.sort((a, b) => {
    if (a.isBuilding !== b.isBuilding) return a.isBuilding ? -1 : 1;
    return area(b) - area(a);
  });
}

/** Materials offered for a layer: by facet if it's a building envelope, else by
 * semantic class. */
export function materialsForLayer(layer: CanvasLayer, facet?: EnvelopeFacet): MaterialScaffold[] {
  if (layer.isBuilding) return materialsFor(facet ?? "cladding");
  return materialsFor(layer.semantic);
}

export { FACET_LABEL };
export type { EnvelopeFacet, MaterialScaffold, SemanticClass };

/** A Reve-legal render canvas (multiple of 32, area in [3072*2560, 4096*4096])
 * matching the source aspect — pins framing (validated: source 2.29:1 → output
 * 2.29:1). */
export function pinAspect(srcW: number, srcH: number): { width: number; height: number } {
  const ar = srcW / srcH;
  const LO = 3072 * 2560, HI = 4096 * 4096;
  let area = (LO + HI) / 2;
  let h = Math.round(Math.sqrt(area / ar) / 32) * 32;
  let w = Math.round((h * ar) / 32) * 32;
  while (w * h > HI) { h -= 32; w = Math.round((h * ar) / 32) * 32; }
  while (w * h < LO) { h += 32; w = Math.round((h * ar) / 32) * 32; }
  return { width: w, height: h };
}

/** Build the change-command new_description for a material edit. For a building
 * envelope we rewrite one facet clause and preserve the rest of the description;
 * for a discrete surface/object we set the material directly on that region. */
export function buildChangeDescription(
  layer: CanvasLayer, material: MaterialScaffold, facet?: EnvelopeFacet,
): string {
  if (layer.isBuilding) {
    const which = facet ?? "cladding";
    const clause =
      which === "roof" ? `the roof is now ${material.prompt}`
      : which === "trim" ? `the trim and details are now ${material.prompt}`
      : which === "foundation" ? `the base and foundation are now ${material.prompt}`
      : `the exterior walls are now clad in ${material.prompt}`;
    return `${layer.prompt} — updated so that ${clause}; keep all other elements, windows, geometry, and composition identical.`;
  }
  return `${material.prompt}; keep the shape, position, and surroundings identical.`;
}
