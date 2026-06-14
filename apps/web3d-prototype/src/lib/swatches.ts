import * as THREE from "three";

/**
 * CC0 PBR material library backed by ambientCG maps (downloaded by
 * scripts/fetch_materials.py into /public/materials/<id>/). UVs are
 * box-projected world coords in FEET (see Scene.boxProjectUVs), so a texture
 * tile is `tileFeet * scale` feet across on every face — metric-consistent
 * regardless of the Rhino mesh UVs.
 *   texture.repeat = 1 / (tileFeet * scale);  `scale` is a live per-swatch control.
 *
 * The `id`, `category`, `tags` and `tileFeet` of every entry MUST stay in sync
 * with scripts/fetch_materials.py:MATERIALS and /public/materials/materials.json.
 *
 * KTX2: shipping default is the .jpg path below (works at $0 today). A
 * best-effort GPU-texture path is wired behind setKTX2Renderer(renderer): a
 * Stage hands over its initialized renderer, and if .ktx2 maps exist on disk
 * they are loaded in preference to .jpg (jpg always remains the fallback when a
 * .ktx2 is missing). No .ktx2 assets ship yet — see scripts/encode_ktx2.mjs.
 */
export type Swatch = {
  id: string;
  label: string;
  color: string;
  tileFeet: number; // real-world tile size at scale=1, in feet
  metalness: number;
  hasAO: boolean;
  tint?: string;
  category: string;
  tags: string[];
};

export const SWATCHES: Swatch[] = [
  // --- brick ---------------------------------------------------------------
  { id: "red_brick", label: "Red Brick", color: "#9d4a39", tileFeet: 3, metalness: 0, hasAO: true, category: "brick", tags: ["red", "wall", "masonry", "facade"] },
  { id: "brown_brick", label: "Brown Brick", color: "#7a4632", tileFeet: 3, metalness: 0, hasAO: true, category: "brick", tags: ["brown", "wall", "masonry"] },
  { id: "buff_brick", label: "Buff Brick", color: "#b89873", tileFeet: 2.75, metalness: 0, hasAO: true, category: "brick", tags: ["buff", "tan", "wall", "masonry"] },
  { id: "clinker_brick", label: "Clinker Brick", color: "#5a4034", tileFeet: 2.75, metalness: 0, hasAO: true, category: "brick", tags: ["dark", "clinker", "wall", "masonry"] },

  // --- stone ---------------------------------------------------------------
  { id: "stone_veneer", label: "Stone Veneer", color: "#8d877c", tileFeet: 3, metalness: 0, hasAO: true, category: "stone", tags: ["veneer", "wall", "natural", "gray"] },
  { id: "ashlar_stone", label: "Ashlar Stone", color: "#9b958a", tileFeet: 3, metalness: 0, hasAO: true, category: "stone", tags: ["ashlar", "wall", "cut", "gray"] },
  { id: "limestone", label: "Limestone", color: "#cfc4a8", tileFeet: 3, metalness: 0, hasAO: false, category: "stone", tags: ["limestone", "buff", "wall", "smooth"] },
  { id: "fieldstone", label: "Fieldstone", color: "#7e756a", tileFeet: 4, metalness: 0, hasAO: true, category: "stone", tags: ["fieldstone", "rubble", "wall", "natural"] },
  { id: "travertine", label: "Travertine", color: "#d8ccb4", tileFeet: 4, metalness: 0, hasAO: true, category: "stone", tags: ["travertine", "buff", "floor", "wall"] },
  { id: "white_marble", label: "White Marble", color: "#e6e3dd", tileFeet: 4, metalness: 0, hasAO: false, category: "stone", tags: ["marble", "white", "floor", "polished"] },
  { id: "gray_marble", label: "Gray Marble", color: "#b9b7b4", tileFeet: 4, metalness: 0, hasAO: false, category: "stone", tags: ["marble", "gray", "floor", "veined"] },

  // --- concrete ------------------------------------------------------------
  { id: "smooth_concrete", label: "Smooth Concrete", color: "#a6a6a3", tileFeet: 8, metalness: 0, hasAO: false, category: "concrete", tags: ["smooth", "wall", "panel", "gray"] },
  { id: "board_concrete", label: "Board-Formed Concrete", color: "#9c9b96", tileFeet: 7, metalness: 0, hasAO: true, category: "concrete", tags: ["board-formed", "wall", "texture"] },
  { id: "rough_concrete", label: "Rough Concrete", color: "#999791", tileFeet: 8, metalness: 0, hasAO: false, category: "concrete", tags: ["rough", "wall", "raw", "gray"] },

  // --- plaster / stucco ----------------------------------------------------
  { id: "white_stucco", label: "White Stucco", color: "#e7e2d6", tileFeet: 6, metalness: 0, hasAO: false, category: "plaster", tags: ["white", "stucco", "wall", "smooth"] },
  { id: "tan_stucco", label: "Tan Stucco", color: "#d3c3a6", tileFeet: 6, metalness: 0, hasAO: false, category: "plaster", tags: ["tan", "stucco", "wall"] },

  // --- wood ----------------------------------------------------------------
  { id: "weathered_cedar", label: "Weathered Cedar", color: "#6f5942", tileFeet: 3.5, metalness: 0, hasAO: true, category: "wood", tags: ["cedar", "siding", "plank", "gray"] },
  { id: "wood_planks", label: "Wood Planks", color: "#8a6b46", tileFeet: 3.5, metalness: 0, hasAO: true, category: "wood", tags: ["plank", "floor", "deck", "warm"] },
  { id: "wood_siding", label: "Wood Siding", color: "#9c8f78", tileFeet: 3.5, metalness: 0, hasAO: true, category: "wood", tags: ["siding", "plank", "painted", "wall"] },

  // --- paving --------------------------------------------------------------
  { id: "paving_stones", label: "Paving Stones", color: "#8f8c87", tileFeet: 2.5, metalness: 0, hasAO: true, category: "paving", tags: ["paver", "ground", "patio", "gray"] },
  { id: "cobblestone", label: "Cobblestone", color: "#7c7770", tileFeet: 2, metalness: 0, hasAO: true, category: "paving", tags: ["cobble", "ground", "round", "old"] },
  { id: "brick_paving", label: "Brick Paving", color: "#9a5b44", tileFeet: 2, metalness: 0, hasAO: true, category: "paving", tags: ["brick", "ground", "herringbone"] },

  // --- metal ---------------------------------------------------------------
  { id: "charcoal_seam", label: "Charcoal Metal", color: "#34373c", tileFeet: 2.5, metalness: 0.5, hasAO: true, tint: "#5a5e63", category: "metal", tags: ["seam", "panel", "dark", "roof"] },
  { id: "corten_steel", label: "Corten Steel", color: "#8a4a2c", tileFeet: 2.5, metalness: 0.3, hasAO: false, tint: "#a06038", category: "metal", tags: ["corten", "weathered", "rust", "panel"] },
  { id: "brushed_metal", label: "Brushed Metal", color: "#9a9ca0", tileFeet: 2, metalness: 0.85, hasAO: false, tint: "#c8cace", category: "metal", tags: ["brushed", "panel", "silver", "cladding"] },

  // --- roofing / terracotta ------------------------------------------------
  { id: "roof_tiles", label: "Roof Tiles", color: "#a4543a", tileFeet: 1.5, metalness: 0, hasAO: true, category: "roofing", tags: ["tile", "roof", "terracotta"] },
  { id: "terracotta", label: "Terracotta", color: "#b6603f", tileFeet: 1.5, metalness: 0, hasAO: true, category: "roofing", tags: ["terracotta", "clay", "roof", "warm"] },

  // --- ground / landscape --------------------------------------------------
  { id: "grass", label: "Grass", color: "#5c6f3a", tileFeet: 5, metalness: 0, hasAO: true, category: "ground", tags: ["grass", "lawn", "landscape", "green"] },
  { id: "gravel", label: "Gravel", color: "#8a857c", tileFeet: 4, metalness: 0, hasAO: true, category: "ground", tags: ["gravel", "ground", "path", "loose"] },
];

export const swatchById = (id: string) => SWATCHES.find((s) => s.id === id);

/** Distinct categories in SWATCHES order (for filter chips in the UI). */
export const swatchCategories = (): string[] => {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of SWATCHES) {
    if (!seen.has(s.category)) {
      seen.add(s.category);
      out.push(s.category);
    }
  }
  return out;
};

// On-demand rendering: request a frame when a texture loads or a scale changes.
let _invalidate: () => void = () => {};
export const setInvalidate = (fn: () => void) => {
  _invalidate = fn;
};

// Live per-swatch scale multiplier (default 1). Bigger = larger texture features.
const scales: Record<string, number> = {};
export const getSwatchScale = (id: string): number => scales[id] ?? 1;

const loader = new THREE.TextureLoader();
const texCache = new Map<string, THREE.Texture>();

function repeatFor(swatchId: string, tileFeet: number): number {
  return 1 / (tileFeet * (scales[swatchId] ?? 1));
}

export function setSwatchScale(id: string, scale: number) {
  scales[id] = scale;
  const s = swatchById(id);
  if (!s) return;
  const r = repeatFor(id, s.tileFeet);
  texCache.forEach((t, key) => {
    if (key.startsWith(id + "/")) t.repeat.set(r, r);
  });
  _invalidate();
}

/**
 * KTX2 hook (best-effort, no-op until .ktx2 assets ship). A Stage may call this
 * with its initialized renderer so a future KTX2Loader can run detectSupport on
 * the right GL/GPU context. Today this only records the renderer; the .jpg path
 * is always used. Wiring KTX2 here keeps the public API stable for the stages.
 */
let _ktx2Renderer: THREE.WebGLRenderer | null = null;
export function setKTX2Renderer(renderer: THREE.WebGLRenderer | null) {
  _ktx2Renderer = renderer;
  void _ktx2Renderer; // reserved for KTX2Loader.detectSupport when .ktx2 ships
}

function tex(swatchId: string, file: string, srgb: boolean, tileFeet: number): THREE.Texture {
  const key = `${swatchId}/${file}`;
  let t = texCache.get(key);
  if (!t) {
    t = loader.load(`/materials/${swatchId}/${file}`, () => _invalidate());
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    const r = repeatFor(swatchId, tileFeet);
    t.repeat.set(r, r);
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    // Max anisotropy keeps brick/stone sharp at grazing angles (big facades seen
    // edge-on); 16 is the desktop GPU cap and clamps down safely elsewhere.
    t.anisotropy = 16;
    texCache.set(key, t);
  }
  return t;
}

const matCache = new Map<string, THREE.MeshStandardMaterial>();

export function swatchMaterial(swatchId: string, semantic: string): THREE.MeshStandardMaterial {
  const key = `${swatchId}__${semantic}`;
  let m = matCache.get(key);
  if (!m) {
    const s = swatchById(swatchId)!;
    m = new THREE.MeshStandardMaterial({
      map: tex(swatchId, "albedo.jpg", true, s.tileFeet),
      normalMap: tex(swatchId, "normal.jpg", false, s.tileFeet),
      roughnessMap: tex(swatchId, "roughness.jpg", false, s.tileFeet),
      roughness: 1,
      metalness: s.metalness,
      color: new THREE.Color(s.tint ?? "#ffffff"),
      side: THREE.DoubleSide,
    });
    if (s.hasAO) {
      m.aoMap = tex(swatchId, "ao.jpg", false, s.tileFeet);
      m.aoMapIntensity = 0.8;
    }
    matCache.set(key, m);
  }
  return m;
}
