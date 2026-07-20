"use client";

import type { CanvasLayer, EnvelopeFacet, MaterialScaffold } from "@/lib/model";
import { CostPill } from "./CostPill";
import { Logo } from "./Logo";
import { CanvasStage } from "./CanvasStage";
import { LayerRail } from "./LayerRail";
import { BeforeAfter } from "./BeforeAfter";

/** Editor shell: slim header, canvas center, layer rail, status/queue toast. */
export function Workspace({
  mode,
  spent,
  image,
  layers,
  selectedId,
  materials,
  facet,
  busy,
  result,
  view,
  driftScore,
  onSelect,
  onFacet,
  onPick,
  onReset,
  onView,
}: {
  mode: "mock" | "live";
  spent: number;
  image: string | undefined;
  layers: CanvasLayer[];
  selectedId: string | null;
  materials: MaterialScaffold[];
  facet: EnvelopeFacet;
  busy: string | null;
  result: { previewUrl?: string; imageDataUrl: string; appliedMaterial: string; editedLayer: string; meta: { mode: "mock" | "live"; usd?: number; requestId?: string } } | null;
  view: "before" | "after";
  driftScore: number;
  onSelect: (id: string) => void;
  onFacet: (f: EnvelopeFacet) => void;
  onPick: (id: string) => void;
  onReset: () => void;
  onView: (v: "before" | "after") => void;
}) {
  const before = image;
  const after = result ? (result.previewUrl ?? result.imageDataUrl) : image;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-line bg-background px-5 py-3">
        <Logo />
        <CostPill mode={mode} spent={spent} />
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_320px]">
        {/* Canvas center */}
        <div className="relative min-h-0">
          <CanvasStage
            image={view === "before" ? before : after}
            layers={layers}
            selectedId={selectedId}
            showBboxes={view === "before"}
            onSelect={onSelect}
          />

          {busy && (
            <div className="absolute inset-0 flex items-center justify-center bg-neutral-950/70 backdrop-blur-sm">
              <div className="flex items-center gap-3 rounded-lg border border-line bg-neutral-900 px-5 py-3 text-sm text-neutral-200">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-600 border-t-accent" />
                {busy}
              </div>
            </div>
          )}

          {result && (
            <BeforeAfter
              before={before}
              after={after}
              view={view}
              onView={onView}
              driftScore={driftScore}
            />
          )}

          {/* status / queue toast area */}
          {result && !busy && (
            <div className="absolute right-4 top-4 max-w-[260px] rounded-lg border border-line bg-neutral-900/90 px-3 py-2 text-xs text-neutral-400 backdrop-blur">
              <p>
                <span className="text-neutral-200">{result.appliedMaterial}</span> on{" "}
                {result.editedLayer}
              </p>
              <p className="mt-0.5 text-neutral-500">
                {result.meta.mode === "live"
                  ? `~$${result.meta.usd?.toFixed(2)} · ${result.meta.requestId ?? ""}`
                  : "mock · $0"}
              </p>
            </div>
          )}
        </div>

        <LayerRail
          layers={layers}
          selectedId={selectedId}
          materials={materials}
          facet={facet}
          busy={!!busy}
          onSelect={onSelect}
          onFacet={onFacet}
          onPick={onPick}
          onReset={onReset}
        />
      </div>
    </div>
  );
}
