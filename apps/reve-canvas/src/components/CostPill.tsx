import { BRAND, MODE_COPY } from "@/lib/brand";

/**
 * Slim header pill: shows the active mode and the running session cost.
 * Costs are always visible (PRD invariant).
 */
export function CostPill({ mode, spent }: { mode: "mock" | "live"; spent: number }) {
  const copy = MODE_COPY[mode];
  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`rounded px-2 py-1 font-medium ${
          mode === "live"
            ? "bg-emerald-900 text-emerald-200"
            : "bg-neutral-800 text-neutral-300"
        }`}
      >
        {copy.label} · {copy.sub}
      </span>
      <span className="font-mono text-neutral-400">
        session ${spent.toFixed(3)}
      </span>
    </div>
  );
}
