"""
Edit-primitive probe (Track 2, PRD Phase 0, critical).

render_layout + region-prompt rewrite did NOT change the wall material (the image
reference dominates). This probe tests Reve's DOCUMENTED edit primitives to find
the one that actually performs a material swap while keeping geometry:

  D  v2 create  — reference image + explicit edit instruction (the "edit"
                  successor path; frame-addressed reference).
  E  create_layout `change` command  — the intended layout-edit op:
                  {op:"change", label, new_description} → then render_layout.

Reuses the S1 cached exterior layout. ~$0.42 (create 150cr + create_layout 80cr
+ render_layout 80cr). Cumulative spend tracked in the ledger.

    spike\\.venv\\Scripts\\python.exe spike/reve/run_edit_primitives.py            # dry-run
    spike\\.venv\\Scripts\\python.exe spike/reve/run_edit_primitives.py --live
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
    Budget, ReveClient, load_api_key, b64_of, pick_building_region,
    drift_outside_bbox, FIXTURES, OUT_DIR, USD_PER_CREDIT, CREDITS,
)

CACHED_LAYOUT = OUT_DIR / "S1_exterior_photoreal_raw.json"
TRAVERTINE_DESC = ("Two-story coastal-style house with exterior walls fully clad in honed cream "
                   "travertine stone with subtle horizontal banding, and crisp white trim. "
                   "Same complex dark-shingled roofline, same windows, same front porch and stairs.")
EDIT_INSTRUCTION = ("Keep this exact house — identical geometry, windows, roofline, porch, stairs, "
                    "camera, and background — but change the exterior wall cladding from grey cedar "
                    "shake shingles to honed cream travertine stone with subtle horizontal banding.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=2.0)
    args = ap.parse_args()

    layout = json.loads(CACHED_LAYOUT.read_text(encoding="utf-8"))["layout"]
    building = pick_building_region(layout)

    if not args.live:
        print("DRY RUN — planned calls:")
        print(f"  D  create (ref+instruction)      {CREDITS['create']}cr ~${CREDITS['create']*USD_PER_CREDIT:.2f}")
        print(f"  E1 create_layout (change cmd)    {CREDITS['create_layout']}cr ~${CREDITS['create_layout']*USD_PER_CREDIT:.2f}")
        print(f"  E2 render_layout (edited layout) {CREDITS['render_layout']}cr ~${CREDITS['render_layout']*USD_PER_CREDIT:.2f}")
        print(f"  building region label: {building['label']}")
        print("  create_layout command:", json.dumps({"op": "change", "label": building["label"],
                                                       "new_description": TRAVERTINE_DESC[:60] + "..."}))
        return

    budget = Budget(cap_usd=args.budget_usd)
    client = ReveClient(load_api_key(), budget, OUT_DIR)
    ref_b64 = b64_of(FIXTURES["exterior_photoreal"])
    results = {}

    # --- D: v2 create with reference + edit instruction ---
    print("D -- v2 create (reference image + edit instruction)")
    try:
        d = client._post("/v2/image/create",
                         {"prompt": f"{EDIT_INSTRUCTION} Reference photo: <frame>0</frame>.",
                          "references": [{"image": {"data": ref_b64}}]},
                         "EP_D_create_editinstr", CREDITS["create"])
        drift = drift_outside_bbox(FIXTURES["exterior_photoreal"], OUT_DIR / "EP_D_create_editinstr.png",
                                   building["bbox"]) if (OUT_DIR / "EP_D_create_editinstr.png").exists() else None
        results["D"] = {"drift_outside_bbox": round(drift, 4) if drift is not None else None,
                        "regions_returned": len(d.get("layout", {}).get("regions", []))}
        print(f"  [D] drift outside building bbox: {drift:.2%}" if drift is not None else "  [D] no image?")
    except Exception as e:
        results["D"] = {"error": str(e)}
        print(f"  [D] FAILED: {e}")

    # --- E: create_layout change command, then render_layout ---
    print("E -- create_layout change command -> render_layout")
    try:
        cl = client._post("/v2/image/create_layout",
                         {"references": [{"image": {"data": ref_b64}, "layout": layout}],
                          "commands": [{"op": "change", "label": building["label"],
                                        "new_description": TRAVERTINE_DESC}]},
                         "EP_E1_create_layout", CREDITS["create_layout"])
        edited_layout = cl.get("layout", layout)
        print(f"  [E1] edited layout has {len(edited_layout.get('regions', []))} regions; "
              f"normalized_edit_instruction={bool(edited_layout.get('normalized_edit_instruction'))}")
        e2 = client.render_layout(edited_layout, ref_b64, "EP_E2_render")
        drift = drift_outside_bbox(FIXTURES["exterior_photoreal"], OUT_DIR / "EP_E2_render.png",
                                   building["bbox"])
        results["E"] = {"drift_outside_bbox": round(drift, 4),
                        "regions_returned": len(e2.get("layout", {}).get("regions", []))}
        print(f"  [E2] drift outside building bbox: {drift:.2%}")
    except Exception as e:
        results["E"] = {"error": str(e)}
        print(f"  [E] FAILED: {e}")

    (OUT_DIR / "edit_primitives_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSPENT: {budget.spent_credits} cr ~ ${budget.spent_usd:.2f}")
    for c in budget.calls:
        print(f"{c['ts']} REVE-SPIKE | edit-primitives | Reve | reve-2.x | "
              f"{c['credits'] * USD_PER_CREDIT:.2f} | {c['what']} (req {c['request_id']})")


if __name__ == "__main__":
    main()
