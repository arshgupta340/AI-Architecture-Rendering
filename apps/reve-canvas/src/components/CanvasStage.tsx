"use client";

import { useState } from "react";
import type { CanvasLayer } from "@/lib/model";
import { semanticColor } from "@/lib/ui";
import { BRAND } from "@/lib/brand";

/**
 * The canvas: the active image with honest rectangle overlays (corner ticks,
 * never fake masks) shown in "before"/original view. Hover highlights a layer;
 * click selects it. Bboxes are normalized [0,1] → % of the stage box.
 */
export function CanvasStage({
  image,
  layers,
  selectedId,
  showBboxes,
  onSelect,
}: {
  image: string | undefined;
  layers: CanvasLayer[];
  selectedId: string | null;
  showBboxes: boolean;
  onSelect: (id: string) => void;
}) {
  const [hoverId, setHoverId] = useState<string | null>(null);

  return (
    <div className="relative flex h-full items-center justify-center overflow-hidden bg-neutral-900 p-6">
      <div className="relative max-h-full max-w-full">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt="scene"
            className="max-h-[calc(100vh-140px)] w-auto rounded-lg shadow-2xl"
          />
        ) : (
          <div className="flex h-[60vh] w-[80vh] items-center justify-center rounded-lg border border-dashed border-neutral-800 text-sm text-neutral-600">
            No image
          </div>
        )}

        {showBboxes &&
          layers.map((l) => {
            const on = l.id === selectedId || l.id === hoverId;
            const c = semanticColor(l);
            return (
              <button
                key={l.id}
                onMouseEnter={() => setHoverId(l.id)}
                onMouseLeave={() => setHoverId(null)}
                onClick={() => onSelect(l.id)}
                title={l.name}
                className="absolute border-2 transition-all"
                style={{
                  left: `${l.bbox.x0 * 100}%`,
                  top: `${l.bbox.y0 * 100}%`,
                  width: `${(l.bbox.x1 - l.bbox.x0) * 100}%`,
                  height: `${(l.bbox.y1 - l.bbox.y0) * 100}%`,
                  borderColor: c,
                  opacity: on ? 1 : 0.35,
                  background: l.id === selectedId ? `${c}22` : "transparent",
                  cursor: "pointer",
                }}
              >
                {/* corner ticks — honest rectangle framing, not a mask */}
                <span className="bbox-tick left-[-1px] top-[-1px] border-l-2 border-t-2" />
                <span className="bbox-tick right-[-1px] top-[-1px] border-r-2 border-t-2" />
                <span className="bbox-tick bottom-[-1px] left-[-1px] border-b-2 border-l-2" />
                <span className="bbox-tick bottom-[-1px] right-[-1px] border-b-2 border-r-2" />
                {l.id === selectedId && (
                  <span
                    className="absolute -top-5 left-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-neutral-950"
                    style={{ background: BRAND.accent }}
                  >
                    {l.name}
                  </span>
                )}
              </button>
            );
          })}
      </div>
    </div>
  );
}
