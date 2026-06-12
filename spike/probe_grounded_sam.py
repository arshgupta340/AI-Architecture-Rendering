"""E5 — discriminative tier-2 tagging probe: text-grounded detection + SAM masks.

Runs an open-vocabulary detection→segmentation stack on E1's beauty.png via
Replicate and scores per-class IoU against the E1 host ground truth — the same
scoring as E4 (probe_vision_banana.py), so the generative and discriminative
fallback candidates and the plugin tier are directly comparable.

Stack: Grounding-DINO (text → boxes) then SAM-2 (boxes → masks), both hosted
on Replicate (REPLICATE_API_TOKEN from spike/.env). SAM 3 isn't a first-class
Replicate endpoint yet; treat this as the floor of the discriminative approach.

Usage:
  spike\\.venv\\Scripts\\python.exe spike/probe_grounded_sam.py --live
  spike\\.venv\\Scripts\\python.exe spike/probe_grounded_sam.py --score
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image

SPIKE = Path(__file__).parent
E1 = SPIKE / "outputs" / "e1_rhino_probe"
OUT = SPIKE / "outputs" / "e5_grounded_sam"
BASE = "https://api.replicate.com/v1"

# class -> text queries fed to the detector
QUERIES = {
    "wall": "building wall facade",
    "window_glass": "window glass pane",
    "mullion": "window mullion frame grid",
    "door": "door",
}


def _headers():
    from dotenv import load_dotenv
    load_dotenv(SPIKE / ".env")
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not set")
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


_VERSION_CACHE: dict = {}


def _version_of(headers, owner_name: str) -> str:
    if owner_name not in _VERSION_CACHE:
        r = requests.get(f"{BASE}/models/{owner_name}", headers=headers, timeout=30)
        r.raise_for_status()
        _VERSION_CACHE[owner_name] = r.json()["latest_version"]["id"]
    return _VERSION_CACHE[owner_name]


def _run_model(headers, owner_name: str, input_: dict, timeout_s: int = 300):
    # community models 404 on the model-path endpoint; use version-pinned predictions
    for attempt in range(8):
        r = requests.post(f"{BASE}/predictions", headers=headers,
                          json={"version": _version_of(headers, owner_name), "input": input_},
                          timeout=60)
        if r.status_code == 429:
            wait = min(2 ** attempt * 2, 30)
            print(f"  (429 rate-limited, retrying in {wait}s)")
            time.sleep(wait)
            continue
        break
    r.raise_for_status()
    body = r.json()
    poll = (body.get("urls") or {}).get("get") or f"{BASE}/predictions/{body['id']}"
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        resp = requests.get(poll, headers=headers, timeout=30).json()
        if resp["status"] == "succeeded":
            return resp["output"]
        if resp["status"] in ("failed", "canceled"):
            raise RuntimeError(f"{owner_name} failed: {resp.get('error')}")
        time.sleep(2)
    raise RuntimeError(f"{owner_name} poll timeout")


def _data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def run_live():
    headers = _headers()
    OUT.mkdir(parents=True, exist_ok=True)
    img_url = _data_url(E1 / "beauty.png")
    W, H = Image.open(E1 / "beauty.png").size

    # grounded_sam: text -> mask directly (Grounding DINO + SAM fused)
    union = {}
    NEGATIVES = {
        "wall": "window, glass, sky, ground, road",
        "window_glass": "wall, mullion, sky, ground",
        "mullion": "glass pane, wall, sky",
        "door": "window, wall",
    }
    for cls, query in QUERIES.items():
        print(f"[grounded_sam] {cls!r} <- {query!r}")
        try:
            out = _run_model(headers, "schananas/grounded_sam", {
                "image": img_url,
                "mask_prompt": query,
                "negative_mask_prompt": NEGATIVES.get(cls, ""),
                "adjustment_factor": 0,
            })
        except RuntimeError as e:
            print(f"  -> FAILED: {e}")
            continue
        urls = [str(u) for u in (out if isinstance(out, list) else [out])]
        # outputs: annotated_picture_mask, neg_annotated_picture_mask, mask, inverted_mask
        positives = [u for u in urls if u.endswith("/mask.jpg") or "/mask." in u.rsplit("/", 1)[-1]]
        url = positives[0] if positives else urls[-1]
        m = np.array(Image.open(requests.get(url, stream=True, timeout=60).raw).convert("L"))
        if m.shape != (H, W):
            m = np.array(Image.fromarray(m).resize((W, H), Image.NEAREST))
        mask = m > 127
        union[cls] = mask
        Image.fromarray((mask * 255).astype(np.uint8)).save(OUT / f"mask_{cls}.png")
        print(f"  -> mask_{cls}.png ({int(mask.sum()):,} px)")
    return union


def score():
    gt_inst = np.array(Image.open(E1 / "instance_ids.png"))
    table = json.loads((E1 / "objects.json").read_text())["objects"]
    keys = list(table)
    results = {}
    for cls in QUERIES:
        p = OUT / f"mask_{cls}.png"
        if not p.exists():
            results[cls] = None
            continue
        pred = np.array(Image.open(p).convert("L")) > 127
        gt = np.zeros_like(pred)
        for i, k in enumerate(keys):
            if table[k]["semantic"] == cls:
                gt |= gt_inst == (i + 1)
        inter, uni = int((gt & pred).sum()), int((gt | pred).sum())
        results[cls] = {
            "gt_px": int(gt.sum()), "pred_px": int(pred.sum()),
            "iou": round(inter / uni, 3) if uni else None,
            "recall": round(inter / gt.sum(), 3) if gt.sum() else None,
        }
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()
    if args.live:
        run_live()
    if args.live or args.score:
        print(json.dumps(score(), indent=1))
    if not (args.live or args.score):
        print(__doc__)
