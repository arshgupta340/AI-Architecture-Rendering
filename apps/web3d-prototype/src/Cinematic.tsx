import { useState } from "react";
import { useStore } from "./state/store";

/**
 * "Cinematic (UE5)" hero mode — a full-screen overlay that embeds a
 * SimplyStream-hosted Unreal Engine WebGPU build of THIS model, for a photoreal
 * (baked-archviz) look the live WebGL2 stack can't reach. Toggle off = back to the
 * cheap R3F editor. Client-side UE5 has no Lumen/Nanite, so the build is baked per
 * model; full rationale in wiki/research/web3d-ue-browser.md.
 *
 * The UE build is authored + uploaded by the user (runbook below — needs an Unreal
 * project + a SimplyStream account). This overlay is the app-side half:
 *   • no build URL set  → setup card (paste URL + runbook),
 *   • URL set           → embed the build (iframe), deep-linked with the current
 *     materials + sun, plus an "open in new tab" fallback (some hosts block framing).
 */

// Build a deep-link the UE build can parse to match the editor's current state.
// (The build side parses these params — see runbook step 3. Camera sync is a TODO:
// it needs the live R3F camera pose threaded into the store.)
function deepLink(url: string): string {
  const s = useStore.getState();
  const mats = s.layers
    .filter((l) => l.visible)
    .map((l) => `${l.semantic}:${l.swatch}`)
    .join(",");
  const p = new URLSearchParams();
  if (mats) p.set("materials", mats);
  p.set("lat", s.sky.lat.toFixed(5));
  p.set("lng", s.sky.lng.toFixed(5));
  p.set("date", s.sky.date);
  p.set("time", s.sky.timeOfDay.toFixed(2));
  p.set("sun", s.sky.sunIntensity.toFixed(2));
  p.set("cloud", s.sky.cloudCover.toFixed(2));
  return `${url}${url.includes("?") ? "&" : "?"}${p.toString()}`;
}

const RUNBOOK: string[] = [
  "Sign up at app.simplystream.com (their UE5 → WebGPU host).",
  "In Unreal, Datasmith-import public/model/house.glb; assign PBR materials.",
  "Bake Lightmass GI; build a material-variant configurator keyed to element IDs (wall / roof / window …).",
  "Package + upload to SimplyStream → copy the shareable build URL.",
  "Paste it below — the toggle deep-links the current materials + sun into it.",
];

export function Cinematic() {
  const on = useStore((s) => s.cinematic);
  const url = useStore((s) => s.cinematicUrl);
  const setCinematic = useStore((s) => s.setCinematic);
  const setCinematicUrl = useStore((s) => s.setCinematicUrl);
  const [draft, setDraft] = useState(url);

  if (!on) return null;
  const full = url ? deepLink(url) : "";

  return (
    <div style={overlay}>
      <div style={bar}>
        <span style={{ fontWeight: 600, color: "#c9b6ff" }}>◆ Cinematic (UE5)</span>
        <span style={{ opacity: 0.6, fontSize: 12 }}>
          {url
            ? "Photoreal Unreal build · client-side WebGPU (SimplyStream)"
            : "Set up your SimplyStream build"}
        </span>
        <div style={{ flex: 1 }} />
        {url && (
          <a href={full} target="_blank" rel="noreferrer" style={linkBtn}>
            ↗ Open in new tab
          </a>
        )}
        {url && (
          <span onClick={() => setCinematicUrl("")} style={linkBtn}>
            ⚙ Change build
          </span>
        )}
        <span onClick={() => setCinematic(false)} style={exitBtn}>
          ✕ Exit to editor
        </span>
      </div>

      {url ? (
        <iframe
          title="Cinematic UE5 build"
          src={full}
          style={frame}
          allow="fullscreen; xr-spatial-tracking; gamepad; autoplay"
        />
      ) : (
        <div style={setupWrap}>
          <div style={card}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
              Cinematic (UE5) — photoreal hero
            </div>
            <div style={{ opacity: 0.72, fontSize: 12.5, lineHeight: 1.55, marginBottom: 14 }}>
              Embeds a SimplyStream-hosted Unreal Engine build of this model (runs client-side over
              WebGPU — baked archviz, no per-viewer GPU cost). Author + upload the build once, then
              paste its URL here. The toggle deep-links your current materials + sun into it.
            </div>
            <ol
              style={{ margin: "0 0 16px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.65, opacity: 0.85 }}
            >
              {RUNBOOK.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="https://your-build.simplystream.com/…"
                style={input}
              />
              <button
                onClick={() => setCinematicUrl(draft)}
                style={{ ...saveBtn, opacity: draft.trim() ? 1 : 0.4 }}
                disabled={!draft.trim()}
              >
                Save
              </button>
            </div>
            <div style={{ opacity: 0.5, fontSize: 11, marginTop: 10, lineHeight: 1.5 }}>
              No build yet? Full runbook in <code>docs/HANDOFF-web3d.md</code>. Some hosts block
              embedding — the “Open in new tab” fallback always works.
            </div>
            <div style={{ marginTop: 14, textAlign: "right" }}>
              <span onClick={() => setCinematic(false)} style={exitBtn}>
                ✕ Back to editor
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const overlay: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 50,
  background: "#0b0c0e",
  display: "flex",
  flexDirection: "column",
};
const bar: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "10px 16px",
  background: "rgba(18,20,23,0.96)",
  borderBottom: "1px solid rgba(255,255,255,0.08)",
  color: "#e8eaed",
  fontSize: 13,
};
const frame: React.CSSProperties = { flex: 1, width: "100%", border: "none", background: "#0b0c0e" };
const linkBtn: React.CSSProperties = {
  color: "#9db8ff",
  textDecoration: "none",
  fontSize: 12,
  padding: "5px 10px",
  borderRadius: 6,
  border: "1px solid rgba(157,184,255,0.3)",
};
const exitBtn: React.CSSProperties = {
  cursor: "pointer",
  fontSize: 12,
  padding: "5px 12px",
  borderRadius: 6,
  background: "rgba(255,255,255,0.08)",
  color: "#fff",
  userSelect: "none",
};
const setupWrap: React.CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
};
const card: React.CSSProperties = {
  maxWidth: 470,
  width: "100%",
  background: "rgba(22,24,28,0.96)",
  border: "1px solid rgba(124,77,255,0.35)",
  borderRadius: 12,
  padding: 22,
  color: "#e8eaed",
};
const input: React.CSSProperties = {
  flex: 1,
  padding: "8px 10px",
  borderRadius: 6,
  border: "1px solid rgba(255,255,255,0.15)",
  background: "rgba(0,0,0,0.3)",
  color: "#fff",
  fontSize: 12.5,
};
const saveBtn: React.CSSProperties = {
  padding: "8px 16px",
  borderRadius: 6,
  border: "1px solid #2f6df6",
  background: "rgba(47,109,246,0.25)",
  color: "#fff",
  cursor: "pointer",
  fontSize: 12.5,
  fontWeight: 600,
};
