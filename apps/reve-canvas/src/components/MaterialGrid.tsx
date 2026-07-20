"use client";

import { useMemo, useState } from "react";
import type { MaterialScaffold } from "@/lib/model";

/**
 * Searchable material picker, grouped by category, with color swatch chips.
 * Groups preserve taxonomy category order; search filters across label + tags.
 */
export function MaterialGrid({
  materials,
  busy,
  onPick,
}: {
  materials: MaterialScaffold[];
  busy: boolean;
  onPick: (id: string) => void;
}) {
  const [q, setQ] = useState("");

  const grouped = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = needle
      ? materials.filter(
          (m) =>
            m.label.toLowerCase().includes(needle) ||
            m.tags.some((t) => t.includes(needle)) ||
            m.category.toLowerCase().includes(needle),
        )
      : materials;

    const order: string[] = [];
    const byCat = new Map<string, MaterialScaffold[]>();
    for (const m of filtered) {
      if (!byCat.has(m.category)) {
        byCat.set(m.category, []);
        order.push(m.category);
      }
      byCat.get(m.category)!.push(m);
    }
    return order.map((cat) => ({ cat, items: byCat.get(cat)! }));
  }, [materials, q]);

  if (materials.length === 0) {
    return (
      <p className="text-xs text-neutral-500">
        No material presets for this object type yet.
      </p>
    );
  }

  return (
    <div>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search materials…"
        className="mb-3 w-full rounded border border-neutral-800 bg-neutral-950 px-2.5 py-1.5 text-xs text-neutral-200 placeholder:text-neutral-600 focus:border-neutral-600 focus:outline-none"
      />
      <div className="space-y-3">
        {grouped.map(({ cat, items }) => (
          <div key={cat}>
            <p className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-600">
              {cat}
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {items.map((m) => (
                <button
                  key={m.id}
                  onClick={() => onPick(m.id)}
                  disabled={busy}
                  title={m.prompt}
                  className="flex items-center gap-2 rounded border border-neutral-800 px-2 py-1.5 text-left text-xs text-neutral-200 transition-colors hover:border-neutral-600 hover:bg-neutral-900 disabled:opacity-50"
                >
                  <span
                    className="h-4 w-4 shrink-0 rounded-sm border border-black/30"
                    style={{ background: m.color }}
                  />
                  <span className="truncate">{m.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
        {grouped.length === 0 && (
          <p className="text-xs text-neutral-500">No materials match “{q}”.</p>
        )}
      </div>
    </div>
  );
}
