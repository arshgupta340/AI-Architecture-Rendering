---
type: roadmap
updated: 2026-06-12
---

# Roadmap

Strategic milestones under the plugin-first pivot ([[DECISIONS#plugin-first-pivot]], [master plan v2](../docs/plans/master-plan.md)). The live experiment board is [docs/plans/experiments.md](../docs/plans/experiments.md). The pre-pivot M1–M3 (Spike 3 gate / B3 bake-off / Spike 4 live run) are retired — their goals were absorbed or superseded; see git history of this file.

---

## M1 — Prove the keystone: host ground-truth extraction (E1 + E6)

**Goal:** Demonstrate that Rhino can export pixel-accurate per-object ID masks + usable true depth + an object/material table, and that those masks drive the existing edit pipeline with tag+segment deleted.

**Entry:** Rhino running with the MCP bridge; a real model open. $0.

**Exit gate:** E1 — masks accurate at 1:1 zoom incl. thin mullions, depth usable after linearization; E6 — edit quality ≥ the T24/T25 SAM2-mask baseline.

**Fallback if E1 fails:** conduit issues → try the display-mode-INI approach or temporary material swap; if depth is the blocker, proceed with masks-only (depth from monocular estimation) — the semantic/mask win alone justifies the tier.

---

## M2 — Pick the generative stack (E2 + E3 + E4 + E5)

**Goal:** Lock the render conditioning (true-depth+canny vs FLUX.2 Edit vs Nano Banana) and the swatch-conditioning method (hosted multi-ref vs MatSwap contingency); pick the tier-2 tagging stack.

**Entry:** E1 artifacts; `FAL_KEY` from user. ~$8 of the $50 budget.

**Exit gates:** E2 — ≥1 renderer with zero critical failures; E3 — blind viewer names the material; E4/E5 — tier-2 stack chosen by IoU vs E1 ground truth.

**Fallbacks:** E3 all-fail → MatSwap on Modal (pre-authorized). E2 all-fail → hybrid two-pass (structure pass + material pass).

---

## M3 — Rhino capture plugin + layer-model canvas prototype

**Goal:** Replace the MCP probe with a real capture path (Grasshopper component fast path 3–5 days; full .rhp ~2 weeks) and prototype the scene-graph layer model + canvas on E1's real exports — the make-or-break design decision.

**Entry:** M1 + M2 passed.

**Exit gate:** the killer flow works on one real Rhino model: capture → render → click region → swatch → layer; toggle < 1s from cache; re-swap replaces, not stacks.

---

## M4 — Multi-view material lock + second host (Revit)

**Goal:** Materials lock across N saved views (anchor-reference technique); Revit add-in brings native BIM semantics (zero layer-discipline needed).

**Exit gate:** change one material → propagates coherently to all views; Revit capture produces category-labeled masks out of the box.

---

## Beyond (sketches, not commitments)

Material library seeding (ambientCG → swatches; manufacturer-SKU partnerships as moat) · web canvas MVP productionization (Next.js + Konva) · SketchUp plugin · private beta (~10 architects) · material write-back into the host (`ModifyRenderMaterial` / `doc.Paint`) · watch: Vision Banana public API, HiFi-Inpaint-class FLUX material transfer.
