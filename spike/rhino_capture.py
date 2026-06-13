"""Production Rhino-side capture for the Photoshop-for-Architects plugin tier.

Runs INSIDE Rhino's Python (Rhino 8 CPython) — via the Rhino MCP `run_python`
tool, the ScriptEditor, or (later) a GhPython component. Produces, under a
given output directory, the exact contract proven in E1/E2
(see spike/outputs/e2_house/ and spike/REPORTS/E1.md, E2.md):

  beauty.png      shaded viewport capture (the product's render input)
  depth.png       true z-buffer via Rhino.Display.ZBufferCapture (GrayscaleDib)
  light_pass.png  all objects pure white (white reference pass)
  id_mask.png     all objects flat ID colors (see encoding below)
  objects.json    {"encoding": {...}, "objects": {key -> {guid, layer,
                   semantic, object_type, material, name}}}
  camera.json     location/target/up, lens_35mm, frustum_raw, size_px,
                   projection, depth_meta {minZ, maxZ, hits}

Decode lives host-side in spike/host_probe_rhino.py (decode / mask_for).

THE PROVEN FLOW (do not reorder — every step is load-bearing, see E1 report):

1. Custom display mode "E1_IDMask" (copy of Shaded): LightingScheme=None
   (the enum type `Rhino.Display.LightingSchema` is not directly importable;
   parse the value from the current attribute's GetType), shadows off, all
   curve/annotation/text/point/iso/edge drawing off, DisableTransparency=True.
2. ALL passes captured ATOMICALLY in one script run — the hidden viewport can
   resize between separate MCP calls, silently misaligning the passes.
3. Grid/axes (vp.ConstructionGridVisible etc.) disabled or they pollute pixels.
4. ALL passes captured via view.CaptureToBitmap(size, mode) — beauty with the
   Shaded mode, white/ID with the E1_IDMask mode. The bare CaptureToBitmap(size)
   (no mode arg) does NOT re-render the viewport's current DisplayMode in a
   headless / Rhino-MCP session: it returns a stale default-lit frame, so the
   white pass comes back dim and decode collapses to ~0% on every capture after
   the first. The (size, mode) overload forces a real render and makes capture()
   idempotent across repeated calls in one session (no doc reopen). A foreground
   brightness gate on the white pass raises rather than ship a dim, undecodable
   capture. (Earlier E1 notes claimed the overload ignored mode attributes; that
   was not reproducible here — the overload is the reliable path. See REPORTS.)
5. Rendering transform (empirical): out_ch = 0.7*in_ch + base_ch(pixel), where
   base varies per pixel/channel with surface orientation. The white pass gives
   base_ch = white_ch - 178.5, making the ID decode exact and self-calibrating.
   DO NOT change this color encoding without updating host_probe_rhino.decode.

ID COLOR ENCODING:
  object index i  ->  r = 5*(i // 2704)
                      g = 5*((i % 2704) // 52)
                      b = 5*(i % 52)
  objects.json key: "g,b" when r == 0 (backward compatible with E1/E2 data),
  "r,g,b" when r > 0. The r-plane extension supports 52*2704 = 140,608 objects
  per frame; host_probe_rhino.decode handles both key forms.

SEMANTICS come from layer names via configurable rule sets:
  - "csi"     CSI MasterFormat layers (kCs_SampleHouseProject style:
              08-OPENINGS -> window/door, 06-02 -> wall, 06-04 -> roof, ...)
  - "keyword" plain keyword layers (SFUrban/Enscape style:
              MULLION/GLASS/DOOR/WALL/...)
  - "auto"    sniff the doc's layer names and pick (default)
  - or pass your own ordered [(PATTERN, semantic), ...] list (uppercase
    substring match against the full layer path, first match wins).

Usage inside Rhino (MCP run_python or ScriptEditor):

    src = open(r"C:\\...\\spike\\rhino_capture.py").read()
    ns = {"__rhino_doc__": __rhino_doc__}   # omit in ScriptEditor
    exec(compile(src, "rhino_capture.py", "exec"), ns)
    print(ns["capture"](r"C:\\...\\spike\\outputs\\my_capture"))

The module imports cleanly WITHOUT Rhino (for tests); only capture() requires
the Rhino runtime.
"""
from __future__ import annotations

import json
import re

try:  # Rhino runtime is optional at import time (tests import this module).
    import Rhino  # noqa: F401
    import System  # noqa: F401
    import System.Drawing  # noqa: F401

    HAVE_RHINO = True
except ImportError:
    HAVE_RHINO = False

# --------------------------------------------------------------------------
# ID color encoding (must match host_probe_rhino.decode)
# --------------------------------------------------------------------------
GRID = 5                      # channel spacing of ID colors
PLANE = 52 * 52               # 2704 objects per r-plane
MAX_OBJECTS = 52 * PLANE      # 140,608 with the r-plane extension

ENCODING_DOC = {
    "scheme": "r=5*(i//2704); g=5*((i%2704)//52); b=5*(i%52); "
              "key='g,b' when r==0 else 'r,g,b'",
    "render_transform": "out=0.7*in+base(px,ch); base=white_pass-178.5",
}

# --------------------------------------------------------------------------
# White-reference-pass health check (must agree with host_probe_rhino.decode)
# --------------------------------------------------------------------------
# The decode recovers per-pixel base = light_pass - 0.7*255 (=178.5) and then
# in = (id - base) / 0.7. For that to work, foreground (object) pixels in the
# white pass MUST render brighter than ~178.5; if they collapse toward the
# viewport background gray (~157-170) the base goes negative and NOTHING
# decodes. A healthy white pass has a foreground median ~190 (objects ~191,
# anti-aliased edges pull it down a little); a dim/stale pass sits at ~157.
# We gate on the foreground MEDIAN with a generous margin between the two.
BG_GRAY = (157.0, 163.0, 170.0)   # default Rhino viewport gray (== decoder BG)
BG_FG_TOL = 6                     # |px-BG| > this on max channel => foreground
WHITE_LEVEL = 0.7 * 255           # 178.5 — the decode's base offset
# A pass whose foreground median is below this can't be decoded. Good passes
# sit ~190, broken ones ~157, so 180 is a wide, unambiguous separator.
MIN_LIGHT_PASS_MEDIAN = 180.0


def light_pass_median_brightness(pixels, bg=BG_GRAY, bg_tol=BG_FG_TOL):
    """Median brightness (max channel) of FOREGROUND pixels.

    Pure python — no numpy/PIL/Rhino — so it is unit-testable with synthetic
    pixel lists and also callable inside Rhino on sampled bitmap pixels.

    pixels   iterable of (r, g, b) — a (sub)sample of the light_pass image.
    bg       viewport background color; a pixel is foreground when it differs
             from bg by more than bg_tol on its most-different channel.
    Returns the foreground median, or 0.0 when no foreground pixels are seen
    (an all-background frame is, for our purposes, a failed pass).
    """
    br, bgc, bb = bg
    fg = []
    for r, g, b in pixels:
        if max(abs(r - br), abs(g - bgc), abs(b - bb)) > bg_tol:
            fg.append(max(r, g, b))
    if not fg:
        return 0.0
    fg.sort()
    n = len(fg)
    if n % 2:
        return float(fg[n // 2])
    return (fg[n // 2 - 1] + fg[n // 2]) / 2.0


def id_color(i: int) -> tuple:
    """Flat ID color for object index i. Raises beyond MAX_OBJECTS."""
    if not 0 <= i < MAX_OBJECTS:
        raise ValueError(
            "object index %d out of range: the r-plane ID encoding supports "
            "at most %d visible objects per frame" % (i, MAX_OBJECTS)
        )
    r = GRID * (i // PLANE)
    j = i % PLANE
    return (r, GRID * (j // 52), GRID * (j % 52))


def id_key(i: int) -> str:
    """objects.json key for object index i ('g,b' on plane 0, else 'r,g,b')."""
    r, g, b = id_color(i)
    return "%d,%d" % (g, b) if r == 0 else "%d,%d,%d" % (r, g, b)


# --------------------------------------------------------------------------
# Semantic rule sets (pure python, testable without Rhino)
# --------------------------------------------------------------------------
# Ordered (UPPERCASE substring pattern, semantic); first match wins.
# CSI MasterFormat layers — exact mapping used for the e2_house gate capture.
CSI_RULES = [
    ("08-21", "door"), ("08-22", "door"),          # door panels/hardware
    ("08 - OPENINGS", "window"), ("08-0", "window"),
    ("06-02", "wall"), ("06-03", "wall_interior"),
    ("06-01", "floor"), ("06-04", "roof"),
    ("06-05", "stair"), ("06-06", "stair"),
    ("03 - CONCRETE", "foundation"), ("03-0", "foundation"),
    ("09-5", "stair"), ("09-6", "stair"),          # stair finishes/railings
    ("09-03", "floor"), ("09-04", "floor"),        # finished floors
    ("09-01", "trim"), ("09 - FINISHES", "trim"),
    ("31-03", "paving"), ("31-04", "paving"),      # site concrete/asphalt
    ("31 - SITE", "ground"),
]

# Keyword layers — the E1 SFUrban-style mapping (MULLION before GLASS!).
KEYWORD_RULES = [
    ("MULLION", "mullion"),
    ("GLAZ", "window_glass"), ("GLASS", "window_glass"),
    ("WINDOW", "window_glass"),
    ("DOOR", "door"),
    ("WALL", "wall"),
    ("FLOORPLATE", "floorplate"), ("FLOOR", "floorplate"),
    ("ROOF", "roof"),
    ("PERGOLA", "pergola"),
    ("STAIR", "stair"),
    ("MASSING", "massing"),
    ("SEAT", "seating"), ("BENCH", "seating"), ("FURNITURE", "seating"),
    ("TREE", "vegetation"), ("PLANT", "vegetation"), ("VEG", "vegetation"),
    ("LANDSCAP", "vegetation"),
    ("CONTEXT", "context"), ("SITE", "context"),
]

RULESETS = {"csi": CSI_RULES, "keyword": KEYWORD_RULES}

_CSI_LAYER_RE = re.compile(r"^\s*\d{2}\s*-\s*\S")  # e.g. "08 - OPENINGS"


def semantic_from_layer(layer_path: str, rules) -> str:
    """First-match semantic for a full layer path; 'other' if nothing hits."""
    up = (layer_path or "").upper()
    for pattern, semantic in rules:
        if pattern in up:
            return semantic
    return "other"


def pick_ruleset(layer_paths) -> str:
    """Sniff layer names: CSI MasterFormat numbering -> 'csi', else 'keyword'."""
    for p in layer_paths:
        top = (p or "").split("::")[0]
        if _CSI_LAYER_RE.match(top):
            return "csi"
    return "keyword"


def resolve_rules(semantic_rules, layer_paths):
    """Resolve the semantic_rules argument of capture() to (name, rules)."""
    if semantic_rules is None or semantic_rules == "auto":
        name = pick_ruleset(layer_paths)
        return name, RULESETS[name]
    if isinstance(semantic_rules, str):
        if semantic_rules not in RULESETS:
            raise ValueError(
                "unknown ruleset %r (expected 'csi', 'keyword', 'auto', or a "
                "list of (pattern, semantic) pairs)" % (semantic_rules,)
            )
        return semantic_rules, RULESETS[semantic_rules]
    return "custom", list(semantic_rules)


# --------------------------------------------------------------------------
# Rhino-side capture
# --------------------------------------------------------------------------
ID_MODE_NAME = "E1_IDMask"

# Object types that are 2D/non-renderable noise for our passes.
_2D_TYPE_NAMES = (
    "Curve", "Annotation", "TextDot", "Point", "PointSet", "Hatch",
    "Detail", "Light", "Grip", "ClipPlane", "Leader", "TextEntity",
)


def _try_set(obj, name, value):
    """setattr that tolerates missing/readonly members (RhinoCommon drift)."""
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        return False


def _try_call(obj, name, *args):
    """Call obj.name(*args) if it exists as a method, else try setattr."""
    fn = getattr(obj, name, None)
    if callable(fn):
        try:
            fn(*args)
            return True
        except Exception:
            pass
    return _try_set(obj, name, args[0] if len(args) == 1 else args)


def _ensure_id_display_mode():
    """Find or create the E1_IDMask display mode; (re)apply its attributes."""
    DMD = Rhino.Display.DisplayModeDescription
    modes = list(DMD.GetDisplayModes())
    idmode = next((m for m in modes if m.EnglishName == ID_MODE_NAME), None)
    if idmode is None:
        shaded = next(m for m in modes if m.EnglishName == "Shaded")
        new_id = DMD.CopyDisplayMode(shaded.Id, ID_MODE_NAME)
        idmode = DMD.GetDisplayMode(new_id)

    attrs = idmode.DisplayAttributes
    # LightingScheme=None — parse the enum value from the live attribute's
    # type (Rhino.Display.LightingSchema is not directly importable).
    try:
        ls_type = attrs.LightingScheme.GetType()
        attrs.LightingScheme = System.Enum.Parse(ls_type, "None")
    except Exception:
        pass
    # CRITICAL for the white-reference decode: force flat, unlit shading so a
    # pure-white object renders ~pure white everywhere (out = 0.7*in + base with
    # base ~constant), not shaded to mid-gray on angled faces. Without these the
    # white pass collapses toward background gray and decode drops to ~0%.
    # (LightingScheme="None" alone is NOT enough — the camera headlight remains.)
    _try_set(attrs, "FrontFlatShaded", True)
    try:
        white = System.Drawing.Color.FromArgb(255, 255, 255, 255)
        attrs.AmbientLightingColor = white
    except Exception:
        pass
    _try_set(attrs, "FrontDiffuse", System.Drawing.Color.FromArgb(255, 255, 255, 255))
    for name in ("ShadowsOn", "CastShadows", "UseDocumentAmbientLight"):
        _try_set(attrs, name, False)
    for name in (
        "ShowCurves", "ShowAnnotations", "ShowText", "ShowPoints",
        "ShowIsoCurves", "ShowIsocurves",
        "ShowSurfaceEdges", "ShowSurfaceNakedEdge", "ShowMeshEdges",
        "ShowMeshNakedEdges", "ShowTangentEdges", "ShowTangentSeams",
    ):
        if not _try_set(attrs, name, False):
            # Some edge toggles live on nested attribute objects.
            for sub in ("MeshSpecificAttributes", "CurveStrokeAttributes"):
                nested = getattr(attrs, sub, None)
                if nested is not None and _try_set(nested, name, False):
                    break
    _try_set(attrs, "DisableTransparency", True)
    DMD.UpdateDisplayMode(idmode)
    return DMD.GetDisplayMode(idmode.Id)  # re-fetch post-update


def _visible_capture_objects(doc, hide_2d_objects):
    """Visible objects that should receive ID colors, in stable order."""
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.NormalObjects = True
    settings.LockedObjects = True
    settings.HiddenObjects = False
    out = []
    for obj in doc.Objects.GetObjectList(settings):
        if not obj.Visible:
            continue
        tname = str(obj.ObjectType)
        if hide_2d_objects and any(t in tname for t in _2D_TYPE_NAMES):
            continue
        out.append(obj)
    return out


def _material_name(doc, obj):
    try:
        idx = obj.Attributes.MaterialIndex
        if idx >= 0:
            return doc.Materials[idx].Name
    except Exception:
        pass
    return None


def _save_bitmap(bmp, path):
    bmp.Save(str(path), System.Drawing.Imaging.ImageFormat.Png)


def _bitmap_median_fg_brightness(bmp, step=3):
    """Foreground median brightness of a System.Drawing.Bitmap (Rhino-side).

    Subsamples on a `step` grid (full-res is needless and slow — at 813x386,
    step=3 reads ~8k pixels in ~0.2s and matches the host-side number) and
    delegates the actual statistic to the pure light_pass_median_brightness so
    the threshold logic is identical to what the unit tests exercise.
    """
    w, h = bmp.Width, bmp.Height

    def _pixels():
        for y in range(0, h, step):
            for x in range(0, w, step):
                c = bmp.GetPixel(x, y)
                yield (c.R, c.G, c.B)

    return light_pass_median_brightness(_pixels())


def _capture_idmode(view, size, idmode):
    """Capture the active view into a bitmap, FORCING render of `idmode`.

    THE REPEATABILITY FIX. The bare `view.CaptureToBitmap(size)` does NOT
    reliably re-render the viewport's *current* DisplayMode in a headless /
    Rhino-MCP-driven session — it returns whatever cached pipeline frame Rhino
    last produced (a default-lit, mid-gray frame), so the white-reference pass
    comes back dim and decode collapses to ~0% on every capture after the
    first. The `CaptureToBitmap(size, displayModeDescription)` overload forces
    the pipeline to render that exact mode and is reliable on the 1st, 2nd, and
    Nth call in one session — making capture() idempotent with no doc reopen.
    Measured: bare -> foreground median 157 (dead); overload -> 191 (decodes
    ~97%). See spike/REPORTS for the investigation.
    """
    view.Document.Views.Redraw()
    return view.CaptureToBitmap(size, idmode)


def capture(out_dir, semantic_rules=None, hide_layer_prefixes=None,
            hide_2d_objects=True, camera=None, doc_path=None):
    """Atomic ground-truth capture of the active viewport.

    Writes beauty.png, depth.png, light_pass.png, id_mask.png, objects.json,
    camera.json into out_dir and returns a summary dict.

    semantic_rules      'csi' | 'keyword' | 'auto'/None | [(pattern, semantic)]
    hide_layer_prefixes layer full-path prefixes to switch off for the capture
                        (restored afterwards), e.g. ["#", "X-TitleBlock"]
    hide_2d_objects     hide curves/annotations/points/hatches for ALL passes
                        (incl. beauty), restored afterwards
    camera              optional {"location":[x,y,z], "target":[x,y,z],
                        "up":[x,y,z], "lens_35mm": f} applied before capture
                        so the whole run is self-contained
    doc_path            optional absolute .3dm path. Recovery safety net: if the
                        white-reference pass is still dim after the in-process
                        Wireframe-bounce flush (should not happen with the
                        CaptureToBitmap(size, mode) fix), attempt a reopen of
                        this file and retry the whole capture ONCE — but only if
                        the reopen actually RESETS the document (in a headless
                        MCP doc, ReadFile can append instead of replace; that is
                        detected and refused). Whether or not doc_path is given,
                        a persistently dim pass raises RuntimeError rather than
                        returning silent garbage; the authoritative reset is a
                        host-side open_doc(clearFirst=True).

    Raises RuntimeError if it cannot produce a healthy (decodable) white pass.
    """
    if not HAVE_RHINO:
        raise RuntimeError(
            "rhino_capture.capture() must run inside Rhino's Python "
            "(Rhino MCP run_python, ScriptEditor, or GhPython)."
        )
    import os

    doc = globals().get("__rhino_doc__") or Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("no active Rhino document")
    os.makedirs(str(out_dir), exist_ok=True)
    j = lambda name: os.path.join(str(out_dir), name)  # noqa: E731

    view = doc.Views.ActiveView
    vp = view.ActiveViewport

    # ---- optional explicit camera (inside the atomic run) ----
    if camera:
        loc = camera.get("location")
        tgt = camera.get("target")
        up = camera.get("up")
        if loc and tgt:
            vp.SetCameraLocations(
                Rhino.Geometry.Point3d(*tgt), Rhino.Geometry.Point3d(*loc)
            )
        if up:
            vp.CameraUp = Rhino.Geometry.Vector3d(*up)
        if camera.get("lens_35mm"):
            vp.Camera35mmLensLength = float(camera["lens_35mm"])

    # ---- gather objects + rules ----
    rule_name, rules = resolve_rules(
        semantic_rules, [l.FullPath for l in doc.Layers if not l.IsDeleted]
    )

    # ---- state to restore (try/finally below) ----
    hidden_layer_ids = []
    hidden_obj_ids = []
    saved_colors = []
    saved_mode = vp.DisplayMode
    saved_grid = vp.ConstructionGridVisible
    saved_axes = vp.ConstructionAxesVisible
    saved_world = vp.WorldAxesVisible

    summary = {}
    white_pass_median = 0.0  # set when the white pass is captured (health gate)
    try:
        # layer prefix hiding
        if hide_layer_prefixes:
            for layer in doc.Layers:
                if layer.IsDeleted or not layer.IsVisible:
                    continue
                if any(layer.FullPath.startswith(p)
                       for p in hide_layer_prefixes):
                    layer.IsVisible = False
                    hidden_layer_ids.append(layer.Id)

        # 2D object hiding (affects beauty too — linework/titleblocks out)
        if hide_2d_objects:
            settings = Rhino.DocObjects.ObjectEnumeratorSettings()
            settings.NormalObjects = True
            settings.LockedObjects = False
            settings.HiddenObjects = False
            for obj in list(doc.Objects.GetObjectList(settings)):
                tname = str(obj.ObjectType)
                if obj.Visible and any(t in tname for t in _2D_TYPE_NAMES):
                    if doc.Objects.Hide(obj.Id, True):
                        hidden_obj_ids.append(obj.Id)

        objects = _visible_capture_objects(doc, hide_2d_objects)
        if len(objects) > MAX_OBJECTS:
            raise RuntimeError(
                "%d visible objects exceeds the ID encoding capacity (%d)"
                % (len(objects), MAX_OBJECTS)
            )

        idmode = _ensure_id_display_mode()
        modes = list(Rhino.Display.DisplayModeDescription.GetDisplayModes())
        shaded = next(m for m in modes if m.EnglishName == "Shaded")

        # grid/axes pollute pixels — off for every pass
        vp.ConstructionGridVisible = False
        vp.ConstructionAxesVisible = False
        vp.WorldAxesVisible = False

        size = System.Drawing.Size(vp.Size.Width, vp.Size.Height)

        # ---- pass 1: beauty (Shaded) ----
        vp.DisplayMode = shaded
        doc.Views.Redraw()
        bmp = view.CaptureToBitmap(size, shaded)
        _save_bitmap(bmp, j("beauty.png"))

        # ---- pass 2: depth (true z-buffer) ----
        zb = Rhino.Display.ZBufferCapture(vp)
        for name in ("ShowCurves", "ShowAnnotations", "ShowText", "ShowPoints",
                     "ShowLights", "ShowMeshWires", "ShowIsocurves"):
            _try_call(zb, name, False)
        zb.SetDisplayMode(shaded.Id)
        depth_meta = {"minZ": None, "maxZ": None, "hits": None}
        try:
            depth_meta["minZ"] = float(zb.MinZ() if callable(zb.MinZ) else zb.MinZ)
            depth_meta["maxZ"] = float(zb.MaxZ() if callable(zb.MaxZ) else zb.MaxZ)
            depth_meta["hits"] = int(
                zb.HitCount() if callable(zb.HitCount) else zb.HitCount
            )
        except Exception:
            pass
        _save_bitmap(zb.GrayscaleDib(), j("depth.png"))

        # ---- ID display mode for white + ID passes ----
        # REPEATABILITY FIX: render via the CaptureToBitmap(size, idmode)
        # overload (see _capture_idmode). The bare CaptureToBitmap(size)
        # returns a stale, default-lit frame in headless/MCP sessions, so the
        # white pass came back dim and decode collapsed to ~0% on every capture
        # after the first. The overload forces a real render of idmode and is
        # idempotent across captures in one session — no doc reopen needed.
        vp.DisplayMode = idmode

        # save original colors, then white reference pass
        white = System.Drawing.Color.FromArgb(255, 255, 255)
        from_obj = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        for obj in objects:
            saved_colors.append(
                (obj, obj.Attributes.ObjectColor, obj.Attributes.ColorSource)
            )
            obj.Attributes.ObjectColor = white
            obj.Attributes.ColorSource = from_obj
            obj.CommitChanges()
        bmp = _capture_idmode(view, size, idmode)

        # ---- white-pass health gate (catch a dim pass IN-RHINO) ----
        # A dim pass means every downstream mask is garbage; reject it here,
        # before returning, rather than letting the host decode silently to 0%.
        median = _bitmap_median_fg_brightness(bmp)
        if median < MIN_LIGHT_PASS_MEDIAN:
            # Try a harder in-process pipeline flush (no reopen): bounce the
            # display mode through Wireframe to drop any cached shaded frame,
            # let Rhino process the redraw, then re-capture via the overload.
            try:
                wf = next(m for m in modes if m.EnglishName == "Wireframe")
                vp.DisplayMode = wf
                doc.Views.Redraw()
                Rhino.RhinoApp.Wait()
                vp.DisplayMode = idmode
                doc.Views.Redraw()
                Rhino.RhinoApp.Wait()
            except Exception:
                pass
            bmp = _capture_idmode(view, size, idmode)
            median = _bitmap_median_fg_brightness(bmp)
        white_pass_median = median
        _save_bitmap(bmp, j("light_pass.png"))

        # ---- ID pass ----
        table = {}
        for i, obj in enumerate(objects):
            r, g, b = id_color(i)
            obj.Attributes.ObjectColor = System.Drawing.Color.FromArgb(r, g, b)
            obj.Attributes.ColorSource = from_obj
            obj.CommitChanges()
            layer = doc.Layers[obj.Attributes.LayerIndex].FullPath
            table[id_key(i)] = {
                "guid": str(obj.Id),
                "layer": layer,
                "semantic": semantic_from_layer(layer, rules),
                "object_type": str(obj.ObjectType),
                "material": _material_name(doc, obj),
                "name": obj.Attributes.Name or None,
            }
        # Same overload — the ID pass must render with the identical pipeline as
        # the white pass or the per-pixel base calibration won't line up.
        bmp = _capture_idmode(view, size, idmode)
        _save_bitmap(bmp, j("id_mask.png"))

        # ---- metadata ----
        with open(j("objects.json"), "w") as f:
            json.dump(
                {"encoding": dict(ENCODING_DOC, ruleset=rule_name),
                 "objects": table},
                f, indent=1,
            )

        frustum = vp.GetFrustum()  # 7-tuple in Python: (ok, l, r, b, t, n, f)
        cam = {
            "location": [vp.CameraLocation.X, vp.CameraLocation.Y,
                         vp.CameraLocation.Z],
            "target": [vp.CameraTarget.X, vp.CameraTarget.Y,
                       vp.CameraTarget.Z],
            "up": [vp.CameraUp.X, vp.CameraUp.Y, vp.CameraUp.Z],
            "lens_35mm": vp.Camera35mmLensLength,
            "frustum_raw": list(frustum),
            "size_px": [size.Width, size.Height],
            "projection": "perspective" if vp.IsPerspectiveProjection
                          else "parallel",
            "depth_meta": depth_meta,
        }
        with open(j("camera.json"), "w") as f:
            json.dump(cam, f, indent=1)

        summary = {
            "out_dir": str(out_dir),
            "n_objects": len(objects),
            "size_px": [size.Width, size.Height],
            "ruleset": rule_name,
            "depth_meta": depth_meta,
            "white_pass_median": round(white_pass_median, 1),
            "files": ["beauty.png", "depth.png", "light_pass.png",
                      "id_mask.png", "objects.json", "camera.json"],
        }
    finally:
        # ---- restore document + viewport state ----
        for obj, color, source in saved_colors:
            try:
                obj.Attributes.ObjectColor = color
                obj.Attributes.ColorSource = source
                obj.CommitChanges()
            except Exception:
                pass
        for oid in hidden_obj_ids:
            try:
                doc.Objects.Show(oid, True)
            except Exception:
                pass
        for lid in hidden_layer_ids:
            try:
                doc.Layers.FindId(lid).IsVisible = True
            except Exception:
                pass
        try:
            vp.DisplayMode = saved_mode
            vp.ConstructionGridVisible = saved_grid
            vp.ConstructionAxesVisible = saved_axes
            vp.WorldAxesVisible = saved_world
            doc.Views.Redraw()
        except Exception:
            pass

    # ---- white-pass health enforcement (after state is restored) ----
    # With the CaptureToBitmap(size, idmode) overload this should always pass
    # (it has across 1st/2nd/Nth captures in a session); the in-pass Wireframe
    # bounce above is the cheap in-process recovery. This block is the final
    # safety net so a regression can never silently ship an undecodable capture.
    if white_pass_median < MIN_LIGHT_PASS_MEDIAN:
        # Optional reopen-and-retry. NOTE: RhinoDoc.ReadFile APPENDS rather than
        # replaces in a headless/MCP-driven doc (verified: 7762 -> 15956), so we
        # only proceed if the reopen genuinely RESET the document (object count
        # did not balloon). If it appended instead, we abort rather than render a
        # doubled scene — the authoritative reset is a router-level
        # open_doc(clearFirst=True) / close_slot+spawn_slot, which the caller
        # drives, not this in-script path.
        if doc_path:
            before = doc.Objects.Count
            Rhino.RhinoApp.Wait()
            opts = Rhino.FileIO.FileReadOptions()
            opts.OpenMode = True   # File>Open semantics (resets when honored)
            opened = Rhino.RhinoDoc.ReadFile(str(doc_path), opts)
            doc_now = Rhino.RhinoDoc.ActiveDoc or doc
            after = doc_now.Objects.Count
            # A clean reset keeps the count at (roughly) the file's own object
            # count; an append leaves it >= before + something. Require it to be
            # no larger than the pre-reopen count to call it a real reset.
            if opened and after <= before:
                retry = capture(
                    out_dir, semantic_rules=semantic_rules,
                    hide_layer_prefixes=hide_layer_prefixes,
                    hide_2d_objects=hide_2d_objects, camera=camera,
                    doc_path=None,  # recurse once only — cannot loop
                )
                retry["recovered_by_reopen"] = True
                return retry
            raise RuntimeError(
                "white-reference pass was dim (foreground median %.1f < %.1f) "
                "and the in-script reopen of %r did not reset the document "
                "(objects %d -> %d). Reset the slot from the host "
                "(open_doc(clearFirst=True) or close_slot + spawn_slot + "
                "open_doc) and capture again." % (
                    white_pass_median, MIN_LIGHT_PASS_MEDIAN, str(doc_path),
                    before, after)
            )
        raise RuntimeError(
            "white-reference pass was dim (foreground median %.1f < %.1f): "
            "objects rendered near background gray, so every decoded mask would "
            "be garbage. The viewport pipeline did not render the ID display "
            "mode. Reopen the model in Rhino (host-side open_doc(clearFirst=True)"
            " or close_slot + spawn_slot + open_doc) and capture again."
            % (white_pass_median, MIN_LIGHT_PASS_MEDIAN)
        )

    return summary


def capture_and_send(out_dir, server_url="http://127.0.0.1:8765",
                     render=True, timeout_s=420, **capture_kwargs):
    """Capture the active viewport, then POST it to the canvas server's
    /api/ingest so the browser updates. This is the body of the eventual
    Rhino "Send to Canvas" plugin/Grasshopper button — capture lives in
    Rhino; the server does decode -> locked render -> web prep.

    Runs inside Rhino's Python (urllib is available there). The server and
    Rhino are co-located in dev, so a path hand-off is enough; a networked
    plugin would instead upload the six files.

    Accepts the same kwargs as capture() — notably doc_path=<the .3dm> to enable
    the dim-white-pass reopen-and-retry recovery.
    """
    summary = capture(out_dir, **capture_kwargs)
    import json as _json
    import urllib.request

    body = _json.dumps({"capture_dir": str(out_dir), "render": render}).encode()
    req = urllib.request.Request(
        server_url.rstrip("/") + "/api/ingest", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            summary["ingest"] = _json.loads(resp.read())
            print("sent to canvas:", summary["ingest"])
    except Exception as e:  # noqa: BLE001 — surface but don't lose the capture
        summary["ingest_error"] = str(e)
        print("capture saved but ingest POST failed:", e)
    return summary


if __name__ == "__main__" and HAVE_RHINO:
    # ScriptEditor convenience: capture to a sibling 'capture_out' directory.
    import os

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "outputs", "capture_out")
    print(capture(out))
