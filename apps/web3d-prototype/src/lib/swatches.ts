import * as THREE from "three";

/**
 * Swatch identities from spike/multiview_apply.py:SWATCH_PROMPTS, backed by CC0
 * PBR maps from ambientCG. UVs are box-projected world coords in FEET (see
 * Scene.boxProjectUVs), so a texture tile is `tileFeet * scale` feet across on
 * every face — metric-consistent regardless of the Rhino mesh UVs.
 * texture.repeat = 1 / (tileFeet * scale); `scale` is a live per-swatch control.
 */
export type Swatch = {
  id: string;
  label: string;
  color: string;
  tileFeet: number; // real-world tile size at scale=1, in feet
  metalness: number;
  hasAO: boolean;
  tint?: string;
};

export const SWATCHES: Swatch[] = [
  { id: "travertine", label: "Travertine", color: "#d8ccb4", tileFeet: 4, metalness: 0.0, hasAO: true },
  { id: "red_brick", label: "Red Brick", color: "#9d4a39", tileFeet: 3, metalness: 0.0, hasAO: true },
  { id: "white_stucco", label: "White Stucco", color: "#e7e2d6", tileFeet: 5, metalness: 0.0, hasAO: false },
  { id: "weathered_cedar", label: "Weathered Cedar", color: "#6f5942", tileFeet: 2.5, metalness: 0.0, hasAO: true },
  { id: "charcoal_seam", label: "Charcoal Metal", color: "#34373c", tileFeet: 3, metalness: 0.5, hasAO: true, tint: "#5a5e63" },
];

export const swatchById = (id: string) => SWATCHES.find((s) => s.id === id);

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
