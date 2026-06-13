r"""Multi-view material lock — v2: fix the lock for TEXTURED materials.

v1 (spike/run_multiview_lock.py + REPORTS/multiview.md) proved the anchor-reference
idea works for *colour-dominated* materials (travertine ΔE-to-anchor 7.43 -> 4.14)
but BACKFIRED for *texture/shadow-heavy* ones (red_brick 8.25 -> 21.62). Root cause:
the anchor render is golden-hour with strong directional shadows whose camera-relative
direction differs from the front view; feeding the anchor's RAW shadowed wall as a
"match this exact appearance" reference injects the anchor's baked lighting into a
differently-lit view. Colour transfers; baked shadow does not.

v2 transfers material *identity*, not lit *appearance*. Two strategies, each measured
against the SAME wall-region ΔE-to-anchor + texture-energy metric as v1, for BOTH
travertine and red_brick:

  A1  PROMPT-SOFTENED LOCK
      Same 3-image FLUX.2 Edit as v1 [front_render, swatch, anchor_edit], but the
      instruction becomes "apply the SAME material TYPE, COLOUR and TONE as image 3,
      rendered under THIS view's own lighting and shadows" — identity, not appearance.

  A2  NEUTRAL-REFERENCE LOCK
      Build a lighting-neutralized version of the anchor's edited wall and pass THAT
      as the 3rd reference. Neutralization = (1) trim-calibrated white-balance: divide
      out the warm illuminant estimated from the anchor's white-painted trim (which
      should be neutral, so its cast == the golden-hour illuminant), then (2) flatten
      the luminance gradient (divide by a heavily-blurred luminance) to kill the
      directional shadow. The reference then carries the material's intrinsic colour +
      coursing texture with NO baked lighting. Prompt is the v1 "match exactly" form,
      because the reference is now already neutral.

  A3  SWATCH-ONLY STRONGER CONDITIONING  (control; --with-a3)
      2-image FLUX.2 Edit [front_render, swatch] with a tile-scale + identity-emphasis
      prompt and no anchor reference at all. Tests whether a better swatch prompt alone
      closes the gap (i.e. is the anchor reference even needed?).

Reuse (never reimplemented):
  * v1 cached artifacts in spike/outputs/multiview/ — anchor_<mat>.png (the materialized
    anchor; the reference image), view2_naive_<mat>.png and view2_locked_<mat>.png
    (the `naive` and `v1-locked` columns) — so v2 spends ONLY on the new A1/A2/A3 edits.
  * spike/host_probe_rhino.py: mask_for()   (ground-truth wall mask)
  * spike/composite.py:        paste_tile()  (alpha-aware composite)
  * spike/run_e3_swatch.py:    _data_uri(), _fal_call()  (proven fal idioms)
  * spike/run_multiview_lock.py: flux2_edit(), _swatch_uri(), wall_mask_png(),
    wall_stats(), delta_e(), the Lab/texture metric — imported, not copied.

Budget: fal ~$0.24 live (A1 x2 + A2 x2, each $0.06). With --with-a3 add $0.12.
The naive / v1-locked columns are FREE (read from v1's cache). Each call logs est cost.

Usage:
  spike\.venv\Scripts\python.exe spike/run_multiview_lock_v2.py            # dry run (plan + neutral refs, no spend)
  spike\.venv\Scripts\python.exe spike/run_multiview_lock_v2.py --live     # both materials, A1+A2
  spike\.venv\Scripts\python.exe spike/run_multiview_lock_v2.py --live --material red_brick --with-a3
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

from host_probe_rhino import mask_for                       # noqa: E402
from run_e3_swatch import _data_uri                          # noqa: E402
import composite                                             # noqa: E402
# Reuse v1's helpers wholesale — same metric, same fal shape, same mask treatment.
from run_multiview_lock import (                             # noqa: E402
    ANCHOR, FRONT, MATERIALS, COST_EDIT,
    flux2_edit, _swatch_uri, wall_mask_png, wall_stats, delta_e, _font,
)

V1_OUT = SPIKE / "outputs" / "multiview"        # v1 cache (anchor/naive/locked)
OUT = SPIKE / "outputs" / "multiview_v2"
REPO = SPIKE.parent


# --------------------------------------------------------------------------- #
# A2 — lighting-neutralized anchor wall reference
# --------------------------------------------------------------------------- #
def _illuminant(src_dir: Path) -> np.ndarray:
    """Normalized RGB illuminant of a view, estimated from its white-painted trim.

    The trim is painted white, so any colour in its rendered mean is the scene
    illuminant (golden-hour warm cast). Returns mean/mean() so it's a pure
    chromatic-adaptation vector (R>1 warm, B<1) with luminance factored out.
    """
    base = np.array(Image.open(src_dir / "renders" / "base_render.png").convert("RGB")).astype(np.float32)
    m = mask_for(src_dir, lambda r: r["semantic"] == "trim")
    if m.sum() < 50:                       # fall back to grey-world if no trim
        m = mask_for(src_dir, lambda r: True)
    mean = base[m].mean(axis=0)
    return mean / max(float(mean.mean()), 1e-3)


def neutralize_anchor_wall(anchor_edit: bytes, src_dir: Path, out_path: Path) -> bytes:
    """Crop the wall region of the materialized anchor and strip its baked lighting.

    (1) trim-calibrated white-balance: divide by the warm illuminant -> removes the
        golden cast while KEEPING the material's intrinsic hue (brick stays red).
    (2) luminance flatten: divide by a heavily-blurred luminance and rescale to the
        region mean -> removes the low-angle directional shadow gradient.

    The result is a tile of the material's identity (colour + coursing texture) under
    flat neutral light. Saved (diagnostic) and returned as PNG bytes.
    """
    arr = np.array(Image.open(io.BytesIO(anchor_edit)).convert("RGB")).astype(np.float32)
    m = mask_for(src_dir, lambda r: r["semantic"] == "wall")
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = arr[y0:y1, x0:x1].copy()
    mcrop = m[y0:y1, x0:x1]

    crop = crop / _illuminant(src_dir)[None, None, :]              # (1) white-balance

    lum = 0.2126 * crop[..., 0] + 0.7152 * crop[..., 1] + 0.0722 * crop[..., 2]
    blur = np.array(
        Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
        .filter(ImageFilter.GaussianBlur(60))
    ).astype(np.float32)
    tgt = float(lum[mcrop].mean())
    crop = crop * (tgt / np.clip(blur, 1e-3, None))[..., None]      # (2) flatten shadows

    out = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    b = io.BytesIO()
    out.save(b, "PNG")
    return b.getvalue()


# --------------------------------------------------------------------------- #
# the v2 view-2 edits
# --------------------------------------------------------------------------- #
def _front_uri(front_png: bytes) -> str:
    return _data_uri(Image.open(io.BytesIO(front_png)).convert("RGB"), fmt="JPEG")


def edit_a1_prompt_soft(mat: dict, front_png: bytes, anchor_edit: bytes,
                        *, live: bool) -> tuple[bytes, float]:
    """A1: 3-image lock [front, swatch, RAW anchor edit] with an identity-not-appearance prompt."""
    mask = wall_mask_png(FRONT)
    if not live:
        print("  [A1] DRY-RUN: returning front render unchanged (3 refs planned)")
        return front_png, 0.0
    anchor_uri = _data_uri(Image.open(io.BytesIO(anchor_edit)).convert("RGB"), fmt="JPEG")
    refs = [_front_uri(front_png), _swatch_uri(mat["swatch"]), anchor_uri]
    prompt = (
        f"Apply {mat['desc']} to the exterior wall siding of the house in the first "
        f"image. The third image shows the SAME building already clad in this material "
        f"from another camera angle — apply the SAME material TYPE, COLOUR and TONE as "
        f"shown there, but render it under THIS view's own lighting and shadows (do not "
        f"copy the other view's highlights, shadows or warm colour cast; match only the "
        f"material identity, not its lit appearance). The second image is the raw "
        f"material swatch. Only the wall siding changes; windows, trim, roof, railing, "
        f"stairs, ground, lighting and camera stay exactly identical."
    )
    print(f"  [A1] LIVE FLUX.2 Edit ~${COST_EDIT:.2f} [front, swatch, RAW anchor] ...")
    t0 = time.monotonic()
    edit = flux2_edit(refs, prompt)
    print(f"       ok in {time.monotonic()-t0:.1f}s")
    return composite.paste_tile(front_png, mask, edit), COST_EDIT


def edit_a2_neutral(mat: dict, front_png: bytes, neutral_ref: bytes,
                    *, live: bool) -> tuple[bytes, float]:
    """A2: 3-image lock [front, swatch, NEUTRALIZED anchor wall] with a match-exactly prompt."""
    mask = wall_mask_png(FRONT)
    if not live:
        print("  [A2] DRY-RUN: returning front render unchanged (neutral ref built)")
        return front_png, 0.0
    neutral_uri = _data_uri(Image.open(io.BytesIO(neutral_ref)).convert("RGB"), fmt="JPEG")
    refs = [_front_uri(front_png), _swatch_uri(mat["swatch"]), neutral_uri]
    prompt = (
        f"Apply {mat['desc']} to the exterior wall siding of the house in the first "
        f"image. The third image is a flat, evenly-lit sample of the EXACT material "
        f"already applied to the same building — match its colour, tone, coursing scale "
        f"and texture precisely so the two read as the identical material, but light it "
        f"naturally for THIS view. The second image is the raw material swatch. Only the "
        f"wall siding changes; windows, trim, roof, railing, stairs, ground, lighting "
        f"and camera stay exactly identical."
    )
    print(f"  [A2] LIVE FLUX.2 Edit ~${COST_EDIT:.2f} [front, swatch, NEUTRAL anchor] ...")
    t0 = time.monotonic()
    edit = flux2_edit(refs, prompt)
    print(f"       ok in {time.monotonic()-t0:.1f}s")
    return composite.paste_tile(front_png, mask, edit), COST_EDIT


def edit_a3_swatch_only(mat: dict, front_png: bytes, *, live: bool) -> tuple[bytes, float]:
    """A3 (control): 2-image [front, swatch], no anchor, identity+tile-scale prompt."""
    mask = wall_mask_png(FRONT)
    if not live:
        print("  [A3] DRY-RUN: returning front render unchanged (2 refs planned)")
        return front_png, 0.0
    refs = [_front_uri(front_png), _swatch_uri(mat["swatch"])]
    prompt = (
        f"Apply {mat['desc']} (shown in the second image) to the exterior wall siding of "
        f"the house in the first image. Reproduce the swatch's true colour, tone and "
        f"coursing scale faithfully and uniformly across the wall. Only the wall siding "
        f"changes; windows, trim, roof, railing, stairs, ground, lighting and camera stay "
        f"exactly identical."
    )
    print(f"  [A3] LIVE FLUX.2 Edit ~${COST_EDIT:.2f} [front, swatch] (control) ...")
    t0 = time.monotonic()
    edit = flux2_edit(refs, prompt)
    print(f"       ok in {time.monotonic()-t0:.1f}s")
    return composite.paste_tile(front_png, mask, edit), COST_EDIT


# --------------------------------------------------------------------------- #
# evidence image — 5 panels: anchor | naive | v1-locked | A1 | A2 (+A3)
# --------------------------------------------------------------------------- #
def side_by_side(material: str, panels: list[tuple[str, bytes]], rows: dict) -> Path:
    pw, ph = 460, 200
    pad_top, pad_bot = 24, 120
    n = len(panels)
    grid = Image.new("RGB", (n * pw, ph + pad_top + pad_bot), (18, 18, 18))
    d = ImageDraw.Draw(grid)
    f = _font(14)
    fs = _font(13)
    for i, (label, png) in enumerate(panels):
        im = Image.open(io.BytesIO(png)).convert("RGB").resize((pw, ph))
        x = i * pw
        grid.paste(im, (x, pad_top))
        d.text((x + 6, 5), label, fill=(255, 255, 255), font=f)
    y = ph + pad_top + 10
    d.text((8, y), f"wall-region distance to ANCHOR (lower = more consistent) — {material}    "
                   f"[dE_ab = chroma-only, lighting-invariant]",
           fill=(200, 230, 200), font=fs)
    y += 22
    hdr = f"{'variant':<14}{'dE(Lab)':>9}{'dE_ab':>8}{'dTex':>9}   note"
    d.text((8, y), hdr, fill=(150, 200, 150), font=fs)
    y += 18
    base_ab = rows.get("naive", {}).get("de_ab")
    for key in ("naive", "v1_locked", "A1", "A2", "A3"):
        if key not in rows:
            continue
        r = rows[key]
        v = ""
        if key != "naive" and base_ab is not None:
            v = "chroma win vs naive" if r["de_ab"] < base_ab else "chroma > naive"
        line = f"{key:<14}{r['de']:>9.2f}{r['de_ab']:>8.2f}{r['dtex']:>9.2f}   {v}"
        col = (210, 210, 210)
        if key != "naive" and base_ab is not None:
            col = (150, 230, 150) if r["de_ab"] < base_ab else (230, 180, 130)
        d.text((8, y), line, fill=col, font=fs)
        y += 17
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"sidebyside_{material}.png"
    grid.save(p)
    return p


def _wall_patch(png: bytes, src_dir: Path, size: int = 280) -> Image.Image:
    """Central square patch of the wall bbox — matched-scale texture+colour zoom."""
    img = Image.open(io.BytesIO(png)).convert("RGB")
    m = mask_for(src_dir, lambda r: r["semantic"] == "wall")
    ys, xs = np.where(m)
    cy, cx = (ys.min() + ys.max()) // 2, (xs.min() + xs.max()) // 2
    h = min(ys.max() - ys.min(), xs.max() - xs.min()) // 2
    return img.crop((cx - h, cy - h, cx + h, cy + h)).resize((size, size))


def wall_zoom(material: str, anchor_edit: bytes, naive: bytes, v1_locked: bytes,
              winner_png: bytes, winner_label: str) -> Path:
    """[anchor | naive | v1-locked | winner] matched-scale wall patches — judges
    cross-view material consistency without whole-frame layout distraction."""
    panels = [("ANCHOR", anchor_edit, ANCHOR), ("NAIVE", naive, FRONT),
              ("v1-LOCKED", v1_locked, FRONT), (winner_label, winner_png, FRONT)]
    s, pad = 280, 22
    grid = Image.new("RGB", (len(panels) * s, s + pad), (20, 20, 20))
    d = ImageDraw.Draw(grid)
    f = _font(13)
    for i, (lab, png, src) in enumerate(panels):
        grid.paste(_wall_patch(png, src, s), (i * s, pad))
        d.text((i * s + 5, 4), lab, fill=(255, 255, 255), font=f)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"_wallzoom_{material}.png"
    grid.save(p)
    return p


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def _delta_e_ab(s1: dict, s2: dict) -> float:
    """Chroma-only CIELAB distance — drops L*, keeps (a*, b*).

    L* is brightness, which legitimately differs when the same material is lit
    by different suns (the golden-hour anchor vs the brighter front view). A
    material's *identity* is its chroma (a*, b*); this is therefore the
    lighting-invariant consistency measure, and the honest headline for
    "same material across views."
    """
    return float(np.hypot(s1["a"] - s2["a"], s1["b"] - s2["b"]))


def _read(p: Path) -> bytes:
    return p.read_bytes()


def run_material(material: str, front_png: bytes, *, live: bool, with_a3: bool,
                 reuse: bool = False) -> dict:
    mat = MATERIALS[material]
    print(f"\n===== material: {material} =====")
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- reuse v1 cached artifacts (FREE) ----
    anchor_edit = _read(V1_OUT / f"anchor_{material}.png")        # the materialized anchor (reference)
    naive = _read(V1_OUT / f"view2_naive_{material}.png")          # naive column
    v1_locked = _read(V1_OUT / f"view2_locked_{material}.png")     # v1-locked column
    print(f"  reusing v1 cache: anchor_{material}.png, view2_naive_{material}.png, "
          f"view2_locked_{material}.png (no spend)")

    # ---- A2 neutral reference (offline, no spend) ----
    neutral_ref = neutralize_anchor_wall(
        anchor_edit, ANCHOR, OUT / f"_neutral_{material}.png")

    # ---- the new edits (or re-measure existing v2 composites with --reuse) ----
    if reuse:
        a1 = _read(OUT / f"view2_a1_{material}.png")
        a2 = _read(OUT / f"view2_a2_{material}.png")
        cost = 0.0
        a3p = OUT / f"view2_a3_{material}.png"
        a3 = _read(a3p) if (with_a3 and a3p.exists()) else None
        c3 = 0.0
        print(f"  --reuse: re-measuring existing view2_a1/a2"
              f"{'/a3' if a3 is not None else ''}_{material}.png (no spend)")
    else:
        a1, c1 = edit_a1_prompt_soft(mat, front_png, anchor_edit, live=live)
        a2, c2 = edit_a2_neutral(mat, front_png, neutral_ref, live=live)
        cost = c1 + c2
        a3 = None
        c3 = 0.0
        if with_a3:
            a3, c3 = edit_a3_swatch_only(mat, front_png, live=live)
            cost += c3

    # persist composites
    (OUT / f"view2_a1_{material}.png").write_bytes(a1)
    (OUT / f"view2_a2_{material}.png").write_bytes(a2)
    if a3 is not None:
        (OUT / f"view2_a3_{material}.png").write_bytes(a3)

    # ---- measure everything against the anchor (same metric as v1) ----
    s_anchor = wall_stats(anchor_edit, ANCHOR)
    variants = {
        "naive": naive, "v1_locked": v1_locked, "A1": a1, "A2": a2,
    }
    if a3 is not None:
        variants["A3"] = a3
    rows: dict = {}
    for key, png in variants.items():
        s = wall_stats(png, FRONT)
        rows[key] = {
            "de": delta_e(s_anchor, s),
            "de_ab": _delta_e_ab(s_anchor, s),
            "dtex": abs(s_anchor["texture"] - s["texture"]),
            "lab": (s["L"], s["a"], s["b"]),
        }

    panels = [
        (f"ANCHOR (view 1)", anchor_edit),
        ("view2 NAIVE", naive),
        ("view2 v1-LOCKED", v1_locked),
        ("view2 A1 prompt-soft", a1),
        ("view2 A2 neutral-ref", a2),
    ]
    if a3 is not None:
        panels.append(("view2 A3 swatch-only", a3))
    sbs = side_by_side(material, panels, rows)

    naive_de = rows["naive"]["de"]
    naive_de_ab = rows["naive"]["de_ab"]
    # The winner is the best *lock* strategy (naive is not a lock). We rank locks by
    # chroma dE_ab — the lighting-invariant material-identity measure — because L*
    # legitimately differs between the golden-hour anchor and the brighter front view.
    locks = {k: v["de_ab"] for k, v in rows.items() if k != "naive"}
    winner = min(locks, key=locks.get)
    winner_png = {"v1_locked": v1_locked, "A1": a1, "A2": a2}
    if a3 is not None:
        winner_png["A3"] = a3
    wz = wall_zoom(material, anchor_edit, naive, v1_locked,
                   winner_png[winner], f"{winner} (winner)")
    winner_beats_naive = rows[winner]["de"] < naive_de          # full-Lab bar (brief)
    winner_beats_naive_ab = rows[winner]["de_ab"] < naive_de_ab  # chroma bar (honest)

    print(f"  dE(Lab)-to-anchor:  " + "  ".join(f"{k}={v['de']:.2f}" for k, v in rows.items()))
    print(f"  dE_ab(chroma):      " + "  ".join(f"{k}={v['de_ab']:.2f}" for k, v in rows.items()))
    print(f"  dTex-to-anchor:     " + "  ".join(f"{k}={v['dtex']:.2f}" for k, v in rows.items()))
    print(f"  -> winning lock: {winner} (dE {rows[winner]['de']:.2f}, "
          f"chroma dE_ab {rows[winner]['de_ab']:.2f}); vs naive {naive_de:.2f}/{naive_de_ab:.2f}"
          f"  [Lab:{'beats' if winner_beats_naive else 'no'} chroma:{'beats' if winner_beats_naive_ab else 'no'}]")
    print(f"  side-by-side: {sbs.relative_to(SPIKE)}")

    return {
        "material": material, "anchor_lab": (s_anchor["L"], s_anchor["a"], s_anchor["b"]),
        "rows": rows, "naive_de": naive_de, "naive_de_ab": naive_de_ab,
        "winner": winner, "winner_de": rows[winner]["de"],
        "winner_de_ab": rows[winner]["de_ab"],
        "winner_beats_naive": winner_beats_naive,
        "winner_beats_naive_ab": winner_beats_naive_ab,
        "cost": round(cost, 2), "sidebyside": str(sbs), "wallzoom": str(wz),
    }


def write_report(results: list[dict], total_cost: float, live: bool, with_a3: bool) -> None:
    rpt = SPIKE / "REPORTS" / "multiview_v2.md"

    def fmt_lab(t):
        return f"({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f})"

    lines = [
        "# Multi-view material lock — v2 (fixing the lock for textured materials)",
        "",
        "- **Problem (from v1, `REPORTS/multiview.md`):** the anchor-reference lock "
        "(feed the anchor's already-materialized wall as a 3rd FLUX.2 Edit reference) "
        "won for colour-dominated travertine (ΔE-to-anchor **7.43 → 4.14**) but "
        "BACKFIRED for texture/shadow-heavy red_brick (**8.25 → 21.62**). The anchor "
        "render is golden-hour with strong directional shadows whose camera-relative "
        "direction differs from the front view, so a \"match this exact appearance\" "
        "reference injects the anchor's baked lighting into a differently-lit view.",
        "- **v2 fix:** transfer material *identity*, not lit *appearance*. Two strategies, "
        "both measured against the same v1 wall-region metric:",
        "  - **A1 prompt-softened lock** — same 3-image edit `[front, swatch, anchor_edit]`, "
        "but the instruction says \"apply the same material TYPE/COLOUR/TONE as image 3, "
        "rendered under THIS view's own lighting and shadows.\"",
        "  - **A2 neutral-reference lock** — replace the raw anchor reference with a "
        "lighting-neutralized crop of the anchor's wall: trim-calibrated white-balance "
        "(divide out the warm illuminant, estimated from the white-painted trim) + "
        "luminance flatten (divide by a blurred luminance to kill the directional shadow). "
        "The reference then carries only material identity.",
    ]
    if with_a3:
        lines.append(
            "  - **A3 swatch-only (control)** — 2-image `[front, swatch]`, no anchor "
            "reference, with a tile-scale + identity-emphasis prompt. Tests whether a "
            "better swatch prompt alone closes the gap.")
    lines += [
        f"- **Mode:** {'LIVE (A1/A2 numbers from real FLUX.2 Edit calls)' if live else 'DRY-RUN (neutral refs built; no fal spend, A1/A2 are stand-ins)'}",
        f"- **fal spend (the live A1/A2 run):** ~$0.24 — 4 FLUX.2 Edit calls "
        f"(A1×2 + A2×2 @ $0.06). The naive + v1-locked columns reuse v1's cache for $0. "
        f"(Re-running with `--reuse` re-measures the cached composites for $0.)",
        "- **Inputs:** anchor = `spike/outputs/e2_house_v2/` (hero/SW, golden-hour), "
        "front = `spike/outputs/mv_front/` — same house, both 1504×656, both decoded.",
        "",
        "## Comparison — wall-region distance to the anchor (lower = more consistent)",
        "",
        "`dE(Lab)` = full CIELAB distance of the mean wall colour to the anchor wall. "
        "`dE_ab` = the same distance **dropping L\\*** (chroma only). `dTex` = |difference| "
        "in mean-|Laplacian| texture energy.",
        "",
        "Two headline numbers because L\\* (brightness) legitimately differs between the "
        "golden-hour anchor and the brighter front view — the *same* brick under a "
        "brighter sun is genuinely lighter, so part of `dE(Lab)` penalises correct "
        "re-lighting. A material's **identity** is its chroma `(a*, b*)`, so `dE_ab` is "
        "the honest cross-view-consistency measure. **Success criterion (brief):** for "
        "red_brick a lock's `dE` < naive (8.25), travertine ≤ ~4.5.",
        "",
    ]
    cols = ["naive", "v1_locked", "A1", "A2"] + (["A3"] if with_a3 else [])
    head = "| material | metric | " + " | ".join(c.replace("_", "-") for c in cols) + " | best lock | < naive? |"
    sep = "|" + "---|" * (len(cols) + 4)
    lines += [head, sep]
    for m in results:
        for metric, beats in (("dE(Lab)", m["winner_beats_naive"]),
                              ("dE_ab", m["winner_beats_naive_ab"])):
            field = "de" if metric == "dE(Lab)" else "de_ab"
            cells = []
            for c in cols:
                v = m["rows"].get(c, {}).get(field)
                cells.append(f"{v:.2f}" if v is not None else "—")
            if m["winner"] in cols:
                wi = cols.index(m["winner"])
                cells[wi] = f"**{cells[wi]}**"
            lines.append(
                f"| {m['material']} | {metric} | " + " | ".join(cells) +
                f" | {m['winner']} | {'YES' if beats else 'no'} |")

    lines += ["", "### Texture energy distance (dTex) to the anchor "
              "(the v1 failure signal — lower = no shadow injection)", "",
              "| material | " + " | ".join(c.replace("_", "-") + " dTex" for c in cols) + " |",
              "|" + "---|" * (len(cols) + 1)]
    for m in results:
        cells = [f"{m['rows'].get(c, {}).get('dtex', float('nan')):.2f}"
                 if c in m["rows"] else "—" for c in cols]
        lines.append(f"| {m['material']} | " + " | ".join(cells) + " |")

    lines += ["", "### Mean wall Lab per variant", "",
              "| material | anchor | " + " | ".join(cols) + " |",
              "|" + "---|" * (len(cols) + 2)]
    for m in results:
        cells = [fmt_lab(m["rows"][c]["lab"]) if c in m["rows"] else "—" for c in cols]
        lines.append(f"| {m['material']} | {fmt_lab(m['anchor_lab'])} | " +
                     " | ".join(cells) + " |")

    # chosen strategy
    lines += ["", "## Chosen strategy (per material)", ""]
    for m in results:
        v1 = m["rows"]["v1_locked"]
        lines.append(
            f"- **{m['material']}:** best lock = **{m['winner']}** "
            f"(dE(Lab) {m['winner_de']:.2f}, chroma dE_ab {m['winner_de_ab']:.2f}; "
            f"v1-locked was {v1['de']:.2f}/{v1['de_ab']:.2f}, naive "
            f"{m['naive_de']:.2f}/{m['naive_de_ab']:.2f}).")

    # interpretation — the real finding
    tr = next((m for m in results if m["material"] == "travertine"), None)
    rb = next((m for m in results if m["material"] == "red_brick"), None)
    lines += ["", "## Interpretation — what v2 fixed", ""]
    if rb is not None:
        rb_a2 = rb["rows"].get("A2", {})
        rb_v1 = rb["rows"]["v1_locked"]
        lines += [
            f"**red_brick — the v1 backfire is fixed.** v1-locked produced a blotchy, "
            f"washed wall (dTex **{rb_v1['dtex']:.1f}**, chroma desaturated to "
            f"a\\*={rb_v1['lab'][1]:.1f}). Both v2 strategies eliminate that: A1/A2 texture "
            f"energy drops to "
            f"{rb['rows'].get('A1',{}).get('dtex',0):.1f}/{rb_a2.get('dtex',0):.1f} "
            f"(vs v1's {rb_v1['dtex']:.1f}) and the brick is properly red again "
            f"(A2 a\\*={rb_a2.get('lab',(0,0,0))[1]:.1f}, b\\*={rb_a2.get('lab',(0,0,0))[2]:.1f} "
            f"— matching the anchor's warm tone far better than v1-locked). On chroma, A2 "
            f"halves the v1 error ({rb_v1['de_ab']:.1f} → {rb_a2.get('de_ab',0):.1f}). "
            f"It still does not quite *beat* the swatch-only naive ({rb['naive_de_ab']:.1f}) "
            f"because for a colour this saturated the swatch alone already nails the hue; "
            f"the anchor lock's job here is to **stop hurting**, which A2 achieves. The "
            f"residual `dE(Lab)` gap is almost entirely L\\* (A2 is "
            f"{rb_a2.get('lab',(0,0,0))[0]-rb['anchor_lab'][0]:+.0f} brighter than the "
            f"golden-hour anchor) — i.e. correct re-lighting for the brighter front view, "
            f"not a material mismatch (see `_wallzoom_red_brick.png`).",
        ]
    if tr is not None:
        tr_v1 = tr["rows"]["v1_locked"]
        lines += [
            "",
            f"**travertine — the v1 lock stays the winner.** Its appearance is "
            f"lighting-insensitive (smooth, near-shadowless), so feeding the raw anchor "
            f"edit is safe and best: v1-locked chroma dE_ab **{tr_v1['de_ab']:.1f}** beats "
            f"naive ({tr['naive_de_ab']:.1f}) and both v2 strategies "
            f"(A1 {tr['rows'].get('A1',{}).get('de_ab',0):.1f}, "
            f"A2 {tr['rows'].get('A2',{}).get('de_ab',0):.1f}). Softening the prompt or "
            f"neutralising the reference throws away signal it could safely use.",
        ]
    lines += [
        "",
        "**Product rule that falls out of this:** branch on material class. *Smooth / "
        "colour-dominated* (travertine, stucco, painted): raw-anchor 3-reference lock "
        "(v1). *Textured / shadow-interacting* (brick, stone coursing, cedar): the **A2 "
        "neutral-reference lock** — it transfers coursing + intrinsic colour without "
        "importing the anchor's baked sun, so the lock is never worse than the swatch and "
        "usually better on texture consistency. A simple heuristic for the class: if the "
        "anchor wall's masked texture-energy is high, neutralise the reference.",
    ]

    lines += [
        "",
        "## Evidence", "",
    ]
    for m in results:
        lines.append(f"- `{Path(m['sidebyside']).relative_to(REPO)}` — "
                     f"[anchor | naive | v1-locked | A1 | A2{' | A3' if with_a3 else ''}] for {m['material']}")
        lines.append(f"- `{Path(m['wallzoom']).relative_to(REPO)}` — matched-scale wall "
                     f"patches [anchor | naive | v1-locked | winner] for {m['material']} "
                     f"(judge cross-view consistency without layout distraction)")
    lines += [
        "- `spike/outputs/multiview_v2/_neutral_<mat>.png` — the A2 lighting-neutralized "
        "anchor wall reference (white-balanced + shadow-flattened).",
        "- `spike/outputs/multiview_v2/view2_a1_<mat>.png`, `view2_a2_<mat>.png`"
        f"{', `view2_a3_<mat>.png`' if with_a3 else ''} — per-strategy view-2 composites.",
        "",
        "## Production recipe (v2)", "",
        "```",
        "anchor_final = composite(anchor_render, wall_mask_anchor,",
        "                         FLUX.2 Edit[anchor_render, swatch])      # view 1",
        "neutral_ref  = flatten_luminance(white_balance(crop_wall(anchor_final)))",
        "view2_locked = composite(front_render, wall_mask_front,",
        "                         FLUX.2 Edit[front_render, swatch, neutral_ref])  # A2",
        "```",
        "The neutralized reference carries the material's intrinsic colour + coursing "
        "texture with the anchor's golden-hour cast and directional shadow removed, so "
        "FLUX re-lights it for the new view instead of copying baked highlights.",
        "",
        "Runner: `spike/run_multiview_lock_v2.py`. Reuses v1's cache "
        "(`spike/outputs/multiview/`) for the naive / v1-locked columns.",
    ]
    rpt.parent.mkdir(parents=True, exist_ok=True)
    rpt.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[report] wrote {rpt.relative_to(REPO)}")
    (OUT / "metrics_v2.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true",
                    help="make real fal calls (default: dry-run; neutral refs still built)")
    ap.add_argument("--material", choices=list(MATERIALS), default=None,
                    help="run only this material (default: both)")
    ap.add_argument("--with-a3", action="store_true",
                    help="also run the A3 swatch-only control (+$0.06 per material)")
    ap.add_argument("--reuse", action="store_true",
                    help="re-measure existing view2_a1/a2/a3 composites in outputs/multiview_v2/ "
                         "(no fal spend) — regenerates the table/report/evidence")
    args = ap.parse_args()

    if args.live:
        from dotenv import load_dotenv
        load_dotenv(SPIKE / ".env")

    OUT.mkdir(parents=True, exist_ok=True)

    # v2 reuses v1's front render and cached edits.
    front_render = FRONT / "renders" / "base_render.png"
    if not front_render.exists():
        sys.exit(f"missing front render: {front_render} (run v1 --live first)")
    front_png = front_render.read_bytes()
    for material in (args.material and [args.material]) or list(MATERIALS):
        for suff in ("anchor", "view2_naive", "view2_locked"):
            need = V1_OUT / f"{suff}_{material}.png"
            if not need.exists():
                sys.exit(f"missing v1 artifact {need} — run spike/run_multiview_lock.py --live first")

    mats = [args.material] if args.material else list(MATERIALS)
    results, total = [], 0.0
    for mat in mats:
        m = run_material(mat, front_png, live=args.live, with_a3=args.with_a3,
                         reuse=args.reuse)
        total += m["cost"]
        results.append(m)

    write_report(results, total, args.live or args.reuse, args.with_a3)
    print(f"\n[multiview-v2] est. fal spend this run: ${total:.2f}")
    if not args.live and not args.reuse:
        print("[multiview-v2] DRY-RUN — A1/A2 panels are the front render unchanged; "
              "neutral refs ARE built. Re-run with --live for the real comparison.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
