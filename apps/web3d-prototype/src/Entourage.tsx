import { Suspense, useLayoutEffect, useMemo, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { Billboard, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { useStore, type EntItem } from "./state/store";
import {
  defsForKind,
  hashId,
  type EntKind,
  type EntourageDef,
} from "./lib/entourageAssets";

const MAX = 400;

// ---------------------------------------------------------------------------
// Public exports (unchanged signatures — NavBar + store depend on these).
// ---------------------------------------------------------------------------
// BASE_HEIGHT is the "natural" height (ft) a kind renders at when item-scale==1
// and entHeight[kind]==BASE_HEIGHT[kind]. Real GLB species each normalize to
// their own baseHeightFt internally; this map only drives the legacy scale math
// and the NavBar default, so it stays a single representative number per kind.
export const BASE_HEIGHT: Record<string, number> = { tree: 24, bush: 4, person: 6 };

// height slider range (ft) per asset — unchanged.
export const ENT_RANGE: Record<string, [number, number]> = {
  tree: [3, 30],
  bush: [0.5, 5],
  person: [5, 6],
};

export type EntAsset = { id: string; label: string };
export const ENT_ASSETS: EntAsset[] = [
  { id: "tree", label: "Tree" },
  { id: "bush", label: "Bush" },
  { id: "person", label: "Person" },
];

// ---------------------------------------------------------------------------
// Procedural fallbacks (used only if a kind has no real defs / a GLB is absent).
// ---------------------------------------------------------------------------
const trunkGeo = new THREE.CylinderGeometry(0.4, 0.6, 6, 6).translate(0, 3, 0);
const foliageGeo = new THREE.IcosahedronGeometry(5, 1).translate(0, 10, 0);
const bushGeo = new THREE.IcosahedronGeometry(2.3, 1).translate(0, 2.3, 0);
const barkMat = new THREE.MeshStandardMaterial({ color: "#6b513a", roughness: 1, flatShading: true });
const leafMat = new THREE.MeshStandardMaterial({ color: "#5f7d44", roughness: 1, flatShading: true });
const bushFallbackMat = new THREE.MeshStandardMaterial({ color: "#6b8a4c", roughness: 1, flatShading: true });
// Fallback "GLB-equivalent" heights (model units) so procedural + real share scale math.
const FALLBACK: Record<EntKind, { geos: THREE.BufferGeometry[]; mats: THREE.Material[]; heightUnits: number; baseY: number }> = {
  tree: { geos: [trunkGeo, foliageGeo], mats: [barkMat, leafMat], heightUnits: 15, baseY: 0 },
  bush: { geos: [bushGeo], mats: [bushFallbackMat], heightUnits: 4.6, baseY: 0 },
  person: { geos: [], mats: [], heightUnits: 6, baseY: 0 },
};

// ---------------------------------------------------------------------------
// Shared scratch + helpers
// ---------------------------------------------------------------------------
const _dummy = new THREE.Object3D();
const _itemMat = new THREE.Matrix4();
const _outMat = new THREE.Matrix4();

/** Items of `kind` deterministically assigned to species index `idx` of `count`. */
function itemsForSpecies(items: EntItem[], idx: number, count: number): EntItem[] {
  if (count <= 1) return items;
  return items.filter((it) => hashId(it.id) % count === idx);
}

// ---------------------------------------------------------------------------
// A single GLB species → one <instancedMesh> per sub-mesh, sharing that
// sub-mesh's geometry + (fixed-up) material, with the sub-mesh's transform
// relative to the GLB root baked into every instance matrix.
// ---------------------------------------------------------------------------
type SubMesh = { geometry: THREE.BufferGeometry; material: THREE.Material; matrix: THREE.Matrix4 };

function extractSubMeshes(scene: THREE.Object3D): SubMesh[] {
  scene.updateMatrixWorld(true);
  const out: SubMesh[] = [];
  scene.traverse((obj) => {
    const m = obj as THREE.Mesh;
    if (!(m as THREE.Mesh).isMesh || !m.geometry) return;
    // World matrix relative to the GLB root (scene's own matrix is identity at load).
    const rel = m.matrixWorld.clone();
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    // glTF multi-material prims share geometry groups; for the simple Quaternius
    // meshes each mesh maps to one material. Clone+fix each material once.
    const mat = fixMaterial(mats[0] as THREE.Material);
    out.push({ geometry: m.geometry, material: mat, matrix: rel });
  });
  return out;
}

/** Make foliage render correctly + node-safe in all three renderers: double-sided,
 *  alpha-cutout (NOT transparent — keeps shadows + WebGPU happy). Leaves keep their
 *  textured StandardMaterial; we only flip side/alpha flags. */
function fixMaterial(src: THREE.Material): THREE.Material {
  const m = src.clone();
  m.side = THREE.DoubleSide;
  const std = m as THREE.MeshStandardMaterial;
  // Quaternius leaf cards ship as alphaMode BLEND with an RGBA cutout texture;
  // GLTFLoader marks those `transparent` (bark/trunk stays OPAQUE → not). Convert
  // blend → tested cutout so foliage casts clean shadows and doesn't z-sort.
  if (m.transparent && std.map) {
    m.transparent = false;
    m.alphaTest = Math.max(m.alphaTest, 0.4);
    m.depthWrite = true;
  }
  if (std.map) std.map.colorSpace = THREE.SRGBColorSpace;
  return m;
}

function SpeciesInstances({
  def,
  items,
  entFt,
}: {
  def: EntourageDef;
  items: EntItem[];
  entFt: number;
}) {
  const invalidate = useThree((st) => st.invalidate);
  const { scene } = useGLTF(def.url as string);
  const subs = useMemo(() => extractSubMeshes(scene), [scene]);
  const refs = useRef<(THREE.InstancedMesh | null)[]>([]);

  // feet → model-unit scale for THIS species, times entHeight ratio.
  const heightUnits = def.glbHeightUnits ?? 1;
  const baseY = def.glbBaseY ?? 0;
  const unitScale = (entFt / heightUnits); // entFt feet tall at item.scale 1

  useLayoutEffect(() => {
    subs.forEach((sub, si) => {
      const mesh = refs.current[si];
      if (!mesh) return;
      items.forEach((it, i) => {
        const s = unitScale * it.scale;
        // item transform: place at click point (seat base on ground), yaw, scale
        _dummy.position.set(it.pos[0], it.pos[1] - baseY * s, it.pos[2]);
        _dummy.rotation.set(0, it.rot, 0);
        _dummy.scale.setScalar(s);
        _dummy.updateMatrix();
        _itemMat.copy(_dummy.matrix);
        // compose item * subMeshLocal so multi-part GLBs assemble correctly
        _outMat.multiplyMatrices(_itemMat, sub.matrix);
        mesh.setMatrixAt(i, _outMat);
      });
      mesh.count = items.length;
      mesh.instanceMatrix.needsUpdate = true;
    });
    invalidate();
  }, [subs, items, unitScale, baseY, invalidate]);

  return (
    <>
      {subs.map((sub, si) => (
        <instancedMesh
          key={`${def.id}-${si}`}
          ref={(el) => {
            refs.current[si] = el;
          }}
          args={[sub.geometry, sub.material, MAX]}
          count={items.length}
          castShadow
          receiveShadow
          frustumCulled={false}
        />
      ))}
    </>
  );
}

/** All GLB species of one kind. Splits the kind's placed items across species by
 *  a stable hash of item.id, so the single NavBar button yields varied models. */
function GlbKind({ kind, items, entFt }: { kind: EntKind; items: EntItem[]; entFt: number }) {
  const defs = useMemo(() => defsForKind(kind).filter((d) => d.url), [kind]);
  if (defs.length === 0) return <ProceduralKind kind={kind} items={items} entFt={entFt} />;
  return (
    <>
      {defs.map((def, idx) => (
        <Suspense key={def.id} fallback={null}>
          <SpeciesInstances def={def} entFt={entFt} items={itemsForSpecies(items, idx, defs.length)} />
        </Suspense>
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Procedural fallback kind (cylinder/icosahedron) — same scale math as GLB.
// ---------------------------------------------------------------------------
function ProceduralKind({ kind, items, entFt }: { kind: EntKind; items: EntItem[]; entFt: number }) {
  const invalidate = useThree((st) => st.invalidate);
  const fb = FALLBACK[kind];
  const refs = useRef<(THREE.InstancedMesh | null)[]>([]);
  const unitScale = entFt / fb.heightUnits;

  useLayoutEffect(() => {
    fb.geos.forEach((_g, gi) => {
      const mesh = refs.current[gi];
      if (!mesh) return;
      items.forEach((it, i) => {
        const s = unitScale * it.scale;
        _dummy.position.set(it.pos[0], it.pos[1], it.pos[2]);
        _dummy.rotation.set(0, it.rot, 0);
        _dummy.scale.setScalar(s);
        _dummy.updateMatrix();
        mesh.setMatrixAt(i, _dummy.matrix);
      });
      mesh.count = items.length;
      mesh.instanceMatrix.needsUpdate = true;
    });
    invalidate();
  }, [items, unitScale, fb, invalidate]);

  return (
    <>
      {fb.geos.map((g, gi) => (
        <instancedMesh
          key={gi}
          ref={(el) => {
            refs.current[gi] = el;
          }}
          args={[g, fb.mats[gi], MAX]}
          count={items.length}
          castShadow
          receiveShadow
          frustumCulled={false}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// People — improved procedural cutout people (256x512), pose/color variants
// chosen per-item by hash(id). Billboard + alphaTest, unchanged from before.
// ---------------------------------------------------------------------------
const PERSON_PALETTES: { skin: string; shirt: string; pants: string; shirtDark: string; pantsDark: string }[] = [
  { skin: "#caa07a", shirt: "#3b5566", shirtDark: "#2c4150", pants: "#2d2f36", pantsDark: "#212329" },
  { skin: "#e0b48c", shirt: "#8a4b3b", shirtDark: "#6e3b2e", pants: "#3a3f4a", pantsDark: "#2b2f37" },
  { skin: "#9c7350", shirt: "#5a6b4a", shirtDark: "#46543a", pants: "#454952", pantsDark: "#34373e" },
  { skin: "#d9a47e", shirt: "#6d6f78", shirtDark: "#54565d", pants: "#23252b", pantsDark: "#191b1f" },
];

const _personTex: (THREE.Texture | null)[] = [];

/** Draw a reasonably-proportioned standing person (≈ canonical 7.5 heads).
 *  variant picks palette + a small stance offset (walking vs standing). */
function personTexture(variant: number): THREE.Texture {
  const cached = _personTex[variant];
  if (cached) return cached;
  const W = 256;
  const H = 512;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const x = c.getContext("2d")!;
  const p = PERSON_PALETTES[variant % PERSON_PALETTES.length];
  const walking = variant % 2 === 1;
  const cx = W / 2;

  // canonical proportions over usable height (margins top/bottom)
  const top = 24;
  const bottom = H - 12;
  const totalH = bottom - top;
  const headH = totalH * 0.13;
  const headR = headH * 0.5;
  const headCy = top + headR;
  const neckY = top + headH;
  const hipY = top + totalH * 0.52;
  const torsoH = hipY - neckY;
  const shoulderW = totalH * 0.20;

  const fillShade = (light: string, dark: string, drawer: (col: string, dx: number) => void) => {
    // 2-tone: dark base offset right, light on top → subtle volume
    drawer(dark, 3);
    drawer(light, 0);
  };

  // legs (behind torso)
  const legW = shoulderW * 0.34;
  const legTopY = hipY;
  const footY = bottom;
  const stride = walking ? totalH * 0.05 : 0;
  fillShade(p.pants, p.pantsDark, (col, dx) => {
    x.fillStyle = col;
    // left leg
    x.beginPath();
    x.moveTo(cx - legW * 1.05 + dx, legTopY);
    x.lineTo(cx - 1 + dx, legTopY);
    x.lineTo(cx - 1 - stride + dx, footY);
    x.lineTo(cx - legW * 1.05 - stride + dx, footY);
    x.closePath();
    x.fill();
    // right leg
    x.beginPath();
    x.moveTo(cx + 1 + dx, legTopY);
    x.lineTo(cx + legW * 1.05 + dx, legTopY);
    x.lineTo(cx + legW * 1.05 + stride + dx, footY);
    x.lineTo(cx + 1 + stride + dx, footY);
    x.closePath();
    x.fill();
  });
  // shoes
  x.fillStyle = "#1a1c20";
  x.fillRect(cx - legW * 1.1 - stride, footY - 8, legW * 1.1, 8);
  x.fillRect(cx + 1 + stride, footY - 8, legW * 1.1, 8);

  // torso (shirt) — tapered shoulders→hips
  fillShade(p.shirt, p.shirtDark, (col, dx) => {
    x.fillStyle = col;
    x.beginPath();
    x.moveTo(cx - shoulderW * 0.5 + dx, neckY);
    x.lineTo(cx + shoulderW * 0.5 + dx, neckY);
    x.lineTo(cx + shoulderW * 0.42 + dx, hipY);
    x.lineTo(cx - shoulderW * 0.42 + dx, hipY);
    x.closePath();
    x.fill();
  });

  // arms
  const armW = shoulderW * 0.22;
  const armLen = torsoH * 1.02;
  const armSwing = walking ? totalH * 0.04 : 0;
  fillShade(p.shirt, p.shirtDark, (col, dx) => {
    x.fillStyle = col;
    // left arm (forward when walking)
    x.beginPath();
    x.moveTo(cx - shoulderW * 0.5 + dx, neckY + 4);
    x.lineTo(cx - shoulderW * 0.5 + armW + dx, neckY + 4);
    x.lineTo(cx - shoulderW * 0.5 + armW + armSwing + dx, neckY + armLen);
    x.lineTo(cx - shoulderW * 0.5 + armSwing + dx, neckY + armLen);
    x.closePath();
    x.fill();
    // right arm (back when walking)
    x.beginPath();
    x.moveTo(cx + shoulderW * 0.5 - armW + dx, neckY + 4);
    x.lineTo(cx + shoulderW * 0.5 + dx, neckY + 4);
    x.lineTo(cx + shoulderW * 0.5 - armSwing + dx, neckY + armLen);
    x.lineTo(cx + shoulderW * 0.5 - armW - armSwing + dx, neckY + armLen);
    x.closePath();
    x.fill();
  });
  // hands
  x.fillStyle = p.skin;
  x.beginPath();
  x.arc(cx - shoulderW * 0.5 + armW * 0.5 + armSwing, neckY + armLen, armW * 0.5, 0, Math.PI * 2);
  x.fill();
  x.beginPath();
  x.arc(cx + shoulderW * 0.5 - armW * 0.5 - armSwing, neckY + armLen, armW * 0.5, 0, Math.PI * 2);
  x.fill();

  // neck
  x.fillStyle = p.skin;
  x.fillRect(cx - headR * 0.4, neckY - headH * 0.18, headR * 0.8, headH * 0.3);

  // head (skin) with subtle hair cap
  x.fillStyle = p.skin;
  x.beginPath();
  x.arc(cx, headCy, headR, 0, Math.PI * 2);
  x.fill();
  x.fillStyle = "#2b2620";
  x.beginPath();
  x.arc(cx, headCy - headR * 0.18, headR * 0.92, Math.PI * 1.08, Math.PI * 1.92);
  x.fill();

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  _personTex[variant] = tex;
  return tex;
}

function PersonBillboard({ item, s }: { item: EntItem; s: number }) {
  const f = s * item.scale;
  const variant = hashId(item.id) % PERSON_PALETTES.length;
  // texture is 256x512 (1:2), so the plane keeps that aspect: width = height/2.
  const h = 6 * f;
  const w = h * 0.5;
  return (
    <Billboard position={[item.pos[0], item.pos[1] + h * 0.5, item.pos[2]]} lockX lockZ>
      <mesh>
        <planeGeometry args={[w, h]} />
        <meshBasicMaterial map={personTexture(variant)} transparent alphaTest={0.5} toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
    </Billboard>
  );
}

// ---------------------------------------------------------------------------
// Top-level component — same signature/behaviour as before. Reads entourage +
// entHeight from the store, groups by kind, renders real GLB species + people.
// ---------------------------------------------------------------------------
export function Entourage() {
  const items = useStore((st) => st.entourage);
  const entHeight = useStore((st) => st.entHeight);

  const trees = useMemo(() => items.filter((i) => i.asset === "tree"), [items]);
  const bushes = useMemo(() => items.filter((i) => i.asset === "bush"), [items]);
  const people = useMemo(() => items.filter((i) => i.asset === "person"), [items]);

  // entHeight[kind] is the target real-world height (ft); fall back to defaults.
  const treeFt = entHeight.tree ?? 18;
  const bushFt = entHeight.bush ?? 3;
  const personFt = entHeight.person ?? 5.7;
  const sPerson = personFt / BASE_HEIGHT.person;

  return (
    <group>
      <Suspense fallback={null}>
        <GlbKind kind="tree" items={trees} entFt={treeFt} />
      </Suspense>
      <Suspense fallback={null}>
        <GlbKind kind="bush" items={bushes} entFt={bushFt} />
      </Suspense>
      {people.map((p) => (
        <PersonBillboard key={p.id} item={p} s={sPerson} />
      ))}
    </group>
  );
}

// Preload the species GLBs so placement is instant after first paint.
for (const def of [...defsForKind("tree"), ...defsForKind("bush")]) {
  if (def.url) useGLTF.preload(def.url);
}
