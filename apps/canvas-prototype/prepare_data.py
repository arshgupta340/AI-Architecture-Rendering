r"""Convert spike/outputs/e2_house ground-truth data to web format.

Run with: spike\.venv\Scripts\python.exe apps/canvas-prototype/prepare_data.py

Outputs under apps/canvas-prototype/public/project/:
  base.png       — the flux_depth render (canvas base image, 1504x656)
  ids_rgb.png    — instance ids packed into RGB so an HTML canvas can read
                   them losslessly: r = id & 255, g = (id >> 8) & 255, b = 0.
                   Resized to base.png size with NEAREST (source is 1514x659).
  regions.json   — {"regions": {id: {semantic, layer, name, guid}},
                    "semantics": {semantic: {label, color}}}
  swatches/      — travertine.jpeg (real asset) + procedural placeholder tiles
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
REPO = HERE.parent.parent
# e2_house_v2: re-captured at native 1504x656 + depth+canny render (E2b) so the
# ground-truth masks register pixel-for-pixel with the displayed base image.
SRC = REPO / "spike" / "outputs" / "e2_house_v2"
BASE_RENDER = SRC / "renders" / "base_render.png"   # depth+canny union, aligned
OUT = HERE / "public" / "project"

SEMANTIC_META = {
    "wall":          {"label": "Wall",            "color": "#dc503c"},
    "wall_interior": {"label": "Interior Wall",   "color": "#b06050"},
    "window":        {"label": "Window",          "color": "#50a0e6"},
    "door":          {"label": "Door",            "color": "#963cc8"},
    "roof":          {"label": "Roof",            "color": "#c89632"},
    "trim":          {"label": "Trim",            "color": "#fadc3c"},
    "stair":         {"label": "Stair",           "color": "#f08c28"},
    "floor":         {"label": "Floor",           "color": "#787878"},
    "foundation":    {"label": "Foundation",      "color": "#8c6450"},
    "ground":        {"label": "Ground",          "color": "#508c3c"},
    "paving":        {"label": "Paving",          "color": "#a0a0a0"},
    "other":         {"label": "Other",           "color": "#c8c8c8"},
}


def make_swatches(dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    # Real asset
    shutil.copy(REPO / "spike" / "test_assets" / "travertine.jpeg",
                dst / "travertine.jpeg")

    rng = np.random.default_rng(7)
    S = 512

    # --- red brick courses (procedural placeholder) ---
    img = Image.new("RGB", (S, S), (150, 60, 45))
    d = ImageDraw.Draw(img)
    bh, bw, mortar = 32, 96, 5
    for row, y in enumerate(range(0, S, bh)):
        off = (bw // 2) if row % 2 else 0
        for x in range(-bw, S + bw, bw):
            c = (int(rng.normal(152, 12)), int(rng.normal(62, 8)), int(rng.normal(46, 7)))
            d.rectangle([x + off, y, x + off + bw - mortar, y + bh - mortar],
                        fill=tuple(np.clip(c, 0, 255)))
    arr = np.array(img).astype(np.int16) + rng.integers(-8, 9, (S, S, 1))
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(dst / "red_brick.png")

    # --- charcoal standing-seam metal (procedural placeholder) ---
    arr = np.full((S, S, 3), 52, np.uint8)
    grad = (np.sin(np.linspace(0, 24, S)) * 6).astype(np.int16)[None, :, None]
    arr = np.clip(arr.astype(np.int16) + grad + rng.integers(-3, 4, (S, S, 1)), 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    for x in range(0, S, 64):
        d.line([(x, 0), (x, S)], fill=(28, 28, 30), width=3)
        d.line([(x + 3, 0), (x + 3, S)], fill=(86, 88, 92), width=2)
    img.save(dst / "charcoal_seam.png")

    # --- white stucco noise (procedural placeholder) ---
    base = np.full((S, S, 3), 232, np.float32)
    noise = rng.normal(0, 9, (S, S, 1)).astype(np.float32)
    coarse = rng.normal(0, 7, (S // 8, S // 8, 1)).astype(np.float32)
    coarse = np.array(Image.fromarray((coarse[:, :, 0] + 128).clip(0, 255).astype(np.uint8))
                      .resize((S, S), Image.BILINEAR), np.float32)[:, :, None] - 128
    arr = np.clip(base + noise + coarse * 0.8, 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(dst / "white_stucco.png")

    # --- weathered cedar boards (procedural placeholder) ---
    img = Image.new("RGB", (S, S), (120, 100, 82))
    d = ImageDraw.Draw(img)
    bw = 64
    for x in range(0, S, bw):
        c = (int(rng.normal(122, 10)), int(rng.normal(102, 8)), int(rng.normal(84, 7)))
        d.rectangle([x, 0, x + bw - 3, S], fill=tuple(np.clip(c, 0, 255)))
    arr = np.array(img).astype(np.int16)
    streaks = (np.sin(np.linspace(0, 60, S))[:, None, None] * 4).astype(np.int16)
    arr = np.clip(arr + streaks + rng.integers(-6, 7, (S, S, 1)), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(dst / "weathered_cedar.png")


def write_web_project(src_dir: Path, base_render: Path, out_dir: Path = OUT) -> dict:
    """Convert a decoded capture dir + its locked render into the web project.

    src_dir       a capture dir holding instance_ids.png + objects.json
                  (run host_probe_rhino.decode on it first)
    base_render   the geometry-locked render to show as the canvas base
    Reusable by both the CLI (main) and the capture→canvas pipeline (ingest.py).
    """
    src_dir, base_render, out_dir = Path(src_dir), Path(base_render), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear cached layers — their hash key is content-independent, so a data
    # refresh must invalidate them or the server serves layers from the old base.
    layers = out_dir / "layers"
    if layers.exists():
        for p in layers.glob("*.png"):
            p.unlink()

    # 1) base.png — the depth+canny render (aligned to the masks)
    base = Image.open(base_render).convert("RGB")
    base.save(out_dir / "base.png")
    W, H = base.size

    # 2) ids_rgb.png — pack uint16 ids into RGB. Capture grid == render grid,
    # so the resize is a no-op (kept defensively for mismatched inputs).
    inst = np.array(Image.open(src_dir / "instance_ids.png"))
    inst_img = Image.fromarray(inst).resize((W, H), Image.NEAREST)
    inst_r = np.array(inst_img, dtype=np.uint16)
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[:, :, 0] = inst_r & 255
    rgb[:, :, 1] = (inst_r >> 8) & 255
    Image.fromarray(rgb).save(out_dir / "ids_rgb.png")

    # 3) regions.json — instance id i ↔ (i-1)-th key of objects dict
    table = json.loads((src_dir / "objects.json").read_text())["objects"]
    keys = list(table)
    present = set(int(v) for v in np.unique(inst_r) if v != 0)
    regions = {}
    for i in sorted(present):
        rec = table[keys[i - 1]]
        regions[str(i)] = {
            "semantic": rec["semantic"], "layer": rec["layer"],
            "name": rec["name"], "guid": rec["guid"],
        }
    semantics = {s: SEMANTIC_META.get(s, {"label": s.title(), "color": "#c8c8c8"})
                 for s in sorted({r["semantic"] for r in regions.values()})}
    (out_dir / "regions.json").write_text(json.dumps(
        {"size": [W, H], "regions": regions, "semantics": semantics}, indent=1))

    # 4) swatches
    make_swatches(out_dir / "swatches")
    return {"size": [W, H], "n_regions": len(regions), "semantics": list(semantics)}


def main() -> None:
    info = write_web_project(SRC, BASE_RENDER, OUT)
    print(f"base.png {info['size'][0]}x{info['size'][1]}; {info['n_regions']} regions; "
          f"semantics: {', '.join(info['semantics'])}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
