r"""Download a curated CC0 PBR material library from ambientCG for the web-3D
configurator.

Expands the original 5-swatch set (spike/ingest_pbr_swatches.py) to ~28
architectural materials. Each set is pulled at 1K-JPG and unzipped into
apps/web3d-prototype/public/materials/<id>/ with the maps renamed to our slots:

    _Color           -> albedo.jpg
    _NormalGL        -> normal.jpg   (OpenGL normals == three.js convention)
    _Roughness       -> roughness.jpg
    _AmbientOcclusion-> ao.jpg

It also merges public/materials/materials.json so a selective re-run keeps prior
entries. Stdlib only (urllib + zipfile) — no pip deps. ambientCG assets are CC0
(public domain), free to redistribute.

Run all:        spike\.venv\Scripts\python.exe apps/web3d-prototype/scripts/fetch_materials.py
Run a subset:   ... fetch_materials.py red_brick travertine
One bad asset never aborts the rest (try/except per item).

The `tileFeet` here MUST match src/lib/swatches.ts. It is the real-world tile
size in feet at scale=1 on the box-projected (world-feet) UVs in Scene.tsx:
texture.repeat = 1 / (tileFeet * scale). Bigger tileFeet -> larger features.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ lives under apps/web3d-prototype/, so public/ is one level up.
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "materials"))
UA = {"User-Agent": "Mozilla/5.0 (web3d-mvp material ingest)"}

# Direct CC0 1K-JPG zip endpoint (verified this session): no API hop needed.
ZIP_URL = "https://ambientcg.com/get?file={aid}_1K-JPG.zip"

# ambientCG filename suffix -> our local map name.
MAPS = {
    "_Color.": "albedo.jpg",
    "_NormalGL.": "normal.jpg",
    "_Roughness.": "roughness.jpg",
    "_AmbientOcclusion.": "ao.jpg",
}

# id -> (ambientCG assetId, category, tags, tileFeet)
# tileFeet tuned per category to the verified ranges in the task brief:
#   brick ~2.5-3, stone veneer ~2-4, wood plank ~3-4, travertine/marble ~2-4,
#   stucco ~5-8, concrete panel ~6-10, paving ~1.5-3, grass ~3-6,
#   metal seam ~1.5-2.5, roofing/terracotta ~1-2, gravel ~3-5.
MATERIALS: dict[str, tuple[str, str, list[str], float]] = {
    # --- brick -----------------------------------------------------------
    "red_brick":        ("Bricks097", "brick", ["red", "wall", "masonry", "facade"], 3.0),
    "brown_brick":      ("Bricks045", "brick", ["brown", "wall", "masonry"], 3.0),
    "buff_brick":       ("Bricks066", "brick", ["buff", "tan", "wall", "masonry"], 2.75),
    "clinker_brick":    ("Bricks058", "brick", ["dark", "clinker", "wall", "masonry"], 2.75),
    # --- stone / stone veneer -------------------------------------------
    "stone_veneer":     ("Rock029", "stone", ["veneer", "wall", "natural", "gray"], 3.0),
    "ashlar_stone":     ("PavingStones131", "stone", ["ashlar", "wall", "cut", "gray"], 3.0),
    "limestone":        ("Marble016", "stone", ["limestone", "buff", "wall", "smooth"], 3.0),
    "fieldstone":       ("Rock023", "stone", ["fieldstone", "rubble", "wall", "natural"], 4.0),
    # --- concrete --------------------------------------------------------
    "smooth_concrete":  ("Concrete034", "concrete", ["smooth", "wall", "panel", "gray"], 8.0),
    "board_concrete":   ("Concrete032", "concrete", ["board-formed", "wall", "texture"], 7.0),
    "rough_concrete":   ("Concrete016", "concrete", ["rough", "wall", "raw", "gray"], 8.0),
    # --- plaster / stucco -----------------------------------------------
    "white_stucco":     ("Plaster001", "plaster", ["white", "stucco", "wall", "smooth"], 6.0),
    "tan_stucco":       ("Plaster003", "plaster", ["tan", "stucco", "wall"], 6.0),
    # --- wood ------------------------------------------------------------
    "weathered_cedar":  ("WoodSiding009", "wood", ["cedar", "siding", "plank", "gray"], 3.5),
    "wood_planks":      ("WoodFloor043", "wood", ["plank", "floor", "deck", "warm"], 3.5),
    "wood_siding":      ("WoodSiding007", "wood", ["siding", "plank", "painted", "wall"], 3.5),
    # --- travertine / marble --------------------------------------------
    "travertine":       ("Travertine009", "stone", ["travertine", "buff", "floor", "wall"], 4.0),
    "white_marble":     ("Marble006", "stone", ["marble", "white", "floor", "polished"], 4.0),
    "gray_marble":      ("Marble012", "stone", ["marble", "gray", "floor", "veined"], 4.0),
    # --- paving ----------------------------------------------------------
    "paving_stones":    ("PavingStones070", "paving", ["paver", "ground", "patio", "gray"], 2.5),
    "cobblestone":      ("PavingStones128", "paving", ["cobble", "ground", "round", "old"], 2.0),
    "brick_paving":     ("PavingStones126A", "paving", ["brick", "ground", "herringbone"], 2.0),
    # --- metal -----------------------------------------------------------
    "charcoal_seam":    ("CorrugatedSteel009", "metal", ["seam", "panel", "dark", "roof"], 2.5),
    "corten_steel":     ("Metal041B", "metal", ["corten", "weathered", "rust", "panel"], 2.5),
    "brushed_metal":    ("Metal032", "metal", ["brushed", "panel", "silver", "cladding"], 2.0),
    # --- roofing / terracotta -------------------------------------------
    "roof_tiles":       ("RoofingTiles013A", "roofing", ["tile", "roof", "terracotta"], 1.5),
    "terracotta":       ("Tiles101", "roofing", ["terracotta", "clay", "roof", "warm"], 1.5),
    # --- ground / landscape ---------------------------------------------
    "grass":            ("Grass004", "ground", ["grass", "lawn", "landscape", "green"], 5.0),
    "gravel":           ("Gravel022", "ground", ["gravel", "ground", "path", "loose"], 4.0),
}


def _get(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ingest() -> dict:
    os.makedirs(OUT, exist_ok=True)
    mpath = os.path.join(OUT, "materials.json")
    manifest: dict[str, dict] = json.loads(open(mpath).read()) if os.path.exists(mpath) else {}

    only = set(sys.argv[1:])
    items = [(k, v) for k, v in MATERIALS.items() if not only or k in only]
    ok, failed = 0, 0
    for sid, (aid, category, tags, tile_feet) in items:
        try:
            url = ZIP_URL.format(aid=aid)
            print(f"[{sid}] {aid}  ({category})  <- {url}")
            blob = _get(url, 180)
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
                            with z.open(name) as f, open(os.path.join(dest, out), "wb") as o:
                                o.write(f.read())
                            got[out] = name
            if "albedo.jpg" not in got:
                raise RuntimeError(f"no _Color map in zip (got {sorted(got)})")
            manifest[sid] = {
                "assetId": aid,
                "category": category,
                "tags": tags,
                "tileFeet": tile_feet,
                "maps": sorted(got.keys()),
            }
            print(f"    -> {sorted(got.keys())}")
            ok += 1
        except Exception as e:  # noqa: BLE001 — one bad asset shouldn't abort the rest
            print(f"[{sid}] FAILED: {e}")
            failed += 1

    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n{ok} ok, {failed} failed.  manifest has {len(manifest)} entries -> {mpath}")
    return manifest


if __name__ == "__main__":
    ingest()
