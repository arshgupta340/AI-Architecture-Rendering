# Vendored copy of `packages/arch-taxonomy`

This is a **vendored copy** of the canonical `packages/arch-taxonomy` source, kept
in-app to avoid Turbopack cross-package-root resolution friction in the thin
slice. The canonical package at `packages/arch-taxonomy/` remains the source of
truth (and the 3D-track convergence artifact).

**When wiring the real monorepo** (npm workspaces / a proper build), delete this
folder and consume `arch-taxonomy` as a package dependency again. Until then,
keep the two in sync — edit `packages/arch-taxonomy` and re-copy `semantics.ts`,
`materials.ts`, `index.ts` here.
