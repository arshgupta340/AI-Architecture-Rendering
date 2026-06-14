---
type: research
topic: client-side Unreal Engine 5 in the browser (Wonder Interactive / SimplyStream) as a "photoreal hero" toggle
date: 2026-06-13
method: EXA (company_research + advanced search + deep_researcher_pro) — user-flagged gap; agents had only covered pixel-streaming + native JS engines
---

# UE5 client-side in the browser (WASM + WebGPU) — feasibility for a "Cinematic" toggle

> Spawned by the user finding **Wonder Interactive / SimplyStream** ("the death of pixel streaming"). The round-1 agents ([[web3d-realism]], competitor sweep) covered **cloud pixel-streaming** (arcway model) and **native JS engines** (Babylon/PlayCanvas/three.js) but **missed the middle path**: compiling UE5 itself to run client-side via WASM + a custom WebGPU RHI. This doc fills that gap.

## What Wonder Interactive / SimplyStream actually is (verified)
- **Wonder Interactive** (Edmonton, founded 2020, ~2 people, seed-stage, **Epic MegaGrant** recipient). Product = **SimplyStream** (`simplystream.com`, `app.simplystream.com/docs`).
- They built **a WebGPU RHI for UE5 from scratch** (supports UE **5.5–5.7**) + a WASM/Emscripten engine port + an **on-demand asset-streaming** system (small initial chunk, rest streamed). Primary source: Epic forum post by `WonderInteractiv`, 2026-01-21.
- **Self-serve commercial product now:** workflow is *Create Project → **Upload Your Build** → Configure → (Connect Domain) → Deploy & Go Live*. Tiered pricing (PAYG + Indie/Studio/Enterprise), 400+ edge locations.
- **"Smart Rendering" = three modes, auto-selected per device/network:** **local** (client WASM/WebGPU), **hybrid**, **remote** (cloud pixel-streaming). So they cover BOTH the cheap client-side path AND the full-fidelity cloud path under one integration.
- **Live production analog to our use case:** a client-side WebGPU **car configurator** at `garage.cjponyparts.com` (CJ Pony Parts). Also: Lyra sample, Spacelancers, StackGame demos.
- **Maturity caveat (verified, not marketing):** large WASM binaries (tens–hundreds of MB pre-stream), **shader-compile stutter** on first run, CPU-heavy, **Chromium-mainly** (Safari / Apple-Silicon WebGPU spotty). "Console-quality" is real **on limited content + modern desktop**, conditional otherwise.

## The two load-bearing constraints
1. **No Nanite, no Lumen in the browser build** (confirmed by independent porting guides + Epic's own Nanite/Lumen platform notes). Browser-UE = **baked lighting (Lightmass GI) + forward/deferred + screen-space FX + post**. This is the critical reframe: **client-side UE is NOT the arcway/Lumion real-time-GI look** — arcway gets that by **pixel-streaming Lumen+Nanite from a cloud GPU**. Drop those two and UE-in-browser is "baked archviz," which a tuned WebGPU three.js stack can substantially match.
2. **You upload a packaged UE *build*** — content is **authored & baked at build time in the Unreal Editor.** The "asset streaming" only chunks that build's download; it is **not** runtime ingestion of arbitrary external geometry. `glTFRuntime` can load glTF + dynamic materials at runtime in **native** UE, but there is **no public, verified demo of it working inside a browser WASM build** — "plausible but unproven, expect porting work." → **Our live Rhino→glTF scene cannot stream into the UE-WASM runtime today.** The UE view must be a **pre-authored, baked build of the specific model.**

## Licensing
- Standard **UE EULA = 5% royalty on gross revenue above $1M per product** when you ship Engine Code to the client — **a WASM build qualifies.** Pre-rendered images/video are royalty-free; an interactive monetized SaaS is not. Enterprise/custom licensing exists. Real TCO factor vs a royalty-free web-native stack.

## The three honest realism tiers (for "max realism in a browser")
| Tier | Tech | Realism ceiling | Cost | Live per-element swaps? | Vendor risk |
|---|---|---|---|---|---|
| **1. WebGPU three.js** (our stack, upgraded: SSGI/GTAO/TRAA + baked lightmaps + HDRI IBL) | client WebGPU | baked-archviz, ~= client-side UE | **$0** | **Yes (our differentiator)** | none |
| **2. Client-side UE5** (Wonder/SimplyStream "local") | WASM+WebGPU | baked-archviz + UE post/material/asset ecosystem; **no Lumen/Nanite** | hosting + **5% royalty >$1M** | **No** — baked build per model | **2-person startup** |
| **3. Cloud pixel-streamed UE5** (SimplyStream "remote", Vagon, PureWeb — the arcway model) | cloud GPU | **true Lumen+Nanite (the real arcway/Lumion look)** | **~$0.18–2.80 / concurrent-viewer-hr** | Yes (full engine) | medium |

**Key insight:** the thing that makes arcway look unreal is **Lumen+Nanite, which only exist in tier 3 (cloud)**. Client-side UE (tier 2) drops them, landing it close to a well-tuned tier-1 — at the cost of the UE pipeline, royalties, vendor dependency, heaviness, and **losing our live-edit in that view**.

## If we build the "Cinematic (UE5)" toggle — the architecture
- Our **R3F app stays the editor** (live geometry, instant swaps, $0). The toggle does **not** render our live three.js scene in UE.
- Toggle loads a **SimplyStream-hosted UE WebGPU build of the same model** into an embedded canvas/iframe, deep-linked with current **camera + material selections** (URL params / `postMessage`). Toggle back → return to the cheap R3F canvas (exactly the heavy-mode on/off UX the user described).
- **The UE build is authored once per project:** Datasmith/glTF import of the Rhino model → assign PBR materials → **bake Lightmass GI** → build a **material-variant configurator** (Variant Manager / Blueprint) mapped to our **semantic element IDs** → package → upload to SimplyStream.
- **To productize beyond one hero model** you'd need a **templated UE configurator project + an automated build pipeline** (glTF + material-manifest in → bake → deploy). Substantial UE C++/Blueprint + CI work. Initially it's a **manual per-hero-project step**.

## Validated (2026-06-13, in-app spike)
The **app-side toggle is built** (`apps/web3d-prototype/src/Cinematic.tsx` + NavBar button + store `cinematic`/`cinematicUrl`) and verified in-preview. **Embedding works**: SimplyStream builds set no `X-Frame-Options`/CSP block, so `garage.cjponyparts.com` loads inside our `<iframe>` (streamed to 100%). The UE *3D render* needs a working WebGPU adapter (headless preview has `navigator.gpu` but no GPU → black viewport; renders fine in a normal browser). So the in-app "toggle to a photoreal UE build and back" UX is real; remaining = author + upload a UE build of the house (Datasmith → bake → variant configurator → SimplyStream) and paste its URL. Camera-sync into the deep-link is the one open TODO.

## Recommendation
- **Banked now, regardless:** the WebGL2 post-processing + lighting + glass realism wins (N8AO, real glass, HDRI IBL, soft shadows) — they're the base every option toggles *from*, and they're the whole answer for tier 1.
- **For the hero:** prototype the **SimplyStream toggle as a low-commitment spike** (sign up, Datasmith-import the model, deploy one baked build, embed behind a toggle, measure real quality/perf on our model) **before** betting the product on a 2-person platform. In parallel, the **WebGPU three.js** upgrade is the lower-risk route to a *comparable* ceiling with full interactivity, $0, and no royalties.
- **Only reach for tier 3 (pixel-streaming)** if a client demands the literal Lumen/Nanite look while freely navigating — and accept per-viewer GPU cost.

## Sources (primary first)
- Wonder forum (WebGPU RHI, "DM for access", car-configurator demo): https://forums.unrealengine.com/t/webgpu-for-unreal-engine-5-5-6-and-5-7-support/2693960
- SimplyStream about/docs (upload-a-build, local/hybrid/remote smart rendering): https://simplystream.com/about · https://app.simplystream.com/docs
- Live client-side WebGPU car configurator: https://garage.cjponyparts.com/
- Lyra-in-WebGPU demo (2024): https://forums.unrealengine.com/t/lyra-sample-running-in-webgpu-demo-below/1932180
- Khronos talk "Bringing Unreal Engine to the browser" (Wonder, 2022): https://www.khronos.org/assets/uploads/developers/presentations/Bringing_Unreal_Engine_to_the_browser_Wonder_Interactive_Jul22.pdf
- Nanite/Lumen NOT in browser builds (porting guide): https://docs.spawnd.gg/docs/web-porting-in-unreal-wip
- glTFRuntime (runtime glTF + dynamic materials, native UE; WASM unverified): https://github.com/rdeioris/glTFRuntime
- UE EULA / 5% royalty: https://www.unrealengine.com/license
- HN "SimplyStream – UE5 meets WebGPU": https://news.ycombinator.com/item?id=42190897

**See also:** [[arcway-teardown]] (the cloud-Lumen competitor this contrasts) · [[web3d-webgpu]] (tier-1, the $0 WebGPU path we banked) · [[web3d-realism]] · [[STATE]] (the Cinematic toggle's built status). Rationale: [[DECISIONS#web3d-realism-tiers]] · [[DECISIONS#client-ready-render]].
