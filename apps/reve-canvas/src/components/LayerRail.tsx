"use client";

import type { CanvasLayer, EnvelopeFacet, MaterialScaffold } from "@/lib/model";
import { FACET_LABEL } from "@/lib/model";
import { LayerRow } from "./LayerRow";
import { FacetChips } from "./FacetChips";
import { MaterialGrid } from "./MaterialGrid";

/** Right-hand rail: layer list + inline editor for the selected layer. */
export function LayerRail({
  layers,
  selectedId,
  materials,
  facet,
  busy,
  onSelect,
  onFacet,
  onPick,
  onReset,
}: {
  layers: CanvasLayer[];
  selectedId: string | null;
  materials: MaterialScaffold[];
  facet: EnvelopeFacet;
  busy: boolean;
  onSelect: (id: string) => void;
  onFacet: (f: EnvelopeFacet) => void;
  onPick: (id: string) => void;
  onReset: () => void;
}) {
  const selected = layers.find((l) => l.id === selectedId) ?? null;

  return (
    <aside className="flex h-full flex-col overflow-hidden border-l border-line bg-panel">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-neutral-100">Layers</h2>
          <button
            onClick={onReset}
            className="text-xs text-neutral-500 transition-colors hover:text-neutral-300"
          >
            reset
          </button>
        </div>
        <p className="mt-1 text-xs text-neutral-500">
          {layers.length} objects · click one to edit its material
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {layers.map((l) => (
          <div key={l.id}>
            <LayerRow
              layer={l}
              selected={l.id === selectedId}
              onSelect={onSelect}
            />
            {l.id === selectedId && (
              <div className="border-y border-line bg-neutral-900/50 px-4 py-3">
                {l.isBuilding && (
                  <div className="mb-3">
                    <FacetChips
                      facets={l.facets}
                      active={facet}
                      onSelect={onFacet}
                    />
                  </div>
                )}
                <p className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">
                  Material{l.isBuilding ? ` · ${FACET_LABEL[facet]}` : ""}
                </p>
                <MaterialGrid materials={materials} busy={busy} onPick={onPick} />
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
