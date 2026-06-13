r"""Verify the multi-view canvas endpoints (Part B).

Default run is NO-SPEND: it checks /api/views, that the single-view endpoints still
work (back-compat), and the apply_material_all error/guard paths — without issuing
any fal call. Pass --live to also run ONE real apply_material_all (travertine/wall:
anchor served from the precompute for $0, + 1 live FLUX.2 Edit lock for the front
view, ~$0.06) and assert both views get a layer.

Usage (server must be running on PORT, default 8766):
  PORT=8766 spike\.venv\Scripts\python.exe apps/canvas-prototype/server.py   # terminal 1
  spike\.venv\Scripts\python.exe apps/canvas-prototype/verify_multiview_api.py [--live]
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

PORT = int(os.environ.get("PORT", 8766))
BASE = f"http://localhost:{PORT}"
ok_count = 0


def check(name: str, cond: bool, detail: str = ""):
    global ok_count
    print(f"  [{'OK' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if cond:
        ok_count += 1
    else:
        sys.exit(f"verification failed at: {name}")


def get(path: str):
    try:
        with urllib.request.urlopen(BASE + path) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(path: str, body: dict, timeout=300):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


print("1. multi-view manifest")
s, b = get("/api/views")
check("GET /api/views 200", s == 200)
meta = json.loads(b)
check("manifest has >=2 views", len(meta.get("views", [])) >= 2, f"{[v['id'] for v in meta['views']]}")
check("anchor declared", meta.get("anchor") in [v["id"] for v in meta["views"]], meta.get("anchor"))
view_ids = [v["id"] for v in meta["views"]]
for vid in view_ids:
    s, _ = get(f"/project/views/{vid}/base.png")
    check(f"view '{vid}' base.png served", s == 200)
    s, rb = get(f"/project/views/{vid}/regions.json")
    check(f"view '{vid}' regions.json served", s == 200)

print("2. back-compat — single-view endpoints still work")
s, b = get("/")
check("GET / serves canvas", s == 200 and b"<canvas" in b)
s, b = get("/project/regions.json")
check("top-level regions.json (mirror)", s == 200)
walls = sorted(int(k) for k, v in json.loads(b)["regions"].items() if v["semantic"] == "wall")
check("walls present in mirror", len(walls) >= 1, f"{walls}")
s, res = post("/api/apply_material", {"region_semantic": "wall", "swatch": "travertine"})
check("single-view travertine no-spend still works", s == 200 and res["live"] is False)
s, _ = get("/api/version")
check("GET /api/version", s == 200)

print("3. apply_material_all — guards & errors (no spend)")
s, res = post("/api/apply_material_all", {"swatch": "travertine"})
check("missing region -> 400", s == 400, json.dumps(res)[:120])
s, res = post("/api/apply_material_all", {"region_semantic": "wall", "swatch": "nope"})
check("unknown swatch -> 400", s == 400)
s, res = post("/api/apply_material_all", {"region_semantic": "no_such", "swatch": "travertine"})
check("empty semantic -> error", s in (400, 500))

if "--live" in sys.argv:
    print("4. apply_material_all — LIVE travertine/wall (anchor precompute + 1 lock)")
    s, res = post("/api/apply_material_all",
                  {"region_semantic": "wall", "swatch": "travertine"}, timeout=300)
    check("status 200", s == 200, json.dumps(res)[:200])
    check("strategy is raw (travertine=smooth)", res["strategy"] == "raw", res["strategy"])
    check("anchor layer returned", "image_url" in res["anchor"])
    check("all non-anchor views returned a layer",
          all("image_url" in v for v in res["views"] if not v.get("skipped")),
          f"{[v['view_id'] for v in res['views']]}")
    # every returned layer is a valid RGBA PNG with partial (masked) coverage
    for entry in [res["anchor"], *[v for v in res["views"] if not v.get("skipped")]]:
        s, lb = get(entry["image_url"])
        layer = Image.open(io.BytesIO(lb))
        a = np.array(layer)[:, :, 3]
        check(f"layer {entry['view_id']} RGBA, partial coverage",
              s == 200 and layer.mode == "RGBA" and 0 < (a > 0).sum() < a.size,
              f"{(a > 0).sum():,} px opaque")
    print(f"     est cost this run: ${res['cost_est']:.2f}")
else:
    print("   (skip live apply — pass --live to run one ~$0.06 apply_material_all)")

print(f"\nALL {ok_count} CHECKS PASSED")
