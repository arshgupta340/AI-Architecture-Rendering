import { useState } from "react";
import { useStore, type ExportCfg } from "../state/store";
import { ENT_ASSETS, ENT_RANGE } from "../Entourage";
import { downloadBlob, exportFilename } from "../lib/exportImage";

/**
 * Horizontal toolbar, anchored bottom-CENTRE between the two side panels (Sky left,
 * Sidebar right). Laid out as a single wrapping flex row of control groups separated
 * by dividers, so it hugs the bottom edge and never rises up into the model space
 * the way a tall vertical panel did. Groups: Nav · Views · Render mode · Output
 * (presentation/grade/export) · Render actions · Entourage.
 */
const bar: React.CSSProperties = {
  position: "absolute",
  bottom: 14,
  left: "50%",
  transform: "translateX(-50%)",
  // Stay clear of the 250px Sky panel (left) and 280px Sidebar (right).
  maxWidth: "calc(100vw - 548px)",
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  justifyContent: "center",
  columnGap: 8,
  rowGap: 8,
  padding: "7px 12px",
  background: "rgba(18,20,23,0.86)",
  backdropFilter: "blur(10px)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: 12,
  boxShadow: "0 8px 28px rgba(0,0,0,0.35)",
  fontSize: 12,
};

const group: React.CSSProperties = { display: "flex", alignItems: "center", gap: 5 };

function Divider() {
  return <div style={{ width: 1, height: 22, background: "rgba(255,255,255,0.12)", margin: "0 2px" }} />;
}

// Compact segmented button (does NOT stretch — sized to content for a horizontal bar).
const seg = (active: boolean): React.CSSProperties => ({
  padding: "5px 10px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 11.5,
  background: active ? "rgba(47,109,246,0.22)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.08)"}`,
  userSelect: "none",
});

const chip = (active: boolean): React.CSSProperties => ({
  padding: "4px 9px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 11.5,
  display: "flex",
  alignItems: "center",
  gap: 5,
  background: active ? "rgba(47,109,246,0.2)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.1)"}`,
  userSelect: "none",
});

const iconBtn = (active = false): React.CSSProperties => ({
  padding: "5px 8px",
  borderRadius: 6,
  cursor: "pointer",
  userSelect: "none",
  background: active ? "rgba(47,109,246,0.2)" : "rgba(255,255,255,0.05)",
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.12)"}`,
});

const sel: React.CSSProperties = {
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.14)",
  borderRadius: 5,
  color: "#e8e6e3",
  fontSize: 11,
  padding: "3px 4px",
  cursor: "pointer",
};

const primaryBtn = (enabled: boolean): React.CSSProperties => ({
  padding: "5px 11px",
  borderRadius: 7,
  cursor: enabled ? "pointer" : "wait",
  fontWeight: 600,
  fontSize: 11.5,
  opacity: enabled ? 1 : 0.55,
  background: "rgba(47,109,246,0.2)",
  border: "1px solid #2f6df6",
  userSelect: "none",
  whiteSpace: "nowrap",
});

const label: React.CSSProperties = {
  opacity: 0.4,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  fontSize: 9.5,
  marginRight: 1,
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
  const setPresentation = useStore((s) => s.setPresentation);
  const grade = useStore((s) => s.grade);
  const setGrade = useStore((s) => s.setGrade);
  const gradeStrength = useStore((s) => s.gradeStrength);
  const setGradeStrength = useStore((s) => s.setGradeStrength);
  const exportCfg = useStore((s) => s.exportCfg);
  const setExportCfg = useStore((s) => s.setExportCfg);
  const captureFn = useStore((s) => s.captureFn);
  const heroCaptureFn = useStore((s) => s.heroCaptureFn);
  const openHero = useStore((s) => s.openHero);
  const [exporting, setExporting] = useState(false);
  const [heroBusy, setHeroBusy] = useState(false);

  const doHero = async () => {
    if (heroBusy) return;
    if (renderMode === "webgpu" || !heroCaptureFn) {
      alert("Hero render runs in WebGL2 / + GI modes. Switch render mode and try again.");
      return;
    }
    setHeroBusy(true);
    try {
      const cap = await heroCaptureFn({ maxEdge: 1536 });
      if (cap) openHero(cap);
      else alert("Hero capture isn't ready yet — switch to WebGL2 / + GI and retry.");
    } finally {
      setHeroBusy(false);
    }
  };

  const doExport = async () => {
    if (!captureFn || exporting) return;
    setExporting(true);
    try {
      const blob = await captureFn(exportCfg);
      if (blob) downloadBlob(blob, exportFilename(exportCfg));
      else
        alert(
          "Export couldn't read the frame. Switch to a WebGL2 render mode (WebGL2 / + GI) and try again.",
        );
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={bar}>
      {/* ── Navigation ── */}
      <div style={group}>
        <div style={seg(mode === "orbit")} onClick={() => setMode("orbit")}>
          Orbit
        </div>
        <div style={seg(mode === "walk")} onClick={() => setMode("walk")}>
          Walk
        </div>
      </div>

      <Divider />

      {/* ── Views ── */}
      <div style={group}>
        <span style={label}>View</span>
        {presets.map((v) => (
          <span key={v.id} style={chip(false)} onClick={() => requestGoto(v)} title={v.label}>
            {v.label}
          </span>
        ))}
        {views.map((v) => (
          <span key={v.id} style={chip(false)}>
            <span onClick={() => requestGoto(v)}>{v.label}</span>
            <span onClick={() => removeView(v.id)} style={{ opacity: 0.5 }}>
              ✕
            </span>
          </span>
        ))}
        <span style={{ ...chip(false), color: "#9db8ff" }} onClick={requestSave}>
          + Save
        </span>
      </div>

      <Divider />

      {/* ── Render mode ── */}
      <div style={group}>
        {(
          [
            ["webgl2", "WebGL2"],
            ["webgl2gi", "+ GI"],
            ["webgpu", "WebGPU"],
          ] as const
        ).map(([m, lbl]) => (
          <div key={m} style={seg(renderMode === m)} onClick={() => setRenderMode(m)}>
            {lbl}
          </div>
        ))}
      </div>

      <Divider />

      {/* ── Output: presentation · grade · high-res export ── */}
      <div style={group}>
        <div style={iconBtn()} onClick={() => setPresentation(true)} title="Presentation mode (hide panels)">
          ▣
        </div>
        <div
          style={iconBtn(grade)}
          onClick={() => setGrade(!grade)}
          title="Cinematic grade (contrast · vignette · grain)"
        >
          {grade ? "◉" : "○"} Grade
        </div>
        {grade && (
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={gradeStrength}
            onChange={(e) => setGradeStrength(parseFloat(e.target.value))}
            style={{ width: 64, accentColor: "#7c4dff" }}
            title="Grade strength"
          />
        )}
        <select
          value={exportCfg.aspect}
          onChange={(e) => setExportCfg({ aspect: e.target.value as ExportCfg["aspect"] })}
          style={sel}
          title="Aspect ratio"
        >
          <option value="16:9">16:9</option>
          <option value="3:2">3:2</option>
          <option value="4:3">4:3</option>
          <option value="1:1">1:1</option>
          <option value="free">Free</option>
        </select>
        <select
          value={exportCfg.scale}
          onChange={(e) => setExportCfg({ scale: Number(e.target.value) })}
          style={sel}
          title="Resolution supersample"
        >
          <option value={1}>1×</option>
          <option value={2}>2×</option>
          <option value={4}>4×</option>
        </select>
        <select
          value={exportCfg.format}
          onChange={(e) => setExportCfg({ format: e.target.value as ExportCfg["format"] })}
          style={sel}
          title="File format"
        >
          <option value="jpg">JPG</option>
          <option value="png">PNG</option>
        </select>
        <div style={primaryBtn(!!captureFn && !exporting)} onClick={doExport}>
          {exporting ? "Rendering…" : "⬇ Export"}
        </div>
      </div>

      <Divider />

      {/* ── Render actions: path-trace · cinematic UE5 ── */}
      <div style={group}>
        {!rendering ? (
          renderMode === "webgpu" ? (
            <span style={{ opacity: 0.45, fontSize: 11, whiteSpace: "nowrap" }} title="Path-trace runs in WebGL2 / + GI">
              PT · WebGL2 only
            </span>
          ) : (
            <div style={primaryBtn(true)} onClick={() => setRendering(true)}>
              ◆ Path-trace
            </div>
          )
        ) : (
          <>
            <span style={{ color: "#9db8ff", whiteSpace: "nowrap" }}>
              {ptSamples < 0
                ? `Building… ${-ptSamples}%`
                : ptSamples === 0
                  ? "Starting…"
                  : `PT · ${ptSamples} spp`}
            </span>
            <span
              onClick={() => setRendering(false)}
              style={{ cursor: "pointer", padding: "4px 9px", borderRadius: 6, background: "rgba(255,255,255,0.08)" }}
            >
              Exit
            </span>
          </>
        )}
        <div
          onClick={() => setCinematic(true)}
          title="Cinematic (UE5) — embed a SimplyStream WebGPU build"
          style={{
            padding: "5px 11px",
            borderRadius: 7,
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 11.5,
            whiteSpace: "nowrap",
            background: "linear-gradient(90deg, rgba(124,77,255,0.25), rgba(47,109,246,0.18))",
            border: "1px solid rgba(124,77,255,0.6)",
            userSelect: "none",
          }}
        >
          ◆ Cinematic
        </div>
        {renderMode === "webgpu" ? (
          <span style={{ opacity: 0.45, fontSize: 11, whiteSpace: "nowrap" }} title="Hero render runs in WebGL2 / + GI">
            Hero · WebGL2 only
          </span>
        ) : (
          <div
            onClick={doHero}
            title="Hero render — depth+canny-locked photoreal diffusion (FLUX)"
            style={{
              padding: "5px 11px",
              borderRadius: 7,
              cursor: heroBusy ? "wait" : "pointer",
              fontWeight: 600,
              fontSize: 11.5,
              whiteSpace: "nowrap",
              opacity: heroBusy ? 0.6 : 1,
              background: "linear-gradient(90deg, rgba(255,138,77,0.28), rgba(124,77,255,0.2))",
              border: "1px solid rgba(255,138,77,0.6)",
              userSelect: "none",
            }}
          >
            {heroBusy ? "Capturing…" : "✦ Hero render"}
          </div>
        )}
      </div>

      <Divider />

      {/* ── Entourage ── */}
      <div style={group}>
        <span style={label}>Place</span>
        {ENT_ASSETS.map((a) => (
          <span
            key={a.id}
            style={chip(placeAsset === a.id)}
            onClick={() => setPlaceAsset(placeAsset === a.id ? null : a.id)}
          >
            {a.label}
          </span>
        ))}
        {placeAsset && (
          <input
            type="range"
            min={ENT_RANGE[placeAsset][0]}
            max={ENT_RANGE[placeAsset][1]}
            step={ENT_RANGE[placeAsset][1] - ENT_RANGE[placeAsset][0] > 10 ? 0.5 : 0.1}
            value={entHeight[placeAsset] ?? 1}
            onChange={(e) => setEntHeight(placeAsset, parseFloat(e.target.value))}
            style={{ width: 70, accentColor: "#2f6df6" }}
            title={`Height · ${(entHeight[placeAsset] ?? 1).toFixed(1)} ft`}
          />
        )}
        {entourage.length > 0 && (
          <span onClick={clearEnt} style={{ cursor: "pointer", fontSize: 11, opacity: 0.5 }} title="Clear all entourage">
            clear ({entourage.length})
          </span>
        )}
      </div>

      {/* Contextual hint row (wraps to its own line) */}
      {(mode === "walk" || placeAsset) && (
        <div style={{ flexBasis: "100%", textAlign: "center", opacity: 0.5, fontSize: 10.5, lineHeight: 1.4 }}>
          {mode === "walk"
            ? "Click to look · WASD move · Space/Shift up·down · Esc to exit"
            : "Click the ground to place. Click the asset again to stop."}
        </div>
      )}
    </div>
  );
}
