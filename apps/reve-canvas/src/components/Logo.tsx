import { BRAND } from "@/lib/brand";

/**
 * Typographic logo treatment — text only, no image asset required.
 * "Strata" with a stacked-letters mark that hints at layered strata.
 */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 select-none ${className}`}
      aria-label={BRAND.name}
    >
      <span
        aria-hidden
        className="grid h-5 w-5 grid-cols-2 gap-px rounded-[3px] bg-neutral-800 p-[3px]"
        style={{ boxShadow: `inset 0 0 0 1px ${BRAND.accent}55` }}
      >
        <span className="rounded-[1px]" style={{ background: BRAND.accent, opacity: 0.5 }} />
        <span className="rounded-[1px]" style={{ background: BRAND.accent, opacity: 0.8 }} />
        <span className="rounded-[1px]" style={{ background: BRAND.accent, opacity: 1 }} />
        <span className="rounded-[1px]" style={{ background: BRAND.accent, opacity: 0.65 }} />
      </span>
      <span className="text-[15px] font-semibold tracking-tight text-neutral-50">
        {BRAND.name}
      </span>
    </span>
  );
}
