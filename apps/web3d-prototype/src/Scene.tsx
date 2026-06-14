import { useEffect, useMemo, useRef } from "react";
import { useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { useStore, type NavMode, type SavedView } from "./state/store";
import { swatchMaterial, setInvalidate } from "./lib/swatches";
import { WalkControls } from "./Walk";
import { PathTracer } from "./PathTracer";
import { Entourage } from "./Entourage";
import { SolarSky } from "./SolarSky";
import { GeoTiles } from "./GeoTiles";

// Effective Google key: the in-app field wins, else a build-time .env.local fallback.
const ENV_GOOGLE_KEY = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined) ?? "";

const MODEL_URL = "/model/house.glb";
const CAMERA_URL = "/model/camera.json";

// Element classes that count as "the building" (exclude ground/paving/site/massing).
const BUILDING = new Set([
  "wall", "wall_interior", "roof", "window", "door", "floor", "foundation", "trim", "stair",
]);
const HILITE = new THREE.Color("#2f6df6");
const BLACK = new THREE.Color("#000000");

// Shared architectural glass — ONE MeshPhysicalMaterial instance across every
// window pane (transmission does an extra render pass per *distinct* material, so
// sharing keeps it to a single pass). Real refraction + Fresnel reflections from
// scene.environment (the SolarSky IBL) replace the flat opaque GLTF panel — the
// single biggest "this is a toy model" tell. Faint cool tint like real float glass.
const GLASS = new THREE.MeshPhysicalMaterial({
  transmission: 1,
  roughness: 0.07,
  metalness: 0,
  ior: 1.5,
  thickness: 0.2,
  envMapIntensity: 1.25,
  color: new THREE.Color("#e9eff1"),
  side: THREE.DoubleSide,
});

// Resolve a mesh's element class from the nearest ancestor carrying `semantic`.
function semOf(o: THREE.Object3D): string {
  for (let n: THREE.Object3D | null = o; n; n = n.parent) {
    const s = (n.userData as any)?.semantic as string | undefined;
    if (s) return s;
  }
  return "other";
}

// Box-projected world-space UVs (in feet) so texture scale is metric-consistent
// across faces, independent of Rhino's per-face UVs.
const _v = new THREE.Vector3();
const _n = new THREE.Vector3();
const _nm = new THREE.Matrix3();
function boxProjectUVs(mesh: THREE.Mesh) {
  const g = mesh.geometry;
  const pos = g.attributes.position as THREE.BufferAttribute;
  const nor = g.attributes.normal as THREE.BufferAttribute;
  if (!pos || !nor) return;
  _nm.getNormalMatrix(mesh.matrixWorld);
  const uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    _v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
    _n.fromBufferAttribute(nor, i).applyMatrix3(_nm);
    const ax = Math.abs(_n.x);
    const ay = Math.abs(_n.y);
    const az = Math.abs(_n.z);
    let u: number;
    let w: number;
    if (ax >= ay && ax >= az) {
      u = _v.z;
      w = _v.y;
    } else if (ay >= ax && ay >= az) {
      u = _v.x;
      w = _v.z;
    } else {
      u = _v.x;
      w = _v.y;
    }
    uv[i * 2] = u;
    uv[i * 2 + 1] = w;
  }
  const attr = new THREE.BufferAttribute(uv, 2);
  g.setAttribute("uv", attr);
  g.setAttribute("uv1", attr);
}

const zUpToY = (p: number[]): [number, number, number] => [p[0], p[2], -p[1]];

export function Scene() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);
  const controls = useRef<any>(null);
  useEffect(() => setInvalidate(invalidate), [invalidate]);
  const { scene } = useGLTF(MODEL_URL);

  const setModel = useStore((s) => s.setModel);
  const select = useStore((s) => s.select);
  const layers = useStore((s) => s.layers);
  const selected = useStore((s) => s.selected);
  const ready = useStore((s) => s.ready);
  const mode = useStore((s) => s.mode);
  const setPresets = useStore((s) => s.setPresets);
  const saveNonce = useStore((s) => s.saveNonce);
  const addView = useStore((s) => s.addView);
  const goto = useStore((s) => s.goto);
  const clearGoto = useStore((s) => s.clearGoto);
  const rendering = useStore((s) => s.rendering);
  const setSiteAnchor = useStore((s) => s.setSiteAnchor);
  const geoEnabled = useStore((s) => s.geo.enabled);
  const geoApiKey = useStore((s) => s.geo.apiKey);
  const geoHideSite = useStore((s) => s.geo.hideRhinoSite);
  const geoKey = geoApiKey || ENV_GOOGLE_KEY;

  // One-time prep: box UVs, per-mesh material clone, semantic map, building bbox.
  const buildingBox = useMemo(() => {
    scene.updateMatrixWorld(true);
    const bySem = new Map<string, THREE.Mesh[]>();
    const box = new THREE.Box3();
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.receiveShadow = true;
      boxProjectUVs(m);
      const sem = semOf(m);
      // Windows → shared physical glass (no opaque shadow). Everything else keeps
      // a per-mesh clone of its GLTF material so swatches can override per element.
      let mat: THREE.Material;
      if (sem === "window") {
        mat = GLASS;
        m.castShadow = false;
      } else {
        const src = (Array.isArray(m.material) ? m.material[0] : m.material) as THREE.MeshStandardMaterial;
        const cloned = src.clone();
        cloned.side = THREE.DoubleSide;
        mat = cloned;
        m.castShadow = true;
      }
      m.material = mat;
      (m.userData as any).originalMat = mat;
      (bySem.get(sem) ?? bySem.set(sem, []).get(sem)!).push(m);
      if (BUILDING.has(sem) && m.geometry) {
        m.geometry.computeBoundingBox();
        if (m.geometry.boundingBox) {
          box.union(m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld));
        }
      }
    });
    setModel(bySem);
    return box;
  }, [scene, setModel]);

  const center = useMemo(() => buildingBox.getCenter(new THREE.Vector3()), [buildingBox]);
  const radius = useMemo(
    () => (buildingBox.isEmpty() ? 200 : buildingBox.getBoundingSphere(new THREE.Sphere()).radius),
    [buildingBox],
  );

  // overview camera (also preset #1)
  const overview = useMemo(() => {
    const dist = (radius / Math.sin(THREE.MathUtils.degToRad(45) / 2)) * 1.05;
    const dir = new THREE.Vector3(0.7, 0.45, 1).normalize();
    return center.clone().add(dir.multiplyScalar(dist));
  }, [center, radius]);

  // Frame the building once, and seed preset views (Overview + Rhino).
  useEffect(() => {
    if (buildingBox.isEmpty()) return;
    // Anchor the real-world site under the building's ground-centre (feet world-space).
    setSiteAnchor([center.x, buildingBox.min.y, center.z]);
    camera.fov = 45;
    camera.aspect = size.width / size.height;
    camera.near = 0.1;
    camera.far = 20000;
    camera.position.copy(overview);
    camera.up.set(0, 1, 0);
    camera.lookAt(center);
    camera.updateProjectionMatrix();
    if (controls.current) {
      controls.current.target.copy(center);
      controls.current.update();
    }
    const presets: SavedView[] = [
      { id: "overview", label: "Overview", pos: [overview.x, overview.y, overview.z], target: [center.x, center.y, center.z], preset: true },
    ];
    fetch(CAMERA_URL)
      .then((r) => r.json())
      .then((cam) => {
        setPresets([
          ...presets,
          { id: "rhino", label: "Rhino view", pos: zUpToY(cam.location), target: zUpToY(cam.target), preset: true },
        ]);
      })
      .catch(() => setPresets(presets));
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildingBox]);

  // Material + selection-highlight sync.
  useEffect(() => {
    const map = useStore.getState().meshesBySemantic;
    map.forEach((meshes, sem) => {
      const layer = layers.find((l) => l.semantic === sem && l.visible);
      const hot = sem === selected;
      meshes.forEach((mesh) => {
        const base = layer
          ? swatchMaterial(layer.swatch, sem)
          : (mesh.userData.originalMat as THREE.MeshStandardMaterial);
        if (mesh.material !== base) mesh.material = base;
        const mm = mesh.material as THREE.MeshStandardMaterial;
        mm.emissive = hot ? HILITE : BLACK;
        mm.emissiveIntensity = hot ? 0.35 : 0;
      });
    });
    invalidate();
  }, [layers, selected, ready, invalidate]);

  // When real-world tiles are on, hide the Rhino ground/site/topo so the actual
  // terrain shows through (the building + its own floor/foundation stay).
  useEffect(() => {
    const hide = geoEnabled && geoHideSite;
    useStore.getState().meshesBySemantic.forEach((meshes, sem) => {
      if (!BUILDING.has(sem)) meshes.forEach((m) => (m.visible = !hide));
    });
    invalidate();
  }, [geoEnabled, geoHideSite, ready, invalidate]);

  // Capture current camera when the HUD asks (saveNonce bumps).
  const lastSave = useRef(0);
  useEffect(() => {
    if (saveNonce === 0 || saveNonce === lastSave.current) return;
    lastSave.current = saveNonce;
    const p = camera.position;
    const t = new THREE.Vector3();
    if (controls.current && mode === "orbit") t.copy(controls.current.target);
    else camera.getWorldDirection(t).multiplyScalar(radius).add(p);
    const n = useStore.getState().views.length + 1;
    addView({ id: `v${Date.now()}`, label: `View ${n}`, pos: [p.x, p.y, p.z], target: [t.x, t.y, t.z] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveNonce]);

  // Jump to a requested view.
  useEffect(() => {
    if (!goto) return;
    camera.position.set(goto.pos[0], goto.pos[1], goto.pos[2]);
    const t = new THREE.Vector3(goto.target[0], goto.target[1], goto.target[2]);
    if (controls.current && mode === "orbit") {
      controls.current.target.copy(t);
      controls.current.update();
    } else {
      camera.lookAt(t);
    }
    camera.updateProjectionMatrix();
    invalidate();
    clearGoto();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goto]);

  // Returning to orbit from walk: pivot in front of the camera (avoid origin snap).
  const prevMode = useRef<NavMode | null>(null);
  useEffect(() => {
    if (prevMode.current && prevMode.current !== "orbit" && mode === "orbit" && controls.current) {
      const t = new THREE.Vector3();
      camera.getWorldDirection(t).multiplyScalar(radius).add(camera.position);
      controls.current.target.copy(t);
      controls.current.update();
      invalidate();
    }
    prevMode.current = mode;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const onPick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    const placeAsset = useStore.getState().placeAsset;
    if (placeAsset) {
      const p = e.point;
      useStore.getState().addEnt({
        id: `e${Date.now()}_${Math.floor(Math.random() * 1e4)}`,
        asset: placeAsset,
        pos: [p.x, p.y, p.z],
        rot: Math.random() * Math.PI * 2,
        scale: 0.8 + Math.random() * 0.5,
      });
      return;
    }
    select(semOf(e.object));
  };

  return (
    <>
      <SolarSky radius={radius} />
      <primitive object={scene} onClick={onPick} />
      <Entourage />
      {geoEnabled && geoKey && <GeoTiles apiToken={geoKey} />}
      {rendering && <PathTracer />}
      {mode === "walk" ? (
        <WalkControls speed={radius * 0.6} />
      ) : (
        <OrbitControls ref={controls} makeDefault enabled={!rendering} />
      )}
    </>
  );
}

useGLTF.preload(MODEL_URL);
