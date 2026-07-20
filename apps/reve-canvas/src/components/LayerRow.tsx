import type { CanvasLayer } from "@/lib/model";
import { semanticColor } from "@/lib/ui";

/** One row in the layer rail — color dot, name, semantic class. */
export function LayerRow({
  layer,
  selected,
  onSelect,
}: {
  layer: CanvasLayer;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const c = semanticColor(layer);
  return (
    <button
      onClick={() => onSelect(layer.id)}
      className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors hover:bg-neutral-900 ${
        selected ? "bg-neutral-900" : ""
      }`}
    >
      <span
        className="h-2.5 w-2.5 shrink-0 rounded-sm"
        style={{ background: c }}
      />
      <span className="flex-1 truncate text-neutral-200">{layer.name}</span>
      <span className="text-[10px] uppercase tracking-wide text-neutral-500">
        {layer.semantic}
      </span>
    </button>
  );
}
