---
type: research
topic: competitor teardown — arcway.ai
date: 2026-06-13
---

# Arcway.ai teardown (the spark for the web3d direction)

> Web research (WebSearch/exa + job postings + LinkedIn). This analysis is what motivated the engine-first web3d build.

## What Arcway is
End-to-end 3D **decision platform for production homebuilders** (Caleb Barclay, CEO; co-founder Chris Nixon; ex-Figma/Coinbase/Xsolla/Modern Health; investors incl. **Koen Bok & Jorn van Dijk — Framer's founders**, hence the Framer marketing site). Buyers walk a plan in-browser, swap finishes, watch live pricing. White-labeled at `yourbrand.arcway.ai`.

## How the rendering works — **Unreal Engine 5, pixel-streamed**
NOT three.js / in-browser WebGL. The decisive tell is their own job postings requiring **Unreal Engine + Nanite + Lumen** ("luxury archviz realism," "real-time," "configurator pipeline"). Nanite/Lumen can't run in a browser ⇒ rendering happens on a **cloud GPU**, streamed to the browser as **WebRTC video (pixel streaming)**; the browser is a thin client sending input. Corroborated by the whole adjacent industry (NOVAVERSE, QOOP/Flat-Finder, Arkwiz/Geos all describe UE + Pixel Streaming + WebRTC). Photorealism = authored PBR assets + Lumen/path-trace, **no diffusion in the loop**. Cost: GPU per concurrent viewer (QOOP "sunset" their pixel-streamed UE pipeline on cost) + per-plan 3D-artist labor.

**Arcway ≠ Arcware** (arcware.com = separate German UE pixel-streaming-as-a-service co).

## Bridge AI (launched ~2026-06-10)
Blueprint → full walkable UE home, every plan + structural option, "days not months." Still needs human 3D artists (they're hiring Senior 3D Environment Artists). It exists to **reverse-engineer geometry + semantics from flat PDFs**.

## The strategic insight for us
Arcway proves: with **real geometry + a real renderer**, multi-view consistency + instant swaps are *free* — exactly what diffusion (our old 2D spike) bleeds on. **Our unfair advantage:** we already have clean geometry + semantic IDs from Rhino — the thing Bridge AI is built to manufacture. So go engine-first (web 3D) and reserve diffusion for the final hero frame. This is the origin of the [[STATE|web3d]] direction.

**See also:** [[web3d-ue-browser]] (the client-side-UE path Arcway's cloud-Lumen model implies) · [[web3d-rhino-gltf]] (our geometry + semantic IDs — exactly what Bridge AI reverse-engineers from PDFs) · [[DECISIONS#web3d-pivot]] · [[STATE]].
