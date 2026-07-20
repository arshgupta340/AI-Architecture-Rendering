"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  materialsForLayer,
  type CanvasLayer,
  type EnvelopeFacet,
} from "@/lib/model";
import type { ReveLayout } from "@/lib/reve/types";
import { applyMaskedDelta } from "@/lib/composite";
import { toPreview } from "@/lib/ui";
import { WAIT_COPY } from "@/lib/brand";
import { Landing } from "@/components/Landing";
import { Workspace } from "@/components/Workspace";

interface LoadedImage {
  dataUrl: string;
  width: number;
  height: number;
}
interface Meta {
  creditsUsed: number;
  usd: number;
  mode: "mock" | "live";
  requestId?: string;
}
interface EditResult {
  imageDataUrl: string;
  previewUrl?: string;
  meta: Meta;
  appliedMaterial: string;
  editedLayer: string;
}

export default function Home() {
  const [image, setImage] = useState<LoadedImage | null>(null);
  const [layout, setLayout] = useState<ReveLayout | null>(null);
  const [layers, setLayers] = useState<CanvasLayer[]>([]);
  const [mode, setMode] = useState<"mock" | "live">("mock");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [facet, setFacet] = useState<EnvelopeFacet>("cladding");
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<EditResult | null>(null);
  const [view, setView] = useState<"before" | "after">("after");
  const [error, setError] = useState<string | null>(null);
  const [spent, setSpent] = useState(0);
  const [driftScore, setDriftScore] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => layers.find((l) => l.id === selectedId) ?? null,
    [layers, selectedId],
  );
  const materials = useMemo(
    () =>
      selected
        ? materialsForLayer(selected, selected.isBuilding ? facet : undefined)
        : [],
    [selected, facet],
  );

  async function extract(dataUrl: string) {
    setBusy(WAIT_COPY.reading);
    setError(null);
    try {
      const res = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageDataUrl: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "extract failed");
      setLayout(data.layout);
      setLayers(data.layers);
      setMode(data.mode);
      if (data.meta) setSpent((s) => s + (data.meta.usd ?? 0));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const loadFile = useCallback((file: File | Blob) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const img = new window.Image();
      img.onload = () => {
        setImage({
          dataUrl,
          width: img.naturalWidth,
          height: img.naturalHeight,
        });
        setLayout(null);
        setLayers([]);
        setSelectedId(null);
        setResult(null);
        setError(null);
        setDriftScore(0);
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
    setBusy(WAIT_COPY.rendering);
    setError(null);
    try {
      const res = await fetch("/api/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          imageDataUrl: image.dataUrl,
          layout,
          layer: selected,
          materialId,
          facet: selected.isBuilding ? facet : undefined,
          srcWidth: image.width,
          srcHeight: image.height,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "edit failed");

      const renderDataUrl = data.imageDataUrl;
      const previewUrl = await toPreview(renderDataUrl);

      // Composite the render back onto the original via the masked-delta lib
      // (stub today; replaced wholesale by wt/composite at merge). The composite
      // is what we show as the "Edited" view; the drift score tells us how much
      // of the image changed outside the edited region.
      const composite = await applyMaskedDelta(
        image.dataUrl,
        renderDataUrl,
        [selected.bbox],
      );
      setDriftScore(composite.driftScore);

      setResult({ ...data, previewUrl: previewUrl ?? composite.dataUrl });
      setView("after");
      if (data.meta) setSpent((s) => s + (data.meta.usd ?? 0));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const reset = useCallback(() => {
    setImage(null);
    setLayers([]);
    setResult(null);
    setSelectedId(null);
    setDriftScore(0);
  }, []);

  // Esc deselects the active layer.
  const onKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") setSelectedId(null);
  }, []);

  return (
    <div onKeyDown={onKeyDown} tabIndex={-1} className="outline-none">
      {!image ? (
        <Landing onFile={loadFile} onSample={useSample} busy={!!busy} />
      ) : (
        <Workspace
          mode={mode}
          spent={spent}
          image={image.dataUrl}
          layers={layers}
          selectedId={selectedId}
          materials={materials}
          facet={facet}
          busy={busy}
          result={result}
          view={view}
          driftScore={driftScore}
          onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
          onFacet={setFacet}
          onPick={render}
          onReset={reset}
          onView={setView}
        />
      )}

      {error && image && (
        <div className="fixed bottom-4 right-4 z-50 rounded-lg border border-red-900 bg-red-950/80 px-4 py-2 text-xs text-red-300 backdrop-blur">
          {error}
        </div>
      )}
    </div>
  );
}
