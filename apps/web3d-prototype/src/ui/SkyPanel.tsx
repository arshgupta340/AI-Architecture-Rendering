import { useStore, type Mood } from "../state/store";
import { HDRI_PRESETS } from "../SolarSky";

const card: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  height: "100%",
  width: 250,
  padding: "18px 16px",
  background: "rgba(18,20,23,0.82)",
  backdropFilter: "blur(8px)",
  borderRight: "1px solid rgba(255,255,255,0.08)",
  display: "flex",
  flexDirection: "column",
  gap: 16,
  overflowY: "auto",
  fontSize: 13,
};

const h: React.CSSProperties = {
  fontSize: 10,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  opacity: 0.5,
  marginBottom: 7,
};

const chip = (active: boolean): React.CSSProperties => ({
  padding: "5px 9px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 11.5,
  userSelect: "none",
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.12)"}`,
  background: active ? "rgba(47,109,246,0.2)" : "rgba(255,255,255,0.04)",
});

const numInput: React.CSSProperties = {
  width: "100%",
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 5,
  color: "#e8e6e3",
  padding: "4px 7px",
  fontSize: 12,
};

const MOOD_LABELS: { id: Mood; label: string }[] = [
  { id: "sunny", label: "☀ Sunny" },
  { id: "overcast", label: "☁ Overcast" },
  { id: "golden", label: "🌅 Golden hour" },
  { id: "dusk", label: "🌆 Dusk" },
  { id: "night", label: "🌙 Night" },
];

const SEASONS = [
  { label: "Mar equinox", date: "2026-03-20" },
  { label: "Jun solstice", date: "2026-06-21" },
  { label: "Sep equinox", date: "2026-09-22" },
  { label: "Dec solstice", date: "2026-12-21" },
];

const fmtTime = (t: number) => {
  const hh = Math.floor(t);
  const mm = Math.round((t - hh) * 60);
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
};

const ENV_GOOGLE_KEY = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined) ?? "";

export function SkyPanel() {
  const sky = useStore((s) => s.sky);
  const setSky = useStore((s) => s.setSky);
  const applyMood = useStore((s) => s.applyMood);
  const geo = useStore((s) => s.geo);
  const setGeo = useStore((s) => s.setGeo);
  const hasKey = Boolean(geo.apiKey || ENV_GOOGLE_KEY);
  const hdriPreset = useStore((s) => s.hdriPreset);
  const setHdriPreset = useStore((s) => s.setHdriPreset);
  const sunPath = useStore((s) => s.sunPath);
  const setSunPath = useStore((s) => s.setSunPath);
  const showClouds = useStore((s) => s.showClouds);
  const setShowClouds = useStore((s) => s.setShowClouds);

  return (
    <div style={card}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>Sky &amp; Sun</div>
        <div style={{ opacity: 0.55, fontSize: 12 }}>Real solar position by site + time.</div>
      </div>

      <div>
        <div style={h}>Mood</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {MOOD_LABELS.map((m) => (
            <span key={m.id} style={chip(sky.mood === m.id)} onClick={() => applyMood(m.id)}>
              {m.label}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div style={h}>Time of day · {fmtTime(sky.timeOfDay)}</div>
        <input
          type="range"
          min={0}
          max={24}
          step={0.25}
          value={sky.timeOfDay}
          onChange={(e) => setSky({ timeOfDay: parseFloat(e.target.value) })}
          style={{ width: "100%", accentColor: "#2f6df6" }}
        />
      </div>

      <div>
        <div style={h}>Date</div>
        <input
          type="date"
          value={sky.date}
          onChange={(e) => setSky({ date: e.target.value })}
          style={{ ...numInput, marginBottom: 8 }}
        />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {SEASONS.map((s) => (
            <span key={s.date} style={chip(sky.date === s.date)} onClick={() => setSky({ date: s.date })}>
              {s.label}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div style={h}>Sun intensity · {sky.sunIntensity.toFixed(2)}×</div>
        <input
          type="range"
          min={0}
          max={2}
          step={0.05}
          value={sky.sunIntensity}
          onChange={(e) => setSky({ sunIntensity: parseFloat(e.target.value) })}
          style={{ width: "100%", accentColor: "#2f6df6" }}
        />
      </div>

      <div>
        <div style={h}>Cloud cover · {Math.round(sky.cloudCover * 100)}%</div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={sky.cloudCover}
          onChange={(e) => setSky({ cloudCover: parseFloat(e.target.value) })}
          style={{ width: "100%", accentColor: "#2f6df6" }}
        />
      </div>

      <div>
        <div style={h}>HDRI sky</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {HDRI_PRESETS.map((p) => (
            <span
              key={p.id}
              style={chip(hdriPreset === p.id)}
              onClick={() => setHdriPreset(p.id)}
            >
              {p.label}
            </span>
          ))}
        </div>
        <div style={{ opacity: 0.45, fontSize: 10.5, lineHeight: 1.4, marginTop: 6 }}>
          Drives image-based lighting + reflections (WebGPU + path-traced hero).
        </div>
      </div>

      <div>
        <div style={h}>Overlays</div>
        <label
          style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12, marginBottom: 8 }}
        >
          <input
            type="checkbox"
            checked={sunPath}
            onChange={(e) => setSunPath(e.target.checked)}
            style={{ accentColor: "#2f6df6" }}
          />
          Sun-path arc (day track + analemma)
        </label>
        <label
          style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12 }}
        >
          <input
            type="checkbox"
            checked={showClouds}
            onChange={(e) => setShowClouds(e.target.checked)}
            style={{ accentColor: "#2f6df6" }}
          />
          Clouds
        </label>
      </div>

      <div>
        <div style={h}>Site coordinates</div>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1 }}>
            <div style={{ opacity: 0.5, fontSize: 11, marginBottom: 3 }}>Latitude</div>
            <input
              type="number"
              step={0.01}
              value={sky.lat}
              onChange={(e) => setSky({ lat: parseFloat(e.target.value) || 0 })}
              style={numInput}
            />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ opacity: 0.5, fontSize: 11, marginBottom: 3 }}>Longitude</div>
            <input
              type="number"
              step={0.01}
              value={sky.lng}
              onChange={(e) => setSky({ lng: parseFloat(e.target.value) || 0 })}
              style={numInput}
            />
          </div>
        </div>
      </div>

      {/* ---- Real-world context: Google Photorealistic 3D Tiles ---- */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Real-world context</div>
        <div style={{ opacity: 0.55, fontSize: 11.5, lineHeight: 1.4, marginBottom: 10 }}>
          Load Google Photorealistic 3D Tiles around the model at the site coordinates above.
        </div>

        <div style={h}>Google Maps API key</div>
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={geo.apiKey}
          placeholder={ENV_GOOGLE_KEY ? "(using key from .env.local)" : "paste your key…"}
          onChange={(e) => setGeo({ apiKey: e.target.value.trim() })}
          style={{ ...numInput, marginBottom: 6 }}
        />
        <div style={{ opacity: 0.45, fontSize: 10.5, lineHeight: 1.4, marginBottom: 10 }}>
          Stored only in this browser. Needs the “Map Tiles API” enabled; Google bills per session.
        </div>

        <div
          onClick={() => hasKey && setGeo({ enabled: !geo.enabled })}
          style={{
            textAlign: "center",
            padding: "8px 0",
            borderRadius: 7,
            cursor: hasKey ? "pointer" : "not-allowed",
            fontWeight: 600,
            opacity: hasKey ? 1 : 0.4,
            userSelect: "none",
            background: geo.enabled ? "rgba(255,255,255,0.06)" : "rgba(47,109,246,0.18)",
            border: `1px solid ${geo.enabled ? "rgba(255,255,255,0.18)" : "#2f6df6"}`,
          }}
        >
          {!hasKey
            ? "Enter a key to enable"
            : geo.enabled
              ? "■ Hide real-world context"
              : "🌍 Load real-world context"}
        </div>

        {geo.enabled && (
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div style={h}>Site elevation · {geo.height} m</div>
              <input
                type="number"
                step={1}
                value={geo.height}
                onChange={(e) => setGeo({ height: parseFloat(e.target.value) || 0 })}
                style={numInput}
              />
              <div style={{ opacity: 0.45, fontSize: 10.5, marginTop: 3 }}>
                Approx ground elevation (m above sea level). Changing this reloads tiles.
              </div>
            </div>
            <div>
              <div style={h}>
                Seat building · {geo.groundOffset > 0 ? "+" : ""}
                {geo.groundOffset} ft
              </div>
              <input
                type="range"
                min={-120}
                max={120}
                step={1}
                value={geo.groundOffset}
                onChange={(e) => setGeo({ groundOffset: parseFloat(e.target.value) })}
                style={{ width: "100%", accentColor: "#2f6df6" }}
              />
            </div>
            <div>
              <div style={h}>North heading · {geo.heading}°</div>
              <input
                type="range"
                min={0}
                max={359}
                step={1}
                value={geo.heading}
                onChange={(e) => setGeo({ heading: parseFloat(e.target.value) })}
                style={{ width: "100%", accentColor: "#2f6df6" }}
              />
            </div>
            <label
              style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12 }}
            >
              <input
                type="checkbox"
                checked={geo.hideRhinoSite}
                onChange={(e) => setGeo({ hideRhinoSite: e.target.checked })}
                style={{ accentColor: "#2f6df6" }}
              />
              Hide Rhino ground / site mesh
            </label>
          </div>
        )}
      </div>
    </div>
  );
}
