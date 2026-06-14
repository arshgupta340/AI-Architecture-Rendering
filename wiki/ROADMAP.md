---
type: roadmap
updated: 2026-06-14
---

# Roadmap

> ⚠️ **Superseded by the engine-first web3d pivot (2026-06-13/14).** The active direction is now the web 3D rendering tool (`apps/web3d-prototype/`) — see [[STATE]] and [[DECISIONS#web3d-pivot]]. The plugin-first **M1–M4** below is the **prior arc**; its keystone insight (extract host **geometry + semantic IDs** instead of reverse-engineering them from pixels) carried *directly* into web3d, which realizes that ground truth as real 3D rather than ID masks. **Next milestone = the "decked-out, client-ready render" push** (material library at scale · real entourage · Gaussian-splat environment · consistency-locked diffusion hero) — plan + paste-in prompt in [[../docs/HANDOFF-web3d.md]] §Next-steps; direction at [[DECISIONS#client-ready-render]]. The Revit add-in (M4) is deferred behind that.

Strategic milestones under the plugin-first pivot ([[DECISIONS#plugin-first-pivot]], [master plan v2](../docs/plans/master-plan.md)). The live experiment board is [docs/plans/experiments.md](../docs/plans/experiments.md).

**Status (2026-06-13): M1 ✓, M2 ✓, M3 ✓, M4 partial** — the full plugin-first loop works end to end (Grasshopper capture → locked render → ground-truth masks → swatch edit → non-destructive layers → multi-view consistency). Only M4's **Revit add-in** remains. Next focus is the material library + Revit; see [[STATE]] "what to do next".

---

## M1 — Prove the keystone: host ground-truth extraction (E1 + E6) — ✓ DONE

E1 PASSED (93.1% decode, mullions per-instance), E6 PASSED (GT mask → composite, zero leakage). Reports `spike/REPORTS/E1.md`, ladder result log in `docs/plans/experiments.md`.

### (original M1 spec below)
## M1 — Prove the keystone: host ground-truth extraction (E1 + E6)

**Goal:** Demonstrate that Rhino can export pixel-accurate per-object ID masks + usable true depth + an object/material table, and that those masks drive the existing edit pipeline with tag+segment deleted.

**Entry:** Rhino running with the MCP bridge; a real model open. $0.

**Exit gate:** E1 — masks accurate at 1:1 zoom incl. thin mullions, depth usable after linearization; E6 — edit quality ≥ the T24/T25 SAM2-mask baseline.

**Fallback if E1 fails:** conduit issues → try the display-mode-INI approach or temporary material swap; if depth is the blocker, proceed with masks-only (depth from monocular estimation) — the semantic/mask win alone justifies the tier.

---

## M2 — Pick the generative stack (E2 + E3 + E4 + E5) — ✓ DONE

Locked: render = depth+canny union ([[DECISIONS#render-mask-registration]]); material = hosted FLUX.2 Edit + mask composite ([[DECISIONS#material-apply-hosted]]); tier-2 tagging deferred (plugin tier wins decisively; Vision Banana non-public). E4/E5 reports filed.

### (original M2 spec below)
## M2 — Pick the generative stack (E2 + E3 + E4 + E5)

**Goal:** Lock the render conditioning (true-depth+canny vs FLUX.2 Edit vs Nano Banana) and the swatch-conditioning method (hosted multi-ref vs MatSwap contingency); pick the tier-2 tagging stack.

**Entry:** E1 artifacts; `FAL_KEY` from user. ~$8 of the $50 budget.

**Exit gates:** E2 — ≥1 renderer with zero critical failures; E3 — blind viewer names the material; E4/E5 — tier-2 stack chosen by IoU vs E1 ground truth.

**Fallbacks:** E3 all-fail → MatSwap on Modal (pre-authorized). E2 all-fail → hybrid two-pass (structure pass + material pass).

---

## M3 — Rhino capture plugin + layer-model canvas prototype — ✓ DONE

`spike/rhino_capture.py` (idempotent in-session, [[DECISIONS#capture-overload]]) + the Grasshopper "Send to Canvas" component (`spike/grasshopper/`) + the canvas (`apps/canvas-prototype/`): capture → render → click region → swatch → non-destructive layer, eye-toggle, replace-not-stack, localStorage, capture→canvas auto-reload. The make-or-break layer model holds.

### (original M3 spec below)
## M3 — Rhino capture plugin + layer-model canvas prototype

**Goal:** Replace the MCP probe with a real capture path (Grasshopper component fast path 3–5 days; full .rhp ~2 weeks) and prototype the scene-graph layer model + canvas on E1's real exports — the make-or-break design decision.

**Entry:** M1 + M2 passed.

**Exit gate:** the killer flow works on one real Rhino model: capture → render → click region → swatch → layer; toggle < 1s from cache; re-swap replaces, not stacks.

---

## M4 — Multi-view material lock + second host (Revit) — ◑ PARTIAL

**Multi-view lock: ✓ DONE** — "one swatch → all views" in the canvas, material-class-branched lock ([[DECISIONS#multiview-material-class]]); `spike/multiview_apply.py`, `/api/apply_material_all`, view tabs.
**Revit add-in: ☐ PENDING** — native BIM semantics (incl. `OST_CurtainWallMullions`), clean ID masks via SetElementOverrides+ExportImage, no depth API (estimate depth or third-party pass). The host-integration research has the per-host plan: [docs/plans/research/host-integration.md](../docs/plans/research/host-integration.md).

**Exit gate (Revit):** Revit capture produces category-labeled masks out of the box and drives the same canvas loop.

---

## Beyond (sketches, not commitments)

Material library seeding (ambientCG → swatches; manufacturer-SKU partnerships as moat) · web canvas MVP productionization (Next.js + Konva) · SketchUp plugin · private beta (~10 architects) · material write-back into the host (`ModifyRenderMaterial` / `doc.Paint`) · watch: Vision Banana public API, HiFi-Inpaint-class FLUX material transfer.
