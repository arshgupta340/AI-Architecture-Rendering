import { useEffect, useMemo, useRef, useState } from "react";
import { useStore, type HeroLayer, type HeroCaptureData, DEFAULT_HERO_SCALES, DEFAULT_HERO_ENDPOINT } from "./state/store";
import { SWATCHES } from "./lib/swatches";
import { bakeFromHeroViews } from "./lib/splatBake";
import { downloadBlob } from "./lib/exportImage";

/** One multi-view turntable frame: the photoreal render + its bake-ready pose. */
type MvResult = {
  label: string;
  preview: string | null; // object URL (or beauty data URL while pending) for display
  imageB64: string | null; // bare b64 PNG of the hero render — for the splat bake
  transform: number[][]; // 4×4 c2w row-major
  width: number;
  height: number;
  fov: number;
  status: "pending" | "done" | "error";
};

/**
 * HeroRender — the depth+canny-locked diffusion "hero" modal.
 *
 * Opened by the NavBar "Hero render" button (which captures beauty/depth/ids from
 * the live WebGL2 scene via lib/heroCapture.ts and calls openHero(capture)). Runs a
 * self-hosted FLUX.1-dev + ControlNet-Union (canny+depth) backend on Modal
 * (spike/modal_flux.py) for a photoreal, GEOMETRY-LOCKED render, with a Photoshop
 * layer system:
 *   • BASE layer   — full-frame geometry lock (depth + canny ∪ id-edges).
 *   • REGION layers — each re-renders the base with one element class re-prompted
 *     (material / vegetation), and the server returns that region masked. The
 *     preview composites base + every visible region (via its mask) on the client,
 *     so each region is an INDEPENDENT, re-rollable edit and untouched pixels stay
 *     byte-stable. Same seed + same controls → consistent across generations.
 *
 * The backend is a pair of Modal HTTPS endpoints + a shared secret (heroEndpoint);
 * paste them in the setup card after `modal deploy spike/modal_flux.py`.
 */

const MAX_HERO_CALLS = 24; // session cap — the Modal GPU costs real money
let heroCalls = 0;

const DEFAULT_PROMPT =
  "A warm, photorealistic golden-hour architectural exterior photograph of the " +
  "building, crisp materials, soft long shadows, clear sky, shot on a DSLR, high " +
  "detail. Preserve every edge, window, trim line and roof plane exactly — the line " +
  "drawing is binding.";

// ---- networking ---------------------------------------------------------------

function b64ToBlob(b64: string, type = "image/png"): Blob {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type });
}

async function postHero(url: string, body: Record<string, unknown>): Promise<{ image: string; mask?: string; seed: number; ms: number }> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error */
    }
    throw new Error(detail === "401" || res.status === 401 ? "Auth failed — check the shared secret." : `Backend error: ${detail}`);
  }
  return res.json();
}

/** Derive the cheap keep-alive URL from the base-render URL (…/hero_render → …/warm). */
function warmEndpoint(baseUrl: string): string {
  return baseUrl.replace(/\/hero_render\/?$/, "/warm");
}

/**
 * Rewrite a hero endpoint URL between the FLUX.1 (live) and FLUX.2 (experimental) Modal
 * apps — same workspace, different app name. Lets the Backend panel switch models with
 * one click given either URL. FLUX.1 = spike/modal_flux.py (A100, live-verified); FLUX.2
 * = spike/modal_flux2.py (H200 + VideoX-Fun, deploy-gated; see flux2_feasibility.md).
 */
function switchModelUrl(url: string, to: "flux1" | "flux2"): string {
  if (!url) return url;
  return to === "flux2"
    ? url.replace(/arch-rendering-flux-heroflux/g, "arch-rendering-flux2-heroflux2")
    : url.replace(/arch-rendering-flux2-heroflux2/g, "arch-rendering-flux-heroflux");
}

/** Which backend a base URL points at (used to label the model preset). */
function modelOfUrl(url: string): "flux1" | "flux2" {
  return /flux2-heroflux2/.test(url) ? "flux2" : "flux1";
}

/** Ping /warm to reset the container's scaledown timer; returns the backend model id. */
async function pingWarm(baseUrl: string, secret: string): Promise<string | null> {
  try {
    const res = await fetch(warmEndpoint(baseUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret }),
    });
    if (!res.ok) return null;
    const j = await res.json();
    return (j?.model as string) ?? "warm";
  } catch {
    return null;
  }
}

/** Shared render params from a layer → the Modal request body (sans images). */
function layerParams(layer: HeroLayer, neg: string, secret: string) {
  return {
    secret,
    prompt: layer.prompt,
    negative_prompt: neg,
    seed: layer.seed,
    steps: layer.steps,
    guidance_scale: layer.guidance,
    true_cfg_scale: neg.trim() ? 4.0 : 1.0, // enable the negative prompt only if one is set
    canny_scale: layer.scales.canny,
    canny_end: layer.scales.cannyEnd,
    depth_scale: layer.scales.depth,
    depth_end: layer.scales.depthEnd,
  };
}

// ---- client-side mask compositing (base + visible region layers) --------------

function loadImg(url: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error("image load failed"));
    im.src = url;
  });
}

/** Composite the base layer + each visible region layer (via its mask) → object URL. */
async function compositeHero(capture: HeroCaptureData, layers: HeroLayer[]): Promise<string | null> {
  const base = layers.find((l) => l.kind === "base");
  const baseUrl = base?.resultUrl ?? `data:image/png;base64,${capture.beauty}`;
  const W = capture.width;
  const H = capture.height;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  ctx.drawImage(await loadImg(baseUrl), 0, 0, W, H);

  for (const layer of layers) {
    if (layer.kind !== "region" || !layer.visible || !layer.resultUrl) continue;
    const img = await loadImg(layer.resultUrl);
    if (layer.maskUrl) {
      // Mask the region result to its element, then paint over the running composite.
      const tmp = document.createElement("canvas");
      tmp.width = W;
      tmp.height = H;
      const tctx = tmp.getContext("2d")!;
      tctx.drawImage(img, 0, 0, W, H);
      tctx.globalCompositeOperation = "destination-in";
      tctx.drawImage(await loadImg(layer.maskUrl), 0, 0, W, H);
      ctx.drawImage(tmp, 0, 0);
    } else {
      ctx.drawImage(img, 0, 0, W, H);
    }
  }
  return await new Promise<string | null>((resolve) =>
    canvas.toBlob((b) => resolve(b ? URL.createObjectURL(b) : null), "image/png"),
  );
}

// ---- material prompt helper ---------------------------------------------------

function materialClause(swatchId: string): string {
  const sw = SWATCHES.find((s) => s.id === swatchId);
  if (!sw) return "";
  return `${sw.label.toLowerCase()} (${sw.tags.slice(0, 3).join(", ")})`;
}

// ===============================================================================

export function HeroRender() {
  const open = useStore((s) => s.hero.open);
  const endpoint = useStore((s) => s.heroEndpoint);
  if (!open) return null;
  return endpoint.baseUrl && endpoint.regionUrl ? <Workspace /> : <SetupCard />;
}

// ---- setup card ---------------------------------------------------------------

function SetupCard() {
  const endpoint = useStore((s) => s.heroEndpoint);
  const setHeroEndpoint = useStore((s) => s.setHeroEndpoint);
  const closeHero = useStore((s) => s.closeHero);
  const env = DEFAULT_HERO_ENDPOINT; // the FLUX.1 default from `.env.local` (VITE_HERO_*)
  const hasEnvFlux1 = Boolean(env.baseUrl && env.regionUrl);
  // Pre-fill from the configured FLUX.1 default when nothing is stored yet, so the FLUX.1
  // path is one-click (or never shown) and FLUX.2 is the only model that needs fresh creds.
  const [base, setBase] = useState(endpoint.baseUrl || env.baseUrl);
  const [region, setRegion] = useState(endpoint.regionUrl || env.regionUrl);
  const [secret, setSecret] = useState(endpoint.secret || env.secret);
  const [model, setModel] = useState<"flux1" | "flux2">(
    modelOfUrl(endpoint.baseUrl || endpoint.regionUrl || env.baseUrl),
  );
  const pickModel = (to: "flux1" | "flux2") => {
    setModel(to);
    if (to === "flux1") {
      // Restore the configured FLUX.1 default (or derive it from a FLUX.2 URL if that's all we have).
      setBase((u) => env.baseUrl || switchModelUrl(u, "flux1"));
      setRegion((u) => env.regionUrl || switchModelUrl(u, "flux1"));
      setSecret((s) => s || env.secret);
    } else {
      // FLUX.2 = the sibling Modal app in the same workspace — derive its URL from the FLUX.1 one.
      setBase((u) => switchModelUrl(u, "flux2"));
      setRegion((u) => switchModelUrl(u, "flux2"));
    }
  };
  const flux2 = model === "flux2";
  const pyfile = flux2 ? "modal_flux2" : "modal_flux";
  const ready = Boolean(base.trim() && region.trim() && secret.trim());

  return (
    <div style={overlay}>
      <div style={bar}>
        <span style={{ fontWeight: 600, color: "#ffb27a" }}>✦ Hero render — setup</span>
        <div style={{ flex: 1 }} />
        <span onClick={closeHero} style={exitBtn}>
          ✕ Close
        </span>
      </div>
      <div style={setupWrap}>
        <div style={card}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
            {flux2 ? "Connect the FLUX.2 backend" : "Connect the FLUX backend"}
          </div>
          <div style={{ opacity: 0.72, fontSize: 12.5, lineHeight: 1.55, marginBottom: 12 }}>
            The hero render runs a self-hosted, geometry-locked diffusion backend on your Modal GPU.{" "}
            <b>FLUX.1 is the live default</b> — set it once in <code>.env.local</code> and it connects
            automatically. <b>FLUX.2</b> is experimental, and entered here after you deploy it.
          </div>

          <div style={smallLabel}>Backend model</div>
          <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            <div style={modelSeg(!flux2)} onClick={() => pickModel("flux1")}>
              FLUX.1 · live
            </div>
            <div style={modelSeg(flux2)} onClick={() => pickModel("flux2")}>
              FLUX.2 · experimental
            </div>
          </div>
          <div style={{ opacity: 0.55, fontSize: 11, lineHeight: 1.5, marginBottom: 14 }}>
            {flux2 ? (
              <>
                <b>FLUX.2-dev + Fun-Controlnet-Union</b> (H200 + VideoX-Fun, native inpaint). Heavier /
                pricier; <b>deploy-gated</b> — deploy <code>spike/modal_flux2.py</code> first. See{" "}
                <code>spike/REPORTS/flux2_feasibility.md</code>.
              </>
            ) : (
              <>
                <b>FLUX.1-dev + ControlNet-Union</b> (A100, canny + depth lock). The verified default —
                ~$0.01–0.02/render, ~15s warm.
              </>
            )}
          </div>

          {!flux2 &&
            (hasEnvFlux1 ? (
              <div style={envOkBox}>
                ✓ FLUX.1 is configured in <code>.env.local</code> — it connects automatically when you open
                the Hero render. Fields are pre-filled below; just press <b>Connect</b>.
              </div>
            ) : (
              <div style={envHintBox}>
                <b>To make FLUX.1 work out of the box:</b> deploy it once
                (<code>modal deploy spike/modal_flux.py</code>), then copy the URLs + secret into{" "}
                <code>apps/web3d-prototype/.env.local</code> as <code>VITE_HERO_BASE_URL</code> /{" "}
                <code>VITE_HERO_REGION_URL</code> / <code>VITE_HERO_SECRET</code> (see{" "}
                <code>.env.example</code>) — then this modal never asks again. Or paste them below for a
                one-off.
              </div>
            ))}

          <ol style={{ margin: "0 0 16px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.7, opacity: 0.85 }}>
            <li>
              Add <code>HF_TOKEN</code> (accept the {flux2 ? "FLUX.2-dev" : "FLUX.1-dev"} license on
              HuggingFace) and <code>HERO_SHARED_SECRET</code> to the Modal <code>arch-flux</code> secret.
            </li>
            <li>
              <code>modal run spike/{pyfile}.py::warm_weights</code> (one-time weight prefetch).
            </li>
            <li>
              <code>modal deploy spike/{pyfile}.py</code> → copy the printed <code>…modal.run</code> base URL
              (<code>/hero_render</code> + <code>/region_edit</code> routes).
            </li>
          </ol>
          {(
            [
              ["Base render URL (…heroflux-web.modal.run/hero_render)", base, setBase],
              ["Region edit URL (…heroflux-web.modal.run/region_edit)", region, setRegion],
              ["Shared secret (HERO_SHARED_SECRET)", secret, setSecret],
            ] as const
          ).map(([ph, val, set], i) => (
            <input
              key={i}
              value={val}
              onChange={(e) => set(e.target.value)}
              placeholder={ph}
              type={i === 2 ? "password" : "text"}
              style={{ ...input, marginBottom: 8, width: "100%" }}
            />
          ))}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 6 }}>
            <span onClick={closeHero} style={exitBtn}>
              Cancel
            </span>
            <button
              onClick={() => setHeroEndpoint({ baseUrl: base.trim(), regionUrl: region.trim(), secret: secret.trim() })}
              disabled={!ready}
              style={{ ...saveBtn, opacity: ready ? 1 : 0.4 }}
            >
              Connect
            </button>
          </div>
          <div style={{ opacity: 0.5, fontSize: 11, marginTop: 12 }}>
            Full runbook: <code>spike/REPORTS/modal_flux.md</code>. Stored locally in this browser only.
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- workspace ----------------------------------------------------------------

function Workspace() {
  const capture = useStore((s) => s.hero.capture)!;
  const layers = useStore((s) => s.hero.layers);
  const activeId = useStore((s) => s.hero.activeLayerId);
  const prompt = useStore((s) => s.hero.prompt);
  const negative = useStore((s) => s.hero.negativePrompt);
  const baseSeed = useStore((s) => s.hero.baseSeed);
  const endpoint = useStore((s) => s.heroEndpoint);
  const patchHero = useStore((s) => s.patchHero);
  const addHeroLayer = useStore((s) => s.addHeroLayer);
  const updateHeroLayer = useStore((s) => s.updateHeroLayer);
  const removeHeroLayer = useStore((s) => s.removeHeroLayer);
  const reorderHeroLayer = useStore((s) => s.reorderHeroLayer);
  const closeHero = useStore((s) => s.closeHero);
  const setHeroEndpoint = useStore((s) => s.setHeroEndpoint);

  const [preview, setPreview] = useState<string>(`data:image/png;base64,${capture.beauty}`);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const [, force] = useState(0);

  // ---- keep-warm + render timing (UX polish: kill the ~40-60s cold start) -------
  const [keepWarm, setKeepWarm] = useState(false);
  const [warmState, setWarmState] = useState<"idle" | "pinging" | "warm" | "err">("idle");
  const [backendModel, setBackendModel] = useState<string | null>(null);
  const [lastMs, setLastMs] = useState<number | null>(null);

  // ---- multi-view turntable state ----
  const [viewCount, setViewCount] = useState(6);
  const [mvResults, setMvResults] = useState<MvResult[]>([]);
  const [mvBusy, setMvBusy] = useState(false);
  const [mvProgress, setMvProgress] = useState<string | null>(null);
  const [mvSelected, setMvSelected] = useState<number | null>(null);
  // Every blob URL created for a view — revoked on re-run + on unmount so repeated
  // multi-view batches don't leak object URLs (the browser keeps them alive otherwise).
  const mvUrlsRef = useRef<string[]>([]);
  const revokeMvUrls = () => {
    mvUrlsRef.current.forEach((u) => URL.revokeObjectURL(u));
    mvUrlsRef.current = [];
  };
  useEffect(() => revokeMvUrls, []); // revoke any remaining on Workspace unmount (modal close)

  const noteRenderMs = (ms: number | undefined) => {
    if (typeof ms === "number") {
      setLastMs(ms);
      setWarmState("warm"); // a render just finished → the container is definitively warm
    }
  };

  // While "keep warm" is on, ping /warm now + every 240s (inside the 300s scaledown
  // window) so an active editing session never pays the cold start. Pure keep-alive —
  // no render — so it's ~free. Stops on toggle-off or when the modal unmounts.
  useEffect(() => {
    if (!keepWarm || !endpoint.baseUrl) {
      setWarmState((s) => (s === "warm" ? "idle" : s));
      return;
    }
    let alive = true;
    const ping = async () => {
      if (!alive) return;
      setWarmState("pinging");
      const model = await pingWarm(endpoint.baseUrl, endpoint.secret);
      if (!alive) return;
      if (model) {
        setBackendModel(model);
        setWarmState("warm");
      } else {
        setWarmState("err");
      }
    };
    ping();
    const id = window.setInterval(ping, 240_000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [keepWarm, endpoint.baseUrl, endpoint.secret]);

  // Seed the global prompt once.
  useEffect(() => {
    if (!prompt) patchHero({ prompt: DEFAULT_PROMPT });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recompute the composited preview whenever layers / visibility change.
  useEffect(() => {
    let alive = true;
    compositeHero(capture, layers).then((url) => {
      if (alive && url) setPreview(url);
    });
    return () => {
      alive = false;
    };
  }, [capture, layers]);

  const uniqueSemantics = useMemo(() => {
    const set = new Set<string>();
    Object.values(capture.regions).forEach((r) => set.add(r.semantic));
    return [...set].sort();
  }, [capture]);

  const setBusy = (b: boolean) => {
    busyRef.current = b;
    force((n) => n + 1);
  };

  const guardCalls = (): boolean => {
    if (heroCalls >= MAX_HERO_CALLS) {
      setError(`Session cap reached (${MAX_HERO_CALLS} renders). Reopen to reset.`);
      return false;
    }
    return true;
  };

  const idsForSemantic = (semantic: string): number[] =>
    Object.entries(capture.regions)
      .filter(([, r]) => r.semantic === semantic)
      .map(([id]) => Number(id));

  // Run the BASE layer (full geometry-locked render).
  const generateBase = async () => {
    if (busyRef.current || mvBusy || !guardCalls()) return;
    setError(null);
    let base = layers.find((l) => l.kind === "base");
    if (!base) {
      base = {
        id: "base",
        kind: "base",
        label: "Base render",
        prompt,
        seed: baseSeed,
        scales: { ...DEFAULT_HERO_SCALES },
        steps: 32,
        guidance: 3.5,
        resultUrl: null,
        visible: true,
        status: "idle",
      };
      addHeroLayer(base);
    }
    const layer: HeroLayer = { ...base, prompt, seed: baseSeed, status: "running" };
    updateHeroLayer("base", { prompt, seed: baseSeed, status: "running", error: undefined });
    setBusy(true);
    try {
      heroCalls++;
      const r = await postHero(endpoint.baseUrl, {
        ...layerParams(layer, negative, endpoint.secret),
        beauty: capture.beauty,
        depth: capture.depth,
        ids_rgb: capture.idsRgb,
        width: capture.width,
        height: capture.height,
      });
      updateHeroLayer("base", { resultUrl: URL.createObjectURL(b64ToBlob(r.image)), status: "done" });
      noteRenderMs(r.ms);
    } catch (e) {
      updateHeroLayer("base", { status: "error", error: String(e) });
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // Run / re-roll a REGION layer (independent edit of the BASE, masked).
  const runRegion = async (layer: HeroLayer) => {
    if (busyRef.current || mvBusy || !guardCalls()) return;
    const base = layers.find((l) => l.kind === "base" && l.resultUrl);
    if (!base?.resultUrl) {
      setError("Generate the base render first.");
      return;
    }
    setError(null);
    updateHeroLayer(layer.id, { status: "running", error: undefined });
    setBusy(true);
    try {
      heroCalls++;
      // base = the geometry render b64 (strip the objectURL → b64 via fetch).
      const baseB64 = await blobUrlToB64(base.resultUrl);
      const r = await postHero(endpoint.regionUrl, {
        ...layerParams(layer, negative, endpoint.secret),
        beauty: capture.beauty,
        depth: capture.depth,
        ids_rgb: capture.idsRgb,
        width: capture.width,
        height: capture.height,
        base: baseB64,
        region_ids: layer.regionIds ?? [],
      });
      updateHeroLayer(layer.id, {
        resultUrl: URL.createObjectURL(b64ToBlob(r.image)),
        maskUrl: r.mask ? URL.createObjectURL(b64ToBlob(r.mask)) : null,
        status: "done",
      });
      noteRenderMs(r.ms);
    } catch (e) {
      updateHeroLayer(layer.id, { status: "error", error: String(e) });
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const addRegion = (semantic: string) => {
    const ids = idsForSemantic(semantic);
    const id = `region_${semantic}_${layers.length}_${Math.random().toString(36).slice(2, 6)}`;
    addHeroLayer({
      id,
      kind: "region",
      label: semantic,
      semantic,
      regionIds: ids,
      prompt: `${prompt} The ${semantic} is re-clad in a new material.`,
      seed: baseSeed,
      scales: { ...DEFAULT_HERO_SCALES },
      steps: 30,
      guidance: 3.5,
      resultUrl: null,
      maskUrl: null,
      visible: true,
      status: "idle",
    });
  };

  const saveHero = async () => {
    const a = document.createElement("a");
    a.href = preview;
    a.download = `hero_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // ---- multi-view turntable: orbit N poses, render each base-locked with the SAME seed
  //      + prompt → a consistent multi-angle set of the same building. Each view keeps
  //      its bake-ready pose, so the set can also train a photoreal 3DGS. ----
  const renderMultiView = async () => {
    if (busyRef.current || mvBusy) return;
    const viewsFn = useStore.getState().heroCaptureViewsFn;
    if (!viewsFn) {
      setError("Multi-view capture needs a WebGL2 / + GI render mode.");
      return;
    }
    if (heroCalls + viewCount > MAX_HERO_CALLS) {
      setError(`Multi-view needs ${viewCount} renders; only ${MAX_HERO_CALLS - heroCalls} left this session.`);
      return;
    }
    setError(null);
    setMvBusy(true);
    revokeMvUrls(); // free the previous batch's blob URLs before starting a new one
    setMvResults([]);
    setMvSelected(null);
    setPreview(`data:image/png;base64,${capture.beauty}`); // avoid a dangling revoked URL in the preview
    setMvProgress("Capturing orbit views…");
    try {
      // Cap multi-view at 1024 (vs the base's 1536): it's N renders, so favour speed + cost —
      // still plenty for a turntable or a bake. ≈ $0.02 × N, ~15-25s each (warm).
      const mvMaxEdge = Math.min(1024, Math.max(capture.width, capture.height));
      const caps = await viewsFn({ maxEdge: mvMaxEdge, count: viewCount });
      if (!caps || !caps.length) {
        setMvProgress("Orbit capture failed.");
        return;
      }
      const results: MvResult[] = caps.map((c) => ({
        label: c.label,
        preview: `data:image/png;base64,${c.capture.beauty}`,
        imageB64: null,
        transform: c.transform,
        width: c.capture.width,
        height: c.capture.height,
        fov: c.capture.camera.fov,
        status: "pending",
      }));
      setMvResults([...results]);
      let consecutiveFails = 0;
      for (let i = 0; i < caps.length; i++) {
        setMvProgress(`Rendering view ${i + 1}/${caps.length} on the GPU…`);
        const cap = caps[i].capture;
        try {
          heroCalls++;
          const r = await postHero(endpoint.baseUrl, {
            secret: endpoint.secret,
            prompt,
            negative_prompt: negative,
            seed: baseSeed, // SAME seed across views → consistent materials/style
            steps: 32,
            guidance_scale: 3.5,
            true_cfg_scale: negative.trim() ? 4.0 : 1.0,
            canny_scale: DEFAULT_HERO_SCALES.canny,
            canny_end: DEFAULT_HERO_SCALES.cannyEnd,
            depth_scale: DEFAULT_HERO_SCALES.depth,
            depth_end: DEFAULT_HERO_SCALES.depthEnd,
            beauty: cap.beauty,
            depth: cap.depth,
            ids_rgb: cap.idsRgb,
            width: cap.width,
            height: cap.height,
          });
          const url = URL.createObjectURL(b64ToBlob(r.image));
          mvUrlsRef.current.push(url);
          results[i] = { ...results[i], preview: url, imageB64: r.image, status: "done" };
          noteRenderMs(r.ms);
          consecutiveFails = 0;
        } catch (e) {
          const msg = String(e instanceof Error ? e.message : e);
          results[i] = { ...results[i], status: "error" };
          setMvResults([...results]);
          if (/Auth failed/i.test(msg)) {
            setError(`${msg} — stopped the batch.`);
            break; // auth is persistent — no point continuing
          }
          consecutiveFails++;
          if (consecutiveFails >= 2) {
            setError(`View ${i + 1} failed (${msg}). Two in a row — backend likely down; stopped.`);
            break;
          }
          // A single failure (typically a cold-start blip on the FIRST view) shouldn't kill
          // the batch — the container is booting now, so the remaining views usually succeed.
          setError(`View ${i + 1} failed (${msg}); continuing with the rest.`);
          continue;
        }
        setMvResults([...results]);
      }
      const done = results.filter((r) => r.status === "done");
      setMvProgress(`Done — ${done.length}/${caps.length} views rendered (same seed ${baseSeed}).`);
      const firstDone = results.findIndex((r) => r.status === "done");
      if (firstDone >= 0 && results[firstDone].preview) {
        setPreview(results[firstDone].preview!);
        setMvSelected(firstDone);
      }
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setMvBusy(false);
    }
  };

  const downloadView = async (v: MvResult) => {
    if (!v.preview) return;
    const blob = await (await fetch(v.preview)).blob();
    downloadBlob(blob, `hero_${v.label.replace(/\s+/g, "")}_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.png`);
  };

  const downloadAllViews = async () => {
    for (const v of mvResults) if (v.status === "done") await downloadView(v);
  };

  // Synergy: bake a photoreal 3DGS from the rendered views (FLUX materials baked in).
  const bakeMultiView = async () => {
    const done = mvResults.filter((r) => r.status === "done" && r.imageB64);
    if (done.length < 3) {
      setError("Render at least a few views first (a usable splat wants ~24+).");
      return;
    }
    const bakeUrl = useStore.getState().splatBakeUrl;
    if (!bakeUrl.trim()) {
      setError("Set the splat-bake endpoint in the 🌐 Splat panel first (deploy spike/modal_splat.py).");
      return;
    }
    setError(null);
    setMvBusy(true);
    try {
      setMvProgress("Baking a photoreal 3DGS from the views…");
      const ply = await bakeFromHeroViews(
        done.map((r) => ({ imageB64: r.imageB64!, transform: r.transform, width: r.width, height: r.height, fov: r.fov })),
        { bakeUrl: bakeUrl.trim(), secret: endpoint.secret, onProgress: setMvProgress },
      );
      if (ply) {
        const s = useStore.getState();
        s.setSplatUrl(ply);
        s.setSplatSource("file");
        s.setSplatEnabled(true);
        setMvProgress("Photoreal splat trained + loaded into the scene.");
      } else {
        setMvProgress("Bake returned no splat.");
      }
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setMvBusy(false);
    }
  };

  const active = layers.find((l) => l.id === activeId) ?? null;
  const hasBase = layers.some((l) => l.kind === "base" && l.resultUrl);

  return (
    <div style={overlay}>
      <div style={bar}>
        <span style={{ fontWeight: 600, color: "#ffb27a" }}>✦ Hero render</span>
        <span style={{ opacity: 0.6, fontSize: 12 }}>
          {(backendModel ?? "FLUX")} · depth+canny lock · {capture.width}×{capture.height} · {heroCalls}/{MAX_HERO_CALLS} renders
        </span>
        <div style={{ flex: 1 }} />
        {lastMs != null && (
          <span style={timingBadge} title="Last render time (warm A100 ≈ 12–25s; a cold start adds ~40–60s)">
            ⚡ {(lastMs / 1000).toFixed(1)}s
          </span>
        )}
        <span
          onClick={() => setKeepWarm((v) => !v)}
          style={warmToggle(keepWarm, warmState)}
          title={
            keepWarm
              ? "Pinging the GPU every 4 min so it never cold-starts (small GPU cost while on). Click to stop."
              : "Keep the Modal GPU warm during this session to skip the ~40–60s cold start (costs a little GPU while on)."
          }
        >
          {keepWarm ? (warmState === "warm" ? "🔥 Warm" : warmState === "err" ? "🔥 Unreachable" : "🔥 Warming…") : "🔥 Keep warm"}
        </span>
        <span onClick={() => setHeroEndpoint({ baseUrl: "" })} style={linkBtn} title="Reconnect a different backend">
          ⚙ Backend
        </span>
        <span onClick={saveHero} style={linkBtn}>
          ⬇ Save
        </span>
        <span onClick={closeHero} style={exitBtn}>
          ✕ Exit
        </span>
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* preview */}
        <div style={previewWrap}>
          <img src={preview} alt="hero preview" style={previewImg} />
          {busyRef.current && (
            <div style={busyOverlay}>
              <div style={{ fontSize: 13 }}>Rendering on Modal GPU…</div>
              <div style={{ fontSize: 11, opacity: 0.6, marginTop: 4 }}>
                {warmState === "warm"
                  ? "warm GPU — ~12–25s"
                  : "first render boots the GPU (~40–60s) — tip: enable 🔥 Keep warm"}
              </div>
            </div>
          )}
          {mvBusy && !busyRef.current && (
            <div style={busyOverlay}>
              <div style={{ fontSize: 13 }}>{mvProgress ?? "Rendering views…"}</div>
              <div style={{ fontSize: 11, opacity: 0.6, marginTop: 4 }}>multi-view turntable</div>
            </div>
          )}
          {mvResults.length > 0 && (
            <div style={galleryStrip}>
              {mvResults.map((v, i) => (
                <div
                  key={i}
                  style={galleryTile(mvSelected === i)}
                  onClick={() => {
                    if (v.preview) {
                      setPreview(v.preview);
                      setMvSelected(i);
                    }
                  }}
                  title={`${v.label} · ${v.status}`}
                >
                  {v.preview ? <img src={v.preview} style={galleryThumb} alt={v.label} /> : <div style={galleryThumbEmpty} />}
                  <span style={galleryBadge(v.status)}>{v.status === "pending" ? "…" : v.status === "error" ? "✕" : i + 1}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* controls */}
        <div style={panel}>
          {error && <div style={errorBox}>{error}</div>}

          <Section title="Prompt">
            <textarea value={prompt} onChange={(e) => patchHero({ prompt: e.target.value })} rows={4} style={textarea} />
            <div style={smallLabel}>Negative prompt</div>
            <textarea
              value={negative}
              onChange={(e) => patchHero({ negativePrompt: e.target.value })}
              rows={2}
              style={textarea}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
              <span style={smallLabel}>Seed</span>
              <input
                type="number"
                value={baseSeed}
                onChange={(e) => patchHero({ baseSeed: parseInt(e.target.value) || 0 })}
                style={{ ...input, width: 110 }}
              />
              <span
                style={miniBtn}
                onClick={() => patchHero({ baseSeed: Math.floor(Math.random() * 1e9) })}
                title="Randomize seed"
              >
                🎲
              </span>
            </div>
            <button onClick={generateBase} disabled={busyRef.current || mvBusy} style={{ ...primaryBtn, width: "100%", marginTop: 10, opacity: busyRef.current || mvBusy ? 0.5 : 1 }}>
              {hasBase ? "↻ Regenerate base" : "✦ Generate base render"}
            </button>
          </Section>

          <Section title="Multi-view (turntable)">
            <div style={{ opacity: 0.6, fontSize: 11, lineHeight: 1.5, marginBottom: 8 }}>
              Orbit N angles around the building, each rendered with the <b>same seed + prompt</b> — a
              consistent multi-view set. Every frame keeps its camera pose, so the set can also bake a
              photoreal 3DGS. Tip: enable <b>🔥 Keep warm</b> first so the first view skips the cold start.
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={smallLabel}>Views</span>
              {[4, 6, 8, 12, 24].map((n) => (
                <span key={n} style={countChip(viewCount === n)} onClick={() => !mvBusy && setViewCount(n)}>
                  {n}
                </span>
              ))}
            </div>
            <button
              onClick={renderMultiView}
              disabled={mvBusy || busyRef.current}
              style={{ ...primaryBtn, width: "100%", opacity: mvBusy || busyRef.current ? 0.5 : 1 }}
              title={`Render ${viewCount} consistent angles (≈ $0.02 × ${viewCount}, ~15-25s each; first view may cold-start)`}
            >
              {mvBusy ? "Rendering views…" : `✦ Render ${viewCount} views`}
            </button>
            {mvProgress && <div style={mvProgressBox}>{mvProgress}</div>}
            {mvResults.some((r) => r.status === "done") && (
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <span style={miniBtn} onClick={downloadAllViews}>
                  ⬇ Export all
                </span>
                <span
                  style={miniBtn}
                  onClick={bakeMultiView}
                  title="Train a photoreal 3DGS from these views (needs the splat-bake endpoint deployed; ~24+ views recommended)"
                >
                  ✦ Bake → splat
                </span>
              </div>
            )}
          </Section>

          <Section title="Regions (Photoshop layers)">
            <div style={{ opacity: 0.6, fontSize: 11, lineHeight: 1.5, marginBottom: 8 }}>
              Each region re-renders ONE element on the locked geometry, masked — independent + re-rollable.
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 4 }}>
              {uniqueSemantics.map((sem) => (
                <span
                  key={sem}
                  style={{ ...chip, opacity: hasBase ? 1 : 0.4, cursor: hasBase ? "pointer" : "not-allowed" }}
                  onClick={() => hasBase && addRegion(sem)}
                  title={hasBase ? `Add a ${sem} edit layer` : "Generate the base first"}
                >
                  + {sem}
                </span>
              ))}
            </div>
          </Section>

          <Section title={`Layers · ${layers.length}`}>
            {layers.length === 0 && <div style={{ opacity: 0.45, fontSize: 12 }}>No layers — generate the base render.</div>}
            {[...layers]
              .slice()
              .reverse()
              .map((l) => (
                <LayerRow
                  key={l.id}
                  layer={l}
                  active={l.id === activeId}
                  onSelect={() => patchHero({ activeLayerId: l.id })}
                  onToggle={() => updateHeroLayer(l.id, { visible: !l.visible })}
                  onReroll={() => {
                    const seed = Math.floor(Math.random() * 1e9);
                    updateHeroLayer(l.id, { seed });
                    if (l.kind === "base") {
                      patchHero({ baseSeed: seed });
                      generateBase();
                    } else {
                      runRegion({ ...l, seed });
                    }
                  }}
                  onDelete={() => removeHeroLayer(l.id)}
                  onUp={() => reorderHeroLayer(l.id, 1)}
                  onDown={() => reorderHeroLayer(l.id, -1)}
                />
              ))}
          </Section>

          {active && active.kind === "region" && (
            <Section title={`Edit · ${active.label}`}>
              <textarea
                value={active.prompt}
                onChange={(e) => updateHeroLayer(active.id, { prompt: e.target.value })}
                rows={3}
                style={textarea}
              />
              <div style={smallLabel}>Quick material</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                {SWATCHES.slice(0, 14).map((sw) => (
                  <span
                    key={sw.id}
                    title={sw.label}
                    onClick={() =>
                      updateHeroLayer(active.id, {
                        prompt: `${prompt} The ${active.semantic} is clad in ${materialClause(sw.id)}.`,
                      })
                    }
                    style={{ ...swatchChip, background: sw.color }}
                  />
                ))}
              </div>
              <ScaleSliders layer={active} onChange={(patch) => updateHeroLayer(active.id, patch)} />
              <button
                onClick={() => runRegion(active)}
                disabled={busyRef.current || mvBusy || !hasBase}
                style={{ ...primaryBtn, width: "100%", marginTop: 8, opacity: busyRef.current || mvBusy || !hasBase ? 0.5 : 1 }}
              >
                {active.resultUrl ? "↻ Re-run region" : "✦ Run region"}
              </button>
            </Section>
          )}

          {active && active.kind === "base" && (
            <Section title="Base · controls">
              <ScaleSliders layer={active} onChange={(patch) => updateHeroLayer("base", patch)} />
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- subcomponents ------------------------------------------------------------

function ScaleSliders({ layer, onChange }: { layer: HeroLayer; onChange: (p: Partial<HeroLayer>) => void }) {
  const row = (label: string, val: number, min: number, max: number, step: number, key: keyof typeof layer.scales) => (
    <div style={{ marginBottom: 6 }}>
      <div style={smallLabel}>
        {label} · {val.toFixed(2)}
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={val}
        onChange={(e) => onChange({ scales: { ...layer.scales, [key]: parseFloat(e.target.value) } })}
        style={{ width: "100%", accentColor: "#ffb27a" }}
      />
    </div>
  );
  return (
    <div style={{ marginTop: 4 }}>
      {row("Canny (edges)", layer.scales.canny, 0.3, 1, 0.05, "canny")}
      {row("Depth (massing)", layer.scales.depth, 0.2, 1, 0.05, "depth")}
      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={smallLabel}>Steps · {layer.steps}</div>
          <input
            type="range"
            min={20}
            max={40}
            step={1}
            value={layer.steps}
            onChange={(e) => onChange({ steps: parseInt(e.target.value) })}
            style={{ width: "100%", accentColor: "#ffb27a" }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <div style={smallLabel}>Guidance · {layer.guidance.toFixed(1)}</div>
          <input
            type="range"
            min={2}
            max={6}
            step={0.1}
            value={layer.guidance}
            onChange={(e) => onChange({ guidance: parseFloat(e.target.value) })}
            style={{ width: "100%", accentColor: "#ffb27a" }}
          />
        </div>
      </div>
    </div>
  );
}

function LayerRow({
  layer,
  active,
  onSelect,
  onToggle,
  onReroll,
  onDelete,
  onUp,
  onDown,
}: {
  layer: HeroLayer;
  active: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onReroll: () => void;
  onDelete: () => void;
  onUp: () => void;
  onDown: () => void;
}) {
  const statusColor =
    layer.status === "running" ? "#ffd27a" : layer.status === "error" ? "#ff7a7a" : layer.status === "done" ? "#7ad28a" : "#666";
  return (
    <div
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 7,
        padding: "5px 6px",
        borderRadius: 6,
        marginBottom: 4,
        cursor: "pointer",
        background: active ? "rgba(255,178,122,0.14)" : "rgba(255,255,255,0.04)",
        border: `1px solid ${active ? "rgba(255,178,122,0.5)" : "transparent"}`,
      }}
    >
      <span
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        title="visibility"
        style={{ cursor: "pointer", opacity: layer.visible ? 1 : 0.35, width: 14 }}
      >
        {layer.visible ? "●" : "○"}
      </span>
      <div
        style={{
          width: 34,
          height: 24,
          borderRadius: 3,
          flex: "0 0 auto",
          background: layer.resultUrl ? `center/cover url(${layer.resultUrl})` : "rgba(255,255,255,0.06)",
          border: "1px solid rgba(0,0,0,0.4)",
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {layer.kind === "base" ? "Base render" : layer.label}
        </div>
        <div style={{ fontSize: 10, opacity: 0.5 }}>
          <span style={{ color: statusColor }}>●</span> {layer.kind === "base" ? "geometry lock" : "region edit"} · seed {layer.seed}
        </div>
      </div>
      <span onClick={(e) => (e.stopPropagation(), onReroll())} title="re-roll (new seed)" style={iconMini}>
        🎲
      </span>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span onClick={(e) => (e.stopPropagation(), onUp())} style={{ ...iconMini, fontSize: 8, lineHeight: 1 }}>
          ▲
        </span>
        <span onClick={(e) => (e.stopPropagation(), onDown())} style={{ ...iconMini, fontSize: 8, lineHeight: 1 }}>
          ▼
        </span>
      </div>
      {layer.kind !== "base" && (
        <span onClick={(e) => (e.stopPropagation(), onDelete())} title="delete" style={{ ...iconMini, opacity: 0.5 }}>
          ✕
        </span>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ borderTop: "1px solid rgba(255,255,255,0.07)", paddingTop: 12, marginTop: 12 }}>
      <div style={{ fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.5, marginBottom: 8 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

/** objectURL (blob:) → bare base64 PNG. */
async function blobUrlToB64(url: string): Promise<string> {
  const blob = await (await fetch(url)).blob();
  const dataUrl = await new Promise<string>((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result as string);
    fr.onerror = () => rej(fr.error);
    fr.readAsDataURL(blob);
  });
  const c = dataUrl.indexOf(",");
  return c >= 0 ? dataUrl.slice(c + 1) : dataUrl;
}

// ---- styles -------------------------------------------------------------------

const overlay: React.CSSProperties = { position: "fixed", inset: 0, zIndex: 60, background: "#0b0c0e", display: "flex", flexDirection: "column", color: "#e8eaed" };
const bar: React.CSSProperties = { display: "flex", alignItems: "center", gap: 12, padding: "10px 16px", background: "rgba(18,20,23,0.96)", borderBottom: "1px solid rgba(255,255,255,0.08)", fontSize: 13 };
const previewWrap: React.CSSProperties = { flex: 1, position: "relative", display: "flex", alignItems: "center", justifyContent: "center", padding: 18, minWidth: 0, background: "#0b0c0e" };
const previewImg: React.CSSProperties = { maxWidth: "100%", maxHeight: "100%", objectFit: "contain", borderRadius: 6, boxShadow: "0 8px 40px rgba(0,0,0,0.5)" };
const busyOverlay: React.CSSProperties = { position: "absolute", inset: 18, display: "grid", placeItems: "center", background: "rgba(11,12,14,0.55)", backdropFilter: "blur(2px)", textAlign: "center", borderRadius: 6 };
const panel: React.CSSProperties = { width: 320, flex: "0 0 320px", padding: "8px 16px 24px", overflowY: "auto", background: "rgba(18,20,23,0.96)", borderLeft: "1px solid rgba(255,255,255,0.08)" };
const errorBox: React.CSSProperties = { marginTop: 10, padding: "8px 10px", borderRadius: 6, fontSize: 11.5, lineHeight: 1.4, background: "rgba(255,80,80,0.12)", border: "1px solid rgba(255,80,80,0.4)", color: "#ffb3b3" };
const countChip = (active: boolean): React.CSSProperties => ({
  padding: "3px 9px",
  borderRadius: 5,
  cursor: "pointer",
  fontSize: 11.5,
  userSelect: "none",
  color: active ? "#fff" : "#9aa4b2",
  background: active ? "rgba(255,138,77,0.22)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "rgba(255,138,77,0.6)" : "rgba(255,255,255,0.12)"}`,
});
const mvProgressBox: React.CSSProperties = { marginTop: 8, padding: "6px 9px", borderRadius: 6, fontSize: 11, lineHeight: 1.4, background: "rgba(255,138,77,0.1)", border: "1px solid rgba(255,138,77,0.3)", color: "#ffcf99" };
const galleryStrip: React.CSSProperties = { position: "absolute", left: 18, right: 18, bottom: 12, display: "flex", gap: 6, overflowX: "auto", padding: 8, borderRadius: 8, background: "rgba(11,12,14,0.78)", backdropFilter: "blur(6px)", border: "1px solid rgba(255,255,255,0.08)" };
const galleryTile = (active: boolean): React.CSSProperties => ({ position: "relative", flex: "0 0 auto", width: 96, height: 64, borderRadius: 5, overflow: "hidden", cursor: "pointer", border: `2px solid ${active ? "#ffb27a" : "rgba(255,255,255,0.12)"}`, background: "#000" });
const galleryThumb: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover", display: "block" };
const galleryThumbEmpty: React.CSSProperties = { width: "100%", height: "100%", background: "repeating-linear-gradient(45deg,#1a1c1f,#1a1c1f 6px,#222 6px,#222 12px)" };
const galleryBadge = (status: MvResult["status"]): React.CSSProperties => ({
  position: "absolute",
  top: 3,
  left: 3,
  minWidth: 14,
  height: 14,
  padding: "0 3px",
  borderRadius: 7,
  fontSize: 9.5,
  lineHeight: "14px",
  textAlign: "center",
  color: "#fff",
  background: status === "error" ? "rgba(220,70,70,0.9)" : status === "pending" ? "rgba(120,120,120,0.9)" : "rgba(255,138,77,0.9)",
});
const textarea: React.CSSProperties = { width: "100%", background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.14)", borderRadius: 6, color: "#e8e6e3", fontSize: 12, padding: "6px 8px", resize: "vertical", fontFamily: "inherit", marginBottom: 4 };
const input: React.CSSProperties = { background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 5, color: "#fff", fontSize: 12, padding: "6px 8px" };
const smallLabel: React.CSSProperties = { fontSize: 10, opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.04em", marginTop: 6, marginBottom: 3 };
const primaryBtn: React.CSSProperties = { padding: "8px 12px", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: 12, background: "rgba(255,138,77,0.2)", border: "1px solid rgba(255,138,77,0.6)", color: "#fff", userSelect: "none" };
const miniBtn: React.CSSProperties = { cursor: "pointer", padding: "4px 8px", borderRadius: 5, background: "rgba(255,255,255,0.07)", userSelect: "none" };
const chip: React.CSSProperties = { padding: "4px 9px", borderRadius: 6, fontSize: 11.5, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", userSelect: "none" };
const swatchChip: React.CSSProperties = { width: 20, height: 20, borderRadius: 4, cursor: "pointer", border: "1px solid rgba(0,0,0,0.4)" };
const iconMini: React.CSSProperties = { cursor: "pointer", fontSize: 11, padding: "1px 3px", userSelect: "none" };
const setupWrap: React.CSSProperties = { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 };
const card: React.CSSProperties = { maxWidth: 520, width: "100%", background: "rgba(22,24,28,0.96)", border: "1px solid rgba(255,138,77,0.35)", borderRadius: 12, padding: 22 };
const envOkBox: React.CSSProperties = { marginBottom: 14, padding: "9px 11px", borderRadius: 7, fontSize: 11.5, lineHeight: 1.5, background: "rgba(122,210,138,0.1)", border: "1px solid rgba(122,210,138,0.4)", color: "#bfead0" };
const envHintBox: React.CSSProperties = { marginBottom: 14, padding: "9px 11px", borderRadius: 7, fontSize: 11.5, lineHeight: 1.5, background: "rgba(255,178,122,0.08)", border: "1px solid rgba(255,178,122,0.3)", color: "#ffcf99" };
const saveBtn: React.CSSProperties = { padding: "8px 16px", borderRadius: 6, border: "1px solid #ffb27a", background: "rgba(255,138,77,0.25)", color: "#fff", cursor: "pointer", fontSize: 12.5, fontWeight: 600 };
const linkBtn: React.CSSProperties = { color: "#9db8ff", fontSize: 12, padding: "5px 10px", borderRadius: 6, border: "1px solid rgba(157,184,255,0.3)", cursor: "pointer", userSelect: "none" };
const exitBtn: React.CSSProperties = { cursor: "pointer", fontSize: 12, padding: "5px 12px", borderRadius: 6, background: "rgba(255,255,255,0.08)", color: "#fff", userSelect: "none" };
const timingBadge: React.CSSProperties = { fontSize: 11.5, padding: "4px 9px", borderRadius: 6, background: "rgba(255,255,255,0.06)", color: "#bfead0", userSelect: "none", whiteSpace: "nowrap" };
const modelSeg = (active: boolean): React.CSSProperties => ({
  flex: 1,
  textAlign: "center",
  padding: "7px 0",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 12,
  fontWeight: active ? 600 : 400,
  userSelect: "none",
  color: active ? "#fff" : "#9aa4b2",
  background: active ? "rgba(255,138,77,0.2)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "rgba(255,138,77,0.6)" : "rgba(255,255,255,0.12)"}`,
});
function warmToggle(on: boolean, state: "idle" | "pinging" | "warm" | "err"): React.CSSProperties {
  const live = on && state === "warm";
  const err = on && state === "err";
  return {
    cursor: "pointer",
    fontSize: 12,
    padding: "5px 10px",
    borderRadius: 6,
    userSelect: "none",
    whiteSpace: "nowrap",
    color: err ? "#ffb3b3" : live ? "#ffd9a3" : on ? "#ffcf99" : "#9aa4b2",
    background: err ? "rgba(255,80,80,0.12)" : live ? "rgba(255,138,77,0.18)" : "rgba(255,255,255,0.05)",
    border: `1px solid ${err ? "rgba(255,80,80,0.5)" : on ? "rgba(255,138,77,0.5)" : "rgba(255,255,255,0.14)"}`,
  };
}
