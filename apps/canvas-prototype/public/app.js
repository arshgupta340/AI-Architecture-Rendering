/* Canvas prototype — region hover/select, swatch apply, layer stack.
   Vanilla JS, no build step.

   Multi-view ("one swatch -> all views"): when /api/views returns >1 view, the
   canvas shows a tab strip and an "Apply to all views" action. Per-view data
   (base/ids/regions) loads from /project/views/<id>/. Layers are view-aware:
   a single-view layer paints only on its view; a multi-view layer carries one
   image per view and the active view's image is composited. The existing
   single-view flow (one project, /api/apply_material) is unchanged when there
   is no views.json. */
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
let ids = null;                 // Uint16Array W*H (active view)
let regions = {}, semantics = {};
let hoverId = 0;
let selection = new Set();      // instance ids
let selectedSwatch = null;
// A layer: {regionKey, regionIds, semantic, label, swatch, visible, live,
//           multi:bool, byView:{viewId:{imageUrl, img}}}  (single-view layers
//           store a single-entry byView under the active view id at apply time).
let layers = [];
let busy = false;

// multi-view state
let viewsMeta = null;           // {anchor, views:[{id,label,...}]} or null
let activeView = null;          // current view id
const viewCache = {};           // viewId -> {W,H,baseImg,ids,regions,semantics}

// ---------------------------------------------------------------- loading
function loadImage(src) {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error("failed to load " + src));
    im.src = src;
  });
}

let projectVersion = 0;

function idsBase(v) {
  // where a view's files live: multi-view -> /project/views/<id>/, else /project/
  return viewsMeta && v ? `/project/views/${v}` : "/project";
}

// (Re)load ONE view's files into viewCache and (if active) into the live globals.
async function loadView(viewId, v) {
  const root = idsBase(viewId);
  const meta = await (await fetch(`${root}/regions.json?v=${v}`)).json();
  const [vw, vh] = meta.size;
  const baseI = await loadImage(`${root}/base.png?v=${v}`);
  const idsImg = await loadImage(`${root}/ids_rgb.png?v=${v}`);
  const c = document.createElement("canvas");
  c.width = vw; c.height = vh;
  const cx = c.getContext("2d", { willReadFrequently: true });
  cx.drawImage(idsImg, 0, 0);
  const d = cx.getImageData(0, 0, vw, vh).data;
  const idArr = new Uint16Array(vw * vh);
  for (let i = 0, p = 0; i < idArr.length; i++, p += 4)
    idArr[i] = d[p] | (d[p + 1] << 8);
  viewCache[viewId || "_single"] = {
    W: vw, H: vh, baseImg: baseI, ids: idArr,
    regions: meta.regions, semantics: meta.semantics,
  };
}

// Switch the canvas to a view already present in viewCache.
function activateView(viewId) {
  const c = viewCache[viewId || "_single"];
  if (!c) return;
  activeView = viewId;
  W = c.W; H = c.H; baseImg = c.baseImg; ids = c.ids;
  regions = c.regions; semantics = c.semantics;
  view.width = overlay.width = W;
  view.height = overlay.height = H;
  hoverId = 0; selection.clear();
  renderViewTabs();
  redraw(); renderInspector();
  $("status").textContent =
    `${Object.keys(regions).length} regions · ${viewId ? viewId + " · " : ""}${W}×${H}`;
}

async function loadProject(v) {
  viewsMeta = null;
  try {
    const vm = await (await fetch(`/api/views?v=${v}`)).json();
    if (vm && vm.views && vm.views.length) viewsMeta = vm;
  } catch { /* no multi-view */ }

  if (viewsMeta) {
    for (const vw of viewsMeta.views) await loadView(vw.id, v);
    activateView(activeView && viewCache[activeView] ? activeView : viewsMeta.anchor);
  } else {
    await loadView(null, v);
    activateView(null);
  }
}

async function init() {
  projectVersion = (await (await fetch("/api/version")).json()).version || 0;
  await loadProject(projectVersion);
  buildSwatchGrid();
  await restoreLayers();
  redraw();
  renderLayerPanel();

  view.style.pointerEvents = "auto";
  view.addEventListener("pointermove", onMove);
  view.addEventListener("pointerleave", () => { hoverId = 0; drawOverlay(); tooltip(null); });
  view.addEventListener("click", onClick);
  startSyncPoll();
}

function startSyncPoll() {
  const sync = $("sync");
  setInterval(async () => {
    let v;
    try { v = (await (await fetch("/api/version", { cache: "no-store" })).json()).version; }
    catch { return; }
    if (!v || v === projectVersion) return;
    projectVersion = v;
    sync.textContent = "⟳ syncing from Rhino…";
    layers = []; persistLayers();
    for (const k of Object.keys(viewCache)) delete viewCache[k];
    await loadProject(v);
    renderLayerPanel();
    const t = new Date().toLocaleTimeString();
    sync.textContent = `● synced ${t}`;
  }, 3000);
}

// ---------------------------------------------------------------- view tabs
function renderViewTabs() {
  const bar = $("view-tabs");
  if (!bar) return;
  if (!viewsMeta) { bar.style.display = "none"; return; }
  bar.style.display = "flex";
  bar.innerHTML = "";
  for (const vw of viewsMeta.views) {
    const b = document.createElement("button");
    b.className = "view-tab" + (vw.id === activeView ? " active" : "");
    b.textContent = vw.label + (vw.anchor ? " ★" : "");
    b.title = vw.anchor ? "anchor view" : "linked view";
    b.onclick = () => { if (vw.id !== activeView) { activateView(vw.id); redraw(); } };
    bar.appendChild(b);
  }
}

// ---------------------------------------------------------------- canvas
function redraw() {
  if (!baseImg) return;
  vctx.clearRect(0, 0, W, H);
  vctx.drawImage(baseImg, 0, 0);
  for (const l of layers) {
    if (!l.visible) continue;
    const ent = layerImageForActiveView(l);
    if (ent && ent.img) vctx.drawImage(ent.img, 0, 0, W, H);
  }
}

// Which image (if any) this layer paints on the active view.
function layerImageForActiveView(l) {
  const key = activeView || "_single";
  return l.byView && l.byView[key];
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
  const canApply = !busy && selection.size > 0 && selectedSwatch;
  $("apply-btn").disabled = !canApply;
  const allBtn = $("apply-all-btn");
  if (allBtn) {
    // "Apply to all views" needs a single-semantic selection (the cross-view key)
    const oneSem = selectionSemantics().length === 1;
    allBtn.style.display = viewsMeta ? "block" : "none";
    allBtn.disabled = !canApply || !oneSem;
    allBtn.title = oneSem ? "" : "select a single material type (e.g. all walls) to propagate";
  }
  $("apply-note").textContent = selectedSwatch === "travertine" && selectionSemantics().join() === "wall"
    ? "travertine on walls uses the precomputed demo result (no API spend)"
    : selectedSwatch ? "live FLUX.2 Edit call (~$0.06 per view)" : "";
}

function buildSwatchGrid() {
  const grid = $("swatch-grid");
  grid.innerHTML = "";
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
  $("apply-btn").onclick = () => applyMaterial(false);
  const allBtn = $("apply-all-btn");
  if (allBtn) allBtn.onclick = () => applyMaterial(true);
}

// ---------------------------------------------------------------- layers
function regionKey(idsArr) { return [...idsArr].sort((a, b) => a - b).join(","); }

function setBusy(on, text) {
  busy = on;
  $("spinner").classList.toggle("hidden", !on);
  if (on) $("spinner-text").textContent = text;
  renderInspector();
}

async function applyMaterial(allViews) {
  if (busy || !selectedSwatch || selection.size === 0) return;
  const regionIds = [...selection].sort((a, b) => a - b);
  const sems = selectionSemantics();
  const semLabel = sems.length === 1 ? (semantics[sems[0]]?.label || sems[0]) : "Mixed";

  if (allViews) {
    if (sems.length !== 1) { alert("Pick a single material type (e.g. all walls)."); return; }
    return applyMaterialAll(sems[0], semLabel);
  }

  setBusy(true, `applying ${selectedSwatch}…`);
  try {
    const r = await fetch("/api/apply_material", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region_ids: regionIds, swatch: selectedSwatch }),
    });
    const res = await r.json();
    if (!r.ok) throw new Error(res.error || r.statusText);
    const img = await loadImage(res.image_url + "?t=" + Date.now());
    const key = regionKey(regionIds);
    const vk = activeView || "_single";
    const layer = {
      regionKey: key, regionIds, semantic: sems.join("+"),
      label: `${semLabel} (${regionIds.length})`,
      swatch: selectedSwatch, visible: true, live: res.live, multi: false,
      byView: { [vk]: { imageUrl: res.image_url, img } },
    };
    const i = layers.findIndex((l) => l.regionKey === key && !l.multi);
    if (i >= 0) layers[i] = layer; else layers.push(layer);
    persistLayers(); redraw(); renderLayerPanel();
    $("status").textContent = res.live
      ? `live edit done (est $${res.cost_est.toFixed(2)})`
      : res.cached ? "layer served from cache" : "layer served (no spend)";
  } catch (e) {
    $("status").textContent = "apply failed: " + e.message;
    alert("Apply failed: " + e.message);
  } finally {
    setBusy(false);
  }
}

async function applyMaterialAll(semantic, semLabel) {
  setBusy(true, `applying ${selectedSwatch} to all ${viewsMeta.views.length} views…`);
  try {
    const r = await fetch("/api/apply_material_all", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region_semantic: semantic, swatch: selectedSwatch }),
    });
    const res = await r.json();
    if (!r.ok) throw new Error(res.error || r.statusText);

    // collect anchor + each view into one multi-view layer
    const byView = {};
    const entries = [res.anchor, ...res.views].filter((e) => e && !e.skipped);
    for (const e of entries) {
      const img = await loadImage(e.image_url + "?t=" + Date.now());
      byView[e.view_id] = { imageUrl: e.image_url, img, regionIds: e.region_ids };
    }
    const key = `mv:${semantic}`;
    const layer = {
      regionKey: key, regionIds: res.anchor.region_ids, semantic,
      label: `${semLabel} · all views`,
      swatch: selectedSwatch, visible: true, live: res.live, multi: true,
      strategy: res.strategy, byView,
    };
    const i = layers.findIndex((l) => l.regionKey === key && l.multi);
    if (i >= 0) layers[i] = layer; else layers.push(layer);
    persistLayers(); redraw(); renderLayerPanel();
    $("status").textContent =
      `applied to ${entries.length} views · ${res.strategy} lock · est $${res.cost_est.toFixed(2)}`;
  } catch (e) {
    $("status").textContent = "apply-all failed: " + e.message;
    alert("Apply to all views failed: " + e.message);
  } finally {
    setBusy(false);
  }
}

function swatchFile(name) { return (SWATCHES.find((s) => s.name === name) || {}).file; }

function renderLayerPanel() {
  const list = $("layer-list");
  list.innerHTML = "";
  $("layer-empty").style.display = layers.length ? "none" : "block";
  [...layers].reverse().forEach((l) => {
    const el = document.createElement("div");
    el.className = "layer-item" + (l.visible ? "" : " off");
    const sub = l.multi
      ? `${l.swatch} · ${Object.keys(l.byView).length} views${l.strategy ? " · " + l.strategy : ""}`
      : `${l.swatch}${l.live ? "" : " · demo"}`;
    el.innerHTML =
      `<img src="/project/swatches/${swatchFile(l.swatch)}" alt="">` +
      `<div class="l-meta"><div class="l-name">${l.label}` +
      (l.multi ? ` <span class="badge mv">all views</span>` : ``) +
      `</div><div class="l-sub">${sub}</div></div>` +
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
  // store URLs (not the decoded images) per view; images reload on restore
  localStorage.setItem(LS_KEY, JSON.stringify(layers.map((l) => ({
    regionKey: l.regionKey, regionIds: l.regionIds, semantic: l.semantic,
    label: l.label, swatch: l.swatch, visible: l.visible, live: l.live,
    multi: l.multi, strategy: l.strategy,
    byView: Object.fromEntries(Object.entries(l.byView || {}).map(
      ([k, e]) => [k, { imageUrl: e.imageUrl, regionIds: e.regionIds }])),
  }))));
}

async function restoreLayers() {
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch {}
  for (const l of saved) {
    try {
      const byView = {};
      for (const [k, e] of Object.entries(l.byView || {})) {
        byView[k] = { imageUrl: e.imageUrl, regionIds: e.regionIds,
                      img: await loadImage(e.imageUrl) };
      }
      l.byView = byView;
      layers.push(l);
    } catch { /* a cached layer image is gone — drop the layer */ }
  }
}

init().catch((e) => { $("status").textContent = "init failed: " + e.message; });
