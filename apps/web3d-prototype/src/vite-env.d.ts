/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional Google Maps Tiles API key for the geo-context 3D Tiles feature. */
  readonly VITE_GOOGLE_MAPS_API_KEY?: string;
  /** FLUX.1 hero backend — the live default. Set these once in `.env.local` and the
   *  Hero render connects out of the box (no per-session credential paste). FLUX.2
   *  stays manual (deploy-gated). See `apps/web3d-prototype/.env.example`. */
  readonly VITE_HERO_BASE_URL?: string; // …heroflux-web.modal.run/hero_render
  readonly VITE_HERO_REGION_URL?: string; // …heroflux-web.modal.run/region_edit
  readonly VITE_HERO_SECRET?: string; // your HERO_SHARED_SECRET
}
