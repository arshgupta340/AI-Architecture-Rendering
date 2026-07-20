"use client";

import { useEffect, useMemo, useState } from "react";
import { applyMaskedDelta, type BBox, type CompositeResult } from "@/lib/composite";
import type { CanvasLayer } from "@/lib/model";
import type { ReveLayout } from "@/lib/reve/types";

type View = "original" | "render" | "composite" | "mask" | "diff";

interface FixtureState {
  original: string;
  render: string;
  result: CompositeResult;
  width: number;
  height: number;
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Unable to read sample image"));
    reader.readAsDataURL(blob);
  });
}

function dimensions(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = () => reject(new Error("Unable to read image dimensions"));
    image.src = dataUrl;
  });
}

function coverFit(ctx: CanvasRenderingContext2D, image: HTMLImageElement, width: number, height: number): void {
  const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
  const drawWidth = image.naturalWidth * scale;
  const drawHeight = image.naturalHeight * scale;
  ctx.drawImage(image, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight);
}

function diffHeatmap(originalUrl: string, renderUrl: string, width: number, height: number): Promise<string> {
  return Promise.all([dimensions(originalUrl), dimensions(renderUrl)]).then(([originalSize, renderSize]) => new Promise((resolve, reject) => {
    const original = new Image();
    const render = new Image();
    let loaded = 0;
    const draw = () => {
      loaded += 1;
      if (loaded !== 2) return;
      const originalCanvas = document.createElement("canvas");
      const renderCanvas = document.createElement("canvas");
      const outputCanvas = document.createElement("canvas");
      originalCanvas.width = renderCanvas.width = outputCanvas.width = width;
      originalCanvas.height = renderCanvas.height = outputCanvas.height = height;
      const originalCtx = originalCanvas.getContext("2d", { willReadFrequently: true });
      const renderCtx = renderCanvas.getContext("2d", { willReadFrequently: true });
      const outputCtx = outputCanvas.getContext("2d", { willReadFrequently: true });
      if (!originalCtx || !renderCtx || !outputCtx) return reject(new Error("2D canvas is unavailable"));
      originalCtx.drawImage(original, 0, 0, originalSize.width, originalSize.height);
      coverFit(renderCtx, render, width, height);
      const source = originalCtx.getImageData(0, 0, width, height).data;
      const edited = renderCtx.getImageData(0, 0, width, height).data;
      const heatmap = outputCtx.createImageData(width, height);
      for (let offset = 0; offset < heatmap.data.length; offset += 4) {
        const delta = (Math.abs(source[offset] - edited[offset]) + Math.abs(source[offset + 1] - edited[offset + 1]) + Math.abs(source[offset + 2] - edited[offset + 2])) / 3;
        heatmap.data[offset] = Math.min(255, delta * 3);
        heatmap.data[offset + 1] = Math.min(255, delta * 0.25);
        heatmap.data[offset + 2] = 0;
        heatmap.data[offset + 3] = 255;
      }
      outputCtx.putImageData(heatmap, 0, 0);
      resolve(outputCanvas.toDataURL("image/png"));
    };
    original.onload = draw;
    render.onload = draw;
    original.onerror = render.onerror = () => reject(new Error("Unable to decode fixture images"));
    original.src = originalUrl;
    render.src = renderUrl;
  }));
}

export default function CompositeDevPage() {
  const [fixture, setFixture] = useState<FixtureState | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [view, setView] = useState<View>("composite");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadFixture() {
      try {
        const original = await blobToDataUrl(await (await fetch("/sample.jpg")).blob());
        const { width, height } = await dimensions(original);
        const extractResponse = await fetch("/api/extract", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ imageDataUrl: original }),
        });
        const extracted = await extractResponse.json() as { layout?: ReveLayout; layers?: CanvasLayer[]; error?: string };
        if (!extractResponse.ok || !extracted.layout || !extracted.layers?.length) throw new Error(extracted.error ?? "Mock extract failed");
        const layer = extracted.layers.find((candidate) => candidate.isBuilding) ?? extracted.layers[0];
        const editResponse = await fetch("/api/edit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ imageDataUrl: original, layout: extracted.layout, layer, materialId: "travertine", facet: "cladding", srcWidth: width, srcHeight: height }),
        });
        const edited = await editResponse.json() as { imageDataUrl?: string; error?: string };
        if (!editResponse.ok || !edited.imageDataUrl) throw new Error(edited.error ?? "Mock edit failed");
        const bboxes: BBox[] = [layer.bbox];
        const result = await applyMaskedDelta(original, edited.imageDataUrl, bboxes);
        const heatmap = await diffHeatmap(original, edited.imageDataUrl, width, height);
        if (!cancelled) {
          setFixture({ original, render: edited.imageDataUrl, result, width, height });
          setDiff(heatmap);
        }
      } catch (reason) {
        if (!cancelled) setError((reason as Error).message);
      }
    }
    void loadFixture();
    return () => { cancelled = true; };
  }, []);

  const selectedImage = useMemo(() => {
    if (!fixture) return null;
    if (view === "original") return fixture.original;
    if (view === "render") return fixture.render;
    if (view === "mask") return fixture.result.maskDataUrl;
    if (view === "diff") return diff;
    return fixture.result.dataUrl;
  }, [diff, fixture, view]);

  if (error) return <main className="min-h-screen bg-neutral-950 p-8 text-red-300">Composite fixture failed: {error}</main>;
  if (!fixture || !selectedImage) return <main className="min-h-screen bg-neutral-950 p-8 text-neutral-300">Loading mock masked-delta fixture…</main>;

  return (
    <main className="min-h-screen bg-neutral-950 p-6 text-neutral-100">
      <div className="mx-auto max-w-6xl">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-emerald-400">Mock · $0</p>
            <h1 className="mt-1 text-2xl font-semibold">Masked-delta composite verifier</h1>
            <p className="mt-1 text-sm text-neutral-400">Output: {fixture.width} × {fixture.height} px · outside-mask drift: {fixture.result.driftScore.toFixed(4)}</p>
          </div>
          <div className="flex flex-wrap gap-1 rounded-lg border border-neutral-800 bg-neutral-900 p-1 text-sm">
            {(["original", "render", "composite", "mask", "diff"] as View[]).map((candidate) => (
              <button key={candidate} onClick={() => setView(candidate)}
                className={`rounded-md px-3 py-1.5 capitalize ${view === candidate ? "bg-neutral-100 text-neutral-950" : "text-neutral-300 hover:bg-neutral-800"}`}>
                {candidate === "diff" ? "Diff heatmap" : candidate}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900 p-3 shadow-2xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={selectedImage} alt={`${view} fixture`} className="mx-auto max-h-[72vh] w-auto rounded-md" />
        </div>
        <p className="mt-3 text-xs text-neutral-500">The fixture fetches only the existing mock extract/edit routes, then composites the selected building bbox client-side.</p>
      </div>
    </main>
  );
}
