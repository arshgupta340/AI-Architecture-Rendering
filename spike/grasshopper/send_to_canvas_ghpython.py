"""Send to Canvas — GhPython Script component body (Rhino 8, Python 3).

Paste this into a Grasshopper "Python 3 Script" component (the GhPython /
ScriptEditor component that ships with Rhino 8). It is the architect-facing
button: press it and the active Rhino viewport is captured (beauty / depth /
light_pass / id_mask / objects / camera) and POSTed to the web canvas server's
``POST /api/ingest``, which decodes it, runs the geometry-locked render, and
updates the browser. The heavy lifting lives in ``spike/rhino_capture.py``
(``capture`` + ``capture_and_send``) — this component is a thin, robust wrapper
around ``capture_and_send`` so the proven capture contract is never duplicated.

--------------------------------------------------------------------------
COMPONENT INPUTS  (right-click each input → set Type hint as noted)
--------------------------------------------------------------------------
  run            Boolean   — a Button (preferred) or Toggle. Fires on the
                            RISING EDGE only (False→True), so a Toggle left
                            on True does not re-capture every solve.
  out_dir        str       — where the capture bundle is written. Leave empty
                            to use a timestamped dir under
                            <repo>/spike/outputs/gh_captures/.
  server_url     str       — canvas server base URL. Default http://127.0.0.1:8765.
  render         bool       — True (default): server runs the locked render
                            (~5 min / costs money). False: ingest + decode only,
                            reusing any existing base render — use this to test
                            the wiring with zero spend.
  semantic_rules str       — 'auto' (default, sniffs the doc's layers),
                            'csi', or 'keyword'. Passed through to capture().
  module_path    str       — OPTIONAL fallback. Absolute path to
                            spike/rhino_capture.py. Only needed if the component
                            cannot locate the repo automatically (see _find_module).

Set "run" type hint to bool; set out_dir/server_url/semantic_rules/module_path
to str; set render to bool. Make every input "Item Access".

--------------------------------------------------------------------------
COMPONENT OUTPUTS
--------------------------------------------------------------------------
  status         str — human-readable result / error (always set).
  decode_pct     float — % of object pixels decoded by the server (or -1).
  n_regions      int — number of regions the server found in frame (or -1).

--------------------------------------------------------------------------
PREREQUISITE
--------------------------------------------------------------------------
The canvas server must be running:
    spike\\.venv\\Scripts\\python.exe apps/canvas-prototype/server.py
(then the browser at http://localhost:8765 auto-reloads on a new capture).
See spike/grasshopper/README.md for full install/use notes.
"""

import os
import datetime

# Rhino runtime imports. Available inside a GhPython / Python 3 Script
# component in Rhino 8. Imported defensively so a bad host still yields a clean
# status string instead of a red component with an opaque traceback.
try:
    import Rhino  # noqa: F401
    _HAVE_RHINO = True
except Exception as _imp_err:  # pragma: no cover - only on a broken host
    _HAVE_RHINO = False
    _RHINO_IMPORT_ERR = _imp_err


# --------------------------------------------------------------------------
# Locate spike/rhino_capture.py robustly.
# --------------------------------------------------------------------------
# GhPython script components do NOT reliably expose __file__ (it is absent in
# the in-process script engine and points at a temp file in some setups), so we
# try several strategies in order and fall back to the explicit module_path
# input. The first directory that actually contains rhino_capture.py wins.
def _candidate_repo_dirs(module_path):
    """Yield directories that might contain rhino_capture.py, best-guess first."""
    # 1. Explicit override input — always honoured first when given.
    if module_path:
        mp = str(module_path).strip()
        if mp:
            if mp.lower().endswith(".py"):
                yield os.path.dirname(mp)
            else:
                yield mp                      # a directory was given
                yield os.path.join(mp, "spike")

    # 2. __file__, if the engine provides one (walk up looking for spike/).
    here = globals().get("__file__")
    if here:
        d = os.path.dirname(os.path.abspath(here))
        for _ in range(6):
            yield d
            yield os.path.join(d, "spike")
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent

    # 3. The GH document's own folder (if the .gh/.ghx file has been saved),
    #    walking up toward a repo root that holds spike/.
    ghdoc = globals().get("ghdoc")
    doc_path = None
    try:
        if ghdoc is not None and getattr(ghdoc, "Path", None):
            doc_path = ghdoc.Path
    except Exception:
        doc_path = None
    if not doc_path:
        try:
            import scriptcontext as _sc
            ghd = getattr(_sc, "doc", None)
            if ghd is not None and getattr(ghd, "FilePath", None):
                doc_path = ghd.FilePath
        except Exception:
            pass
    if doc_path:
        d = os.path.dirname(os.path.abspath(doc_path))
        for _ in range(8):
            yield d
            yield os.path.join(d, "spike")
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent

    # 4. The active Rhino document's folder, same upward walk.
    if _HAVE_RHINO:
        try:
            rdoc = Rhino.RhinoDoc.ActiveDoc
            rpath = rdoc.Path if rdoc else None
        except Exception:
            rpath = None
        if rpath:
            d = os.path.dirname(os.path.abspath(rpath))
            for _ in range(8):
                yield d
                yield os.path.join(d, "spike")
                parent = os.path.dirname(d)
                if parent == d:
                    break
                d = parent

    # 5. Last-ditch hardcoded guesses for this machine's known layout.
    for guess in (
        r"C:\Users\arshg\AI Architecture Rendering\spike",
        os.path.join(os.path.expanduser("~"), "AI Architecture Rendering", "spike"),
    ):
        yield guess


def _find_module(module_path):
    """Return (spike_dir, rhino_capture_path) or raise a clear error."""
    seen = set()
    for d in _candidate_repo_dirs(module_path):
        if not d:
            continue
        d = os.path.normpath(d)
        if d in seen:
            continue
        seen.add(d)
        cand = os.path.join(d, "rhino_capture.py")
        if os.path.isfile(cand):
            return d, cand
    raise RuntimeError(
        "could not locate spike/rhino_capture.py. Set the 'module_path' input "
        "to its absolute path (e.g. "
        r"C:\Users\you\AI Architecture Rendering\spike\rhino_capture.py). "
        "Searched: " + "; ".join(sorted(seen))
    )


def _load_capture_module(module_path):
    """exec spike/rhino_capture.py into a namespace seeded with the Rhino doc.

    capture() reads __rhino_doc__ from its module globals and falls back to
    Rhino.RhinoDoc.ActiveDoc when it is absent. In a GhPython component the
    reliable handle is ActiveDoc (the in-process script engine shares Rhino's
    live document), so we seed __rhino_doc__ with it explicitly.
    """
    spike_dir, mod_path = _find_module(module_path)
    src = open(mod_path, "r").read()
    ns = {"__name__": "rhino_capture", "__file__": mod_path}
    if _HAVE_RHINO:
        try:
            ns["__rhino_doc__"] = Rhino.RhinoDoc.ActiveDoc
        except Exception:
            pass
    exec(compile(src, "rhino_capture.py", "exec"), ns)
    return ns, spike_dir


def _default_out_dir(spike_dir):
    """Timestamped capture dir under spike/outputs/gh_captures/."""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(spike_dir, "outputs", "gh_captures", "capture_" + stamp)


# --------------------------------------------------------------------------
# Rising-edge state. GhPython preserves module globals across solves within a
# session, so we remember the previous 'run' value and only fire on False->True.
# (Set "run" to a Button so it auto-resets; a Toggle works too — it just won't
# re-fire while held True.)
# --------------------------------------------------------------------------
if "_prev_run" not in globals():
    _prev_run = False


def _send(out_dir, server_url, render, semantic_rules, module_path):
    """Do the capture+POST. Returns (status, decode_pct, n_regions)."""
    if not _HAVE_RHINO:
        return ("Rhino runtime unavailable: %r" % (_RHINO_IMPORT_ERR,), -1.0, -1)

    ns, spike_dir = _load_capture_module(module_path)

    # Resolve inputs / defaults.
    od = (str(out_dir).strip() if out_dir else "") or _default_out_dir(spike_dir)
    url = (str(server_url).strip() if server_url else "") or "http://127.0.0.1:8765"
    rules = (str(semantic_rules).strip() if semantic_rules else "") or "auto"
    do_render = True if render is None else bool(render)

    # doc_path lets capture()'s dim-white-pass reopen-retry safety net work.
    doc_path = None
    try:
        rdoc = Rhino.RhinoDoc.ActiveDoc
        if rdoc and rdoc.Path:
            doc_path = rdoc.Path
    except Exception:
        doc_path = None

    summary = ns["capture_and_send"](
        od, server_url=url, render=do_render,
        semantic_rules=rules, doc_path=doc_path,
    )

    # Pull decode_pct / n_regions out of the server's ingest response when present.
    dpct, nreg = -1.0, -1
    ingest = summary.get("ingest")
    if isinstance(ingest, dict):
        if ingest.get("decode_pct") is not None:
            try:
                dpct = float(ingest["decode_pct"])
            except (TypeError, ValueError):
                pass
        if ingest.get("n_regions") is not None:
            try:
                nreg = int(ingest["n_regions"])
            except (TypeError, ValueError):
                pass

    n_objects = summary.get("n_objects")
    if "ingest_error" in summary:
        msg = ("Captured %s objects to %s, but ingest POST failed: %s"
               % (n_objects, od, summary["ingest_error"]))
    elif isinstance(ingest, dict):
        rendered = ingest.get("rendered")
        msg = ("Sent to canvas: %s objects, decode %.1f%%, %s regions"
               "%s (-> %s)" % (
                   n_objects, dpct if dpct >= 0 else -1.0, nreg,
                   ", rendered" if rendered else " (no render)", od))
    else:
        msg = ("Captured %s objects to %s; POSTed to %s (no JSON response "
               "parsed)" % (n_objects, od, url))
    return (msg, dpct, nreg)


def run_component(run, out_dir, server_url, render, semantic_rules, module_path):
    """Entry point: rising-edge guard + exception → status string.

    Returns (status, decode_pct, n_regions). The script-component footer assigns
    these to the component outputs.
    """
    global _prev_run
    prev = _prev_run
    _prev_run = bool(run)

    if not run:
        return ("idle — set 'run' True (press the Button) to capture & send",
                -1.0, -1)
    if prev:
        # Still held True from a previous solve; don't re-fire (Toggle case).
        return ("idle — 'run' still True from last solve; reset it to re-send",
                -1.0, -1)

    try:
        return _send(out_dir, server_url, render, semantic_rules, module_path)
    except Exception as e:  # noqa: BLE001 — never let the component go red.
        import traceback
        return ("ERROR: %s\n%s" % (e, traceback.format_exc()), -1.0, -1)


# --------------------------------------------------------------------------
# Script-component footer. In a GhPython / Python 3 Script component the input
# variable names (run, out_dir, server_url, render, semantic_rules, module_path)
# are injected as globals, and assigning the output names (status, decode_pct,
# n_regions) wires them to the outputs. The guards below let this same file be
# imported in plain CPython (e.g. by the validation harness) without NameErrors.
# --------------------------------------------------------------------------
run = globals().get("run", False)
out_dir = globals().get("out_dir", None)
server_url = globals().get("server_url", None)
render = globals().get("render", True)
semantic_rules = globals().get("semantic_rules", "auto")
module_path = globals().get("module_path", None)

status, decode_pct, n_regions = run_component(
    run, out_dir, server_url, render, semantic_rules, module_path
)
