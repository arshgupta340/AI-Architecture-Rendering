import { useStore } from "../state/store";
import { ENT_ASSETS, ENT_RANGE } from "../Entourage";

const panel: React.CSSProperties = {
  position: "absolute",
  left: 14,
  bottom: 14,
  width: 232,
  background: "rgba(18,20,23,0.82)",
  backdropFilter: "blur(8px)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  padding: 12,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  fontSize: 12,
};

const seg = (active: boolean): React.CSSProperties => ({
  flex: 1,
  textAlign: "center",
  padding: "6px 0",
  borderRadius: 6,
  cursor: "pointer",
  background: active ? "rgba(47,109,246,0.22)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "#2f6df6" : "transparent"}`,
  userSelect: "none",
});

const chip: React.CSSProperties = {
  padding: "4px 9px",
  borderRadius: 6,
  cursor: "pointer",
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.1)",
  fontSize: 11.5,
  display: "flex",
  alignItems: "center",
  gap: 6,
};

const cinematicBtn: React.CSSProperties = {
  marginTop: 8,
  textAlign: "center",
  padding: "7px 0",
  borderRadius: 7,
  cursor: "pointer",
  background: "linear-gradient(90deg, rgba(124,77,255,0.25), rgba(47,109,246,0.18))",
  border: "1px solid rgba(124,77,255,0.6)",
  fontWeight: 600,
  fontSize: 11.5,
  userSelect: "none",
};

export function NavBar() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const requestSave = useStore((s) => s.requestSave);
  const requestGoto = useStore((s) => s.requestGoto);
  const removeView = useStore((s) => s.removeView);
  const presets = useStore((s) => s.presets);
  const views = useStore((s) => s.views);
  const rendering = useStore((s) => s.rendering);
  const setRendering = useStore((s) => s.setRendering);
  const setCinematic = useStore((s) => s.setCinematic);
  const renderMode = useStore((s) => s.renderMode);
  const setRenderMode = useStore((s) => s.setRenderMode);
  const ptSamples = useStore((s) => s.ptSamples);
  const placeAsset = useStore((s) => s.placeAsset);
  const setPlaceAsset = useStore((s) => s.setPlaceAsset);
  const entourage = useStore((s) => s.entourage);
  const clearEnt = useStore((s) => s.clearEnt);
  const entHeight = useStore((s) => s.entHeight);
  const setEntHeight = useStore((s) => s.setEntHeight);

  return (
    <div style={panel}>
      <div style={{ display: "flex", gap: 6 }}>
        <div style={seg(mode === "orbit")} onClick={() => setMode("orbit")}>
          Orbit
        </div>
        <div style={seg(mode === "walk")} onClick={() => setMode("walk")}>
          Walk
        </div>
      </div>
      {mode === "walk" && (
        <div style={{ opacity: 0.55, fontSize: 11, lineHeight: 1.45 }}>
          Click to look · WASD move · Space/Shift up·down · Esc to exit
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>
          Views
        </span>
        <span onClick={requestSave} style={{ cursor: "pointer", color: "#9db8ff" }}>
          + Save view
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {presets.map((v) => (
          <span key={v.id} style={chip} onClick={() => requestGoto(v)}>
            {v.label}
          </span>
        ))}
        {views.map((v) => (
          <span key={v.id} style={chip}>
            <span onClick={() => requestGoto(v)}>{v.label}</span>
            <span onClick={() => removeView(v.id)} style={{ opacity: 0.5 }}>
              ✕
            </span>
          </span>
        ))}
      </div>
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 10 }}>
        <span style={{ opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>
          Render mode
        </span>
        <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
          {(
            [
              ["webgl2", "WebGL2"],
              ["webgl2gi", "+ GI"],
              ["webgpu", "WebGPU"],
            ] as const
          ).map(([m, label]) => (
            <div
              key={m}
              style={{ ...seg(renderMode === m), fontSize: 10.5, padding: "5px 0" }}
              onClick={() => setRenderMode(m)}
            >
              {label}
            </div>
          ))}
        </div>
      </div>
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 10 }}>
        {!rendering ? (
          <div
            onClick={() => setRendering(true)}
            style={{
              textAlign: "center",
              padding: "7px 0",
              borderRadius: 7,
              cursor: "pointer",
              background: "rgba(47,109,246,0.18)",
              border: "1px solid #2f6df6",
              fontWeight: 600,
            }}
          >
            ◆ Path-trace render
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ flex: 1, color: "#9db8ff" }}>
              {ptSamples < 0
                ? `Building… ${-ptSamples}%`
                : ptSamples === 0
                  ? "Starting…"
                  : `Path-tracing · ${ptSamples} spp`}
            </span>
            <span
              onClick={() => setRendering(false)}
              style={{ cursor: "pointer", padding: "4px 10px", borderRadius: 6, background: "rgba(255,255,255,0.08)" }}
            >
              Exit
            </span>
          </div>
        )}
        <div onClick={() => setCinematic(true)} style={cinematicBtn}>
          ◆ Cinematic (UE5) — photoreal
        </div>
      </div>
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <span style={{ opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 10 }}>
            Entourage · {entourage.length}
          </span>
          {entourage.length > 0 && (
            <span onClick={clearEnt} style={{ cursor: "pointer", fontSize: 11, opacity: 0.55 }}>
              clear
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {ENT_ASSETS.map((a) => (
            <span
              key={a.id}
              style={{
                ...chip,
                border: `1px solid ${placeAsset === a.id ? "#2f6df6" : "rgba(255,255,255,0.1)"}`,
                background: placeAsset === a.id ? "rgba(47,109,246,0.2)" : "rgba(255,255,255,0.05)",
              }}
              onClick={() => setPlaceAsset(placeAsset === a.id ? null : a.id)}
            >
              {a.label}
            </span>
          ))}
        </div>
        {placeAsset && (
          <>
            <div style={{ marginTop: 8 }}>
              <div
                style={{
                  opacity: 0.5,
                  fontSize: 10,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                Height · {(entHeight[placeAsset] ?? 1).toFixed(1)} ft
              </div>
              <input
                type="range"
                min={ENT_RANGE[placeAsset][0]}
                max={ENT_RANGE[placeAsset][1]}
                step={ENT_RANGE[placeAsset][1] - ENT_RANGE[placeAsset][0] > 10 ? 0.5 : 0.1}
                value={entHeight[placeAsset] ?? 1}
                onChange={(e) => setEntHeight(placeAsset, parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#2f6df6" }}
              />
            </div>
            <div style={{ opacity: 0.55, fontSize: 11, marginTop: 6, lineHeight: 1.4 }}>
              Click the ground to place. Click the asset again to stop.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
