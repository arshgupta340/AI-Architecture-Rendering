<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Reve Canvas — app manual

Architecture-native layer editor wrapping Reve 2.x's layout API. The 2D
fast-to-market sibling of the mesh-first 3D track. PRD:
`../../docs/plans/PRD-reve-canvas.md`. Spike evidence + the validated edit
pipeline: `../../spike/REPORTS/reve_spike.md`. This is a **thin vertical slice**
(no auth/persistence/credits yet — those are the next phase).

## Stack & run
- Next.js 16 (App Router, Turbopack) + React 19 + Tailwind 4. Node 24.
- Dev: `npm run dev` → http://localhost:5182 (or `preview_start` name `reve-canvas`).
- Mode: `.env.local` `REVE_MODE=mock` for $0 dev; `REVE_MODE=live` (or a key present)
  hits real Reve (~$0.21/edit, ~35s). The key is read from `REVE_API_KEY`, with a
  dev fallback to `../../spike/.env` — **server-side only, never shipped to the browser.**

## The validated edit pipeline (do not change without re-spiking)
`extract_layout(image)` → `create_layout(references=[{image, layout}], commands=[{op:"change", label, new_description}])` → `render_layout(edited_layout, references=[{image}])` with the layout width/height pinned to the source aspect. Proven 2026-07-16: swaps materials with geometry pixel-locked (1.34% drift), RegionKey labels round-trip.

## Non-negotiable invariants (PRD §2, spike findings)
- **Reve key is server-only.** All Reve calls go through `src/lib/reve/client.ts`
  (marked `server-only`) via the `/api/extract` and `/api/edit` route handlers.
- **Edit from the ORIGINAL, never chain Reve outputs.** Each edit re-runs from the
  source image + one change-command → drift can't compound.
- **Region model is object-level.** One `CanvasLayer` = one Reve region. A building
  envelope (`isBuilding`) exposes material FACETS (cladding/roof/trim/foundation),
  each rewriting a clause of that region's description. `render_layout` prompt-rewrite
  does NOT change material (reference dominates) — always use the change-command.
- **No user-visible multi-model.** (Reve license.) **Honest UI** — bboxes are
  rectangles, not masks.

## Layout
- `src/lib/reve/types.ts` — Reve API types (verbatim SDK mirror).
- `src/lib/reve/client.ts` — server-only client + mock mode; the 3-call pipeline.
- `src/lib/reve/mock/` — cached fixtures (real exterior layout + travertine result) for $0 dev.
- `src/lib/model.ts` — CanvasLayer, RegionKey, autoLayerize, pinAspect, buildChangeDescription.
- `src/lib/taxonomy/` — **VENDORED copy** of `packages/arch-taxonomy` (see its README;
  keep in sync; drop it once real monorepo workspace wiring lands).
- `src/app/api/{extract,edit}/route.ts` — the two route handlers.
- `src/app/page.tsx` — upload → region overlay → object layer panel → facet+material picker → render → before/after.

## Next phase (not built yet)
Supabase auth + snapshot/edit-graph persistence + credit metering + job queue;
masked-delta composite-back onto the source (currently shows the aspect-pinned
render directly); version tree + variants + drift-score badge; Rhino bridge.
Display already downscales the render for the canvas (full-res kept for export).
