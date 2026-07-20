"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Before / after comparison for the edit result.
 * - segmented toggle (Original / Edited)
 * - in Edited view, a draggable split slider wipes between original + edited
 *   inside the same stage (clipped images; honest rectangle, not a mask)
 * - drift badge: how much of the composite changed outside the edited region
 */
export function BeforeAfter({
  before,
  after,
  view,
  onView,
  driftScore,
}: {
  before: string | undefined;
  after: string | undefined;
  view: "before" | "after";
  onView: (v: "before" | "after") => void;
  driftScore: number;
}) {
  const [split, setSplit] = useState(50);
  const [dragging, setDragging] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const onMove = useCallback((clientX: number) => {
    const box = boxRef.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setSplit(Math.max(0, Math.min(100, pct)));
  }, []);

  const driftPct = (driftScore * 100).toFixed(1);

  return (
    <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-3">
      <div className="flex gap-1 rounded-lg border border-neutral-700 bg-neutral-900/90 p-1 text-xs backdrop-blur">
        {(["before", "after"] as const).map((v) => (
          <button
            key={v}
            onClick={() => {
              onView(v);
              setSplit(50);
            }}
            className={`rounded px-3 py-1 transition-colors ${
              view === v
                ? "bg-neutral-100 text-neutral-900"
                : "text-neutral-300 hover:text-neutral-100"
            }`}
          >
            {v === "before" ? "Original" : "Edited"}
          </button>
        ))}
      </div>

      <span
        className="rounded-lg border border-neutral-700 bg-neutral-900/90 px-2.5 py-1 text-[11px] font-mono text-neutral-400 backdrop-blur"
        title="How much of the composite changed outside the edited region"
      >
        {driftPct}% outside-edit change
      </span>

      {view === "after" && (
        <div
          ref={boxRef}
          className="absolute inset-x-0 bottom-14 mx-auto h-2 max-w-md cursor-ew-resize"
          onMouseDown={() => setDragging(true)}
          onMouseUp={() => setDragging(false)}
          onMouseLeave={() => setDragging(false)}
          onMouseMove={(e) => dragging && onMove(e.clientX)}
          onTouchStart={() => setDragging(true)}
          onTouchEnd={() => setDragging(false)}
          onTouchMove={(e) => onMove(e.touches[0].clientX)}
        >
          <div
            className="absolute top-1/2 h-4 w-0.5 -translate-y-1/2 bg-white/80"
            style={{ left: `${split}%` }}
          >
            <div className="absolute -top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full border border-white/80 bg-neutral-900" />
          </div>
        </div>
      )}
    </div>
  );
}
