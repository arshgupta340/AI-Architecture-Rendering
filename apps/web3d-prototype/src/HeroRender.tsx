import { useStore } from "./state/store";

/**
 * STUB (Phase 0) — filled by the hero-modal agent.
 *
 * Full-screen overlay modal (mirror Cinematic.tsx). When `hero.open`, shows the
 * captured beauty as the base, Photoshop controls (prompt/seed/canny+depth
 * strengths), a layer panel (base + region inpaint layers; re-roll/visibility/
 * reorder/delete), and Generate/Run-region actions that POST the capture buffers to
 * the Modal FLUX endpoints (store.heroEndpoint). "Save hero" reuses exportImage.
 */
export function HeroRender() {
  const open = useStore((s) => s.hero.open);
  const closeHero = useStore((s) => s.closeHero);
  if (!open) return null;
  // Minimal stub overlay so the open/close wiring is testable before the real UI.
  return (
    <div
      onClick={closeHero}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "grid",
        placeItems: "center",
        background: "rgba(10,11,13,0.92)",
        color: "#9aa4b2",
        font: "14px ui-sans-serif, system-ui",
        cursor: "pointer",
      }}
    >
      Hero render modal — coming up. (click to close)
    </div>
  );
}
