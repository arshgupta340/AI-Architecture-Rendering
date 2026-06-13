r"""Capture -> canvas pipeline: one capture dir in, a ready web project out.

build_project(capture_dir) runs the full chain on a Rhino capture bundle
(beauty/depth/light_pass/id_mask/objects/camera written by spike/rhino_capture.py):

  1. host_probe_rhino.decode  -> instance_ids.png (+ semantic_decoded)
  2. run_e2b_registration.render_locked -> geometry-locked warm render (fal),
     saved as <capture_dir>/renders/base_render.png   [set render=False to reuse]
  3. prepare_data.write_web_project -> public/project/{base,ids_rgb,regions,swatches}

The server's POST /api/ingest calls this; the canvas auto-reloads on the new
base. Also runnable from the CLI for a capture dir on disk.

Usage:
  spike\.venv\Scripts\python.exe apps/canvas-prototype/ingest.py <capture_dir> [--no-render]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
SPIKE = REPO / "spike"
sys.path.insert(0, str(SPIKE))
sys.path.insert(0, str(HERE))

from host_probe_rhino import decode                  # noqa: E402
from run_e2b_registration import render_locked        # noqa: E402
from prepare_data import write_web_project, OUT       # noqa: E402

REQUIRED = ("beauty.png", "depth.png", "light_pass.png", "id_mask.png",
            "objects.json", "camera.json")


def build_project(capture_dir, render: bool = True, out_dir: Path = OUT) -> dict:
    """Decode a capture dir, lock-render it, and write the web project.

    Returns {size, n_regions, semantics, base_render, decode_pct, rendered}.
    """
    capture_dir = Path(capture_dir)
    missing = [f for f in REQUIRED if not (capture_dir / f).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{capture_dir} is not a capture bundle (missing: {', '.join(missing)})")

    stats = decode(capture_dir)                       # writes instance_ids.png

    # Guard: a healthy capture decodes ~90%+ of object pixels. A much lower
    # number means the white-reference pass came back dim/stale (seen on
    # long-idle or heavily-churned Rhino sessions) — the masks would be
    # garbage. Reject BEFORE the paid render and tell the user to recapture.
    pct = stats["decoded_pct_of_object_px"]
    if pct < 50:
        raise ValueError(
            f"capture decoded only {pct}% of object pixels — the Rhino "
            "white-reference pass looks stale (common after a long-running "
            "session). Reopen the model in Rhino and capture again.")

    renders = capture_dir / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    base_render = renders / "base_render.png"
    if render or not base_render.is_file():
        base_render.write_bytes(render_locked(capture_dir))
        rendered = True
    else:
        rendered = False

    info = write_web_project(capture_dir, base_render, out_dir)
    info["base_render"] = str(base_render)
    info["decode_pct"] = stats["decoded_pct_of_object_px"]
    info["rendered"] = rendered
    return info


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    render = "--no-render" not in args
    dirs = [a for a in args if not a.startswith("--")]
    if not dirs:
        sys.exit("usage: ingest.py <capture_dir> [--no-render]")
    try:
        from dotenv import load_dotenv
        load_dotenv(SPIKE / ".env")
    except ImportError:
        pass
    import json
    print(json.dumps(build_project(dirs[0], render=render), indent=1))
