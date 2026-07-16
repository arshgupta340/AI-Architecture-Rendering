/**
 * Material prompt scaffolds — the 29 CC0 swatches from
 * apps/web3d-prototype/src/lib/swatches.ts, re-expressed as Reve change-command
 * descriptions. `id`s are kept IDENTICAL so a material picked in Reve Canvas is
 * later replayable as a PBR assignment in the 3D app (the convergence contract).
 *
 * `prompt` is a concise architectural noun phrase Reve applies to a region's
 * surface via `create_layout` {op:"change", new_description}. `appliesTo` lists
 * the SemanticClass / envelope facets the swatch is offered for in the UI.
 */
import type { SemanticClass, EnvelopeFacet } from "./semantics";

export type MaterialTarget = SemanticClass | EnvelopeFacet;

export interface MaterialScaffold {
  id: string;
  label: string;
  category: string;
  color: string; // albedo hint, mirrors swatches.ts
  prompt: string; // Reve change-command surface description
  appliesTo: MaterialTarget[];
  tags: string[];
}

export const MATERIALS: MaterialScaffold[] = [
  // --- brick ---------------------------------------------------------------
  { id: "red_brick", label: "Red Brick", category: "brick", color: "#9d4a39",
    prompt: "red clay brick masonry in running bond, tumbled texture, light mortar joints",
    appliesTo: ["wall", "cladding"], tags: ["red", "masonry", "facade"] },
  { id: "brown_brick", label: "Brown Brick", category: "brick", color: "#7a4632",
    prompt: "brown clay brick masonry, running bond, weathered texture, recessed mortar",
    appliesTo: ["wall", "cladding"], tags: ["brown", "masonry"] },
  { id: "buff_brick", label: "Buff Brick", category: "brick", color: "#b89873",
    prompt: "buff tan brick masonry, smooth face, fine light mortar joints",
    appliesTo: ["wall", "cladding"], tags: ["buff", "tan", "masonry"] },
  { id: "clinker_brick", label: "Clinker Brick", category: "brick", color: "#5a4034",
    prompt: "dark clinker brick masonry, irregular scorched texture, deep mortar shadows",
    appliesTo: ["wall", "cladding"], tags: ["dark", "clinker", "masonry"] },

  // --- stone ---------------------------------------------------------------
  { id: "stone_veneer", label: "Stone Veneer", category: "stone", color: "#8d877c",
    prompt: "grey natural stone veneer, dry-stacked coursed ledgestone, tight joints",
    appliesTo: ["wall", "cladding", "foundation"], tags: ["veneer", "natural", "gray"] },
  { id: "ashlar_stone", label: "Ashlar Stone", category: "stone", color: "#9b958a",
    prompt: "grey ashlar cut-stone masonry, precise rectangular coursing, fine joints",
    appliesTo: ["wall", "cladding", "foundation"], tags: ["ashlar", "cut", "gray"] },
  { id: "limestone", label: "Limestone", category: "stone", color: "#cfc4a8",
    prompt: "buff limestone cladding, smooth honed panels, subtle natural veining",
    appliesTo: ["wall", "cladding", "floor"], tags: ["limestone", "buff", "smooth"] },
  { id: "fieldstone", label: "Fieldstone", category: "stone", color: "#7e756a",
    prompt: "natural fieldstone rubble masonry, rounded stones, irregular mortar",
    appliesTo: ["wall", "cladding", "foundation"], tags: ["fieldstone", "rubble", "natural"] },
  { id: "travertine", label: "Travertine", category: "stone", color: "#d8ccb4",
    prompt: "honed cream travertine stone cladding with subtle horizontal banding, matte finish",
    appliesTo: ["wall", "cladding", "floor", "paving"], tags: ["travertine", "buff", "stone"] },
  { id: "white_marble", label: "White Marble", category: "stone", color: "#e6e3dd",
    prompt: "polished white marble with soft grey veining, high-end honed finish",
    appliesTo: ["floor", "wall", "cladding"], tags: ["marble", "white", "polished"] },
  { id: "gray_marble", label: "Gray Marble", category: "stone", color: "#9a9992",
    prompt: "grey marble with dramatic dark veining, polished finish",
    appliesTo: ["floor", "wall", "cladding"], tags: ["marble", "gray", "veined"] },

  // --- concrete ------------------------------------------------------------
  { id: "smooth_concrete", label: "Smooth Concrete", category: "concrete", color: "#a6a29b",
    prompt: "smooth grey architectural concrete panels, crisp form-tie joints, matte",
    appliesTo: ["wall", "cladding", "floor"], tags: ["smooth", "panel", "gray"] },
  { id: "board_concrete", label: "Board-Formed Concrete", category: "concrete", color: "#9c968d",
    prompt: "board-formed concrete, horizontal timber-grain texture imprinted, grey",
    appliesTo: ["wall", "cladding"], tags: ["board-formed", "texture"] },
  { id: "rough_concrete", label: "Rough Concrete", category: "concrete", color: "#918d86",
    prompt: "raw board-marked grey concrete, rough cast texture, industrial",
    appliesTo: ["wall", "cladding"], tags: ["rough", "raw", "gray"] },

  // --- plaster -------------------------------------------------------------
  { id: "white_stucco", label: "White Stucco", category: "plaster", color: "#ece7de",
    prompt: "smooth white stucco render, clean matte plaster finish",
    appliesTo: ["wall", "cladding", "ceiling"], tags: ["white", "stucco", "smooth"] },
  { id: "tan_stucco", label: "Tan Stucco", category: "plaster", color: "#c9b596",
    prompt: "warm tan stucco render, lightly troweled matte plaster",
    appliesTo: ["wall", "cladding"], tags: ["tan", "stucco"] },

  // --- wood ----------------------------------------------------------------
  { id: "weathered_cedar", label: "Weathered Cedar", category: "wood", color: "#8f8578",
    prompt: "weathered grey cedar shake siding, natural silvered patina",
    appliesTo: ["wall", "cladding"], tags: ["cedar", "siding", "gray"] },
  { id: "wood_planks", label: "Wood Planks", category: "wood", color: "#a9793f",
    prompt: "warm wide-plank wood flooring, matte natural oil finish, visible grain",
    appliesTo: ["floor", "paving"], tags: ["plank", "deck", "warm"] },
  { id: "wood_siding", label: "Wood Siding", category: "wood", color: "#b08b5a",
    prompt: "vertical wood board-and-batten siding, warm stained timber",
    appliesTo: ["wall", "cladding"], tags: ["siding", "plank", "wall"] },

  // --- paving --------------------------------------------------------------
  { id: "paving_stones", label: "Paving Stones", category: "paving", color: "#9a958c",
    prompt: "grey stone pavers in a regular grid, fine sand joints",
    appliesTo: ["paving", "ground"], tags: ["paver", "patio", "gray"] },
  { id: "cobblestone", label: "Cobblestone", category: "paving", color: "#7d786f",
    prompt: "old rounded cobblestone paving, irregular set stones, aged",
    appliesTo: ["paving", "ground"], tags: ["cobble", "round", "old"] },
  { id: "brick_paving", label: "Brick Paving", category: "paving", color: "#9a5942",
    prompt: "clay brick paving in herringbone pattern, warm red-brown",
    appliesTo: ["paving", "ground"], tags: ["brick", "herringbone"] },

  // --- metal ---------------------------------------------------------------
  { id: "charcoal_seam", label: "Charcoal Metal", category: "metal", color: "#3b3d40",
    prompt: "standing-seam charcoal grey metal roofing, crisp vertical seams, low sheen",
    appliesTo: ["roof", "wall", "cladding"], tags: ["seam", "dark", "roof"] },
  { id: "corten_steel", label: "Corten Steel", category: "metal", color: "#8a4b32",
    prompt: "weathered corten steel panels, rich rust-orange patina, matte",
    appliesTo: ["wall", "cladding", "roof"], tags: ["corten", "rust", "panel"] },
  { id: "brushed_metal", label: "Brushed Metal", category: "metal", color: "#b8b8b5",
    prompt: "brushed silver aluminium cladding panels, fine directional grain",
    appliesTo: ["wall", "cladding"], tags: ["brushed", "silver", "cladding"] },

  // --- roofing -------------------------------------------------------------
  { id: "roof_tiles", label: "Roof Tiles", category: "roofing", color: "#a5502f",
    prompt: "terracotta clay roof tiles, warm orange, regular barrel pattern",
    appliesTo: ["roof"], tags: ["tile", "terracotta"] },
  { id: "terracotta", label: "Terracotta", category: "roofing", color: "#b0623a",
    prompt: "warm terracotta clay tile roofing, mediterranean barrel tiles",
    appliesTo: ["roof"], tags: ["terracotta", "clay", "warm"] },

  // --- ground --------------------------------------------------------------
  { id: "grass", label: "Grass", category: "ground", color: "#5f7b43",
    prompt: "lush manicured green lawn, healthy summer grass",
    appliesTo: ["ground"], tags: ["grass", "lawn", "green"] },
  { id: "gravel", label: "Gravel", category: "ground", color: "#9c968a",
    prompt: "loose pale gravel groundcover, fine crushed stone",
    appliesTo: ["ground", "paving"], tags: ["gravel", "path", "loose"] },
];

const BY_ID = new Map(MATERIALS.map((m) => [m.id, m]));
export const getMaterial = (id: string): MaterialScaffold | undefined => BY_ID.get(id);

/** Materials offered for a given target (semantic class or envelope facet). */
export function materialsFor(target: MaterialTarget): MaterialScaffold[] {
  return MATERIALS.filter((m) => m.appliesTo.includes(target));
}

/** Non-material edit scaffolds (lighting / sky presets) — whole-image prompt
 * augmentations, mirroring the web3d MOODS. */
export const LIGHTING_PRESETS: { id: string; label: string; prompt: string }[] = [
  { id: "golden_hour", label: "Golden hour", prompt: "golden-hour lighting, low warm sun, long soft shadows" },
  { id: "overcast", label: "Overcast", prompt: "soft overcast daylight, even diffuse shadows, cool white balance" },
  { id: "dusk", label: "Dusk", prompt: "photographed at dusk, warm interior lights glowing, deep blue sky" },
  { id: "midday", label: "Bright midday", prompt: "bright clear midday sun, crisp shadows, blue sky" },
];

export const SKY_PRESETS: { id: string; label: string; prompt: string }[] = [
  { id: "clear_blue", label: "Clear blue", prompt: "clear deep-blue sky, a few high wispy clouds" },
  { id: "dramatic", label: "Dramatic", prompt: "dramatic sky with sculpted clouds, warm low sun breaking through" },
  { id: "clouded", label: "Soft clouds", prompt: "soft scattered cumulus clouds, gentle blue sky" },
];
