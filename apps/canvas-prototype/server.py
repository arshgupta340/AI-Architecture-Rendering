r"""Canvas-prototype local server — stdlib http.server + the proven E3 loop.

Run with: spike\.venv\Scripts\python.exe apps/canvas-prototype/server.py
Then open http://localhost:8765

Serves apps/canvas-prototype/public/ statically, plus:

  POST /api/apply_material
    body: {"region_ids": [int, ...]  OR  "region_semantic": "wall",
           "swatch": "<name from public/project/swatches/>"}
    → builds the union instance mask server-side, runs FLUX.2 [pro] Edit
      (fal.ai, the exact E3-winning recipe), composites with
      spike/composite.paste_tile, and returns the result as an RGBA *layer*
      (edit pixels inside the mask, transparent outside) cached under
      public/project/layers/<hash>.png.
    → {"layer_id", "image_url", "cost_est", "live", "cached"}

NO-SPEND fallback: swatch == "travertine" on the wall semantic serves the
precomputed spike/outputs/e3_swatch/final_composite.png — zero API calls.

Budget guard: at most MAX_LIVE_CALLS live fal calls per server session.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent
REPO = HERE.parent.parent
SPIKE = REPO / "spike"
PUBLIC = HERE / "public"
PROJECT = PUBLIC / "project"
LAYERS = PROJECT / "layers"

sys.path.insert(0, str(SPIKE))
import composite  # noqa: E402  (spike/composite.py — paste_tile)
from run_e3_swatch import _data_uri, _fal_call  # noqa: E402  (proven fal idioms)
from ingest import build_project  # noqa: E402  (capture -> canvas pipeline)
import multiview_apply  # noqa: E402  (spike/multiview_apply.py — the v2 lock engine)

PORT = int(os.environ.get("PORT", 8765))
COST_PER_CALL = 0.06          # FLUX.2 [pro] Edit, measured in E3
MAX_LIVE_CALLS = 8            # ~ $0.50 hard budget guard
_live_calls = 0

# ---------------------------------------------------------------- data load
_ids: np.ndarray | None = None      # (H, W) uint16
_regions: dict | None = None
_base_png: bytes | None = None


def _load_project():
    global _ids, _regions, _base_png
    rgb = np.array(Image.open(PROJECT / "ids_rgb.png").convert("RGB"))
    _ids = rgb[:, :, 0].astype(np.uint16) | (rgb[:, :, 1].astype(np.uint16) << 8)
    _regions = json.loads((PROJECT / "regions.json").read_text())
    _base_png = (PROJECT / "base.png").read_bytes()


def _project_version() -> float:
    """Monotonic-ish version = base.png mtime. The canvas polls this and
    reloads when it changes (i.e. after a new capture is ingested)."""
    b = PROJECT / "base.png"
    return b.stat().st_mtime if b.exists() else 0.0


def ingest(body: dict) -> dict:
    """Run the capture->canvas pipeline on a Rhino capture bundle, then reload.

    body: {"capture_dir": "<path with beauty/depth/id_mask/objects/camera>",
           "render": true}   # render=false reuses an existing base_render.png
    The locked render (when render=true) counts against the live-call budget.
    """
    global _live_calls
    capture_dir = body.get("capture_dir")
    if not capture_dir:
        raise ValueError("missing 'capture_dir'")
    render = bool(body.get("render", True))
    if render:
        if not os.environ.get("FAL_KEY"):
            raise RuntimeError("FAL_KEY not set (spike/.env) — cannot render")
        if _live_calls >= MAX_LIVE_CALLS:
            raise RuntimeError(f"budget guard: {MAX_LIVE_CALLS} live calls already spent")
        _live_calls += 1
    print(f"[ingest] capture_dir={capture_dir} render={render} "
          f"(live {_live_calls}/{MAX_LIVE_CALLS})")
    t0 = time.monotonic()
    info = build_project(capture_dir, render=render, out_dir=PROJECT)
    _load_project()
    info["version"] = _project_version()
    info["elapsed_s"] = round(time.monotonic() - t0, 1)
    print(f"[ingest] done in {info['elapsed_s']}s: {info['n_regions']} regions, "
          f"{info['size']}, decode {info['decode_pct']}%")
    return info


# Mask edge treatment. Registration is tight post-E2b (98% of edges within
# 2px), so we dilate only +1px to cover the anti-aliased ring, then feather
# ~1px so paste_tile's linear blend hides hairline seams at trim boundaries.
DILATE = 3      # MaxFilter window: +1px each side
FEATHER = 1.1   # Gaussian blur radius on the mask edge


def _mask_png(region_ids: list[int]) -> bytes:
    """Soft union mask for the given instance ids (+1px dilate, ~1px feather)."""
    m = np.isin(_ids, region_ids)
    img = Image.fromarray((m * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(DILATE))
    img = img.filter(ImageFilter.GaussianBlur(FEATHER))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _layer_rgba(final_png: bytes, mask_png: bytes) -> bytes:
    """Edit pixels inside mask, transparent outside → a stackable layer."""
    img = Image.open(io.BytesIO(final_png)).convert("RGBA")
    mask = Image.open(io.BytesIO(mask_png)).convert("L").resize(img.size)
    img.putalpha(mask)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


SWATCH_PROMPTS = {
    "travertine": "honed travertine stone cladding",
    "red_brick": "red clay brick in running bond courses with mortar joints",
    "charcoal_seam": "charcoal standing-seam metal cladding with vertical seams",
    "white_stucco": "smooth white stucco render",
    "weathered_cedar": "weathered cedar board siding",
}


def _swatch_path(name: str) -> Path:
    for ext in (".jpeg", ".jpg", ".png"):
        p = PROJECT / "swatches" / f"{name}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"unknown swatch: {name}")


def _semantic_of(region_ids: list[int]) -> set[str]:
    return {_regions["regions"].get(str(i), {}).get("semantic", "?")
            for i in region_ids}


def apply_material(body: dict) -> dict:
    global _live_calls
    swatch = body.get("swatch")
    if not swatch:
        raise ValueError("missing 'swatch'")
    swatch_file = _swatch_path(swatch)

    if body.get("region_ids"):
        region_ids = sorted(int(i) for i in body["region_ids"])
    elif body.get("region_semantic"):
        sem = body["region_semantic"]
        region_ids = sorted(int(k) for k, r in _regions["regions"].items()
                            if r["semantic"] == sem)
    else:
        raise ValueError("missing 'region_ids' or 'region_semantic'")
    if not region_ids:
        raise ValueError("no regions matched")

    key = hashlib.sha1(
        f"{swatch}|{','.join(map(str, region_ids))}".encode()).hexdigest()[:16]
    LAYERS.mkdir(parents=True, exist_ok=True)
    out_path = LAYERS / f"{key}.png"
    url = f"/project/layers/{key}.png"
    if out_path.exists():
        print(f"[apply] cache hit {key} ({swatch} -> {len(region_ids)} regions)")
        return {"layer_id": key, "image_url": url, "cost_est": 0.0,
                "live": False, "cached": True}

    mask_png = _mask_png(region_ids)
    semantics = _semantic_of(region_ids)

    # ---- NO-SPEND demo path: precomputed travertine walls on the ALIGNED base
    if swatch == "travertine" and semantics == {"wall"}:
        # travertine_walls_v2.png has travertine across the whole wall semantic
        # on the same depth+canny base the canvas shows; masking by the
        # *requested* instance mask yields a correct per-selection layer.
        final = (SPIKE / "outputs" / "e2_house_v2" / "travertine_walls_v2.png").read_bytes()
        out_path.write_bytes(_layer_rgba(final, mask_png))
        print(f"[apply] NO-SPEND path: precomputed E3 travertine walls -> {key}")
        return {"layer_id": key, "image_url": url, "cost_est": 0.0,
                "live": False, "cached": False}

    # ---- live path: FLUX.2 [pro] Edit (E3 winner) + mask composite
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY not set (spike/.env) — live path unavailable")
    if _live_calls >= MAX_LIVE_CALLS:
        raise RuntimeError(
            f"budget guard: {MAX_LIVE_CALLS} live calls "
            f"(~${MAX_LIVE_CALLS * COST_PER_CALL:.2f}) already spent this session")

    material = SWATCH_PROMPTS.get(swatch, swatch.replace("_", " "))
    target = " and ".join(sorted(semantics))
    prompt = (f"Apply the {material} material shown in the second image to the "
              f"{target} surfaces of the building in the first image. Only those "
              f"surfaces change; windows, trim, roof, ground, lighting, and "
              f"camera stay exactly identical.")
    _live_calls += 1
    print(f"[apply] LIVE fal call {_live_calls}/{MAX_LIVE_CALLS} "
          f"(~${COST_PER_CALL:.2f}): {swatch} -> {target} ({len(region_ids)} regions)")
    t0 = time.monotonic()
    edit = _fal_call("fal-ai/flux-2-pro/edit", {
        "prompt": prompt,
        "image_urls": [_data_uri(PROJECT / "base.png", fmt="JPEG"),
                       _data_uri(swatch_file, fmt="JPEG")],
        "output_format": "png",
        "safety_tolerance": "5",
    })
    print(f"[apply] fal returned in {time.monotonic() - t0:.1f}s")
    final = composite.paste_tile(_base_png, mask_png, edit)
    out_path.write_bytes(_layer_rgba(final, mask_png))
    return {"layer_id": key, "image_url": url, "cost_est": COST_PER_CALL,
            "live": True, "cached": False}


# =================================================================== MULTI-VIEW
# "one swatch -> all views": apply a material to a semantic across every view of
# the building, anchor-first then locking the rest (spike/multiview_apply.py engine).
# Purely additive — the single-view state/endpoints above are untouched.
VIEWS_DIR = PROJECT / "views"
MANIFEST = PROJECT / "views.json"


def _load_view(vid: str) -> multiview_apply.View:
    vdir = VIEWS_DIR / vid
    rgb = np.array(Image.open(vdir / "ids_rgb.png").convert("RGB"))
    ids = rgb[:, :, 0].astype(np.uint16) | (rgb[:, :, 1].astype(np.uint16) << 8)
    regions = json.loads((vdir / "regions.json").read_text())["regions"]
    base_png = (vdir / "base.png").read_bytes()
    return multiview_apply.View(vid, base_png, ids, regions)


def _views_meta() -> dict | None:
    """Manifest dict, or None if this project has no multi-view data."""
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text())


def _mv_layer_rgba_for(view: multiview_apply.View, final_png: bytes,
                       region_ids: list[int]) -> bytes:
    """RGBA layer for one view: edit pixels inside its instance mask, else transparent."""
    mask_png = multiview_apply.mask_png_from_ids(view.ids, region_ids)
    return _layer_rgba(final_png, mask_png)


def apply_material_all(body: dict) -> dict:
    """Apply a material to a semantic (or id set) across ALL views with the locked
    consistency. body: {"region_semantic": "wall" | "region_ids": [...], "swatch": ...}.

    Returns {"strategy", "swatch", "semantic", "anchor", "views":[{view_id, layer_id,
    image_url, region_ids, ...}], "cost_est", "live"}. Per-view layers are cached
    under public/project/layers/<hash>.png keyed by (swatch, view, ids)."""
    global _live_calls
    meta = _views_meta()
    if meta is None:
        raise ValueError("no multi-view project (run prepare_data_multiview.py)")
    swatch = body.get("swatch")
    if not swatch:
        raise ValueError("missing 'swatch'")
    swatch_file = _swatch_path(swatch)
    region_semantic = body.get("region_semantic")
    region_ids = sorted(int(i) for i in body["region_ids"]) if body.get("region_ids") else None
    if region_semantic is None and region_ids is None:
        raise ValueError("missing 'region_ids' or 'region_semantic'")

    anchor_id = meta["anchor"]
    anchor = _load_view(anchor_id)
    others = [_load_view(v["id"]) for v in meta["views"] if v["id"] != anchor_id]
    material_desc = SWATCH_PROMPTS.get(swatch, swatch.replace("_", " "))
    strategy = multiview_apply.lock_strategy(swatch)

    def _mv_key(vid: str, ids: list[int]) -> str:
        return hashlib.sha1(
            f"mv|{swatch}|{vid}|{','.join(map(str, ids))}".encode()).hexdigest()[:16]

    def _ids_in(view: multiview_apply.View) -> list[int]:
        if region_semantic is not None:
            return view.ids_for_semantic(region_semantic)
        present = set(int(k) for k in view.regions)
        return sorted(i for i in (region_ids or []) if i in present)

    # ---- cache short-circuit: if every view's layer already exists, no spend ----
    all_views = [anchor, *others]
    planned = [(v, _ids_in(v)) for v in all_views]
    cached = {}
    for v, vids in planned:
        if not vids:
            continue
        p = LAYERS / f"{_mv_key(v.id, vids)}.png"
        if p.exists():
            cached[v.id] = {"view_id": v.id, "layer_id": p.stem,
                            "image_url": f"/project/layers/{p.stem}.png", "region_ids": vids}
    if cached and all(v.id in cached or not vids for v, vids in planned):
        print(f"[apply_all] cache hit: {swatch} -> {region_semantic or region_ids} "
              f"({len(cached)} view layers, no spend)")
        views_out = [cached[v.id] if v.id in cached
                     else {"view_id": v.id, "skipped": True, "region_ids": []}
                     for v in others]
        return {"strategy": strategy, "swatch": swatch, "semantic": region_semantic,
                "anchor_id": anchor.id, "anchor": cached[anchor.id], "views": views_out,
                "cost_est": 0.0, "live": False, "cached": True}

    # The anchor stage equals the single-view apply, so reuse its no-spend path:
    # travertine on the wall semantic serves the precomputed E3/E2b walls for $0.
    anchor_sem_ids = (anchor.ids_for_semantic(region_semantic) if region_semantic
                      else [i for i in (region_ids or []) if str(i) in anchor.regions])
    anchor_precomp = None
    sem_set = {anchor.regions[str(i)]["semantic"] for i in anchor_sem_ids} if anchor_sem_ids else set()
    if swatch == "travertine" and sem_set == {"wall"}:
        anchor_precomp = (SPIKE / "outputs" / "e2_house_v2" / "travertine_walls_v2.png").read_bytes()

    # ---- budget guard: count the billable edits up front ----
    n_live = (0 if anchor_precomp is not None else 1) + len(others)
    if not os.environ.get("FAL_KEY") and n_live > 0:
        raise RuntimeError("FAL_KEY not set (spike/.env) — multi-view live path unavailable")
    if _live_calls + n_live > MAX_LIVE_CALLS:
        raise RuntimeError(
            f"budget guard: this would make {n_live} live calls and only "
            f"{MAX_LIVE_CALLS - _live_calls} remain this session "
            f"({MAX_LIVE_CALLS} total, ~${MAX_LIVE_CALLS * COST_PER_CALL:.2f})")

    def on_cost(c: float, label: str):
        global _live_calls
        _live_calls += 1
        print(f"[apply_all] LIVE fal {_live_calls}/{MAX_LIVE_CALLS} (~${c:.2f}): {label}")

    print(f"[apply_all] {swatch} -> {region_semantic or region_ids} across "
          f"{1 + len(others)} views (strategy={strategy}, "
          f"{'no-spend anchor' if anchor_precomp else 'live anchor'}, "
          f"{n_live} live calls)")
    t0 = time.monotonic()
    res = multiview_apply.apply_to_views(
        anchor=anchor, others=others, swatch_name=swatch, swatch_path=swatch_file,
        material_desc=material_desc, region_semantic=region_semantic,
        anchor_region_ids=region_ids, anchor_precomputed=anchor_precomp, on_cost=on_cost)
    print(f"[apply_all] done in {time.monotonic() - t0:.1f}s, est ${res['cost']:.2f}")

    # ---- persist per-view layers + assemble the response ----
    LAYERS.mkdir(parents=True, exist_ok=True)

    def emit(view: multiview_apply.View, final_png: bytes, ids: list[int]) -> dict:
        key = _mv_key(view.id, ids)
        p = LAYERS / f"{key}.png"
        p.write_bytes(_mv_layer_rgba_for(view, final_png, ids))
        return {"view_id": view.id, "layer_id": key,
                "image_url": f"/project/layers/{key}.png", "region_ids": ids}

    view_by_id = {anchor.id: anchor, **{v.id: v for v in others}}
    anchor_out = emit(anchor, res["anchor"]["final_png"], res["anchor"]["region_ids"])
    views_out = []
    for vr in res["views"]:
        if vr.get("skipped"):
            views_out.append({"view_id": vr["view_id"], "skipped": True,
                              "region_ids": []})
            continue
        views_out.append(emit(view_by_id[vr["view_id"]], vr["final_png"], vr["region_ids"]))

    return {
        "strategy": res["strategy"], "swatch": swatch,
        "semantic": region_semantic, "anchor_id": anchor.id,
        "anchor": anchor_out, "views": views_out,
        "cost_est": res["cost"], "live": anchor_precomp is None or len(others) > 0,
    }


# ------------------------------------------------------------------ server
MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
        ".png": "image/png", ".jpeg": "image/jpeg", ".jpg": "image/jpeg",
        ".json": "application/json", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter static logs
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/version":
            return self._json(200, {"version": _project_version()})
        if path == "/api/views":
            meta = _views_meta()
            return self._json(200, meta or {"anchor": None, "views": []})
        if path == "/":
            path = "/index.html"
        f = (PUBLIC / path.lstrip("/")).resolve()
        if PUBLIC.resolve() not in f.parents and f != PUBLIC.resolve():
            return self._json(403, {"error": "forbidden"})
        if not f.is_file():
            return self._json(404, {"error": f"not found: {path}"})
        self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))

    def do_POST(self):
        handler = {"/api/apply_material": apply_material,
                   "/api/apply_material_all": apply_material_all,
                   "/api/ingest": ingest}.get(self.path)
        if handler is None:
            return self._json(404, {"error": "unknown endpoint"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            self._json(200, handler(body))
        except (ValueError, FileNotFoundError) as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            print(f"[{handler.__name__}] ERROR: {e}")
            self._json(500, {"error": str(e)})


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(SPIKE / ".env")
    except ImportError:
        pass
    if not (PROJECT / "base.png").exists():
        sys.exit("run prepare_data.py first (no public/project/base.png)")
    _load_project()
    print(f"project loaded: {len(_regions['regions'])} regions, "
          f"ids {_ids.shape[1]}x{_ids.shape[0]}")
    print(f"FAL_KEY: {'set' if os.environ.get('FAL_KEY') else 'NOT set (no-spend only)'}")
    print(f"serving http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
