"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { materialsForLayer, FACET_LABEL, type CanvasLayer, type EnvelopeFacet } from "@/lib/model";
import type { ReveLayout } from "@/lib/reve/types";

interface LoadedImage { dataUrl: string; width: number; height: number; }
interface Meta { creditsUsed: number; usd: number; mode: "mock" | "live"; requestId?: string; }
interface EditResult { imageDataUrl: string; previewUrl?: string; meta: Meta; appliedMaterial: string; editedLayer: string; }

/** Downscale a (possibly 16MP) render to a light preview for on-canvas display;
 * the full-res data URL is kept for export/download. */
function toPreview(dataUrl: string, maxW = 1600): Promise<string> {
  return new Promise((resolve) => {
    const img = new window.Image();
    img.onload = () => {
      if (img.naturalWidth <= maxW) return resolve(dataUrl);
      const scale = maxW / img.naturalWidth;
      const c = document.createElement("canvas");
      c.width = maxW; c.height = Math.round(img.naturalHeight * scale);
      c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
      resolve(c.toDataURL("image/jpeg", 0.9));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

const SEMANTIC_COLOR: Record<string, string> = {
  wall: "#e0794a", glazing: "#4aa3e0", roof: "#8a6bd6", floor: "#c9a24a", ceiling: "#7fb0d0",
  ground: "#6fae54", paving: "#9a8f7a", vegetation: "#4fb06a", furniture: "#d06fb0",
  fixture: "#e0c24a", sky: "#7cc4e8", water: "#3fb6c9", context: "#c0603a", door: "#d98a3a",
  person: "#e04a7a", vehicle: "#5a7fd0", text: "#aaaaaa",
};

export default function Home() {
  const [image, setImage] = useState<LoadedImage | null>(null);
  const [layout, setLayout] = useState<ReveLayout | null>(null);
  const [layers, setLayers] = useState<CanvasLayer[]>([]);
  const [mode, setMode] = useState<"mock" | "live">("mock");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [facet, setFacet] = useState<EnvelopeFacet>("cladding");
  const [busy, setBusy] = useState<null | string>(null);
  const [result, setResult] = useState<EditResult | null>(null);
  const [view, setView] = useState<"before" | "after">("after");
  const [error, setError] = useState<string | null>(null);
  const [spent, setSpent] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(() => layers.find((l) => l.id === selectedId) ?? null, [layers, selectedId]);
  const materials = useMemo(
    () => (selected ? materialsForLayer(selected, selected.isBuilding ? facet : undefined) : []),
    [selected, facet],
  );

  async function extract(dataUrl: string) {
    setBusy("Reading the scene…");
    setError(null);
    try {
      const res = await fetch("/api/extract", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageDataUrl: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "extract failed");
      setLayout(data.layout); setLayers(data.layers); setMode(data.mode);
      if (data.meta) setSpent((s) => s + (data.meta.usd ?? 0));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  const loadFile = useCallback((file: File | Blob) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const img = new window.Image();
      img.onload = () => {
        setImage({ dataUrl, width: img.naturalWidth, height: img.naturalHeight });
        setLayout(null); setLayers([]); setSelectedId(null); setResult(null); setError(null);
        void extract(dataUrl);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  }, []);

  async function useSample() {
    const blob = await (await fetch("/sample.jpg")).blob();
    loadFile(blob);
  }

  async function render(materialId: string) {
    if (!image || !layout || !selected) return;
    setBusy("Rendering the edit… (~35s live)");
    setError(null);
    try {
      const res = await fetch("/api/edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imageDataUrl: image.dataUrl, layout, layer: selected, materialId,
          facet: selected.isBuilding ? facet : undefined,
          srcWidth: image.width, srcHeight: image.height,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "edit failed");
      const previewUrl = await toPreview(data.imageDataUrl);
      setResult({ ...data, previewUrl }); setView("after");
      if (data.meta) setSpent((s) => s + (data.meta.usd ?? 0));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  const shownImage = result && view === "after" ? (result.previewUrl ?? result.imageDataUrl) : image?.dataUrl;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="flex items-center justify-between border-b border-neutral-800 px-5 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-semibold tracking-tight">Reve Canvas</h1>
          <span className="text-xs text-neutral-500">architecture-native layer editing · thin slice</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className={`rounded px-2 py-1 font-medium ${mode === "live" ? "bg-emerald-900 text-emerald-200" : "bg-neutral-800 text-neutral-300"}`}>
            {mode === "live" ? "LIVE · Reve" : "MOCK · $0"}
          </span>
          <span className="text-neutral-500">session ${spent.toFixed(3)}</span>
        </div>
      </header>

      {!image ? (
        <div className="flex h-[calc(100vh-53px)] items-center justify-center">
          <div className="w-full max-w-md rounded-xl border border-dashed border-neutral-700 p-10 text-center">
            <p className="mb-1 text-sm text-neutral-300">Upload a viewport screenshot, render, or photo</p>
            <p className="mb-6 text-xs text-neutral-500">Reve reads it into editable architectural layers.</p>
            <div className="flex flex-col gap-3">
              <button onClick={() => fileRef.current?.click()}
                className="rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-white">
                Choose image…
              </button>
              <button onClick={useSample}
                className="rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:border-neutral-500">
                Use sample building
              </button>
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden"
              onChange={(e) => e.target.files?.[0] && loadFile(e.target.files[0])} />
          </div>
        </div>
      ) : (
        <div className="grid h-[calc(100vh-53px)] grid-cols-[1fr_320px]">
          {/* Canvas */}
          <div className="relative flex items-center justify-center overflow-hidden bg-neutral-900 p-6">
            <div className="relative max-h-full max-w-full">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={shownImage} alt="scene" className="max-h-[calc(100vh-140px)] w-auto rounded-lg shadow-2xl" />
              {view === "before" && layers.map((l) => {
                const on = l.id === selectedId;
                const c = SEMANTIC_COLOR[l.semantic] ?? "#888";
                return (
                  <button key={l.id} onClick={() => setSelectedId(l.id)} title={l.name}
                    className="absolute border-2 transition-all"
                    style={{
                      left: `${l.bbox.x0 * 100}%`, top: `${l.bbox.y0 * 100}%`,
                      width: `${(l.bbox.x1 - l.bbox.x0) * 100}%`, height: `${(l.bbox.y1 - l.bbox.y0) * 100}%`,
                      borderColor: c, opacity: on ? 1 : 0.35,
                      background: on ? `${c}22` : "transparent",
                    }} />
                );
              })}
            </div>

            {busy && (
              <div className="absolute inset-0 flex items-center justify-center bg-neutral-950/70">
                <div className="rounded-lg bg-neutral-900 px-5 py-3 text-sm text-neutral-200">{busy}</div>
              </div>
            )}

            {result && (
              <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 gap-1 rounded-lg border border-neutral-700 bg-neutral-900/90 p-1 text-xs">
                {(["before", "after"] as const).map((v) => (
                  <button key={v} onClick={() => setView(v)}
                    className={`rounded px-3 py-1 ${view === v ? "bg-neutral-100 text-neutral-900" : "text-neutral-300"}`}>
                    {v === "before" ? "Original" : "Edited"}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Layer panel */}
          <aside className="flex flex-col overflow-hidden border-l border-neutral-800">
            <div className="border-b border-neutral-800 px-4 py-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium">Layers</h2>
                <button onClick={() => { setImage(null); setLayers([]); setResult(null); }}
                  className="text-xs text-neutral-500 hover:text-neutral-300">reset</button>
              </div>
              <p className="mt-1 text-xs text-neutral-500">{layers.length} objects · click one to edit its material</p>
            </div>

            <div className="flex-1 overflow-y-auto">
              {layers.map((l) => (
                <div key={l.id}>
                  <button onClick={() => setSelectedId(l.id === selectedId ? null : l.id)}
                    className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-neutral-900 ${l.id === selectedId ? "bg-neutral-900" : ""}`}>
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: SEMANTIC_COLOR[l.semantic] ?? "#888" }} />
                    <span className="flex-1 truncate">{l.name}</span>
                    <span className="text-[10px] uppercase tracking-wide text-neutral-500">{l.semantic}</span>
                  </button>

                  {l.id === selectedId && (
                    <div className="border-y border-neutral-800 bg-neutral-900/50 px-4 py-3">
                      {l.isBuilding && (
                        <div className="mb-3">
                          <p className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">Facet</p>
                          <div className="flex flex-wrap gap-1">
                            {l.facets.map((f) => (
                              <button key={f} onClick={() => setFacet(f)}
                                className={`rounded px-2 py-1 text-xs ${facet === f ? "bg-neutral-100 text-neutral-900" : "bg-neutral-800 text-neutral-300"}`}>
                                {FACET_LABEL[f]}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      <p className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">
                        Material {l.isBuilding ? `· ${FACET_LABEL[facet]}` : ""}
                      </p>
                      <div className="grid grid-cols-2 gap-1.5">
                        {materials.map((m) => (
                          <button key={m.id} onClick={() => render(m.id)} disabled={!!busy}
                            className="flex items-center gap-2 rounded border border-neutral-800 px-2 py-1.5 text-left text-xs hover:border-neutral-600 disabled:opacity-50">
                            <span className="h-4 w-4 shrink-0 rounded-sm border border-black/30" style={{ background: m.color }} />
                            <span className="truncate">{m.label}</span>
                          </button>
                        ))}
                        {materials.length === 0 && <p className="col-span-2 text-xs text-neutral-500">No material presets for this object type yet.</p>}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {result && (
              <div className="border-t border-neutral-800 px-4 py-3 text-xs text-neutral-400">
                <p><span className="text-neutral-200">{result.appliedMaterial}</span> on {result.editedLayer}</p>
                <p className="mt-0.5 text-neutral-500">{result.meta.mode === "live" ? `~$${result.meta.usd.toFixed(2)} · ${result.meta.requestId ?? ""}` : "mock · $0"}</p>
              </div>
            )}
            {error && <div className="border-t border-red-900 bg-red-950/50 px-4 py-2 text-xs text-red-300">{error}</div>}
          </aside>
        </div>
      )}
    </div>
  );
}
