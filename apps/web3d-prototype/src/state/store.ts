import { create } from "zustand";
import { persist } from "zustand/middleware";
import type * as THREE from "three";
import { setSwatchScale as applySwatchScale } from "../lib/swatches";

export type Layer = { semantic: string; swatch: string; visible: boolean };

export type SavedView = {
  id: string;
  label: string;
  pos: [number, number, number];
  target: [number, number, number];
  preset?: boolean;
};

/** A placed entourage instance. `scale` is a per-item variation (~0.85–1.15); the
 *  rendered size = entHeight[asset]/baseHeight[asset] * scale. */
export type EntItem = {
  id: string;
  asset: string;
  pos: [number, number, number];
  rot: number;
  scale: number;
};

export type NavMode = "orbit" | "walk";
/** Renderer/quality path. Each maps to a self-contained Stage component (own
 *  Canvas + renderer + post) so the three can be built/compared independently:
 *  webgl2 = baseline N8AO/AgX; webgl2gi = WebGL2 area-lights + SSR + tuned GI;
 *  webgpu = three.js WebGPU renderer + TSL GTAO/SSGI/TRAA. */
export type RenderMode = "webgl2" | "webgl2gi" | "webgpu";
export type Mood = "sunny" | "overcast" | "golden" | "dusk" | "night";

export type SkyState = {
  lat: number;
  lng: number;
  date: string; // YYYY-MM-DD
  timeOfDay: number; // 0–24 (local)
  sunIntensity: number; // multiplier
  cloudCover: number; // 0–1
  mood: Mood | null;
};

const DEFAULT_SKY: SkyState = {
  lat: 37.77,
  lng: -122.42,
  date: "2026-06-21",
  timeOfDay: 14,
  sunIntensity: 1,
  cloudCover: 0.1,
  mood: "sunny",
};

/** Real-world site context: Google Photorealistic 3D Tiles georeferenced around
 *  the model. Site lat/lng is shared with `sky` (one place → sun + context agree).
 *  `enabled` is intentionally NOT persisted (tiles cost per session; start off). */
export type GeoState = {
  enabled: boolean;
  apiKey: string; // Google Maps Tiles API key (user-provided; persisted locally)
  height: number; // metres above the WGS84 ellipsoid (approx site ground elevation)
  heading: number; // degrees; rotate the real context to align with the model's north
  groundOffset: number; // feet; vertical nudge to seat the building on the real terrain
  hideRhinoSite: boolean; // hide the Rhino ground/site/topo so real terrain shows through
};

const DEFAULT_GEO: GeoState = {
  enabled: false,
  apiKey: "",
  height: 0,
  heading: 0,
  groundOffset: 0,
  hideRhinoSite: true,
};

// Mood presets — partial sky overrides applied on top of lat/lng/date.
export const MOODS: Record<Mood, Partial<SkyState>> = {
  sunny: { cloudCover: 0.05, sunIntensity: 1.15, timeOfDay: 13 },
  overcast: { cloudCover: 0.9, sunIntensity: 0.55, timeOfDay: 13 },
  golden: { cloudCover: 0.12, sunIntensity: 1.0, timeOfDay: 18.6 },
  dusk: { cloudCover: 0.25, sunIntensity: 0.5, timeOfDay: 19.6 },
  night: { cloudCover: 0.15, sunIntensity: 0.12, timeOfDay: 23 },
};

const DEFAULT_ENT_HEIGHT: Record<string, number> = { tree: 18, bush: 3, person: 5.7 };

/** High-res "client-ready" still export config. `scale` multiplies the canvas
 *  pixel size; aspect crops the framed still; format picks the encoder. */
export type ExportCfg = { aspect: "16:9" | "3:2" | "4:3" | "1:1" | "free"; scale: number; format: "jpg" | "png" };
const DEFAULT_EXPORT: ExportCfg = { aspect: "16:9", scale: 2, format: "jpg" };

type Store = {
  // ---- runtime ----
  meshesBySemantic: Map<string, THREE.Mesh[]>;
  semanticsPresent: string[];
  ready: boolean;
  selected: string | null;
  mode: NavMode;
  presets: SavedView[];
  saveNonce: number;
  goto: SavedView | null;
  rendering: boolean;
  ptSamples: number;
  placeAsset: string | null;
  /** Building ground-centre in feet world-space; the real-world site is anchored here. */
  siteAnchor: [number, number, number] | null;
  /** Cinematic (UE5) hero mode on/off — overlays an embedded SimplyStream WebGPU build. */
  cinematic: boolean;
  /** Presentation mode: hide all DOM panels so the on-screen preview == the export frame. */
  presentation: boolean;
  /** Async high-res capture fn registered by the ACTIVE Stage (it owns the renderer +
   *  scene + camera). NavBar's export button calls it; returns a Blob (or null on
   *  failure). Runtime-only (never persisted). */
  captureFn: ((cfg: ExportCfg) => Promise<Blob | null>) | null;

  // ---- persisted ----
  layers: Layer[];
  views: SavedView[];
  swatchScale: Record<string, number>;
  entourage: EntItem[];
  entHeight: Record<string, number>;
  sky: SkyState;
  geo: GeoState;
  /** SimplyStream-hosted UE WebGPU build URL for the "Cinematic" hero toggle. */
  cinematicUrl: string;
  /** Active renderer/quality path (see RenderMode). */
  renderMode: RenderMode;
  /** High-res still export config (aspect / scale / format). */
  exportCfg: ExportCfg;
  /** Equirect HDRI sky preset slug → public/hdri/<slug>.hdr (drives WebGPU IBL + PT hero). */
  hdriPreset: string;
  /** Sun-path arc overlay (analemma + day arc from the suncalc sun) on/off. */
  sunPath: boolean;
  /** Cheap billboard cloud plate for the hero (drei <Cloud>) on/off. */
  showClouds: boolean;
  /** Ground contact-shadow catcher under the building (WebGL2 stages) on/off. */
  contactShadows: boolean;
  /** Cinematic post grade (DoF/film-grain/vignette/LUT) on/off + strength 0–1. */
  grade: boolean;
  gradeStrength: number;
  /** Gaussian-splat "context backdrop" scaffold (webgl2gi only) — enable + asset URL. */
  splatEnabled: boolean;
  splatUrl: string;

  // ---- actions ----
  setModel: (bySem: Map<string, THREE.Mesh[]>) => void;
  select: (s: string | null) => void;
  applySwatch: (semantic: string, swatch: string) => void;
  toggleLayer: (semantic: string) => void;
  removeLayer: (semantic: string) => void;
  clearLayers: () => void;
  setMode: (m: NavMode) => void;
  setPresets: (p: SavedView[]) => void;
  requestSave: () => void;
  addView: (v: SavedView) => void;
  removeView: (id: string) => void;
  requestGoto: (v: SavedView) => void;
  clearGoto: () => void;
  setRendering: (b: boolean) => void;
  setSamples: (n: number) => void;
  setSwatchScale: (id: string, v: number) => void;
  setPlaceAsset: (a: string | null) => void;
  addEnt: (e: EntItem) => void;
  removeEnt: (id: string) => void;
  clearEnt: () => void;
  setEntHeight: (asset: string, ft: number) => void;
  setSky: (patch: Partial<SkyState>) => void;
  applyMood: (m: Mood) => void;
  setGeo: (patch: Partial<GeoState>) => void;
  setSiteAnchor: (a: [number, number, number]) => void;
  setCinematic: (on: boolean) => void;
  setCinematicUrl: (url: string) => void;
  setRenderMode: (m: RenderMode) => void;
  setPresentation: (on: boolean) => void;
  setCaptureFn: (fn: ((cfg: ExportCfg) => Promise<Blob | null>) | null) => void;
  setExportCfg: (patch: Partial<ExportCfg>) => void;
  setHdriPreset: (slug: string) => void;
  setSunPath: (on: boolean) => void;
  setShowClouds: (on: boolean) => void;
  setContactShadows: (on: boolean) => void;
  setGrade: (on: boolean) => void;
  setGradeStrength: (v: number) => void;
  setSplatEnabled: (on: boolean) => void;
  setSplatUrl: (url: string) => void;
};

export const useStore = create<Store>()(
  persist(
    (set, get) => ({
      meshesBySemantic: new Map(),
      semanticsPresent: [],
      ready: false,
      selected: null,
      mode: "orbit",
      presets: [],
      saveNonce: 0,
      goto: null,
      rendering: false,
      ptSamples: 0,
      placeAsset: null,
      siteAnchor: null,
      cinematic: false,
      presentation: false,
      captureFn: null,
      layers: [],
      views: [],
      swatchScale: {},
      entourage: [],
      entHeight: { ...DEFAULT_ENT_HEIGHT },
      sky: { ...DEFAULT_SKY },
      geo: { ...DEFAULT_GEO },
      cinematicUrl: "",
      renderMode: "webgl2",
      exportCfg: { ...DEFAULT_EXPORT },
      hdriPreset: "sky",
      sunPath: false,
      showClouds: false,
      contactShadows: true,
      grade: false,
      gradeStrength: 0.6,
      splatEnabled: false,
      splatUrl: "",

      setModel: (bySem) =>
        set({ meshesBySemantic: bySem, semanticsPresent: [...bySem.keys()].sort(), ready: true }),
      select: (s) => set({ selected: s }),
      applySwatch: (semantic, swatch) => {
        const layers = get().layers.filter((l) => l.semantic !== semantic);
        layers.push({ semantic, swatch, visible: true });
        set({ layers });
      },
      toggleLayer: (semantic) =>
        set({
          layers: get().layers.map((l) =>
            l.semantic === semantic ? { ...l, visible: !l.visible } : l,
          ),
        }),
      removeLayer: (semantic) => set({ layers: get().layers.filter((l) => l.semantic !== semantic) }),
      clearLayers: () => set({ layers: [] }),
      setMode: (m) => set({ mode: m }),
      setPresets: (p) => set({ presets: p }),
      requestSave: () => set({ saveNonce: get().saveNonce + 1 }),
      addView: (v) => set({ views: [...get().views, v] }),
      removeView: (id) => set({ views: get().views.filter((v) => v.id !== id) }),
      requestGoto: (v) => set({ goto: v }),
      clearGoto: () => set({ goto: null }),
      setRendering: (b) => set({ rendering: b, ptSamples: 0, selected: b ? null : get().selected }),
      setSamples: (n) => set({ ptSamples: n }),
      setSwatchScale: (id, v) => {
        applySwatchScale(id, v);
        set({ swatchScale: { ...get().swatchScale, [id]: v } });
      },
      setPlaceAsset: (a) => set({ placeAsset: a, selected: a ? null : get().selected }),
      addEnt: (e) => set({ entourage: [...get().entourage, e] }),
      removeEnt: (id) => set({ entourage: get().entourage.filter((e) => e.id !== id) }),
      clearEnt: () => set({ entourage: [] }),
      setEntHeight: (asset, ft) => set({ entHeight: { ...get().entHeight, [asset]: ft } }),
      setSky: (patch) => set({ sky: { ...get().sky, ...patch, mood: patch.mood ?? null } }),
      applyMood: (m) => set({ sky: { ...get().sky, ...MOODS[m], mood: m } }),
      setGeo: (patch) => set({ geo: { ...get().geo, ...patch } }),
      setSiteAnchor: (a) => set({ siteAnchor: a }),
      setCinematic: (on) => set({ cinematic: on, selected: on ? null : get().selected }),
      setCinematicUrl: (url) => set({ cinematicUrl: url.trim() }),
      setRenderMode: (m) => set({ renderMode: m }),
      setPresentation: (on) => set({ presentation: on, selected: on ? null : get().selected }),
      setCaptureFn: (fn) => set({ captureFn: fn }),
      setExportCfg: (patch) => set({ exportCfg: { ...get().exportCfg, ...patch } }),
      setHdriPreset: (slug) => set({ hdriPreset: slug }),
      setSunPath: (on) => set({ sunPath: on }),
      setShowClouds: (on) => set({ showClouds: on }),
      setContactShadows: (on) => set({ contactShadows: on }),
      setGrade: (on) => set({ grade: on }),
      setGradeStrength: (v) => set({ gradeStrength: v }),
      setSplatEnabled: (on) => set({ splatEnabled: on }),
      setSplatUrl: (url) => set({ splatUrl: url.trim() }),
    }),
    {
      name: "web3d-layers-v1",
      partialize: (s) =>
        ({
          layers: s.layers,
          views: s.views,
          swatchScale: s.swatchScale,
          entourage: s.entourage,
          entHeight: s.entHeight,
          sky: s.sky,
          cinematicUrl: s.cinematicUrl,
          renderMode: s.renderMode,
          exportCfg: s.exportCfg,
          hdriPreset: s.hdriPreset,
          sunPath: s.sunPath,
          showClouds: s.showClouds,
          contactShadows: s.contactShadows,
          grade: s.grade,
          gradeStrength: s.gradeStrength,
          // Persist geo settings (key/location/offsets) but never auto-enable on
          // reload — tile loading bills per session, so it must be an explicit click.
          geo: { ...s.geo, enabled: false },
        }) as Partial<Store>,
    },
  ),
);
