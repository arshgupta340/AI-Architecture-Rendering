import { useState } from "react";
import { useStore, type SplatTransform } from "./state/store";
import { requestBake } from "./lib/splatBake";

/**
 * Side panel for the Gaussian-splat backdrop. Source = a drop-in file (Marble .spz /
 * CC0 .ply in public/splats/, or any URL) OR a Modal scene-bake ("convert our scene
 * → splat"). Plus alignment sliders that seat the splat on the building. WebGL2 /
 * + GI only (Spark is WebGLRenderer-only). Collapsed to a chip by default so it
 * doesn't crowd the editor.
 */
export function SplatPanel() {
  const renderMode = useStore((s) => s.renderMode);
  const enabled = useStore((s) => s.splatEnabled);
  const url = useStore((s) => s.splatUrl);
  const source = useStore((s) => s.splatSource);
  const tf = useStore((s) => s.splatTransform);
  const exposure = useStore((s) => s.splatExposure);
  const bakeUrl = useStore((s) => s.splatBakeUrl);
  const secret = useStore((s) => s.heroEndpoint.secret);
  const setSplatEnabled = useStore((s) => s.setSplatEnabled);
  const setSplatUrl = useStore((s) => s.setSplatUrl);
  const setSplatSource = useStore((s) => s.setSplatSource);
  const setSplatTransform = useStore((s) => s.setSplatTransform);
  const setSplatExposure = useStore((s) => s.setSplatExposure);
  const setSplatBakeUrl = useStore((s) => s.setSplatBakeUrl);

  const [openPanel, setOpenPanel] = useState(false);
  const [draftUrl, setDraftUrl] = useState(url || "/splats/context.ply");
  const [baking, setBaking] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);

  if (renderMode === "webgpu") return null; // Spark is WebGL2-only

  if (!openPanel) {
    return (
      <div style={{ ...chipWrap }} onClick={() => setOpenPanel(true)} title="Gaussian-splat environment">
        <span style={{ color: enabled ? "#7ad28a" : "#9aa4b2" }}>🌐</span> Splat env{enabled ? " · on" : ""}
      </div>
    );
  }

  const doBake = async () => {
    if (baking) return;
    if (!bakeUrl.trim() || !secret.trim()) {
      setProgress("Set the bake endpoint URL (and connect the FLUX backend for the shared secret) first.");
      return;
    }
    setBaking(true);
    setProgress("Starting…");
    try {
      const result = await requestBake({ bakeUrl: bakeUrl.trim(), secret: secret.trim(), onProgress: setProgress });
      if (result) {
        setSplatUrl(result);
        setSplatSource("file");
        setSplatEnabled(true);
        setProgress("Done — splat loaded.");
      } else {
        setProgress("Bake returned no splat.");
      }
    } catch (e) {
      setProgress(String(e instanceof Error ? e.message : e));
    } finally {
      setBaking(false);
    }
  };

  const slider = (label: string, key: keyof SplatTransform, min: number, max: number, step: number) => (
    <div style={{ marginBottom: 6 }}>
      <div style={smallLabel}>
        {label} · {tf[key]}
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={tf[key]}
        onChange={(e) => setSplatTransform({ [key]: parseFloat(e.target.value) })}
        style={{ width: "100%", accentColor: "#7ad28a" }}
      />
    </div>
  );

  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>🌐 Splat environment</span>
        <div style={{ flex: 1 }} />
        <span onClick={() => setOpenPanel(false)} style={{ cursor: "pointer", opacity: 0.6, fontSize: 12 }}>
          ✕
        </span>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12, marginBottom: 10 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setSplatEnabled(e.target.checked)} style={{ accentColor: "#7ad28a" }} />
        Show splat backdrop
      </label>

      <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
        {(["file", "bake"] as const).map((s) => (
          <div key={s} style={seg(source === s)} onClick={() => setSplatSource(s)}>
            {s === "file" ? "Drop-in file" : "Bake our scene"}
          </div>
        ))}
      </div>

      {source === "file" ? (
        <div style={{ marginBottom: 10 }}>
          <div style={smallLabel}>Splat URL (.ply / .spz)</div>
          <div style={{ display: "flex", gap: 6 }}>
            <input value={draftUrl} onChange={(e) => setDraftUrl(e.target.value)} placeholder="/splats/context.ply" style={input} />
            <span style={miniBtn} onClick={() => { setSplatUrl(draftUrl); setSplatEnabled(true); }}>
              Load
            </span>
          </div>
          <div style={{ opacity: 0.45, fontSize: 10.5, marginTop: 4, lineHeight: 1.4 }}>
            Drop a World Labs Marble <code>.spz</code> or a CC0 <code>.ply</code> in <code>public/splats/</code>.
          </div>
        </div>
      ) : (
        <div style={{ marginBottom: 10 }}>
          <div style={smallLabel}>Bake endpoint (Modal splat_bake)</div>
          <input value={bakeUrl} onChange={(e) => setSplatBakeUrl(e.target.value)} placeholder="…splatbake-web.modal.run" style={{ ...input, width: "100%", marginBottom: 6 }} />
          <button onClick={doBake} disabled={baking} style={{ ...primaryBtn, width: "100%", opacity: baking ? 0.6 : 1 }}>
            {baking ? "Baking…" : "✦ Bake this scene → splat"}
          </button>
          <div style={{ opacity: 0.45, fontSize: 10.5, marginTop: 5, lineHeight: 1.4 }}>
            Orbits ~42 posed views → trains a 3DGS on the Modal GPU (~15–25 min, ~$0.30–0.50). A one-way
            “publish” bake (deploy <code>spike/modal_splat.py</code> first).
          </div>
        </div>
      )}

      {progress && <div style={progressBox}>{progress}</div>}

      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 8, marginTop: 4 }}>
        <div style={{ ...smallLabel, marginBottom: 6 }}>Alignment</div>
        {slider("Height (ft)", "posY", -200, 200, 1)}
        {slider("Scale", "scale", 0.05, 8, 0.05)}
        {slider("Heading °", "heading", 0, 360, 1)}
        {slider("Yaw °", "yaw", 0, 360, 1)}
        <div style={{ marginBottom: 2 }}>
          <div style={smallLabel}>Exposure · {exposure.toFixed(2)}</div>
          <input
            type="range"
            min={0.3}
            max={2}
            step={0.05}
            value={exposure}
            onChange={(e) => setSplatExposure(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "#7ad28a" }}
          />
        </div>
      </div>
    </div>
  );
}

// ---- styles ----
const chipWrap: React.CSSProperties = {
  position: "absolute",
  top: 14,
  left: 264,
  padding: "6px 11px",
  borderRadius: 8,
  background: "rgba(18,20,23,0.82)",
  backdropFilter: "blur(8px)",
  border: "1px solid rgba(255,255,255,0.1)",
  fontSize: 12,
  cursor: "pointer",
  userSelect: "none",
  color: "#e8eaed",
};
const card: React.CSSProperties = {
  position: "absolute",
  top: 14,
  left: 264,
  width: 250,
  maxHeight: "calc(100vh - 28px)",
  overflowY: "auto",
  padding: 14,
  borderRadius: 10,
  background: "rgba(18,20,23,0.9)",
  backdropFilter: "blur(8px)",
  border: "1px solid rgba(255,255,255,0.1)",
  color: "#e8eaed",
  fontSize: 12,
};
const seg = (active: boolean): React.CSSProperties => ({
  flex: 1,
  textAlign: "center",
  padding: "5px 0",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 11.5,
  background: active ? "rgba(122,210,138,0.2)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "#7ad28a" : "transparent"}`,
  userSelect: "none",
});
const input: React.CSSProperties = {
  flex: 1,
  background: "rgba(0,0,0,0.3)",
  border: "1px solid rgba(255,255,255,0.14)",
  borderRadius: 5,
  color: "#e8e6e3",
  fontSize: 11.5,
  padding: "5px 7px",
};
const miniBtn: React.CSSProperties = {
  padding: "5px 10px",
  borderRadius: 5,
  background: "rgba(122,210,138,0.18)",
  border: "1px solid rgba(122,210,138,0.5)",
  cursor: "pointer",
  fontSize: 11.5,
  userSelect: "none",
  whiteSpace: "nowrap",
};
const primaryBtn: React.CSSProperties = {
  padding: "7px 10px",
  borderRadius: 7,
  cursor: "pointer",
  fontWeight: 600,
  fontSize: 11.5,
  background: "rgba(122,210,138,0.18)",
  border: "1px solid rgba(122,210,138,0.55)",
  color: "#fff",
  userSelect: "none",
};
const smallLabel: React.CSSProperties = {
  fontSize: 10,
  opacity: 0.5,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  marginBottom: 3,
};
const progressBox: React.CSSProperties = {
  marginBottom: 10,
  padding: "6px 8px",
  borderRadius: 6,
  fontSize: 11,
  lineHeight: 1.4,
  background: "rgba(122,210,138,0.1)",
  border: "1px solid rgba(122,210,138,0.3)",
};
