r"""LOCAL MOCK of the Modal FLUX hero backend — for QA of the web app's hero flow
WITHOUT a GPU / Modal deploy. It runs the REAL conditioning (prep_canny ∪ id-edges,
prep_depth) ported in modal_flux.py, and returns a VISIBLE composite so you can
confirm the geometry lock is correct end to end:

  POST /hero_render  -> beauty with the canny ∪ id-edge lines burned in (red) and a
                        depth inset (top-right). This is what FLUX would be locked to.
  POST /region_edit  -> base with the selected region tinted green (validates the
                        id→mask→composite path is byte-stable outside the mask).

Auth: accepts any non-empty `body["secret"]` (mock). CORS open for localhost.

Run:  spike\.venv\Scripts\python.exe spike/mock_hero_server.py   (serves :5999)
Then in the app's Hero modal setup card paste:
  Base URL:   http://127.0.0.1:5999/hero_render
  Region URL: http://127.0.0.1:5999/region_edit
  Secret:     test
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image

# Reuse the REAL prep_canny / prep_depth / mask / composite from modal_flux.py.
_spec = importlib.util.spec_from_file_location("modal_flux", "spike/modal_flux.py")
mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mf)

PORT = 5999


def _unb64(s: str) -> bytes:
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def hero_render(body: dict) -> dict:
    beauty = Image.open(io.BytesIO(_unb64(body["beauty"]))).convert("RGB")
    W, H = body.get("width") or beauty.width, body.get("height") or beauty.height
    beauty = beauty.resize((W, H))
    canny = mf.prep_canny(_unb64(body["beauty"]), _unb64(body["ids_rgb"])).resize((W, H))
    depth = mf.prep_depth(_unb64(body["depth"])).resize((W, H))

    # Burn the canny lines into a dimmed beauty (red) so alignment is obvious.
    out = (np.array(beauty).astype(float) * 0.55).astype(np.uint8)
    edge = np.array(canny) > 128
    out[edge] = [255, 40, 40]
    comp = Image.fromarray(out)
    # Depth inset, top-right quarter.
    inset = depth.convert("RGB").resize((W // 4, H // 4))
    comp.paste(inset, (W - W // 4 - 6, 6))
    return {"image": _b64(_png(comp)), "seed": int(body.get("seed", 0)), "ms": 1}


def region_edit(body: dict) -> dict:
    base = _unb64(body["base"])
    ids = mf._decode_ids(_unb64(body["ids_rgb"]))
    mask_png = _unb64(body["mask"]) if body.get("mask") else mf.mask_png_from_ids(ids, body.get("region_ids", []))
    # Tint the region green over the base (so the masked area is obvious + byte-stable elsewhere).
    base_img = Image.open(io.BytesIO(base)).convert("RGB")
    green = Image.new("RGB", base_img.size, (40, 220, 90))
    tinted = Image.blend(base_img, green, 0.5)
    edit = _png(tinted)
    final = mf.paste_tile(base, mask_png, edit)
    return {"image": _b64(final), "mask": _b64(mask_png), "seed": int(body.get("seed", 0)), "ms": 1}


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Hero-Secret")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if not body.get("secret"):
            self.send_response(401)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"detail": "bad secret"}).encode())
            return
        try:
            out = hero_render(body) if self.path.rstrip("/").endswith("hero_render") else region_edit(body)
            payload = json.dumps(out).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"detail": str(e)}).encode())

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    print(f"[mock] hero backend on http://127.0.0.1:{PORT}  (/hero_render, /region_edit)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
