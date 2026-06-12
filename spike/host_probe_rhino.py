"""E1 — Rhino native-extraction probe: decode + validate host-exported passes.

The Rhino-side capture runs INSIDE Rhino (via the Rhino MCP `run_python`, or later a
plugin/Grasshopper component). It produces, under spike/outputs/e1_rhino_probe/:

  beauty.png      shaded viewport capture (the product's render input)
  depth.png       true z-buffer via Rhino.Display.ZBufferCapture (GrayscaleDib)
  light_pass.png  all objects pure white, flat unlit-ish display mode
  id_mask.png     all objects flat ID colors: r=0, g=5*(i//52), b=5*(i%52)
  objects.json    {"g,b" -> {guid, layer, semantic, object_type, material, name}}
  camera.json     camera location/target/up, 35mm lens, frustum, capture size

KEY EMPIRICAL FINDINGS (Rhino 8, custom display mode copied from Shaded with
LightingScheme=None, edges/curves/shadows off, DisableTransparency=True):

1. "LightingScheme None" is NOT unlit. The pipeline renders
       out_ch = 0.7 * in_ch + base_ch(pixel)
   where the 0.7 slope is constant everywhere but base_ch varies per pixel AND
   per channel with surface orientation (camera headlight + ambient).
2. Therefore a single ID pass cannot be decoded by exact color match.
   The fix is a WHITE REFERENCE PASS: with in=255 on every object,
       white_ch = 0.7*255 + base_ch  =>  base_ch = white_ch - 178.5
   which makes the ID decode exact and self-calibrating per pixel/channel:
       in_ch = (id_ch - base_ch) / 0.7
3. All passes must be captured ATOMICALLY (one script, no camera/viewport
   changes in between) — the viewport can resize between MCP calls.
4. Disable grid/axes (vp.ConstructionGridVisible etc.) or they pollute pixels.
5. CaptureToBitmap(size, displayMode) does not reliably honor updated display
   mode attributes; set vp.DisplayMode = mode and capture without the arg.
6. Anti-aliased edge pixels (~7% of object pixels at 1515px width) fail the
   residual check and stay unassigned — correct behavior; they are boundary
   pixels, not misassignments.

Measured on `SFUrban Rhino model for claude.3dm` (2026-06-12):
  93.1% of object pixels decoded exactly; 685 distinct objects in frame;
  257 individual mullion instances with pixel-accurate masks at 2-4px width.

Usage (venv):
  spike\\.venv\\Scripts\\python.exe spike/host_probe_rhino.py decode
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).parent / "outputs" / "e1_rhino_probe"
SLOPE = 0.7
WHITE_LEVEL = SLOPE * 255  # 178.5
GRID = 5                   # g/b channel spacing of ID colors
BG = np.array([157.0, 163.0, 170.0])  # default Rhino viewport gray

SEMANTIC_PALETTE = {
    "wall": (220, 80, 60), "window_glass": (80, 160, 230), "mullion": (250, 220, 60),
    "door": (150, 60, 200), "floorplate": (120, 120, 120), "pergola": (80, 200, 120),
    "seating": (240, 140, 40), "context": (70, 70, 90), "massing": (140, 100, 80),
    "other": (200, 200, 200), "vegetation": (40, 140, 60),
    # CSI-ruleset semantics (rhino_capture.py)
    "window": (80, 160, 230), "roof": (90, 60, 40), "trim": (250, 250, 200),
    "ground": (60, 110, 50), "paving": (110, 110, 100), "stair": (200, 120, 200),
    "foundation": (100, 100, 130), "floor": (160, 130, 90),
    "wall_interior": (240, 170, 150),
}


def decode(out_dir: Path = OUT, tol: float = 1.7) -> dict:
    """Decode id_mask.png against objects.json using the white reference pass.

    Returns summary stats; writes semantic_decoded.png and instance_ids.png.
    """
    idm = np.array(Image.open(out_dir / "id_mask.png").convert("RGB")).astype(float)
    lit = np.array(Image.open(out_dir / "light_pass.png").convert("RGB")).astype(float)
    data = json.loads((out_dir / "objects.json").read_text())
    table = data["objects"]
    h, w, _ = idm.shape

    fg = np.abs(lit - BG).max(axis=2) > 6
    base = lit - WHITE_LEVEL
    inn = (idm - base) / SLOPE
    r_in, g_in, b_in = inn[:, :, 0], inn[:, :, 1], inn[:, :, 2]
    g_s = np.clip(np.round(g_in / GRID) * GRID, 0, 255)
    b_s = np.clip(np.round(b_in / GRID) * GRID, 0, 255)

    # r-plane extension (rhino_capture.py): captures with >2704 objects use
    # r = 5*(i//2704) and keys "r,g,b" for r>0 ("g,b" stays the r==0 form).
    has_r_planes = any(k.count(",") == 2 for k in table)
    if has_r_planes:
        r_s = np.clip(np.round(r_in / GRID) * GRID, 0, 255)
        ok = (fg & (np.abs(r_in - r_s) < 2.5)
              & (np.abs(g_in - g_s) < tol) & (np.abs(b_in - b_s) < tol))
    else:
        r_s = np.zeros_like(r_in)
        ok = (fg & (np.abs(r_in) < 4)
              & (np.abs(g_in - g_s) < tol) & (np.abs(b_in - b_s) < tol))

    def to_key(key_n: int) -> str:
        r, g, b = key_n // 1_000_000, (key_n // 1000) % 1000, key_n % 1000
        return f"{g},{b}" if r == 0 else f"{r},{g},{b}"

    sem_px: collections.Counter = collections.Counter()
    obj_px: collections.Counter = collections.Counter()
    code = (r_s * 1_000_000 + g_s * 1000 + b_s).astype(int)
    keys, counts = np.unique(code[ok], return_counts=True)
    matched = 0
    for key_n, n in zip(keys, counts):
        key = to_key(key_n)
        if key in table:
            sem_px[table[key]["semantic"]] += int(n)
            obj_px[key] = int(n)
            matched += int(n)

    vis = np.zeros((h, w, 3), np.uint8)
    inst = np.zeros((h, w), np.uint16)
    key_to_idx = {k: i + 1 for i, k in enumerate(table)}
    for key_n in keys:
        key = to_key(key_n)
        if key in table:
            m = ok & (code == key_n)
            vis[m] = SEMANTIC_PALETTE.get(table[key]["semantic"], (255, 255, 255))
            inst[m] = key_to_idx[key]
    Image.fromarray(vis).save(out_dir / "semantic_decoded.png")
    Image.fromarray(inst).save(out_dir / "instance_ids.png")

    fgn = int(fg.sum())
    stats = {
        "frame": [w, h],
        "object_px": fgn,
        "decoded_px": matched,
        "decoded_pct_of_object_px": round(100 * matched / max(fgn, 1), 1),
        "distinct_objects_in_frame": len(obj_px),
        "objects_in_table": len(table),
        "px_per_semantic": dict(sem_px.most_common()),
        "mullion_instances_with_px": sum(
            1 for k in obj_px if table[k]["semantic"] == "mullion"
        ),
    }
    return stats


def mask_for(out_dir: Path, predicate) -> np.ndarray:
    """Boolean mask of pixels whose decoded object satisfies `predicate(record)`.

    Example: mask_for(OUT, lambda rec: rec["semantic"] == "wall")
    """
    inst = np.array(Image.open(out_dir / "instance_ids.png"))
    table = json.loads((out_dir / "objects.json").read_text())["objects"]
    keys = list(table)
    wanted = {i + 1 for i, k in enumerate(keys) if predicate(table[k])}
    return np.isin(inst, list(wanted))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "decode":
        print(json.dumps(decode(), indent=1))
    else:
        print(__doc__)
