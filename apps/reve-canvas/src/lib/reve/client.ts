/**
 * Server-ONLY Reve client. The API key never reaches the browser (PRD §2
 * invariant). Implements the validated edit pipeline:
 *
 *   extract_layout(image)
 *   create_layout(references=[{image, layout}], commands=[{op:"change", ...}])
 *   render_layout(edited_layout, references=[{image}])   // aspect-pinned
 *
 * Mock mode (REVE_MODE=mock, or no key found) serves cached fixtures so the whole
 * UI is developable at $0. Live mode reads REVE_API_KEY from the environment, and
 * as a dev convenience falls back to the repo's spike/.env (server-side only).
 */
import "server-only";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ReveChangeCommand, ReveLayout, ReveResponse } from "./types";

const API_BASE = "https://api.reve.com";
const USD_PER_CREDIT = 10 / 7500;

export type ReveMode = "mock" | "live";

let cachedKey: string | null | undefined;

function loadApiKey(): string | null {
  if (cachedKey !== undefined) return cachedKey;
  let key = process.env.REVE_API_KEY?.trim() || "";
  if (!key) {
    // Dev fallback: reuse the spike's key (server-side only, never shipped).
    try {
      const envPath = join(process.cwd(), "..", "..", "spike", ".env");
      const txt = readFileSync(envPath, "utf8");
      for (const line of txt.split(/\r?\n/)) {
        const m = line.match(/^\s*REVE_API_KEY\s*=\s*(.+?)\s*$/);
        if (m) { key = m[1].replace(/^["']|["']$/g, ""); break; }
      }
    } catch { /* no fallback available */ }
  }
  cachedKey = key || null;
  return cachedKey;
}

export function resolveMode(): ReveMode {
  const explicit = process.env.REVE_MODE?.toLowerCase();
  if (explicit === "live") return "live";
  if (explicit === "mock") return "mock";
  // default: live only if a key is available, else mock
  return loadApiKey() ? "live" : "mock";
}

export interface ReveCallMeta {
  creditsUsed: number;
  usd: number;
  requestId?: string;
  mode: ReveMode;
}

async function post(endpoint: string, body: unknown, tag: string): Promise<{ data: ReveResponse; meta: ReveCallMeta }> {
  const key = loadApiKey();
  if (!key) throw new Error("REVE_API_KEY not set (and no spike/.env fallback). Set it in .env.local or use REVE_MODE=mock.");
  const resp = await fetch(`${API_BASE}${endpoint}?breadcrumb=reve-canvas-${tag}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    // Reve layout calls take 10-80s; give them room.
    signal: AbortSignal.timeout(180_000),
  });
  if (!resp.ok) {
    const code = resp.headers.get("x-reve-error-code") ?? "?";
    throw new Error(`Reve ${tag} HTTP ${resp.status} (${code})`);
  }
  const data = (await resp.json()) as ReveResponse;
  const creditsUsed = data.credits_used ?? 0;
  return {
    data,
    meta: { creditsUsed, usd: creditsUsed * USD_PER_CREDIT, requestId: data.request_id, mode: "live" },
  };
}

// ---- Live primitives ----
async function extractLayoutLive(imageB64: string) {
  return post("/v2/image/extract_layout", { image: { data: imageB64 } }, "extract");
}

async function createLayoutChangeLive(imageB64: string, layout: ReveLayout, commands: ReveChangeCommand[]) {
  return post("/v2/image/create_layout", {
    references: [{ image: { data: imageB64 }, layout }],
    commands,
  }, "create_layout");
}

async function renderLayoutLive(layout: ReveLayout, imageB64: string) {
  return post("/v2/image/render_layout", {
    layout,
    references: [{ image: { data: imageB64 } }],
  }, "render");
}

// ---- Mock fixtures ----
function mockFixture(name: string): string {
  return readFileSync(join(process.cwd(), "src", "lib", "reve", "mock", name), "utf8");
}

// ---- Public API (mode-aware) ----
export interface ExtractResult { layout: ReveLayout; meta: ReveCallMeta; }

export async function extractLayout(imageB64: string): Promise<ExtractResult> {
  if (resolveMode() === "mock") {
    const layout = JSON.parse(mockFixture("layout.json")) as ReveLayout;
    return { layout, meta: { creditsUsed: 0, usd: 0, mode: "mock" } };
  }
  const { data, meta } = await extractLayoutLive(imageB64);
  if (!data.layout) throw new Error("extract_layout returned no layout");
  return { layout: data.layout, meta };
}

export interface EditResult { imageB64: string; layout: ReveLayout; meta: ReveCallMeta; }

/** The full change-command edit pipeline. `aspect` pins the render canvas to the
 * source aspect ratio (framing control). */
export async function editRegion(opts: {
  imageB64: string;
  layout: ReveLayout;
  command: ReveChangeCommand;
  aspect?: { width: number; height: number };
}): Promise<EditResult> {
  if (resolveMode() === "mock") {
    // return the canned travertine result; echo the edited layout
    return {
      imageB64: mockFixture("edited.b64").trim(),
      layout: opts.layout,
      meta: { creditsUsed: 0, usd: 0, mode: "mock" },
    };
  }
  const cl = await createLayoutChangeLive(opts.imageB64, opts.layout, [opts.command]);
  const edited = cl.data.layout ?? opts.layout;
  if (opts.aspect) { edited.width = opts.aspect.width; edited.height = opts.aspect.height; }
  const rl = await renderLayoutLive(edited, opts.imageB64);
  if (!rl.data.image) throw new Error("render_layout returned no image");
  const creditsUsed = cl.meta.creditsUsed + rl.meta.creditsUsed;
  return {
    imageB64: rl.data.image,
    layout: rl.data.layout ?? edited,
    meta: { creditsUsed, usd: creditsUsed * USD_PER_CREDIT, requestId: rl.meta.requestId, mode: "live" },
  };
}
