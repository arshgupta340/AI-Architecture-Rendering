"""E4 — Vision-Banana-style segmentation probe on public Nano Banana Pro.

Vision Banana (DeepMind, arXiv 2604.20329) is Nano Banana Pro instruction-tuned to
emit color-coded segmentation maps as generated images. The tuned model is not
public, but Veras v4.5 ships on it. This probe measures how close PROMPTING the
public base model (`nano-banana-pro-preview`) gets — scored with real IoU against
the E1 ground-truth masks extracted from the host (same frame, same pixels).

Usage:
  spike\\.venv\\Scripts\\python.exe spike/probe_vision_banana.py --live   # ~$0.13-0.24/call
  spike\\.venv\\Scripts\\python.exe spike/probe_vision_banana.py --score  # decode + IoU only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

SPIKE = Path(__file__).parent
E1 = SPIKE / "outputs" / "e1_rhino_probe"
OUT = SPIKE / "outputs" / "e4_vision_banana"

MODEL = "nano-banana-pro-preview"

# Class palette the model is asked to paint. Chosen for maximal RGB separation.
CLASSES = {
    "wall": (255, 0, 0),
    "window_glass": (0, 0, 255),
    "mullion": (255, 255, 0),
    "door": (255, 0, 255),
    "context": (0, 255, 255),       # surrounding context buildings
    "ground": (0, 255, 0),
    "background": (0, 0, 0),        # sky / empty
}

PROMPT = """You are a precise semantic segmentation engine for architecture.
Repaint the attached 3D-model viewport screenshot as a flat color-coded
segmentation map with EXACTLY the same dimensions, camera, and pixel alignment.
Every pixel must be one of these pure flat colors (no shading, no gradients,
no lighting, no texture, no outlines):

- exterior wall surfaces of the project buildings: pure red (255,0,0)
- glass / glazing / window panes: pure blue (0,0,255)
- mullions, window frames, glazing bars (the thin members subdividing glass):
  pure yellow (255,255,0)
- doors: pure magenta (255,0,255)
- surrounding context buildings (the plain massing blocks around the site):
  pure cyan (0,255,255)
- ground plane, roads, terrain: pure green (0,255,0)
- sky / empty background: pure black (0,0,0)

Preserve the exact silhouette of every element. Do not invent, move, or omit
any geometry. Thin elements like mullions must be painted individually even if
only 2-3 pixels wide. Output only the segmentation image."""


def run_live() -> Path:
    from dotenv import load_dotenv
    load_dotenv(SPIKE / ".env")
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    from google import genai
    from google.genai import types

    OUT.mkdir(parents=True, exist_ok=True)
    src = (E1 / "beauty.png").read_bytes()
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=src, mime_type="image/png"),
            PROMPT,
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    img_bytes = None
    for part in resp.candidates[0].content.parts:
        if part.inline_data is not None:
            img_bytes = part.inline_data.data
            break
    if img_bytes is None:
        raise RuntimeError(f"no image in response: {resp}")
    p = OUT / "nb_segmentation.png"
    p.write_bytes(img_bytes)
    print(f"saved {p} ({len(img_bytes):,} bytes)")
    return p


def score() -> dict:
    """Nearest-palette decode of the model output, IoU vs E1 ground truth."""
    seg = Image.open(OUT / "nb_segmentation.png").convert("RGB")
    gt_inst = np.array(Image.open(E1 / "instance_ids.png"))
    table = json.loads((E1 / "objects.json").read_text())["objects"]
    keys = list(table)
    H, W = gt_inst.shape
    if seg.size != (W, H):
        print(f"resizing model output {seg.size} -> {(W, H)}")
        seg = seg.resize((W, H), Image.NEAREST)
    a = np.array(seg).astype(int)

    # nearest palette color per pixel
    pal_names = list(CLASSES)
    pal = np.array([CLASSES[n] for n in pal_names])
    d = ((a[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(axis=3)
    pred = d.argmin(axis=2)  # index into pal_names

    # ground-truth semantic map (instance ids -> semantic)
    sem_of_idx = {}
    for i, k in enumerate(keys):
        s = table[k]["semantic"]
        sem_of_idx[i + 1] = s if s in CLASSES else None
    gt = np.full((H, W), -1)
    for idx, s in sem_of_idx.items():
        if s is not None:
            gt[gt_inst == idx] = pal_names.index(s)

    results = {}
    for ci, name in enumerate(pal_names):
        if name in ("background", "ground", "context"):
            continue  # no reliable ground truth for these
        gt_m = gt == ci
        pr_m = pred == ci
        inter = int((gt_m & pr_m).sum())
        union = int((gt_m | pr_m).sum())
        results[name] = {
            "gt_px": int(gt_m.sum()),
            "pred_px": int(pr_m.sum()),
            "iou": round(inter / union, 3) if union else None,
            "recall": round(inter / gt_m.sum(), 3) if gt_m.sum() else None,
        }

    # side-by-side: ground truth semantic vs prediction
    vis = np.zeros((H, W * 2 + 10, 3), np.uint8)
    gt_vis = np.zeros((H, W, 3), np.uint8)
    for idx, s in sem_of_idx.items():
        if s is not None:
            gt_vis[gt_inst == idx] = CLASSES[s]
    vis[:, :W] = gt_vis
    vis[:, W + 10:] = pal[pred]
    Image.fromarray(vis).save(OUT / "e4_gt_vs_pred_comparison.png")
    print("e4_gt_vs_pred_comparison.png saved")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()
    if args.live:
        run_live()
    if args.score or args.live:
        print(json.dumps(score(), indent=1))
    if not (args.live or args.score):
        print(__doc__)
