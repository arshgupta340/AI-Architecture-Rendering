"""
Reve layout-API validation spike (Track 2 gate -- PRD-reve-canvas.md Phase 0).

Answers ONE question for <=$5: does Reve's experimental layout API
(extract_layout -> edit regions -> render_layout) hold up on architectural
imagery well enough to build Reve Canvas on it?

Default mode (dry run): prints every planned request payload (base64 elided)
with projected credit cost, calls nothing, spends nothing. Use it to review
the exact call plan before authorizing spend.

Live mode (`--live`): executes the plan against api.reve.com with
`REVE_API_KEY` from `spike/.env`. Every raw response (JSON + image bytes) is
saved to `spike/reve/outputs/` BEFORE any parsing -- never lose paid data to a
validation bug. A hard budget guard stops before any call that would push the
run past `--budget-usd` (default 5.00).

Pass/fail criteria (scored into spike/REPORTS/reve_spike.md after the run):
  C1  extract_layout tags >=70% of major architectural elements sensibly,
      and the taxonomy fuzzy-matcher maps >=80% of returned labels.
  C2  KILL GATE: render_layout material swap changes <5% of pixels (mean)
      outside the edited region bbox; no warping of windows/rooflines at zoom.
  C3  founder judgment: client-deck quality at full resolution.
  C4  5 sequential edits show no compounding drift in untouched areas.
  C5  a raw shaded viewport becomes presentable (gates the Rhino-bridge pitch,
      not the product).
  C6  our RegionKey labels round-trip verbatim through render_layout.

Examples:
    # review the plan, $0
    spike\\.venv\\Scripts\\python.exe spike/reve/run_reve_spike.py

    # run only extraction, live
    spike\\.venv\\Scripts\\python.exe spike/reve/run_reve_spike.py --live --steps S1

    # full plan, live, default $5 cap
    spike\\.venv\\Scripts\\python.exe spike/reve/run_reve_spike.py --live

NOTE (field-name risk): request shapes below follow the v2 docs schemas
captured 2026-07-14 (see PRD appendix). Before the first live run, cross-check
against the official SDK (github.com/reve-ai/reve-sdk) -- the endpoints are
flagged experimental and a field rename costs a wasted call. S1 alone
(`--steps S1`, $0.32) is the cheap way to validate the shapes.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

API_BASE = "https://api.reve.com"
USD_PER_CREDIT = 10.0 / 7500.0  # $10 min pack = 7,500 credits
CREDITS = {"extract_layout": 80, "render_layout": 80, "create_layout": 80, "create": 150}
OUT_DIR = Path(__file__).resolve().parent / "outputs"
LEDGER = _REPO_ROOT / "spike" / "REPORTS" / "cost_ledger.md"

# Fixtures (interior is founder-supplied; steps skip gracefully if missing).
FIXTURES = {
    "exterior_photoreal": _REPO_ROOT / "spike/outputs/e2_house/renders/flux_depth.png",
    "viewport_shaded": _REPO_ROOT / "spike/outputs/e2_house/beauty.png",
    "interior_photo": Path(__file__).resolve().parent / "fixtures" / "interior.png",
}

# --- Minimal taxonomy fuzzy matcher (mirror of the planned packages/arch-taxonomy) ---
SEMANTICS = [
    "wall", "glazing", "door", "roof", "floor", "ceiling", "ground", "paving",
    "vegetation", "person", "vehicle", "furniture", "fixture", "sky", "water",
    "text", "context",
]
ALIASES = {
    "window": "glazing", "windows": "glazing", "mullion": "glazing", "glass": "glazing",
    "facade": "wall", "siding": "wall", "brick": "wall", "cladding": "wall",
    "tree": "vegetation", "trees": "vegetation", "bush": "vegetation", "plant": "vegetation",
    "grass": "ground", "lawn": "ground", "driveway": "paving", "path": "paving",
    "sidewalk": "paving", "road": "paving", "street": "context", "building": "context",
    "house": "context", "car": "vehicle", "sofa": "furniture", "couch": "furniture",
    "table": "furniture", "chair": "furniture", "lamp": "fixture", "light": "fixture",
    "clouds": "sky", "man": "person", "woman": "person", "people": "person",
}
MATERIAL_SCAFFOLDS = {
    "travertine": "honed travertine stone cladding, buff cream tone, subtle horizontal banding, matte finish",
    "red_brick": "red clay brick masonry in running bond, tumbled texture, light mortar joints",
    "oak_floor": "wide-plank white oak flooring, matte natural oil finish, subtle grain variation",
    "charcoal_metal_roof": "standing-seam charcoal grey metal roofing, crisp vertical seams, low sheen",
}


def match_semantic(label: str) -> str | None:
    words = re.findall(r"[a-z]+", label.lower())
    for w in words:
        if w in SEMANTICS:
            return w
        if w in ALIASES:
            return ALIASES[w]
    return None


def region_key(semantic: str, label: str, idx: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:32] or "r"
    return f"{semantic}.{slug}#{idx:03d}"


# --- Budget guard ---
@dataclass
class Budget:
    cap_usd: float
    spent_credits: int = 0
    calls: list[dict] = field(default_factory=list)

    @property
    def spent_usd(self) -> float:
        return self.spent_credits * USD_PER_CREDIT

    def check(self, credits: int, what: str) -> None:
        projected = (self.spent_credits + credits) * USD_PER_CREDIT
        if projected > self.cap_usd:
            raise SystemExit(
                f"BUDGET STOP before '{what}': spent ${self.spent_usd:.2f}, next call "
                f"~${credits * USD_PER_CREDIT:.2f} would exceed the ${self.cap_usd:.2f} cap."
            )

    def record(self, what: str, credits_used: int, request_id: str | None) -> None:
        self.spent_credits += credits_used
        self.calls.append({"what": what, "credits": credits_used, "request_id": request_id,
                           "ts": time.strftime("%Y-%m-%d %H:%M")})


# --- Reve client (server-side key, raw-save discipline) ---
class ReveClient:
    def __init__(self, api_key: str, budget: Budget, out_dir: Path):
        self.api_key = api_key
        self.budget = budget
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _post(self, endpoint: str, payload: dict, tag: str, projected_credits: int) -> dict:
        import httpx  # already a spike dependency (respx tests)

        self.budget.check(projected_credits, tag)
        url = f"{API_BASE}{endpoint}?breadcrumb=reve-spike-{tag}"
        t0 = time.time()
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=180.0,
        )
        elapsed = time.time() - t0
        raw_path = self.out_dir / f"{tag}_raw.json"
        raw_path.write_bytes(resp.content)  # raw save BEFORE any parsing
        if resp.status_code != 200:
            err = resp.headers.get("x-reve-error-code", "?")
            raise RuntimeError(f"{tag}: HTTP {resp.status_code} (X-Reve-Error-Code: {err}) -- raw at {raw_path}")
        data = resp.json()
        used = int(data.get("credits_used", projected_credits))
        self.budget.record(tag, used, data.get("request_id"))
        print(f"  [{tag}] {elapsed:.1f}s | {used} credits (~${used * USD_PER_CREDIT:.3f}) "
              f"| remaining balance {data.get('credits_remaining', '?')}")
        if data.get("content_violation"):
            print(f"  [{tag}] WARNING content_violation=true (still billed)")
        if "image" in data and data["image"]:
            img_path = self.out_dir / f"{tag}.png"
            img_path.write_bytes(base64.b64decode(data["image"]))
            print(f"  [{tag}] image -> {img_path.relative_to(_REPO_ROOT)}")
        return data

    def extract_layout(self, image_b64: str, tag: str) -> dict:
        return self._post("/v2/image/extract_layout", {"image": {"data": image_b64}},
                          tag, CREDITS["extract_layout"])

    def render_layout(self, layout: dict, ref_image_b64: str | None, tag: str) -> dict:
        payload: dict = {"layout": layout}
        if ref_image_b64 is not None:
            payload["references"] = [{"image": {"data": ref_image_b64}}]
        return self._post("/v2/image/render_layout", payload, tag, CREDITS["render_layout"])

    def create(self, prompt: str, tag: str) -> dict:
        return self._post("/v2/image/create", {"prompt": prompt}, tag, CREDITS["create"])


# --- Layout manipulation helpers ---
def relabel_with_region_keys(layout: dict) -> tuple[dict, dict[str, str]]:
    """Rewrite region labels to RegionKeys (C6 probe). Returns (layout, old->new)."""
    mapping: dict[str, str] = {}
    out = json.loads(json.dumps(layout))
    for i, region in enumerate(out.get("regions", [])):
        semantic = match_semantic(region.get("label", "")) or "context"
        new = region_key(semantic, region.get("label", ""), i)
        mapping[region["label"]] = new
        region["label"] = new
    # parent references must follow the rename
    for region in out.get("regions", []):
        if region.get("parent") in mapping:
            region["parent"] = mapping[region["parent"]]
    return out, mapping


def pick_region(layout: dict, semantic: str) -> dict | None:
    """Largest-area region matching a semantic class."""
    best, best_area = None, 0.0
    for region in layout.get("regions", []):
        if match_semantic(region.get("label", "")) != semantic:
            continue
        b = region.get("bbox", {})
        area = max(0.0, (b.get("x1", 0) - b.get("x0", 0)) * (b.get("y1", 0) - b.get("y0", 0)))
        if area > best_area:
            best, best_area = region, area
    return best


def patch_region_prompt(layout: dict, label: str, new_prompt: str) -> dict:
    out = json.loads(json.dumps(layout))
    for region in out.get("regions", []):
        if region["label"] == label:
            region["prompt"] = new_prompt
            return out
    raise KeyError(f"region '{label}' not in layout")


def drift_outside_bbox(img_a: Path, img_b: Path, bbox: dict) -> float:
    """C2 metric: mean absolute pixel change (0..1) OUTSIDE the edited bbox."""
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(img_a).convert("RGB"), dtype=np.float32)
    b_img = Image.open(img_b).convert("RGB")
    if b_img.size != (a.shape[1], a.shape[0]):
        b_img = b_img.resize((a.shape[1], a.shape[0]))
    b = np.asarray(b_img, dtype=np.float32)
    h, w = a.shape[:2]
    mask = np.ones((h, w), dtype=bool)
    x0, y0 = int(bbox["x0"] * w), int(bbox["y0"] * h)
    x1, y1 = int(bbox["x1"] * w), int(bbox["y1"] * h)
    mask[y0:y1, x0:x1] = False
    if not mask.any():
        return 0.0
    return float((np.abs(a - b).mean(axis=2)[mask] / 255.0).mean())


def score_extraction(layout: dict) -> dict:
    regions = layout.get("regions", [])
    matched = [r for r in regions if match_semantic(r.get("label", ""))]
    classes = sorted({match_semantic(r["label"]) for r in matched if match_semantic(r["label"])})
    return {
        "n_regions": len(regions),
        "n_matched": len(matched),
        "match_rate": round(len(matched) / len(regions), 3) if regions else 0.0,
        "classes_found": classes,
        "labels": [r.get("label") for r in regions],
    }


def b64_of(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def load_api_key() -> str:
    env_path = _REPO_ROOT / "spike" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("REVE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    import os
    if os.environ.get("REVE_API_KEY"):
        return os.environ["REVE_API_KEY"]
    raise SystemExit("REVE_API_KEY not found in spike/.env or environment. "
                     "Buy the $10 pack at https://api.reve.com/console and add the key.")


# --- The plan ---
def build_plan() -> list[dict]:
    return [
        {"id": "S1", "what": "extract_layout on all available fixtures", "credits": 240,
         "tests": "C1 extraction sanity + taxonomy match rate"},
        {"id": "S2", "what": "wall -> travertine swap on exterior (render_layout, image-anchored)",
         "credits": 80, "tests": "C2 drift outside bbox, C3 quality, C6 label round-trip"},
        {"id": "S3", "what": "floor -> oak swap on interior (skipped if no interior fixture)",
         "credits": 80, "tests": "C2/C3 interior"},
        {"id": "S4", "what": "5 sequential edits on exterior (wall, roof, sky, lighting, vegetation)",
         "credits": 400, "tests": "C4 compounding drift, C6"},
        {"id": "S5", "what": "photorealize the raw shaded viewport (render_layout on its extract)",
         "credits": 80, "tests": "C5 Rhino-bridge value prop"},
        {"id": "S6", "what": "control: create-from-prompt (no input image)", "credits": 150,
         "tests": "quality baseline"},
    ]


def dry_run(steps: list[str]) -> None:
    plan = [s for s in build_plan() if s["id"] in steps]
    total = sum(s["credits"] for s in plan)
    print("REVE SPIKE -- DRY RUN (nothing called, nothing spent)\n")
    for f_name, f_path in FIXTURES.items():
        status = "OK" if f_path.exists() else ("MISSING (user-supplied)" if f_name == "interior_photo" else "MISSING")
        print(f"  fixture {f_name:22s} {status:24s} {f_path.relative_to(_REPO_ROOT) if f_path.is_absolute() and f_path.exists() else f_path}")
    print()
    for s in plan:
        print(f"  {s['id']}  {s['credits']:>4} cr  ~${s['credits'] * USD_PER_CREDIT:5.2f}  {s['what']}")
        print(f"       tests: {s['tests']}")
    print(f"\n  PLANNED TOTAL: {total} credits ~ ${total * USD_PER_CREDIT:.2f} "
          f"(reroll headroom to the $5 cap: ${5.0 - total * USD_PER_CREDIT:.2f})")
    print("\n  Example extract_layout payload:")
    print(json.dumps({"image": {"data": "<base64 elided>"}}, indent=4))
    print("\n  Example render_layout payload (S2):")
    print(json.dumps({
        "layout": {"prompt": "<whole-image prompt from extract>", "width": "<from extract>",
                   "height": "<from extract>",
                   "regions": [{"label": "wall.front-facade#001",
                                "prompt": MATERIAL_SCAFFOLDS["travertine"],
                                "bbox": {"x0": "…", "y0": "…", "x1": "…", "y1": "…"}}, "…"]},
        "references": [{"image": {"data": "<base64 of current snapshot, elided>"}}],
    }, indent=4))
    print("\nRun with --live to execute. Validate shapes cheaply first: --live --steps S1")


def live_run(steps: list[str], budget_cap: float) -> None:
    budget = Budget(cap_usd=budget_cap)
    client = ReveClient(load_api_key(), budget, OUT_DIR)
    results: dict = {"started": time.strftime("%Y-%m-%d %H:%M"), "steps": {}}
    layouts: dict[str, dict] = {}

    def save_results() -> None:
        (OUT_DIR / "spike_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    try:
        if "S1" in steps:
            print("S1 -- extract_layout on fixtures")
            for name, path in FIXTURES.items():
                if not path.exists():
                    print(f"  skip {name} (missing)")
                    continue
                data = client.extract_layout(b64_of(path), f"S1_{name}")
                layouts[name] = data["layout"]
                score = score_extraction(data["layout"])
                results["steps"][f"S1_{name}"] = score
                print(f"  [{name}] {score['n_regions']} regions, "
                      f"{score['match_rate']:.0%} taxonomy-matched, classes: {score['classes_found']}")
            save_results()

        def swap(fixture: str, semantic: str, scaffold: str, tag: str) -> None:
            if fixture not in layouts:
                if not FIXTURES[fixture].exists():
                    print(f"  skip {tag} ({fixture} missing)")
                    return
                data = client.extract_layout(b64_of(FIXTURES[fixture]), f"{tag}_extract")
                layouts[fixture] = data["layout"]
            keyed, _ = relabel_with_region_keys(layouts[fixture])
            target = pick_region(keyed, semantic)
            if target is None:
                results["steps"][tag] = {"error": f"no '{semantic}' region found -- C1 signal"}
                print(f"  [{tag}] NO {semantic} REGION -- that is itself a C1 finding")
                return
            edited = patch_region_prompt(keyed, target["label"], MATERIAL_SCAFFOLDS[scaffold])
            data = client.render_layout(edited, b64_of(FIXTURES[fixture]), tag)
            returned_labels = [r.get("label") for r in data.get("layout", {}).get("regions", [])]
            drift = drift_outside_bbox(FIXTURES[fixture], OUT_DIR / f"{tag}.png", target["bbox"])
            results["steps"][tag] = {
                "edited_region": target["label"],
                "drift_outside_bbox": round(drift, 4),
                "c2_pass_threshold_0.05": drift < 0.05,
                "c6_label_roundtrip": target["label"] in returned_labels,
            }
            print(f"  [{tag}] drift outside bbox: {drift:.2%} "
                  f"({'PASS' if drift < 0.05 else 'FAIL'} vs 5%) | "
                  f"C6 label round-trip: {target['label'] in returned_labels}")

        if "S2" in steps:
            print("S2 -- exterior wall -> travertine")
            swap("exterior_photoreal", "wall", "travertine", "S2_wall_travertine")
            save_results()

        if "S3" in steps:
            print("S3 -- interior floor -> oak")
            swap("interior_photo", "floor", "oak_floor", "S3_floor_oak")
            save_results()

        if "S4" in steps:
            print("S4 -- 5 sequential edits (C4 compounding drift)")
            fixture = "exterior_photoreal"
            if fixture not in layouts:
                data = client.extract_layout(b64_of(FIXTURES[fixture]), "S4_extract")
                layouts[fixture] = data["layout"]
            current_layout, _ = relabel_with_region_keys(layouts[fixture])
            current_image = FIXTURES[fixture]
            edits = [
                ("wall", "prompt", MATERIAL_SCAFFOLDS["red_brick"]),
                ("roof", "prompt", MATERIAL_SCAFFOLDS["charcoal_metal_roof"]),
                ("sky", "prompt", "dramatic golden-hour sky, low warm sun, scattered clouds"),
                (None, "global", "photographed at dusk, warm interior lights glowing, long soft shadows"),
                ("vegetation", "prompt", "mature leafy deciduous trees, lush summer foliage"),
            ]
            for i, (semantic, mode, text) in enumerate(edits, 1):
                tag = f"S4_edit{i}_{semantic or 'global'}"
                if mode == "global":
                    edited = json.loads(json.dumps(current_layout))
                    edited["prompt"] = ((edited.get("prompt") or "") + " " + text).strip()
                else:
                    target = pick_region(current_layout, semantic)
                    if target is None:
                        print(f"  [{tag}] no {semantic} region, skipping")
                        continue
                    edited = patch_region_prompt(current_layout, target["label"], text)
                data = client.render_layout(edited, b64_of(current_image), tag)
                current_layout = data.get("layout", edited)
                current_image = OUT_DIR / f"{tag}.png"
            if current_image != FIXTURES[fixture]:
                from PIL import Image
                import numpy as np
                a = np.asarray(Image.open(FIXTURES[fixture]).convert("RGB"), dtype=np.float32)
                b_img = Image.open(current_image).convert("RGB").resize((a.shape[1], a.shape[0]))
                total_drift = float((np.abs(a - np.asarray(b_img, dtype=np.float32)) / 255.0).mean())
                results["steps"]["S4"] = {"frames": 5, "total_mean_drift_frame1_vs_5": round(total_drift, 4),
                                          "note": "manual C4 review: compare untouched areas across S4_edit*.png"}
            save_results()

        if "S5" in steps:
            print("S5 -- photorealize the raw shaded viewport")
            fixture = "viewport_shaded"
            if fixture not in layouts:
                data = client.extract_layout(b64_of(FIXTURES[fixture]), "S5_extract")
                layouts[fixture] = data["layout"]
            keyed, _ = relabel_with_region_keys(layouts[fixture])
            edited = json.loads(json.dumps(keyed))
            edited["prompt"] = ((edited.get("prompt") or "")
                                + " professional architectural photograph, photorealistic materials and "
                                  "lighting, golden hour, high-end residential exterior").strip()
            client.render_layout(edited, b64_of(FIXTURES[fixture]), "S5_photorealize")
            results["steps"]["S5"] = {"note": "manual C5 review of S5_photorealize.png vs beauty.png"}
            save_results()

        if "S6" in steps:
            print("S6 -- control: create from prompt")
            client.create(
                "professional architectural photograph of a modern two-story house, "
                "white render walls, large glazing, flat roof, golden hour, landscaped garden",
                "S6_control",
            )
            results["steps"]["S6"] = {"note": "quality baseline, manual review"}
            save_results()

    finally:
        results["spent_credits"] = budget.spent_credits
        results["spent_usd"] = round(budget.spent_usd, 2)
        results["calls"] = budget.calls
        save_results()
        print(f"\nSPENT: {budget.spent_credits} credits ~ ${budget.spent_usd:.2f} "
              f"(cap ${budget.cap_usd:.2f}) | results -> {OUT_DIR / 'spike_results.json'}")
        print("\nPaste-ready cost-ledger lines (spike/REPORTS/cost_ledger.md):")
        for c in budget.calls:
            print(f"{c['ts']} REVE-SPIKE | reve-canvas P0 | Reve | reve-2.x layouts | "
                  f"{c['credits'] * USD_PER_CREDIT:.2f} | {c['what']} (request {c['request_id']})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--live", action="store_true", help="actually call the Reve API (spends money)")
    ap.add_argument("--steps", default="S1,S2,S3,S4,S5,S6",
                    help="comma-separated subset of S1..S6 (default: all)")
    ap.add_argument("--budget-usd", type=float, default=5.00,
                    help="hard stop before exceeding this spend (default 5.00, user-authorized 2026-07-14)")
    args = ap.parse_args()
    steps = [s.strip().upper() for s in args.steps.split(",") if s.strip()]

    if args.live:
        live_run(steps, args.budget_usd)
    else:
        dry_run(steps)


if __name__ == "__main__":
    main()
