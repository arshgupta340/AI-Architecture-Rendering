import { useLayoutEffect, useMemo, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { Billboard } from "@react-three/drei";
import * as THREE from "three";
import { useStore, type EntItem } from "./state/store";

const MAX = 400;

// ---- procedural low-poly assets (model units = feet) ----
// Geometry is authored so its base sits at y=0; BASE_HEIGHT is its natural top
// (in feet) at item-scale 1, so a real-world target height maps to a scale.
const trunkGeo = new THREE.CylinderGeometry(0.4, 0.6, 6, 6).translate(0, 3, 0);
const foliageGeo = new THREE.IcosahedronGeometry(5, 1).translate(0, 10, 0);
const bushGeo = new THREE.IcosahedronGeometry(2.3, 1).translate(0, 2.3, 0);

export const BASE_HEIGHT: Record<string, number> = { tree: 15, bush: 4.6, person: 6 };
// height slider range (ft) per asset
export const ENT_RANGE: Record<string, [number, number]> = {
  tree: [3, 30],
  bush: [0.5, 5],
  person: [5, 6],
};

const barkMat = new THREE.MeshStandardMaterial({ color: "#6b513a", roughness: 1, flatShading: true });
const leafMat = new THREE.MeshStandardMaterial({ color: "#5f7d44", roughness: 1, flatShading: true });
const bushMat = new THREE.MeshStandardMaterial({ color: "#6b8a4c", roughness: 1, flatShading: true });

export type EntAsset = { id: string; label: string };
export const ENT_ASSETS: EntAsset[] = [
  { id: "tree", label: "Tree" },
  { id: "bush", label: "Bush" },
  { id: "person", label: "Person" },
];

let _personTex: THREE.Texture | null = null;
function personTexture(): THREE.Texture {
  if (_personTex) return _personTex;
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 256;
  const x = c.getContext("2d")!;
  x.fillStyle = "#363b45";
  x.beginPath();
  x.arc(64, 46, 20, 0, Math.PI * 2);
  x.fill();
  x.beginPath();
  x.moveTo(42, 70);
  x.lineTo(86, 70);
  x.lineTo(80, 178);
  x.lineTo(48, 178);
  x.closePath();
  x.fill();
  x.fillRect(50, 176, 11, 74);
  x.fillRect(67, 176, 11, 74);
  _personTex = new THREE.CanvasTexture(c);
  _personTex.colorSpace = THREE.SRGBColorSpace;
  return _personTex;
}

const _dummy = new THREE.Object3D();
function writeMatrices(mesh: THREE.InstancedMesh | null, items: EntItem[], s: number) {
  if (!mesh) return;
  items.forEach((it, i) => {
    _dummy.position.set(it.pos[0], it.pos[1], it.pos[2]);
    _dummy.rotation.set(0, it.rot, 0);
    _dummy.scale.setScalar(s * it.scale);
    _dummy.updateMatrix();
    mesh.setMatrixAt(i, _dummy.matrix);
  });
  mesh.count = items.length;
  mesh.instanceMatrix.needsUpdate = true;
}

function PersonBillboard({ item, s }: { item: EntItem; s: number }) {
  const f = s * item.scale;
  return (
    <Billboard position={[item.pos[0], item.pos[1] + 3 * f, item.pos[2]]} lockX lockZ>
      <mesh>
        <planeGeometry args={[3 * f, 6 * f]} />
        <meshBasicMaterial map={personTexture()} transparent alphaTest={0.5} toneMapped={false} />
      </mesh>
    </Billboard>
  );
}

export function Entourage() {
  const invalidate = useThree((st) => st.invalidate);
  const items = useStore((st) => st.entourage);
  const entHeight = useStore((st) => st.entHeight);
  const trees = useMemo(() => items.filter((i) => i.asset === "tree"), [items]);
  const bushes = useMemo(() => items.filter((i) => i.asset === "bush"), [items]);
  const people = useMemo(() => items.filter((i) => i.asset === "person"), [items]);

  const sTree = (entHeight.tree ?? 18) / BASE_HEIGHT.tree;
  const sBush = (entHeight.bush ?? 3) / BASE_HEIGHT.bush;
  const sPerson = (entHeight.person ?? 5.7) / BASE_HEIGHT.person;

  const trunkRef = useRef<THREE.InstancedMesh>(null);
  const foliageRef = useRef<THREE.InstancedMesh>(null);
  const bushRef = useRef<THREE.InstancedMesh>(null);

  useLayoutEffect(() => {
    writeMatrices(trunkRef.current, trees, sTree);
    writeMatrices(foliageRef.current, trees, sTree);
    invalidate();
  }, [trees, sTree, invalidate]);
  useLayoutEffect(() => {
    writeMatrices(bushRef.current, bushes, sBush);
    invalidate();
  }, [bushes, sBush, invalidate]);

  return (
    <group>
      <instancedMesh ref={trunkRef} args={[trunkGeo, barkMat, MAX]} count={trees.length} castShadow receiveShadow frustumCulled={false} />
      <instancedMesh ref={foliageRef} args={[foliageGeo, leafMat, MAX]} count={trees.length} castShadow receiveShadow frustumCulled={false} />
      <instancedMesh ref={bushRef} args={[bushGeo, bushMat, MAX]} count={bushes.length} castShadow receiveShadow frustumCulled={false} />
      {people.map((p) => (
        <PersonBillboard key={p.id} item={p} s={sPerson} />
      ))}
    </group>
  );
}
