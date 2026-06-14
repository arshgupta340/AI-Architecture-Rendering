import { useMemo, useState } from "react";
import { useStore } from "../state/store";
import { SWATCHES, swatchById, swatchCategories, type Swatch } from "../lib/swatches";

const card: React.CSSProperties = {
  position: "absolute",
  top: 0,
  right: 0,
  height: "100%",
  width: 280,
  padding: "18px 16px",
  background: "rgba(18,20,23,0.82)",
  backdropFilter: "blur(8px)",
  borderLeft: "1px solid rgba(255,255,255,0.08)",
  display: "flex",
  flexDirection: "column",
  gap: 16,
  overflowY: "auto",
  fontSize: 13,
};

const h: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  opacity: 0.5,
  marginBottom: 8,
};

const chip = (active: boolean): React.CSSProperties => ({
  padding: "5px 10px",
  borderRadius: 6,
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.12)"}`,
  background: active ? "rgba(47,109,246,0.18)" : "rgba(255,255,255,0.04)",
  cursor: "pointer",
  fontSize: 12,
  userSelect: "none",
});

// Small filter pill for category + search. Slightly tighter than `chip`.
const pill = (active: boolean): React.CSSProperties => ({
  padding: "3px 9px",
  borderRadius: 999,
  border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.12)"}`,
  background: active ? "rgba(47,109,246,0.18)" : "rgba(255,255,255,0.04)",
  cursor: "pointer",
  fontSize: 11,
  textTransform: "capitalize",
  userSelect: "none",
  whiteSpace: "nowrap",
});

const searchInput: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "6px 9px",
  borderRadius: 6,
  border: "1px solid rgba(255,255,255,0.12)",
  background: "rgba(255,255,255,0.05)",
  color: "inherit",
  fontSize: 12,
  outline: "none",
};

function matches(sw: Swatch, q: string): boolean {
  if (!q) return true;
  const hay = `${sw.label} ${sw.category} ${sw.tags.join(" ")}`.toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((term) => hay.includes(term));
}

export function Sidebar() {
  const present = useStore((s) => s.semanticsPresent);
  const selected = useStore((s) => s.selected);
  const select = useStore((s) => s.select);
  const layers = useStore((s) => s.layers);
  const applySwatch = useStore((s) => s.applySwatch);
  const toggleLayer = useStore((s) => s.toggleLayer);
  const removeLayer = useStore((s) => s.removeLayer);
  const clearLayers = useStore((s) => s.clearLayers);
  const swatchScale = useStore((s) => s.swatchScale);
  const setSwatchScale = useStore((s) => s.setSwatchScale);

  const [query, setQuery] = useState("");
  const [cat, setCat] = useState<string | null>(null);
  const categories = useMemo(() => swatchCategories(), []);

  const results = useMemo(
    () => SWATCHES.filter((sw) => (cat ? sw.category === cat : true) && matches(sw, query)),
    [query, cat]
  );

  return (
    <div style={card}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>Architect 3D</div>
        <div style={{ opacity: 0.55, fontSize: 12 }}>
          Click an element, then pick a material.
        </div>
      </div>

      <div>
        <div style={h}>Element {selected ? `· ${selected}` : ""}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {present.map((s) => (
            <span key={s} style={chip(s === selected)} onClick={() => select(s === selected ? null : s)}>
              {s}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div style={h}>Material · {SWATCHES.length}</div>
        {!selected && <div style={{ opacity: 0.5, fontSize: 12 }}>Select an element first.</div>}

        {selected && (
          <>
            <input
              style={searchInput}
              placeholder="Search brick, wood, concrete…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: "8px 0" }}>
              <span style={pill(cat === null)} onClick={() => setCat(null)}>
                all
              </span>
              {categories.map((c) => (
                <span key={c} style={pill(cat === c)} onClick={() => setCat(cat === c ? null : c)}>
                  {c}
                </span>
              ))}
            </div>

            {results.length === 0 && (
              <div style={{ opacity: 0.5, fontSize: 12 }}>No materials match.</div>
            )}

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 8,
              }}
            >
              {results.map((sw) => {
                const active = layers.some((l) => l.semantic === selected && l.swatch === sw.id);
                return (
                  <div
                    key={sw.id}
                    onClick={() => applySwatch(selected, sw.id)}
                    title={sw.label}
                    style={{
                      cursor: "pointer",
                      borderRadius: 7,
                      overflow: "hidden",
                      border: `1px solid ${active ? "#2f6df6" : "rgba(255,255,255,0.1)"}`,
                      boxShadow: active ? "0 0 0 1px rgba(47,109,246,0.6)" : "none",
                      background: "rgba(255,255,255,0.03)",
                    }}
                  >
                    <div
                      style={{
                        position: "relative",
                        width: "100%",
                        aspectRatio: "1 / 1",
                        background: sw.color, // chip fallback shows behind the image
                        backgroundImage: `url(/materials/${sw.id}/albedo.jpg)`,
                        backgroundSize: "cover",
                        backgroundPosition: "center",
                      }}
                    />
                    <div
                      style={{
                        fontSize: 9.5,
                        lineHeight: 1.15,
                        padding: "3px 4px",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        opacity: active ? 1 : 0.75,
                      }}
                    >
                      {sw.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {selected &&
          layers.some((l) => l.semantic === selected) &&
          (() => {
            const sw = layers.find((l) => l.semantic === selected)!.swatch;
            const val = swatchScale[sw] ?? 1;
            return (
              <div style={{ marginTop: 12 }}>
                <div style={{ ...h, marginBottom: 4 }}>Texture scale · {val.toFixed(2)}×</div>
                <input
                  type="range"
                  min={0.25}
                  max={4}
                  step={0.05}
                  value={val}
                  onChange={(e) => setSwatchScale(sw, parseFloat(e.target.value))}
                  style={{ width: "100%", accentColor: "#2f6df6" }}
                />
              </div>
            );
          })()}
      </div>

      <div style={{ marginTop: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={h}>Layers · {layers.length}</div>
          {layers.length > 0 && (
            <span
              onClick={clearLayers}
              style={{ fontSize: 11, opacity: 0.55, cursor: "pointer" }}
            >
              clear
            </span>
          )}
        </div>
        {layers.length === 0 && <div style={{ opacity: 0.4, fontSize: 12 }}>No materials applied.</div>}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {layers.map((l) => (
            <div
              key={l.semantic}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 7px",
                borderRadius: 6,
                background: "rgba(255,255,255,0.04)",
              }}
            >
              <span
                onClick={() => toggleLayer(l.semantic)}
                title="toggle visibility"
                style={{ cursor: "pointer", width: 16, opacity: l.visible ? 1 : 0.35 }}
              >
                {l.visible ? "●" : "○"}
              </span>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 3,
                  background: swatchById(l.swatch)?.color ?? "#888",
                  flex: "0 0 auto",
                }}
              />
              <span style={{ flex: 1, fontSize: 12 }}>
                {l.semantic} <span style={{ opacity: 0.5 }}>· {swatchById(l.swatch)?.label}</span>
              </span>
              <span
                onClick={() => removeLayer(l.semantic)}
                title="remove"
                style={{ cursor: "pointer", opacity: 0.5 }}
              >
                ✕
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
