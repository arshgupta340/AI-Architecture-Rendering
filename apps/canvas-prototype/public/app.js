/* Canvas prototype — region hover/select, swatch apply, layer stack.
   Vanilla JS, no build step. */
"use strict";

const SWATCHES = [
  { name: "travertine",     label: "Travertine",          file: "travertine.jpeg", real: true },
  { name: "red_brick",      label: "Red Brick",           file: "red_brick.png" },
  { name: "charcoal_seam",  label: "Charcoal Seam Metal", file: "charcoal_seam.png" },
  { name: "white_stucco",   label: "White Stucco",        file: "white_stucco.png" },
  { name: "weathered_cedar",label: "Weathered Cedar",     file: "weathered_cedar.png" },
];
const LS_KEY = "canvas-proto-layers-v1";

const $ = (id) => document.getElementById(id);
const view = $("view"), overlay = $("overlay");
const vctx = view.getContext("2d"), octx = overlay.getContext("2d");

let W = 0, H = 0;
let baseImg = null;
let ids = null;                 // Uint16Array W*H
let regions = {}, semantics = {};
let hoverId = 0;
let selection = new Set();      // instance ids
let selectedSwatch = null;
let layers = [];                // {regionKey, regionIds, semantic, label, swatch, imageUrl, visible, img, live}
let busy = false;

// ---------------------------------------------------------------- loading
function loadImage(src) {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error("failed to load " + src));
    im.src = src;
  });
}

async function init() {
  const meta = await (await fetch("/project/regions.json")).json();
  regions = meta.regions; semantics = meta.semantics;
  [W, H] = meta.size;

  baseImg = await loadImage("/project/base.png");
  view.width = overlay.width = W;
  view.height = overlay.height = H;

  const idsImg = await loadImage("/project/ids_rgb.png");
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const cx = c.getContext("2d", { willReadFrequently: true });
  cx.drawImage(idsImg, 0, 0);
  const d = cx.getImageData(0, 0, W, H).data;
  ids = new Uint16Array(W * H);
  for (let i = 0, p = 0; i < ids.length; i++, p += 4)
    ids[i] = d[p] | (d[p + 1] << 8);

  buildSwatchGrid();
  await restoreLayers();
  redraw();
  renderLayerPanel();
  renderInspector();
  $("status").textContent =
    `${Object.keys(regions).length} regions · base ${W}×${H}`;

  view.style.pointerEvents = "auto";
  view.addEventListener("pointermove", onMove);
  view.addEventListener("pointerleave", () => { hoverId = 0; drawOverlay(); tooltip(null); });
  view.addEventListener("click", onClick);
}

// ---------------------------------------------------------------- canvas
function redraw() {
  vctx.clearRect(0, 0, W, H);
  vctx.drawImage(baseImg, 0, 0);
  for (const l of layers)
    if (l.visible && l.img) vctx.drawImage(l.img, 0, 0, W, H);
}

function hexRGB(hex) {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16),
          parseInt(hex.slice(5, 7), 16)];
}

function drawOverlay() {
  octx.clearRect(0, 0, W, H);
  if (!hoverId && selection.size === 0) return;
  const im = octx.createImageData(W, H);
  const px = im.data;
  const hc = hoverId ? hexRGB((semantics[regions[hoverId]?.semantic] || {}).color || "#ffffff") : null;
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i];
    if (!id) continue;
    const sel = selection.has(id);
    const hov = id === hoverId;
    if (!sel && !hov) continue;
    const p = i * 4;
    if (sel) { px[p] = 90; px[p + 1] = 169; px[p + 2] = 230; px[p + 3] = hov ? 150 : 110; }
    else     { px[p] = hc[0]; px[p + 1] = hc[1]; px[p + 2] = hc[2]; px[p + 3] = 90; }
  }
  octx.putImageData(im, 0, 0);
}

function eventToPixel(ev) {
  const r = view.getBoundingClientRect();
  const x = Math.floor((ev.clientX - r.left) * (W / r.width));
  const y = Math.floor((ev.clientY - r.top) * (H / r.height));
  if (x < 0 || y < 0 || x >= W || y >= H) return -1;
  return y * W + x;
}

function tooltip(ev) {
  const t = $("tooltip");
  if (!ev || !hoverId) { t.style.display = "none"; return; }
  const rec = regions[hoverId];
  if (!rec) { t.style.display = "none"; return; }
  const sem = semantics[rec.semantic] || { label: rec.semantic };
  t.innerHTML = `<div class="t-sem">${sem.label}</div>` +
                `<div class="t-layer">${rec.layer || ""}</div>`;
  const wrap = $("canvas-wrap").getBoundingClientRect();
  t.style.left = (ev.clientX - wrap.left + 14) + "px";
  t.style.top = (ev.clientY - wrap.top + 14) + "px";
  t.style.display = "block";
}

function onMove(ev) {
  const i = eventToPixel(ev);
  const id = i >= 0 ? ids[i] : 0;
  if (id !== hoverId) { hoverId = id; drawOverlay(); }
  tooltip(ev);
}

function onClick(ev) {
  const i = eventToPixel(ev);
  const id = i >= 0 ? ids[i] : 0;
  if (!id) { selection.clear(); }
  else if (ev.shiftKey || ev.ctrlKey) {
    selection.has(id) ? selection.delete(id) : selection.add(id);
  } else {
    selection = new Set([id]);
  }
  drawOverlay();
  renderInspector();
}

// ---------------------------------------------------------------- inspector
function selectionSemantics() {
  return [...new Set([...selection].map((i) => regions[i]?.semantic).filter(Boolean))];
}

function renderInspector() {
  const info = $("sel-info"), actions = $("sel-actions");
  actions.innerHTML = "";
  if (selection.size === 0) {
    info.innerHTML = "Hover to inspect, click to select a region.<br>" +
      "<span style='font-size:11px'>Shift-click adds to the selection.</span>";
  } else {
    const sems = selectionSemantics();
    const first = regions[[...selection][0]];
    const label = sems.length === 1 ? (semantics[sems[0]]?.label || sems[0]) : "Mixed";
    info.innerHTML =
      `<div class="s-sem">${label}</div>` +
      `<div class="s-layer">${first?.layer || ""}</div>` +
      `<div class="s-count">${selection.size} region${selection.size > 1 ? "s" : ""} selected</div>`;
    if (sems.length === 1) {
      const all = Object.keys(regions).filter((k) => regions[k].semantic === sems[0]).map(Number);
      if (all.length > selection.size) {
        const b = document.createElement("button");
        b.textContent = `Select all ${semantics[sems[0]]?.label || sems[0]} (${all.length})`;
        b.onclick = () => { selection = new Set(all); drawOverlay(); renderInspector(); };
        actions.appendChild(b);
      }
    }
  }
  $("apply-btn").disabled = busy || selection.size === 0 || !selectedSwatch;
  $("apply-note").textContent = selectedSwatch === "travertine" && selectionSemantics().join() === "wall"
    ? "travertine on walls uses the precomputed demo result (no API spend)"
    : selectedSwatch ? "live FLUX.2 Edit call (~$0.06)" : "";
}

function buildSwatchGrid() {
  const grid = $("swatch-grid");
  for (const s of SWATCHES) {
    const el = document.createElement("div");
    el.className = "swatch";
    el.innerHTML = `<img src="/project/swatches/${s.file}" alt="${s.label}">` +
      `<div class="sw-name">${s.label}${s.real ? "" : '<span class="badge">procedural</span>'}</div>`;
    el.onclick = () => {
      selectedSwatch = s.name;
      grid.querySelectorAll(".swatch").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      renderInspector();
    };
    grid.appendChild(el);
  }
  $("apply-btn").onclick = applyMaterial;
}

// ---------------------------------------------------------------- layers
function regionKey(idsArr) { return [...idsArr].sort((a, b) => a - b).join(","); }

async function applyMaterial() {
  if (busy || !selectedSwatch || selection.size === 0) return;
  const regionIds = [...selection].sort((a, b) => a - b);
  busy = true;
  $("spinner").classList.remove("hidden");
  $("spinner-text").textContent = `applying ${selectedSwatch}…`;
  renderInspector();
  try {
    const r = await fetch("/api/apply_material", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region_ids: regionIds, swatch: selectedSwatch }),
    });
    const res = await r.json();
    if (!r.ok) throw new Error(res.error || r.statusText);
    const img = await loadImage(res.image_url + "?t=" + Date.now());
    const key = regionKey(regionIds);
    const sems = selectionSemantics();
    const semLabel = sems.length === 1 ? (semantics[sems[0]]?.label || sems[0]) : "Mixed";
    const layer = {
      regionKey: key, regionIds, semantic: sems.join("+"),
      label: `${semLabel} (${regionIds.length})`,
      swatch: selectedSwatch, imageUrl: res.image_url,
      visible: true, img, live: res.live,
    };
    // core behavior: re-applying to the SAME region REPLACES that layer
    const i = layers.findIndex((l) => l.regionKey === key);
    if (i >= 0) layers[i] = layer; else layers.push(layer);
    persistLayers();
    redraw();
    renderLayerPanel();
    $("status").textContent = res.live
      ? `live edit done (est $${res.cost_est.toFixed(2)})`
      : res.cached ? "layer served from cache" : "layer served (no spend)";
  } catch (e) {
    $("status").textContent = "apply failed: " + e.message;
    alert("Apply failed: " + e.message);
  } finally {
    busy = false;
    $("spinner").classList.add("hidden");
    renderInspector();
  }
}

function swatchFile(name) { return (SWATCHES.find((s) => s.name === name) || {}).file; }

function renderLayerPanel() {
  const list = $("layer-list");
  list.innerHTML = "";
  $("layer-empty").style.display = layers.length ? "none" : "block";
  // top of the stack first, Photoshop-style
  [...layers].reverse().forEach((l) => {
    const el = document.createElement("div");
    el.className = "layer-item" + (l.visible ? "" : " off");
    el.innerHTML =
      `<img src="/project/swatches/${swatchFile(l.swatch)}" alt="">` +
      `<div class="l-meta"><div class="l-name">${l.label}</div>` +
      `<div class="l-sub">${l.swatch}${l.live ? "" : " · demo"}</div></div>` +
      `<button class="eye" title="toggle visibility">${l.visible ? "👁" : "—"}</button>` +
      `<button class="del" title="delete layer">✕</button>`;
    el.querySelector(".eye").onclick = () => {
      l.visible = !l.visible; persistLayers(); redraw(); renderLayerPanel();
    };
    el.querySelector(".del").onclick = () => {
      layers = layers.filter((x) => x !== l);
      persistLayers(); redraw(); renderLayerPanel();
    };
    list.appendChild(el);
  });
}

function persistLayers() {
  localStorage.setItem(LS_KEY, JSON.stringify(layers.map(
    ({ regionKey, regionIds, semantic, label, swatch, imageUrl, visible, live }) =>
      ({ regionKey, regionIds, semantic, label, swatch, imageUrl, visible, live }))));
}

async function restoreLayers() {
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch {}
  for (const l of saved) {
    try { l.img = await loadImage(l.imageUrl); layers.push(l); }
    catch { /* cached layer image gone — drop it */ }
  }
}

init().catch((e) => { $("status").textContent = "init failed: " + e.message; });
