# Send to Canvas — Grasshopper component

The architect-facing button for **Photoshop-for-Architects**: press it in
Grasshopper and the active Rhino viewport is captured (beauty / depth /
light_pass / id_mask / objects / camera) and POSTed to the web canvas server,
which decodes it, runs the geometry-locked render, and updates the browser.

It is a thin wrapper around the proven capture flow in
[`spike/rhino_capture.py`](../rhino_capture.py) — the component body just locates
that module, seeds the active Rhino document, and calls `capture_and_send(...)`.
The capture contract (white-reference pass, atomic six-file bundle, CSI/keyword
semantic sniffing, in-session idempotency) is never duplicated here.

## Files

| file | what it is |
|---|---|
| `send_to_canvas_ghpython.py` | the **script-component body** — paste into a Python 3 Script component (or it is already embedded in `send_to_canvas.gh`) |
| `send_to_canvas.gh` | a **ready-to-open** Grasshopper definition: the configured Python 3 Script component + a Boolean Toggle wired to `run`. Open this and skip the manual setup below |
| `mock_ingest_server.py` | a stdlib HTTP receiver used to **validate** the component with zero API spend (see "Validation") |

## Prerequisite — the canvas server must be running

```
spike\.venv\Scripts\python.exe apps/canvas-prototype/server.py
```

Then the browser at <http://localhost:8765> auto-reloads on each new capture
(it polls `GET /api/version` every 3 s and shows "● synced HH:MM:SS").
First-ever run also needs `apps/canvas-prototype/prepare_data.py` once.

## Quick start (open the prebuilt definition)

1. Open `kCs_SampleHouseProject V1.3dm` (or any model) in **Rhino 8** and frame
   the view you want to send.
2. Start the canvas server (above).
3. In Rhino, run `_Grasshopper`, then **File → Open** `spike/grasshopper/send_to_canvas.gh`.
4. Double-click the **Boolean Toggle** to set it `True`. The component captures
   and sends; the `status` output reports the result and the browser updates.
   Set the toggle back to `False` before sending again (it fires on the
   **rising edge** False→True, so a toggle left on `True` will not re-capture
   every solve).

The definition ships with `server_url = http://127.0.0.1:8765` and
`render = True`. To test the wiring without spending money, set `render` to
`False` (see "Inputs").

## Manual setup (build the component yourself, Rhino 8)

1. Open Grasshopper (`_Grasshopper`).
2. **Maths → Script → Python 3 Script** — drop the component on the canvas.
   (This is the Rhino 8 native CPython component, NickName `Py3`. The older
   `GhPython Script` component also works but targets IronPython 2; prefer
   Python 3.)
3. **Add the inputs.** Zoom in until the input "+"/"–" zappers appear, and add
   inputs until you have six, then rename each (double-click the name):

   | input | type hint (right-click input → Type hint) | notes |
   |---|---|---|
   | `run` | Boolean | wire a **Button** (preferred) or **Boolean Toggle** here |
   | `out_dir` | str | leave empty → timestamped dir under `spike/outputs/gh_captures/` |
   | `server_url` | str | default `http://127.0.0.1:8765` if left empty |
   | `render` | bool | `True` = server renders (~5 min, costs money); `False` = ingest+decode only, no spend |
   | `semantic_rules` | str | `auto` (default), `csi`, or `keyword` |
   | `module_path` | str | OPTIONAL — absolute path to `spike/rhino_capture.py` if auto-locate fails |

   Set every input to **Item Access** (the default).

4. **Add the outputs.** Add output params and rename them to:

   | output | meaning |
   |---|---|
   | `status` | human-readable result / error (always set) |
   | `decode_pct` | % of object pixels the server decoded (or `-1` if not reported) |
   | `n_regions` | regions the server found in frame (or `-1`) |

   (The fixed first output `out` is the script's captured `print()` text —
   leave it; it carries the "sent to canvas: …" log line.)

5. **Paste the body.** Double-click the component to open the editor and paste
   the full contents of `send_to_canvas_ghpython.py`. Hit the editor's
   *Test/Close* so it compiles.
6. **Wire `run`.** Drop a **Button** (Params → Input → Button) or **Boolean
   Toggle** and connect it to the `run` input.
7. Press the Button (or flip the Toggle to `True`) — the component captures and
   POSTs, and `status` reports the outcome.

### Why not just `import rhino_capture`?

GhPython script components do not reliably put the repo on `sys.path`, and
`__file__` is often absent in the in-process engine. The body therefore
*locates* `spike/rhino_capture.py` (via `__file__`, the saved `.gh`/`.3dm`
folder, then a known-layout fallback) and `exec`s it into a namespace seeded
with `Rhino.RhinoDoc.ActiveDoc`. If auto-location ever fails, set the
`module_path` input to the absolute path of `rhino_capture.py`.

## How it behaves

- **Rising-edge only.** `run` fires on False→True. Held `True` (a Toggle left
  on) does not re-capture on subsequent solves; reset it to `False` first. A
  Button auto-resets, so each click is one send.
- **Never goes red.** All errors (module not found, capture failure, server
  unreachable) are caught and written to `status`; the component stays alive.
  Example: server down → `status = "Captured 326 objects to …, but ingest POST
  failed: <urlopen error 10061>"` — the six-file bundle is still on disk.
- **`doc_path` recovery.** When the active document is saved, its path is passed
  to `capture()` so its dim-white-pass reopen-retry safety net is available.

## Validation (zero spend)

The component was validated against a standalone mock receiver so it does not
depend on the real (actively-edited) canvas server and incurs no render cost:

```
# terminal 1 — start the mock receiver on a dedicated port
spike\.venv\Scripts\python.exe spike/grasshopper/mock_ingest_server.py --port 8770

# then point the component's server_url at it (render=False) and fire run; the
# bundle lands under spike/outputs/gh_captures/<your out_dir>. Verify it decodes
# healthily (substitute your capture dir):
spike\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'spike'); from pathlib import Path; from host_probe_rhino import decode; print(decode(Path('spike/outputs/gh_captures/<capture_dir>'))['decoded_pct_of_object_px'])"
```

Result on `kCs_SampleHouseProject V1.3dm` (hero view, 1504×656): the component
captured **326 objects**, the receiver logged a well-formed
`{"capture_dir": "…", "render": false}` POST, and the bundle decoded at
**92.9 %** of object pixels — matching the proven `rhino_capture` reference.
This held both when the body was `exec`'d directly and when run from the **live
Grasshopper component** (Boolean Toggle → `run`), whose `status`/`decode_pct`/
`n_regions` outputs populated correctly with no component errors.

## Notes on the live-canvas automation

`send_to_canvas.gh` was produced by driving Grasshopper through the Rhino MCP
`g1_*` tools: place the Python 3 Script component, rebuild its input/output
parameters, inject the script source, place and wire a Boolean Toggle, and
solve. One nuance worth recording for future automation:

- The `g1_*` MCP tools place/connect components and read the canvas graph, but
  do **not** expose a way to set arbitrary Python source or custom parameter
  names on a script component. That was done via `run_python` against the
  Grasshopper SDK: the Rhino 8 Python 3 Script component is
  `RhinoCodePluginGH.Components.Python3Component`, implementing
  `RhinoCodePlatform.GH.IScriptComponent`. Its source is the (explicitly
  implemented) `IScriptComponent.Text` property — reachable via the type's
  interface map (`GetInterfaceMap(IScriptComponent)` → `set_Text`) since
  CPython/pythonnet does not surface explicit interface members directly.
  Inputs/outputs are `RhinoCodePluginGH.Parameters.ScriptVariableParam`s,
  added/renamed through the standard `GH_Component.Params` API plus
  `VariableParameterMaintenance()`.
