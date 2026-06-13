"""Tiny stdlib HTTP receiver for validating the Send-to-Canvas component.

Stands in for apps/canvas-prototype/server.py during validation so we do NOT
depend on the real server (which another agent is actively editing) and avoid
the ~5-min / paid locked render. It accepts ``POST /api/ingest``, echoes the
received JSON back (plus a synthetic decode_pct/n_regions/rendered shape that
matches the real server's response contract), and logs each payload to stdout
so the test can assert the POST was well-formed.

Run:
    spike\\.venv\\Scripts\\python.exe spike/grasshopper/mock_ingest_server.py --port 8770

Stdlib only — no project deps — so it starts instantly and never imports the
canvas app.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 (stdlib API name)
        if self.path != "/api/ingest":
            self._json(404, {"error": "not found", "path": self.path})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode() or "{}")
        except Exception as e:  # noqa: BLE001
            self._json(400, {"error": "bad json: %s" % e})
            return

        # Log the received payload (the test scrapes stdout for proof).
        print("RECEIVED /api/ingest:", json.dumps(payload), flush=True)

        # Echo a response shaped like the real server's so the component's
        # decode_pct / n_regions parsing exercises the real code path.
        self._json(200, {
            "ok": True,
            "echo": payload,
            "capture_dir": payload.get("capture_dir"),
            "render": payload.get("render"),
            # Synthetic but realistically-shaped fields (mock does not decode).
            "size": [1504, 656],
            "n_regions": 0,
            "semantics": {},
            "decode_pct": None,
            "rendered": False,
            "version": 0,
            "elapsed_s": 0.0,
            "note": "mock receiver — no decode/render performed",
        })

    def log_message(self, fmt, *args):  # silence default per-request noise
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), _Handler)
    print("mock ingest receiver listening on http://%s:%d/api/ingest"
          % (args.host, args.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
