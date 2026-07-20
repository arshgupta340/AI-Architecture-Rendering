import { FACET_LABEL, type EnvelopeFacet } from "@/lib/model";

/** Facet selector chips for a building-envelope layer. */
export function FacetChips({
  facets,
  active,
  onSelect,
}: {
  facets: EnvelopeFacet[];
  active: EnvelopeFacet;
  onSelect: (f: EnvelopeFacet) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">
        Facet
      </p>
      <div className="flex flex-wrap gap-1">
        {facets.map((f) => (
          <button
            key={f}
            onClick={() => onSelect(f)}
            className={`rounded px-2 py-1 text-xs transition-colors ${
              active === f
                ? "bg-neutral-100 text-neutral-900"
                : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
            }`}
          >
            {FACET_LABEL[f]}
          </button>
        ))}
      </div>
    </div>
  );
}
