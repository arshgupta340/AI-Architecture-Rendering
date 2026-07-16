"""
Gate closeout probe (Track 2, PRD Phase 0 — final de-risk before build).

Given the proven edit pipeline (extract_layout -> create_layout `change` command
-> render_layout locks geometry AND applies the material), this closes the three
open questions that most affect the app's edit model, cheaply (<= ~$1):

  T1  FRAMING PIN — does setting the layout width/height to the SOURCE aspect
      (ultrawide) stop Reve reframing the architect's viewport? (concern A)
  T2  SURGICAL EDIT — can a change-command target the WALL clause without
      disturbing the roof, when extraction exposes a separate roof region?
      (concern B — surface-level granularity)
  T3  COMPOUNDING — do 2 sequential change-command edits keep untouched areas
      stable (C4)?

Reuses the S1 cached exterior layout where possible. Dry-run prints the plan.

    spike\\.venv\\Scripts\\python.exe spike/reve/run_gate_closeout.py            # plan, $0
    spike\\.venv\\Scripts\\python.exe spike/reve/run_gate_closeout.py --live --tests T1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent.parent))

from spike.reve.run_reve_spike import (  # noqa: E402
    Budget, ReveClient, load_api_key, b64_of, pick_building_region, pick_region,
    match_semantic, drift_outside_bbox, FIXTURES, OUT_DIR, USD_PER_CREDIT, CREDITS,
)

CACHED = OUT_DIR / "S1_exterior_photoreal_raw.json"
TRAVERTINE = ("exterior walls fully clad in honed cream travertine stone with subtle horizontal "
              "banding; same roofline, windows, porch, stairs")
BRICK = ("exterior walls in red clay brick masonry, running bond, light mortar joints; same roof, "
         "windows, porch, stairs")


def source_aspect_layout_dims(src_path: Path) -> tuple[int, int]:
    """Pick a Reve-legal (multiple of 32, area in [3072*2560, 4096*4096]) canvas
    whose aspect matches the source, to pin framing."""
    from PIL import Image
    w, h = Image.open(src_path).size
    ar = w / h
    # target area ~ 3.2M px (mid of the legal band), solve for w,h at source aspect
    import math
    area = 3_500_000
    hh = int(round((area / ar) ** 0.5 / 32) * 32)
    ww = int(round(hh * ar / 32) * 32)
    # clamp area into [3072*2560=7,864,320 .. 4096*4096=16,777,216]? NOTE: docs say
    # width*height between 3072*2560 and 4096*4096 — i.e. 7.86M..16.78M. Re-solve.
    lo, hi = 3072 * 2560, 4096 * 4096
    area = (lo + hi) // 2
    hh = int(round((area / ar) ** 0.5 / 32) * 32)
    ww = int(round(hh * ar / 32) * 32)
    while ww * hh > hi:
        hh -= 32; ww = int(round(hh * ar / 32) * 32)
    while ww * hh < lo:
        hh += 32; ww = int(round(hh * ar / 32) * 32)
    return ww, hh


def change_cmd_pipeline(client, ref_b64, layout, label, new_desc, tag, pin_dims=None):
    """The proven edit pipeline: create_layout change -> render_layout."""
    cl = client._post("/v2/image/create_layout",
                     {"references": [{"image": {"data": ref_b64}, "layout": layout}],
                      "commands": [{"op": "change", "label": label, "new_description": new_desc}]},
                     f"{tag}_cl", CREDITS["create_layout"])
    edited = cl.get("layout", layout)
    if pin_dims:
        edited["width"], edited["height"] = pin_dims
    data = client.render_layout(edited, ref_b64, f"{tag}_render")
    return edited, data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--tests", default="T1,T2,T3")
    ap.add_argument("--budget-usd", type=float, default=1.5)
    args = ap.parse_args()
    tests = [t.strip().upper() for t in args.tests.split(",") if t.strip()]

    layout = json.loads(CACHED.read_text(encoding="utf-8"))["layout"]
    building = pick_building_region(layout)
    src = FIXTURES["exterior_photoreal"]
    pin = source_aspect_layout_dims(src)

    if not args.live:
        from PIL import Image
        sw, sh = Image.open(src).size
        print("GATE CLOSEOUT — DRY RUN")
        print(f"  source {sw}x{sh} (ar {sw/sh:.3f}) -> pinned canvas {pin[0]}x{pin[1]} (ar {pin[0]/pin[1]:.3f})")
        print(f"  building region: {building['label']}")
        roofs = [r for r in layout['regions'] if match_semantic(r.get('label','')) == 'roof']
        print(f"  separate roof region available for T2: {bool(roofs)} "
              f"({roofs[0]['label'] if roofs else 'none — T2 edits building, checks roof clause'})")
        print("  T1 framing-pin: create_layout+render_layout, layout dims pinned to source aspect (~$0.21)")
        print("  T2 surgical   : change only wall clause, inspect roof stability (~$0.21)")
        print("  T3 compounding: two sequential change edits (~$0.42)")
        print(f"  max ~$0.84 for all three. Run --live --tests {','.join(tests)}")
        return

    budget = Budget(cap_usd=args.budget_usd)
    client = ReveClient(load_api_key(), budget, OUT_DIR)
    ref_b64 = b64_of(src)
    results = {}

    if "TI" in tests:
        print("TI -- INTERIOR decomposition + floor swap (exteriors-only vs general)")
        interior = FIXTURES["interior_photo"]
        if not interior.exists():
            print(f"  skip TI -- no interior fixture at {interior}")
        else:
            iref = b64_of(interior)
            idata = client.extract_layout(iref, "GC_TI_extract")
            ilayout = idata["layout"]
            labels = [r.get("label") for r in ilayout.get("regions", [])]
            classes = sorted({match_semantic(r.get("label", "")) for r in ilayout.get("regions", [])
                              if match_semantic(r.get("label", ""))})
            floor = pick_region(ilayout, "floor")
            results["TI_extract"] = {"n_regions": len(labels), "labels": labels,
                                     "classes": classes, "has_floor_region": floor is not None}
            print(f"  [TI] {len(labels)} regions | classes {classes}")
            print(f"  [TI] labels: {labels}")
            print(f"  [TI] separate floor region: {floor is not None}")
            # floor swap via the change-command pipeline (if a floor/ground region exists)
            floor_target = floor or pick_region(ilayout, "ground")
            if floor_target is not None:
                _, fdata = change_cmd_pipeline(
                    client, iref, ilayout, floor_target["label"],
                    "wide-plank white oak flooring, matte natural oil finish; keep walls, ceiling, furniture unchanged",
                    "GC_TI_floorswap")
                drift = drift_outside_bbox(interior, OUT_DIR / "GC_TI_floorswap_render.png", floor_target["bbox"])
                results["TI_floorswap"] = {"edited": floor_target["label"], "drift_outside_bbox": round(drift, 4),
                                           "c2_pass_threshold_0.05": drift < 0.05,
                                           "note": "manual: did floor->oak while walls/furniture stayed put?"}
                print(f"  [TI] floor swap drift outside bbox: {drift:.2%} ({'PASS' if drift < 0.05 else 'FAIL'})")
            else:
                results["TI_floorswap"] = {"skip": "no floor/ground region -- interior may be one room-blob"}
                print("  [TI] NO floor/ground region -- possible room-blob; inspect labels above")

    if "T1" in tests:
        print("T1 -- framing pin (layout dims = source aspect)")
        _, data = change_cmd_pipeline(client, ref_b64, layout, building["label"], TRAVERTINE,
                                      "GC_T1_pin", pin_dims=pin)
        from PIL import Image
        out = Image.open(OUT_DIR / "GC_T1_pin_render.png")
        results["T1"] = {"pinned_dims": list(pin), "output_dims": list(out.size),
                         "aspect_matches_source": abs(out.size[0]/out.size[1] - pin[0]/pin[1]) < 0.02}
        print(f"  [T1] output {out.size}, aspect-match {results['T1']['aspect_matches_source']}")

    if "T2" in tests:
        print("T2 -- surgical wall edit, roof stability")
        roofs = [r for r in layout['regions'] if match_semantic(r.get('label','')) == 'roof']
        target = building["label"]
        edited, data = change_cmd_pipeline(client, ref_b64, layout, target, TRAVERTINE, "GC_T2_wallonly")
        results["T2"] = {"edited": target, "has_separate_roof_region": bool(roofs),
                         "note": "manual: inspect GC_T2_wallonly_render.png — did roof stay dark while walls -> travertine?"}
        print(f"  [T2] edited {target}; separate roof region: {bool(roofs)} (inspect image for roof stability)")

    if "T3" in tests:
        print("T3 -- compounding (2 sequential change edits)")
        cur_layout, cur_ref = layout, ref_b64
        for i, desc in enumerate([BRICK, TRAVERTINE], 1):
            edited, data = change_cmd_pipeline(client, cur_ref, cur_layout, pick_building_region(cur_layout)["label"],
                                               desc, f"GC_T3_edit{i}")
            cur_layout = data.get("layout", edited)
            cur_ref = b64_of(OUT_DIR / f"GC_T3_edit{i}_render.png")
        # drift of edit2 vs edit1 outside building (untouched areas should be stable)
        b2 = pick_building_region(cur_layout)
        drift = drift_outside_bbox(OUT_DIR / "GC_T3_edit1_render.png", OUT_DIR / "GC_T3_edit2_render.png",
                                   b2["bbox"] if b2 else building["bbox"])
        results["T3"] = {"drift_edit1_vs_edit2_outside_bbox": round(drift, 4),
                         "c4_pass_threshold_0.05": drift < 0.05}
        print(f"  [T3] drift edit1->edit2 outside bbox: {drift:.2%} ({'PASS' if drift < 0.05 else 'FAIL'})")

    (OUT_DIR / "gate_closeout_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSPENT: {budget.spent_credits} cr ~ ${budget.spent_usd:.2f}")
    for c in budget.calls:
        print(f"{c['ts']} REVE-SPIKE | gate-closeout | Reve | reve-2.x | "
              f"{c['credits']*USD_PER_CREDIT:.2f} | {c['what']} (req {c['request_id']})")


if __name__ == "__main__":
    main()
