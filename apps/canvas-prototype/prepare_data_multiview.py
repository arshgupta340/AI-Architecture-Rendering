r"""Build a MULTI-VIEW canvas project from two capture dirs (Part B data step).

"One swatch -> all views": the canvas holds N views of the SAME building and a
material applied to a semantic propagates across them with the locked consistency
proven in spike/run_multiview_lock_v2.py.

This writes, under apps/canvas-prototype/public/project/:

  views.json                         manifest: {anchor, views:[{id,label,...}]}
  views/<id>/base.png                the view's locked render (canvas base)
  views/<id>/ids_rgb.png             per-pixel instance ids packed into RGB
  views/<id>/regions.json            {size, regions, semantics}

It reuses prepare_data.write_web_project (the exact single-view writer) per view,
so each view's data contract is identical to the existing single-project one.

It ALSO mirrors the ANCHOR view into the top-level public/project/{base,ids_rgb,
regions,swatches} so the existing single-view flow — /api/apply_material,
/api/version, the default prepare_data layout, verify_api.py — keeps working
unchanged. Multi-view is purely additive.

Default views (the two captures the brief points at):
  hero  = spike/outputs/e2_house_v2/   (ANCHOR — hero/SW, golden-hour)
  front = spike/outputs/mv_front/

Run: spike\.venv\Scripts\python.exe apps/canvas-prototype/prepare_data_multiview.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
SPIKE = REPO / "spike"
OUT = HERE / "public" / "project"
VIEWS_DIR = OUT / "views"

import sys
sys.path.insert(0, str(HERE))
from prepare_data import write_web_project, make_swatches    # noqa: E402

# id -> (capture dir, human label, is_anchor). Order = tab order in the UI.
DEFAULT_VIEWS = [
    ("hero",  SPIKE / "outputs" / "e2_house_v2", "Hero · SW", True),
    ("front", SPIKE / "outputs" / "mv_front",    "Front",     False),
]


def build_multiview(views=DEFAULT_VIEWS, out_dir: Path = OUT) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_views = []
    anchor_id = None
    for vid, src, label, is_anchor in views:
        src = Path(src)
        base_render = src / "renders" / "base_render.png"
        if not base_render.exists():
            raise FileNotFoundError(
                f"view '{vid}': missing {base_render} — render it first "
                f"(spike/run_e2b_registration.py --live --src {src} or v1 --live).")
        if not (src / "instance_ids.png").exists():
            # decode on demand so a fresh capture dir works without a manual step
            from host_probe_rhino import decode
            decode(src)
        vdir = VIEWS_DIR / vid
        info = write_web_project(src, base_render, vdir)
        manifest_views.append({
            "id": vid, "label": label, "anchor": is_anchor,
            "size": info["size"], "n_regions": info["n_regions"],
            "semantics": info["semantics"],
        })
        if is_anchor:
            anchor_id = vid
        print(f"  view '{vid}'{' [ANCHOR]' if is_anchor else ''}: "
              f"{info['size'][0]}x{info['size'][1]}, {info['n_regions']} regions")

    if anchor_id is None:
        anchor_id = manifest_views[0]["id"]
        manifest_views[0]["anchor"] = True

    (out_dir / "views.json").write_text(
        json.dumps({"anchor": anchor_id, "views": manifest_views}, indent=1))

    # --- mirror the ANCHOR view into the top-level project files (back-compat) ---
    avdir = VIEWS_DIR / anchor_id
    for fn in ("base.png", "ids_rgb.png", "regions.json"):
        shutil.copy(avdir / fn, out_dir / fn)
    make_swatches(out_dir / "swatches")           # swatches live at top level (shared)
    # clear stale single-view layer cache (data changed)
    layers = out_dir / "layers"
    if layers.exists():
        for p in layers.glob("*.png"):
            p.unlink()

    print(f"[multiview] anchor='{anchor_id}', {len(manifest_views)} views -> "
          f"{(out_dir / 'views.json').relative_to(REPO)}")
    return {"anchor": anchor_id, "views": manifest_views}


if __name__ == "__main__":
    build_multiview()
