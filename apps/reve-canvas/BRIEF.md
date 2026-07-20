# BRIEF — Workstream C: brand + productized UI (branch `wt/brand`)

You are building ONE of three parallel workstreams on the Reve Canvas app. Others are
building (A) Supabase auth/persistence and (B) a masked-delta composite lib in
sibling worktrees. You OWN the UI surface. Your work merges LAST, on top of theirs.

## Orient (do this first)
1. Read `apps/reve-canvas/AGENTS.md` — the invariants are non-negotiable (honest
   rectangles not masks; no user-visible multi-model; edits batch behind explicit
   actions; costs always visible).
2. `cd apps/reve-canvas && npm install`, create `.env.local` containing exactly:
   `REVE_MODE=mock`
   `npm run dev` (port 5182). Walk the flow: landing → "Use sample building" →
   layer panel (12 objects) → House 1 → facet chips → material grid → mock render →
   before/after toggle. THAT feature set must all survive your redesign.

## Hard rules
- **ZERO live API calls** (mock only — the Reve budget is at its cap). Never commit `.env*`.
- Never touch `spike/`, `wiki/`, `docs/`, other apps, `packages/`, `src/lib/reve/`,
  `src/lib/model.ts`, `src/lib/taxonomy/`, or the `src/app/api/` routes. Your surface
  is: `src/app/page.tsx`, `src/app/layout.tsx`, `src/app/globals.css`,
  `src/components/**` (new), `src/lib/brand.ts` (new), `BRAND.md` (new), plus
  `src/app/icon`/metadata assets.
- Commit on `wt/brand`; `npm run build` green before finishing.

## Part 1 — Brand
The internal name "Reve Canvas" CANNOT ship (trademark risk — it's the upstream
model vendor's name). In `BRAND.md`: propose 5 product names for an architect-facing
layer-based AI editing canvas (evocative of layers/materials/architecture; check each
has no obvious big-name collision — reasoning only, no web access needed; .com-style
plausibility is enough). Pick the strongest, state why in 3 sentences. Then create
`src/lib/brand.ts`:
```ts
export const BRAND = { name: "<ChosenName>", tagline: "<short tagline>", accent: "<hex>" };
```
ALL UI copy must consume `BRAND` — renaming later must be a one-file change. Design a
simple typographic logo treatment (text-based, no image assets required) and a
matching favicon via `src/app/icon.tsx` (Next.js dynamic icon) or an inline SVG.

## Part 2 — Productize the UI
Refactor the single-file `page.tsx` into `src/components/` (keep ALL existing state
logic and the exact `/api/extract` + `/api/edit` request/response contracts — read
`page.tsx` carefully first; it is the spec):
- `Landing.tsx` — a real landing/upload hero: brand, one-line value prop ("Your
  render, in layers — swap any material without re-rendering the world"), drag-drop
  zone + sample button, 3 quiet feature bullets (element-aware layers · geometry-locked
  edits · full version trail). Dark, architectural, editorial — think Linear/Arc-level
  polish, not template SaaS.
- `Workspace.tsx` — the editor shell: canvas center, layer rail right, slim header
  (brand mark, mode pill, session cost), status/queue toast area.
- `LayerRail.tsx`, `LayerRow.tsx`, `FacetChips.tsx`, `MaterialGrid.tsx` (searchable,
  grouped by category, swatch color chips), `CanvasStage.tsx` (image + hover-linked
  bbox overlays — rectangles with corner ticks, NOT fake masks), `BeforeAfter.tsx`
  (keep toggle; add a draggable split-slider if quick), `CostPill.tsx`.
- Loading states with progress copy for the ~35s live path ("Reading the scene…",
  "Rendering your edit — ~35s"); empty/error states; keyboard: Esc deselects.
- Tailwind 4 only, no new UI deps. Respect `prefers-reduced-motion`.

## Composite integration (contract with workstream B — code against it blind)
B is implementing exactly:
```ts
// src/lib/composite.ts
export interface BBox { x0:number; y0:number; x1:number; y1:number }
export interface CompositeResult { dataUrl: string; driftScore: number; maskDataUrl: string }
export async function applyMaskedDelta(originalDataUrl: string, renderDataUrl: string,
  editedBboxes: BBox[], opts?: {featherPx?: number; padPct?: number}): Promise<CompositeResult>;
```
Create a STUB at `src/lib/composite.ts` with this exact signature whose body just
returns `{ dataUrl: renderDataUrl, driftScore: 0, maskDataUrl: "" }` and a first line
comment: `// STUB — replaced wholesale by wt/composite at merge. Do not extend.`
In the edit-result flow: call `applyMaskedDelta(original, render, [editedLayer.bbox])`,
show the composite as the "Edited" view, and render a small drift badge
(`{(driftScore*100).toFixed(1)}% outside-edit change`) near the before/after toggle.

## Definition of done
- Full flow works in mock mode end-to-end with the new UI (landing → extract → select →
  facet → material → render → composited before/after + drift badge).
- Brand consumed exclusively from `src/lib/brand.ts`; `BRAND.md` written.
- `npm run build` green; committed on `wt/brand`.
