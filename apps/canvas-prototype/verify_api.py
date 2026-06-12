r"""Verify the canvas-prototype server (no API spend).

Usage: start server.py, then
  spike\.venv\Scripts\python.exe apps/canvas-prototype/verify_api.py
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

BASE = "http://localhost:8765"
ok_count = 0


def check(name: str, cond: bool, detail: str = ""):
    global ok_count
    print(f"  [{'OK' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if cond:
        ok_count += 1
    else:
        sys.exit(f"verification failed at: {name}")


def get(path: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(BASE + path) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


print("1. static serving")
s, b = get("/")
check("GET / serves index.html", s == 200 and b"<canvas" in b)
s, b = get("/project/regions.json")
check("GET regions.json", s == 200)
meta = json.loads(b)
walls = sorted(int(k) for k, v in meta["regions"].items() if v["semantic"] == "wall")
check("wall regions present", len(walls) == 10, f"ids {walls}")
s, b = get("/project/base.png")
base = Image.open(io.BytesIO(b))
check("GET base.png", s == 200 and base.size == tuple(meta["size"]), f"{base.size}")
s, b = get("/project/ids_rgb.png")
check("GET ids_rgb.png", s == 200 and Image.open(io.BytesIO(b)).size == base.size)
for sw in ("travertine.jpeg", "red_brick.png", "charcoal_seam.png",
           "white_stucco.png", "weathered_cedar.png"):
    s, _ = get(f"/project/swatches/{sw}")
    check(f"swatch {sw}", s == 200)
s, _ = get("/../server.py")
check("path traversal blocked", s in (403, 404))

print("2. apply_material — NO-SPEND travertine/wall path")
s, res = post("/api/apply_material", {"region_semantic": "wall", "swatch": "travertine"})
check("status 200", s == 200, json.dumps(res))
check("no spend", res["cost_est"] == 0.0 and res["live"] is False)
s, b = get(res["image_url"])
layer = Image.open(io.BytesIO(b))
check("layer is RGBA at base size", layer.mode == "RGBA" and layer.size == base.size)
a = np.array(layer)[:, :, 3]
check("layer alpha = wall mask (partial coverage)",
      0 < (a > 0).sum() < a.size, f"{(a > 0).sum():,} px opaque")
# opaque pixels differ from base (travertine), transparent region untouched on composite
rgb = np.array(layer)[:, :, :3].astype(int)
bs = np.array(base.convert("RGB")).astype(int)
diff_in = np.abs(rgb - bs)[a > 128].mean()
check("edit pixels differ from base inside mask", diff_in > 8, f"mean |diff| {diff_in:.1f}")

print("3. cache + subset + errors")
s, res2 = post("/api/apply_material", {"region_semantic": "wall", "swatch": "travertine"})
check("identical request is a cache hit", s == 200 and res2["cached"] is True
      and res2["layer_id"] == res["layer_id"])
s, res3 = post("/api/apply_material", {"region_ids": walls[:2], "swatch": "travertine"})
check("wall-subset travertine also no-spend", s == 200 and res3["live"] is False
      and res3["layer_id"] != res["layer_id"])
s, b3 = get(res3["image_url"])
a3 = np.array(Image.open(io.BytesIO(b3)))[:, :, 3]
check("subset layer smaller than full wall layer", (a3 > 0).sum() < (a > 0).sum(),
      f"{(a3 > 0).sum():,} < {(a > 0).sum():,} px")
s, res = post("/api/apply_material", {"swatch": "travertine"})
check("missing regions -> 400", s == 400)
s, res = post("/api/apply_material", {"region_ids": walls[:1], "swatch": "nope"})
check("unknown swatch -> 400", s == 400)
s, res = post("/api/apply_material", {"region_semantic": "no_such", "swatch": "travertine"})
check("empty semantic -> 400", s == 400)

print(f"\nALL {ok_count} CHECKS PASSED")
