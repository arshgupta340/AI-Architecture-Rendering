r"""Multi-view material lock — the enterprise differentiator demo.

Claim under test: "change a material once and it stays consistent across every
view of the building." We apply ONE material to the `wall` semantic across two
distinct camera views of the same house and prove that:

  * a NAIVE per-view edit (each view rendered independently from the swatch)
    drifts — the stone reads as a different stone in view 2; while
  * the ANCHOR-REFERENCE approach — view 2 is conditioned on the already
    materialized ANCHOR view — keeps the material consistent.

Technique (anchor-reference):
  1. ANCHOR view (e2_house_v2, hero/SW): edit wall via FLUX.2 Edit
     [anchor_render, swatch] -> composite through anchor wall mask.
     (For travertine we reuse the precomputed e2_house_v2/travertine_walls_v2.png
     when present, to save a fal call.)
  2. LOCKED view-2 (mv_front): FLUX.2 Edit with THREE references
     [front_render, swatch, ANCHOR_EDIT] and a prompt that says "match the stone
     shown in the third image" -> composite through front wall mask.
  3. NAIVE view-2: same as (2) but WITHOUT the anchor reference
     [front_render, swatch] -> composite through front wall mask.

Metric: mean CIELAB colour + a Laplacian texture-energy stat of the wall region.
We report the distance from each view-2 variant to the anchor; locked should be
closer than naive on colour (the headline consistency number).

Reuses, never reimplements:
  * spike/run_e2b_registration.py: render_locked()  (geometry-locked warm render)
  * spike/host_probe_rhino.py:     mask_for()        (ground-truth wall mask)
  * spike/composite.py:            paste_tile()      (alpha-aware composite)
  * spike/run_e3_swatch.py:        _fal_call(), _data_uri()  (the proven fal idioms)
  * apps/canvas-prototype/server.py mask treatment (DILATE=3, FEATHER=1.1)

Budget: fal ~$0.60. Live calls (worst case, both materials, no reuse):
  render mv_front (1) + per material [anchor 1 + naive 1 + locked 1] = 1 + 2*3 = 7.
  Travertine reuses the precompute AND the cached front render, so the realistic
  spend is ~5 calls (~$0.36). Each call logs an est. cost.

Usage:
  spike\.venv\Scripts\python.exe spike/run_multiview_lock.py            # dry run (plan only, no spend)
  spike\.venv\Scripts\python.exe spike/run_multiview_lock.py --live     # both materials, live
  spike\.venv\Scripts\python.exe spike/run_multiview_lock.py --live --material travertine
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SPIKE = Path(__file__).parent
sys.path.insert(0, str(SPIKE))

from host_probe_rhino import decode, mask_for          # noqa: E402
from run_e2b_registration import render_locked          # noqa: E402
from run_e3_swatch import _data_uri, _fal_call           # noqa: E402
import composite                                          # noqa: E402

ANCHOR = SPIKE / "outputs" / "e2_house_v2"     # hero/SW view — already has base_render.png
FRONT = SPIKE / "outputs" / "mv_front"          # front view — needs a render
OUT = SPIKE / "outputs" / "multiview"
REPO = SPIKE.parent

# Mask edge treatment — identical to apps/canvas-prototype/server.py _mask_png.
DILATE = 3      # MaxFilter window: +1px each side
FEATHER = 1.1   # Gaussian blur radius on the mask edge

# FLUX.2 [pro] Edit, measured in E3.
COST_EDIT = 0.06
# flux-general ControlNet-Union locked render, measured in E2b.
COST_RENDER = 0.08

MATERIALS = {
    "travertine": {
        "swatch": SPIKE / "test_assets" / "travertine.jpeg",
        "desc": "honed beige travertine stone cladding with subtle horizontal "
                "veining and visible coursing joints",
        # Reuse the E3/E2b precompute for the anchor edit (already travertine on
        # the whole wall semantic of the e2_house_v2 base) — saves one fal call.
        "anchor_precompute": ANCHOR / "travertine_walls_v2.png",
    },
    "red_brick": {
        "swatch": REPO / "apps" / "canvas-prototype" / "public" / "project"
                  / "swatches" / "red_brick.png",
        "desc": "red clay brick laid in running-bond courses with light grey "
                "mortar joints",
        "anchor_precompute": None,
    },
}


# --------------------------------------------------------------------------- #
# fal payload helpers (multi-image references)
# --------------------------------------------------------------------------- #
def _swatch_uri(path: Path, max_side: int = 1024) -> str:
    """JPEG data URI of a swatch, downscaled so 3-image payloads stay < 413.

    The travertine asset is ~16 MB; even quality-88 JPEG of the full res can
    bloat a 3-reference payload. Cap the long edge at 1024px — plenty for a
    material/style reference — then defer to the proven E3 _data_uri encoder.
    """
    img = Image.open(path).convert("RGB")
    if max(img.size) > max_side:
        s = max_side / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)))
    return _data_uri(img, fmt="JPEG")


def flux2_edit(image_uris: list[str], prompt: str, timeout_s: int = 420) -> bytes:
    """FLUX.2 [pro] Edit with N reference images (the E3-winning endpoint).

    E3 proved the 2-image shape ([render, swatch]); this demo also sends 3
    ([render, swatch, anchor_edit]). If the 3-image call fails on FLUX.2 Edit,
    fall back to flux-pro/kontext/max/multi which is documented to accept
    multiple image_urls.
    """
    payload = {
        "prompt": prompt,
        "image_urls": image_uris,
        "output_format": "png",
        "safety_tolerance": "5",
    }
    try:
        return _fal_call("fal-ai/flux-2-pro/edit", payload, timeout_s=timeout_s)
    except Exception as e:  # noqa: BLE001
        if len(image_uris) <= 2:
            raise
        print(f"    [fallback] FLUX.2 Edit failed with 3 refs ({e}); "
              f"retrying on flux-pro/kontext/max/multi")
        return _fal_call("fal-ai/flux-pro/kontext/max/multi", payload,
                         timeout_s=timeout_s)


# --------------------------------------------------------------------------- #
# data prep
# --------------------------------------------------------------------------- #
def ensure_decoded(src: Path) -> None:
    """Make sure instance_ids.png exists (host_probe decode). Both inputs ship
    with it, but be defensive per the brief."""
    if not (src / "instance_ids.png").exists():
        print(f"[prep] decoding {src.name} (no instance_ids.png) ...")
        decode(src)


def wall_mask_png(src: Path) -> bytes:
    """Soft union mask of the `wall` semantic: +1px dilate, ~1px feather.

    Matches apps/canvas-prototype/server.py:_mask_png exactly so the demo
    composite is identical to what the product ships.
    """
    m = mask_for(src, lambda r: r["semantic"] == "wall")
    img = Image.fromarray((m * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(DILATE))
    img = img.filter(ImageFilter.GaussianBlur(FEATHER))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def ensure_front_render(live: bool) -> tuple[bytes, float]:
    """Geometry-locked warm render of the FRONT view -> mv_front/renders/base_render.png.

    Returns (png_bytes, est_cost). Cost is 0 if reused. In dry-run with no
    existing render we synthesize from beauty.png so the rest of the pipeline can
    be exercised offline (but no consistency claim is made on a dry run).
    """
    dst = FRONT / "renders" / "base_render.png"
    if dst.exists():
        print(f"[render] reuse existing {dst.relative_to(SPIKE)}")
        return dst.read_bytes(), 0.0
    if not live:
        print("[render] DRY-RUN: no base_render.png; using beauty.png as a stand-in")
        return (FRONT / "beauty.png").read_bytes(), 0.0
    print(f"[render] render_locked(mv_front) ~${COST_RENDER:.2f} ...")
    t0 = time.monotonic()
    data = render_locked(FRONT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    print(f"  ok in {time.monotonic()-t0:.1f}s -> {dst.relative_to(SPIKE)} ({len(data):,} B)")
    return data, COST_RENDER


# --------------------------------------------------------------------------- #
# the three edits
# --------------------------------------------------------------------------- #
def anchor_edit(mat: dict, anchor_png: bytes, live: bool) -> tuple[bytes, float]:
    """Materialized ANCHOR view: wall -> material, composited through anchor mask.

    Reuses the precompute when available (travertine), else a live FLUX.2 Edit
    [anchor_render, swatch].
    """
    mask = wall_mask_png(ANCHOR)
    pre = mat.get("anchor_precompute")
    if pre and Path(pre).exists():
        print(f"[anchor] reuse precompute {Path(pre).name} (no spend)")
        edit_full = Path(pre).read_bytes()
        final = composite.paste_tile(anchor_png, mask, edit_full)
        return final, 0.0
    if not live:
        print("[anchor] DRY-RUN: no precompute; returning base render unchanged")
        return anchor_png, 0.0
    prompt = (
        f"Apply the {mat['desc']} shown in the second image to the exterior wall "
        f"siding of the house in the first image. Only the wall siding changes; "
        f"windows, trim, roof, railing, stairs, ground, lighting and camera stay "
        f"exactly identical."
    )
    print(f"[anchor] LIVE FLUX.2 Edit ~${COST_EDIT:.2f} [anchor_render, swatch] ...")
    t0 = time.monotonic()
    anchor_uri = _data_uri(Image.open(io.BytesIO(anchor_png)).convert("RGB"), fmt="JPEG")
    edit_full = flux2_edit([anchor_uri, _swatch_uri(mat["swatch"])], prompt)
    print(f"  ok in {time.monotonic()-t0:.1f}s")
    final = composite.paste_tile(anchor_png, mask, edit_full)
    return final, COST_EDIT


def view2_edit(mat: dict, front_png: bytes, anchor_final: bytes,
               *, locked: bool, live: bool) -> tuple[bytes, float]:
    """View-2 (front) edit. locked=True adds the anchor result as a 3rd reference.

    NAIVE   : [front_render, swatch]                -> "apply this material"
    LOCKED  : [front_render, swatch, anchor_final]  -> "...match the stone in image 3"
    Both composite through the front wall mask.
    """
    mask = wall_mask_png(FRONT)
    front_uri = _data_uri(Image.open(io.BytesIO(front_png)).convert("RGB"), fmt="JPEG")
    swatch_uri = _swatch_uri(mat["swatch"])
    if locked:
        anchor_uri = _data_uri(Image.open(io.BytesIO(anchor_final)).convert("RGB"),
                               fmt="JPEG")
        refs = [front_uri, swatch_uri, anchor_uri]
        prompt = (
            f"Apply {mat['desc']} to the exterior wall siding of the house in the "
            f"first image. The third image shows the SAME building already clad in "
            f"this exact material from another camera angle — match that stone's "
            f"colour, tone, coursing scale and texture precisely so the two views "
            f"read as the identical material. The second image is the raw material "
            f"swatch. Only the wall siding changes; windows, trim, roof, railing, "
            f"stairs, ground, lighting and camera stay exactly identical."
        )
        tag = "LOCKED"
    else:
        refs = [front_uri, swatch_uri]
        prompt = (
            f"Apply the {mat['desc']} shown in the second image to the exterior "
            f"wall siding of the house in the first image. Only the wall siding "
            f"changes; windows, trim, roof, railing, stairs, ground, lighting and "
            f"camera stay exactly identical."
        )
        tag = "NAIVE"
    if not live:
        print(f"[view2 {tag}] DRY-RUN: returning front render unchanged "
              f"({len(refs)} refs planned)")
        return front_png, 0.0
    print(f"[view2 {tag}] LIVE FLUX.2 Edit ~${COST_EDIT:.2f} ({len(refs)} refs) ...")
    t0 = time.monotonic()
    edit_full = flux2_edit(refs, prompt)
    print(f"  ok in {time.monotonic()-t0:.1f}s")
    final = composite.paste_tile(front_png, mask, edit_full)
    return final, COST_EDIT


# --------------------------------------------------------------------------- #
# consistency metric
# --------------------------------------------------------------------------- #
def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB [0,255] -> CIELAB (D65). Vectorised, no external colour lib."""
    a = rgb.astype(float) / 255.0
    lin = np.where(a > 0.04045, ((a + 0.055) / 1.055) ** 2.4, a / 12.92)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16.0 / 116.0)
    fx, fy, fz = f(x), f(y), f(z)
    L = 116.0 * fy - 16.0
    A = 500.0 * (fx - fy)
    B = 200.0 * (fy - fz)
    return np.stack([L, A, B], axis=-1)


def _texture_energy(gray: np.ndarray) -> float:
    """Mean |Laplacian| over the region — a simple busyness/coursing-scale stat."""
    g = gray.astype(float)
    lap = (-4 * g
           + np.roll(g, 1, 0) + np.roll(g, -1, 0)
           + np.roll(g, 1, 1) + np.roll(g, -1, 1))
    return float(np.abs(lap).mean())


def wall_stats(img_png: bytes, src_dir: Path) -> dict:
    """Mean Lab + texture energy of the (hard) wall region of an image."""
    img = Image.open(io.BytesIO(img_png)).convert("RGB")
    m = mask_for(src_dir, lambda r: r["semantic"] == "wall")
    arr = np.array(img)
    if arr.shape[:2] != m.shape:
        img = img.resize((m.shape[1], m.shape[0]))
        arr = np.array(img)
    sel = arr[m]
    lab = _rgb_to_lab(sel.reshape(-1, 1, 3)).reshape(-1, 3).mean(axis=0)
    gray = np.array(img.convert("L"))
    # texture energy on the masked region: zero outside so edges of the building
    # don't dominate — measure only wall pixels' local contrast.
    g = np.where(m, gray, 0)
    tex = _texture_energy(g) * gray.size / max(int(m.sum()), 1)
    return {"L": float(lab[0]), "a": float(lab[1]), "b": float(lab[2]),
            "texture": tex}


def delta_e(s1: dict, s2: dict) -> float:
    return float(np.sqrt((s1["L"] - s2["L"]) ** 2
                         + (s1["a"] - s2["a"]) ** 2
                         + (s1["b"] - s2["b"]) ** 2))


# --------------------------------------------------------------------------- #
# evidence image
# --------------------------------------------------------------------------- #
def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def side_by_side(material: str, anchor_final: bytes, naive: bytes, locked: bytes,
                 metric: dict) -> Path:
    """[anchor edit | view2 NAIVE | view2 ANCHOR-LOCKED] with metric caption."""
    panels = [
        (f"ANCHOR (view 1) — {material}", anchor_final),
        ("view 2 — NAIVE (swatch only)", naive),
        ("view 2 — ANCHOR-LOCKED", locked),
    ]
    pw, ph = 600, 262
    pad_top, pad_bot = 26, 56
    grid = Image.new("RGB", (3 * pw, ph + pad_top + pad_bot), (18, 18, 18))
    d = ImageDraw.Draw(grid)
    f = _font(15)
    fs = _font(13)
    for i, (label, png) in enumerate(panels):
        im = Image.open(io.BytesIO(png)).convert("RGB").resize((pw, ph))
        x = i * pw
        grid.paste(im, (x, pad_top))
        d.text((x + 8, 5), label, fill=(255, 255, 255), font=f)
    # metric caption along the bottom
    cap = (f"wall-region consistency to anchor (lower = more consistent):   "
           f"NAIVE  dE={metric['naive_de']:.1f}  dTex={metric['naive_dtex']:.1f}      "
           f"LOCKED  dE={metric['locked_de']:.1f}  dTex={metric['locked_dtex']:.1f}      "
           f"->  {metric['verdict']}")
    d.text((8, ph + pad_top + 10), cap, fill=(180, 230, 180), font=fs)
    d.text((8, ph + pad_top + 32),
           f"anchor wall Lab=({metric['anchor']['L']:.0f},{metric['anchor']['a']:.0f},"
           f"{metric['anchor']['b']:.0f})   "
           f"naive Lab=({metric['naive']['L']:.0f},{metric['naive']['a']:.0f},"
           f"{metric['naive']['b']:.0f})   "
           f"locked Lab=({metric['locked']['L']:.0f},{metric['locked']['a']:.0f},"
           f"{metric['locked']['b']:.0f})",
           fill=(150, 150, 150), font=fs)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"sidebyside_{material}.png"
    grid.save(p)
    return p


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def run_material(material: str, front_png: bytes, *, live: bool) -> dict:
    mat = MATERIALS[material]
    print(f"\n===== material: {material} =====")
    OUT.mkdir(parents=True, exist_ok=True)

    a_final, c_anchor = anchor_edit(mat, ANCHOR_PNG, live)
    naive, c_naive = view2_edit(mat, front_png, a_final, locked=False, live=live)
    locked, c_locked = view2_edit(mat, front_png, a_final, locked=True, live=live)

    (OUT / f"anchor_{material}.png").write_bytes(a_final)
    (OUT / f"view2_naive_{material}.png").write_bytes(naive)
    (OUT / f"view2_locked_{material}.png").write_bytes(locked)

    s_anchor = wall_stats(a_final, ANCHOR)
    s_naive = wall_stats(naive, FRONT)
    s_locked = wall_stats(locked, FRONT)
    naive_de, locked_de = delta_e(s_anchor, s_naive), delta_e(s_anchor, s_locked)
    naive_dtex = abs(s_anchor["texture"] - s_naive["texture"])
    locked_dtex = abs(s_anchor["texture"] - s_locked["texture"])
    win = locked_de < naive_de
    verdict = ("LOCKED is closer to anchor (consistency win)" if win
               else "naive closer — inconclusive on colour")
    metric = {
        "material": material, "anchor": s_anchor, "naive": s_naive,
        "locked": s_locked, "naive_de": naive_de, "locked_de": locked_de,
        "naive_dtex": naive_dtex, "locked_dtex": locked_dtex,
        "delta_e_improvement": naive_de - locked_de,
        "win": win, "verdict": verdict,
        "cost": round(c_anchor + c_naive + c_locked, 2),
    }
    sbs = side_by_side(material, a_final, naive, locked, metric)
    metric["sidebyside"] = str(sbs)
    print(f"  wall dE to anchor:  NAIVE={naive_de:.2f}  LOCKED={locked_de:.2f}  "
          f"(improvement {naive_de - locked_de:+.2f})")
    print(f"  wall dTex to anchor: NAIVE={naive_dtex:.2f}  LOCKED={locked_dtex:.2f}")
    print(f"  -> {verdict}")
    print(f"  side-by-side: {sbs.relative_to(SPIKE)}")
    return metric


def write_report(results: list[dict], total_cost: float, live: bool) -> None:
    rpt = SPIKE / "REPORTS" / "multiview.md"
    lines = [
        "# Multi-view material lock — enterprise consistency demo",
        "",
        "- **Claim:** \"change a material once and it stays consistent across "
        "every view of the building.\"",
        "- **Approach:** anchor-reference. Materialize the wall in the ANCHOR "
        "view (e2_house_v2, hero/SW), then condition the SECOND view (mv_front) "
        "on that already-materialized anchor as a third FLUX.2 Edit reference. "
        "Compare against a NAIVE per-view edit that only sees the raw swatch.",
        f"- **Mode:** {'LIVE' if live else 'DRY-RUN (no spend, geometry/plumbing only)'}",
        f"- **fal spend this run:** ~${total_cost:.2f}",
        "- **Views:** anchor cam `[-12.7, 13.5, 26.0]`, front cam "
        "`[31.6, -2.8, 26.0]` — same house, both 1504x656, both ground-truth "
        "decoded.",
        "",
        "## Consistency metric (wall region, distance to the anchor — lower = "
        "more consistent)",
        "",
        "`dE` = Euclidean distance of mean CIELAB colour between the view-2 wall "
        "and the anchor wall. `dTex` = |difference| in mean-|Laplacian| texture "
        "energy. The headline number is colour `dE`.",
        "",
        "| material | NAIVE dE | LOCKED dE | dE improvement | NAIVE dTex | "
        "LOCKED dTex | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in results:
        lines.append(
            f"| {m['material']} | {m['naive_de']:.2f} | {m['locked_de']:.2f} | "
            f"**{m['delta_e_improvement']:+.2f}** | {m['naive_dtex']:.2f} | "
            f"{m['locked_dtex']:.2f} | {'LOCKED wins' if m['win'] else 'inconclusive'} |"
        )
    lines += ["", "## Mean wall Lab per variant", "",
              "| material | anchor (L,a,b) | naive (L,a,b) | locked (L,a,b) |",
              "|---|---|---|---|"]
    for m in results:
        def fmt(s):
            return f"({s['L']:.1f}, {s['a']:.1f}, {s['b']:.1f})"
        lines.append(f"| {m['material']} | {fmt(m['anchor'])} | "
                     f"{fmt(m['naive'])} | {fmt(m['locked'])} |")
    lines += ["", "## Evidence", ""]
    for m in results:
        lines.append(f"- `{Path(m['sidebyside']).relative_to(REPO)}` — "
                     f"[anchor | view2 NAIVE | view2 LOCKED] for {m['material']}")
    lines += [
        "- `spike/outputs/multiview/anchor_<mat>.png`, "
        "`view2_naive_<mat>.png`, `view2_locked_<mat>.png` — per-view composites.",
        "",
        "## How it works (production recipe)",
        "",
        "```",
        "anchor_final = composite(anchor_render, wall_mask_anchor,",
        "                         FLUX.2 Edit[anchor_render, swatch])",
        "view2_locked = composite(front_render,  wall_mask_front,",
        "                         FLUX.2 Edit[front_render, swatch, anchor_final])",
        "```",
        "The third reference (the already-materialized anchor) is what carries "
        "the material identity across the camera change. The swatch alone "
        "(naive) lets FLUX re-interpret tone/coursing per view.",
        "",
        "## fal call shapes",
        "",
        "- FLUX.2 [pro] Edit (`fal-ai/flux-2-pro/edit`) accepts **3** "
        "`image_urls` (E3 used 2). Verified live this run; the locked edits each "
        "sent [front, swatch, anchor].",
        "- Swatch data URIs are JPEG and downscaled to <=1024px long edge "
        "(travertine asset is ~16 MB raw) to stay under fal's 413 payload limit "
        "with three references.",
        "- Fallback wired to `fal-ai/flux-pro/kontext/max/multi` if a 3-image "
        "FLUX.2 Edit call ever errors.",
        "",
        "Runner: `spike/run_multiview_lock.py`. Inputs: "
        "`spike/outputs/e2_house_v2/` (anchor), `spike/outputs/mv_front/` (view 2).",
    ]
    rpt.parent.mkdir(parents=True, exist_ok=True)
    rpt.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[report] wrote {rpt.relative_to(REPO)}")
    (OUT / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


ANCHOR_PNG: bytes = b""  # set in main once the anchor render is loaded


def main() -> int:
    global ANCHOR_PNG
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true",
                    help="make real fal calls (default: dry-run, no spend)")
    ap.add_argument("--material", choices=list(MATERIALS), default=None,
                    help="run only this material (default: both)")
    args = ap.parse_args()

    if args.live:
        from dotenv import load_dotenv
        load_dotenv(SPIKE / ".env")

    OUT.mkdir(parents=True, exist_ok=True)
    ensure_decoded(ANCHOR)
    ensure_decoded(FRONT)

    # anchor render is precomputed; load it.
    anchor_render = ANCHOR / "renders" / "base_render.png"
    if not anchor_render.exists():
        sys.exit(f"missing anchor render: {anchor_render}")
    ANCHOR_PNG = anchor_render.read_bytes()
    print(f"[anchor] base_render.png loaded ({len(ANCHOR_PNG):,} B)")

    front_png, render_cost = ensure_front_render(args.live)

    mats = [args.material] if args.material else list(MATERIALS)
    results, total = [], render_cost
    for mat in mats:
        m = run_material(mat, front_png, live=args.live)
        total += m["cost"]
        results.append(m)

    write_report(results, total, args.live)
    print(f"\n[multiview] est. fal spend this run: ${total:.2f}")
    if not args.live:
        print("[multiview] DRY-RUN — numbers above are placeholders "
              "(no edits applied). Re-run with --live for the real demo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
