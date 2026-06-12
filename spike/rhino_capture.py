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
4. Beauty: view.CaptureToBitmap(size, shadedMode). White/ID passes: set
   vp.DisplayMode = idmode and capture WITHOUT the mode argument —
   CaptureToBitmap(size, mode) does NOT honor updated display-mode attributes.
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
    for name in ("ShadowsOn", "CastShadows"):
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


def capture(out_dir, semantic_rules=None, hide_layer_prefixes=None,
            hide_2d_objects=True, camera=None):
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
        # CRITICAL: CaptureToBitmap(size, mode) does NOT honor updated
        # display-mode attributes; set the viewport's mode and capture bare.
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
        doc.Views.Redraw()
        bmp = view.CaptureToBitmap(size)
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
        doc.Views.Redraw()
        bmp = view.CaptureToBitmap(size)
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

    return summary


if __name__ == "__main__" and HAVE_RHINO:
    # ScriptEditor convenience: capture to a sibling 'capture_out' directory.
    import os

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "outputs", "capture_out")
    print(capture(out))
