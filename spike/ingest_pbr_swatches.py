r"""Download CC0 PBR material sets from ambientCG for the web-3D configurator.

Pulls ~5 material sets (albedo / normalGL / roughness / ao) at 1K-JPG into
apps/web3d-prototype/public/materials/<swatch>/ and writes materials.json with a
per-swatch UV `repeat`. Stdlib only (urllib + zipfile) — no pip deps. ambientCG
assets are CC0 (public domain), free to redistribute.

Run: spike\.venv\Scripts\python.exe spike/ingest_pbr_swatches.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "apps", "web3d-prototype", "public", "materials"))
API = "https://ambientcg.com/api/v2/full_json?type=Material&include=downloadData&limit=1&q="
UA = {"User-Agent": "web3d-mvp-ingest"}

# swatch id -> (ambientCG search query, default UV repeat tuned by eye for the house)
SWATCHES = {
    "travertine": ("travertine", 4),
    "red_brick": ("red brick wall", 14),
    "white_stucco": ("white plaster", 6),
    "weathered_cedar": ("wood plank siding", 10),
    "charcoal_seam": ("corrugated steel", 8),
}

# ambientCG filename suffix -> our local map name (NormalGL = OpenGL normals = three.js)
MAPS = {
    "_Color.": "albedo.jpg",
    "_NormalGL.": "normal.jpg",
    "_Roughness.": "roughness.jpg",
    "_AmbientOcclusion.": "ao.jpg",
}


def _get(url: str, timeout: int) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _zip_link(asset: dict) -> tuple[str, str]:
    cats = asset["downloadFolders"]["default"]["downloadFiletypeCategories"]
    downloads = cats["zip"]["downloads"]
    for dl in downloads:
        if "1K-JPG" in (dl.get("attribute") or ""):
            return dl["downloadLink"], dl.get("fileName", "")
    return downloads[0]["downloadLink"], downloads[0].get("fileName", "")


def ingest() -> dict:
    os.makedirs(OUT, exist_ok=True)
    # Merge into any existing manifest so a selective re-run keeps prior entries.
    mpath = os.path.join(OUT, "materials.json")
    manifest: dict[str, dict] = json.loads(open(mpath).read()) if os.path.exists(mpath) else {}
    only = set(sys.argv[1:])
    items = [(k, v) for k, v in SWATCHES.items() if not only or k in only]
    for sid, (query, repeat) in items:
        try:
            data = json.loads(_get(API + urllib.parse.quote(query), 30).decode())
            assets = data.get("foundAssets", [])
            if not assets:
                print(f"[{sid}] no asset for query '{query}'")
                continue
            asset = assets[0]
            aid = asset.get("assetId", "?")
            link, fname = _zip_link(asset)
            print(f"[{sid}] {aid}  <- '{query}'  ({fname})")
            blob = _get(link, 120)
            dest = os.path.join(OUT, sid)
            os.makedirs(dest, exist_ok=True)
            got: dict[str, str] = {}
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                for name in z.namelist():
                    low = name.lower()
                    if not low.endswith((".jpg", ".jpeg", ".png")):
                        continue
                    for suffix, out in MAPS.items():
                        if suffix in name:
                            with z.open(name) as f:
                                with open(os.path.join(dest, out), "wb") as o:
                                    o.write(f.read())
                            got[out] = name
            manifest[sid] = {"assetId": aid, "repeat": repeat, "maps": sorted(got.keys())}
            print(f"    -> {sorted(got.keys())}")
        except Exception as e:  # noqa: BLE001 — one bad asset shouldn't abort the rest
            print(f"[{sid}] FAILED: {e}")
    with open(os.path.join(OUT, "materials.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("\nmaterials.json:")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    ingest()
