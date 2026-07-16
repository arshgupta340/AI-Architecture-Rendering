"""
Edit-mechanic probe (Track 2, PRD Phase 0 follow-up).

S2 proved geometry locks perfectly BUT the material didn't change, because the
edit APPENDED a travertine clause to a region prompt that still said "dark grey
cedar shake siding" — a contradiction the image-reference resolved toward the
original. This probe finds the edit recipe that makes a material swap actually
take while keeping geometry locked. It answers: replace-vs-append, and
image-reference-vs-none.

Reuses the S1 cached exterior layout (no new extraction spend). ~$0.33 for 3
render_layout calls. Cumulative Reve spend is tracked in the ledger, not here.

    spike\\.venv\\Scripts\\python.exe spike/reve/run_edit_mechanic.py            # dry-run plan
    spike\\.venv\\Scripts\\python.exe spike/reve/run_edit_mechanic.py --live
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
    drift_outside_bbox, FIXTURES, OUT_DIR, USD_PER_CREDIT,
)

CACHED_LAYOUT = OUT_DIR / "S1_exterior_photoreal_raw.json"
TRAVERTINE = "honed cream travertine stone cladding with subtle horizontal banding"
# The exact material phrases Reve wrote into the building region prompt (from S1).
SIDING_PHRASES = ["dark grey cedar shake siding", "dark gray cedar shake siding",
                  "grey cedar shake siding", "cedar shake siding", "shingle siding",
                  "grey shingle siding"]


def replace_material(prompt: str, new_material: str) -> tuple[str, bool]:
    for phrase in SIDING_PHRASES:
        if phrase in prompt:
            return prompt.replace(phrase, new_material), True
    # fallback: prepend a dominant directive if no known phrase found
    return f"The walls are {new_material}. " + prompt, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=2.0)
    args = ap.parse_args()

    layout = json.loads(CACHED_LAYOUT.read_text(encoding="utf-8"))["layout"]
    building = pick_building_region(layout)
    orig_prompt = building["prompt"]
    new_prompt, hit = replace_material(orig_prompt, TRAVERTINE)

    print(f"building region: {building['label']}")
    print(f"material phrase matched in prompt: {hit}")
    print(f"  before: ...{orig_prompt[:130]}...")
    print(f"  after : ...{new_prompt[:130]}...\n")

    variants = [
        ("A_replace_withref", "prompt REPLACE + original image as reference (geometry anchor)", True),
        ("B_replace_noref", "prompt REPLACE + NO reference (layout-only render)", False),
        ("C_replace_withref_v2", "prompt REPLACE + reference, second seed for variance", True),
    ]

    if not args.live:
        print("DRY RUN — planned render_layout calls (80cr ~ $0.11 each):")
        for tag, desc, use_ref in variants:
            print(f"  {tag:22s} ref={use_ref!s:5s}  {desc}")
        print(f"\n  total ~${len(variants) * 80 * USD_PER_CREDIT:.2f}. Run with --live.")
        return

    budget = Budget(cap_usd=args.budget_usd)
    client = ReveClient(load_api_key(), budget, OUT_DIR)
    ref_b64 = b64_of(FIXTURES["exterior_photoreal"])

    edited = json.loads(json.dumps(layout))
    for r in edited["regions"]:
        if r["label"] == building["label"]:
            r["prompt"] = new_prompt

    results = {}
    for tag, desc, use_ref in variants:
        full_tag = f"EM_{tag}"
        data = client.render_layout(edited, ref_b64 if use_ref else None, full_tag)
        drift = drift_outside_bbox(FIXTURES["exterior_photoreal"], OUT_DIR / f"{full_tag}.png",
                                   building["bbox"])
        results[full_tag] = {"desc": desc, "use_ref": use_ref, "drift_outside_bbox": round(drift, 4)}
        print(f"  [{full_tag}] drift outside building bbox: {drift:.2%}")

    (OUT_DIR / "edit_mechanic_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSPENT: {budget.spent_credits} cr ~ ${budget.spent_usd:.2f}")
    for c in budget.calls:
        print(f"{c['ts']} REVE-SPIKE | edit-mechanic | Reve | reve-2.x render_layout | "
              f"{c['credits'] * USD_PER_CREDIT:.2f} | {c['what']} (req {c['request_id']})")


if __name__ == "__main__":
    main()
