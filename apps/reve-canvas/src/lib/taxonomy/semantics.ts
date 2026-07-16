/**
 * arch-taxonomy — the shared architectural vocabulary for the Photoshop-for-
 * Architects project. Consumed by Reve Canvas (2D) now and by the web3d
 * prototype (3D) at the convergence milestone. Keep `SemanticClass` and the
 * material `id`s aligned with apps/web3d-prototype/src/lib/swatches.ts and
 * spike/schemas.py.
 *
 * Reve reality (validated 2026-07-16, see spike/REPORTS/reve_spike.md):
 * extract_layout returns OBJECT-level regions (`<house>`, `<window>`, `<sofa>`,
 * `<floor>`, `<sky>`...), not a fixed surface set. For an exterior the wall/roof/
 * trim materials live as clauses inside the building region's description; for an
 * interior, `<floor>`/`<ceiling>`/`<walls>` come back as separate regions plus
 * individual furniture objects. So a "layer" = one Reve object region, and a
 * material edit = a `change` command rewriting a facet clause of that region.
 */

export type SemanticClass =
  | "wall" | "glazing" | "door" | "roof" | "floor" | "ceiling"
  | "ground" | "paving" | "vegetation" | "person" | "vehicle"
  | "furniture" | "fixture" | "sky" | "water" | "text" | "context";

export const SEMANTICS: readonly SemanticClass[] = [
  "wall", "glazing", "door", "roof", "floor", "ceiling", "ground", "paving",
  "vegetation", "person", "vehicle", "furniture", "fixture", "sky", "water",
  "text", "context",
] as const;

/** Free-form Reve label word -> canonical class. Matching is plural-insensitive
 * (see matchSemantic): "walls" -> "wall", "windows" -> "glazing", etc. */
export const ALIASES: Record<string, SemanticClass> = {
  // glazing
  window: "glazing", mullion: "glazing", glass: "glazing", skylight: "glazing",
  // wall / cladding
  facade: "wall", siding: "wall", cladding: "wall", brick: "wall", plain: "wall",
  // door
  entrance: "door", garage: "door", gate: "door",
  // roof
  gable: "roof", eave: "roof", dormer: "roof",
  // floor / ceiling
  flooring: "floor", rug: "furniture", carpet: "floor",
  soffit: "ceiling",
  // ground / landscape
  grass: "ground", lawn: "ground", field: "ground", meadow: "ground", hill: "ground",
  landscape: "ground", terrain: "ground", yard: "ground", dirt: "ground", sand: "ground",
  // paving
  driveway: "paving", path: "paving", pathway: "paving", sidewalk: "paving", road: "paving",
  patio: "paving", terrace: "paving", walkway: "paving", "stepping_stone": "paving",
  "stepping_stones": "paving", deck: "paving", steps: "paving", stair: "paving", stairs: "paving",
  staircase: "paving",
  // vegetation
  tree: "vegetation", bush: "vegetation", shrub: "vegetation", plant: "vegetation",
  hedge: "vegetation", foliage: "vegetation", garden: "vegetation", flower: "vegetation",
  // water
  pool: "water", pond: "water", fountain: "water", lake: "water",
  // furniture / fixture
  sofa: "furniture", couch: "furniture", table: "furniture", chair: "furniture",
  desk: "furniture", bed: "furniture", cabinet: "furniture", shelf: "furniture",
  bookshelf: "furniture", stool: "furniture", bench: "furniture", ottoman: "furniture",
  "lounge_chair": "furniture", "lounge_chairs": "furniture", pillow: "furniture",
  cushion: "furniture", blanket: "furniture", television: "fixture", tv: "fixture",
  lamp: "fixture", light: "fixture", chandelier: "fixture", sconce: "fixture",
  speaker: "fixture", appliance: "fixture", sink: "fixture", faucet: "fixture",
  painting: "furniture", art: "furniture", artwork: "furniture", mirror: "furniture",
  vase: "furniture", bowl: "furniture", book: "furniture", railing: "fixture", fence: "fixture",
  // people / vehicles
  man: "person", woman: "person", people: "person", figure: "person", pedestrian: "person",
  car: "vehicle", truck: "vehicle", bicycle: "vehicle", bike: "vehicle",
  // sky
  cloud: "sky", sun: "sky", horizon: "sky",
  // context (whole structures / unresolved)
  house: "context", building: "context", villa: "context", cabin: "context",
  cottage: "context", structure: "context", home: "context", wing: "context",
  porch: "context", chimney: "context", balcony: "context", pediment: "context",
  truss: "context", trim: "context", shadow: "context", street: "context",
};

/** Whole-structure labels: a material/"wall" edit rewrites THIS region's
 * description (its wall/roof/trim clauses), because Reve emits the exterior
 * envelope as one object whose children are the windows/porch/stairs. */
export const BUILDING_LABEL_HINTS = [
  "house", "building", "villa", "cabin", "cottage", "structure", "home", "wing",
] as const;

/** Singularize a label word for matching ("walls" -> "wall"). Conservative:
 * only strips a trailing "s"/"es" when the base is a known token. */
function baseForms(word: string): string[] {
  const forms = [word];
  if (word.endsWith("es")) forms.push(word.slice(0, -2));
  if (word.endsWith("s")) forms.push(word.slice(0, -1));
  return forms;
}

/** Map a Reve region label (e.g. "<walls 1>", "<lounge_chairs 2>") to a
 * canonical SemanticClass, or null if unrecognized. */
export function matchSemantic(label: string): SemanticClass | null {
  const words = (label.toLowerCase().match(/[a-z_]+/g) ?? []);
  for (const w of words) {
    for (const form of baseForms(w)) {
      if ((SEMANTICS as readonly string[]).includes(form)) return form as SemanticClass;
      if (form in ALIASES) return ALIASES[form];
    }
  }
  return null;
}

export function isBuildingLabel(label: string): boolean {
  const low = label.toLowerCase();
  return BUILDING_LABEL_HINTS.some((h) => low.includes(h));
}

/** Reve region_type level-of-detail hint per class (feeds create_layout). */
export type ReveRegionType =
  | "coarse_detail" | "medium_detail" | "fine_detail" | "text" | "hand" | "face";

export const REGION_TYPE_HINTS: Record<SemanticClass, ReveRegionType> = {
  wall: "coarse_detail", roof: "coarse_detail", ground: "coarse_detail",
  sky: "coarse_detail", water: "coarse_detail", context: "coarse_detail",
  floor: "coarse_detail", ceiling: "coarse_detail", paving: "medium_detail",
  glazing: "medium_detail", door: "medium_detail", vegetation: "medium_detail",
  furniture: "medium_detail", vehicle: "medium_detail", fixture: "fine_detail",
  person: "face", text: "text",
};

/** UI layer type per class — drives which edit surface the layer panel shows. */
export type LayerType = "base" | "surface" | "object" | "opening" | "lighting" | "sky" | "text";

export const LAYER_TYPE_DEFAULTS: Record<SemanticClass, LayerType> = {
  wall: "surface", roof: "surface", floor: "surface", ceiling: "surface",
  ground: "surface", paving: "surface", water: "surface",
  glazing: "opening", door: "opening",
  furniture: "object", vehicle: "object", person: "object", vegetation: "object",
  fixture: "lighting", sky: "sky", text: "text", context: "surface",
};

/** Material facets of a building-envelope (context) region — each maps to a
 * clause the change-command rewrites, so "click the building, change the roof"
 * works even when wall/roof/trim aren't separate Reve regions. */
export type EnvelopeFacet = "cladding" | "roof" | "trim" | "foundation";

export const ENVELOPE_FACETS: readonly EnvelopeFacet[] = [
  "cladding", "roof", "trim", "foundation",
] as const;

export const FACET_LABEL: Record<EnvelopeFacet, string> = {
  cladding: "Walls / cladding",
  roof: "Roof",
  trim: "Trim & details",
  foundation: "Base / foundation",
};
