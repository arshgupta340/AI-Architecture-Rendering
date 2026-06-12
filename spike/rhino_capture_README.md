# rhino_capture.py — Rhino-side ground-truth capture

Productionized E1/E2 capture flow. One atomic run inside Rhino's Python writes
the proven output contract to a directory (same shape as
`spike/outputs/e2_house/`):

| file | contents |
|---|---|
| `beauty.png` | Shaded viewport capture (render input) |
| `depth.png` | true z-buffer (`ZBufferCapture.GrayscaleDib`) |
| `light_pass.png` | white reference pass (per-pixel lighting base) |
| `id_mask.png` | flat per-object ID colors |
| `objects.json` | `{"encoding": {...}, "objects": {key → guid/layer/semantic/object_type/material/name}}` |
| `camera.json` | location/target/up, lens_35mm, frustum_raw (7-tuple), size_px, projection, depth_meta |

Decode host-side with `spike/host_probe_rhino.py` (`decode(out_dir)`,
`mask_for(out_dir, predicate)`). ID encoding: `r=5*(i//2704)`,
`g=5*((i%2704)//52)`, `b=5*(i%52)` — keys are `"g,b"` on plane 0 (backward
compatible with E1/E2 data), `"r,g,b"` beyond, up to 140,608 objects/frame.
The decoder handles both.

## API

```python
capture(out_dir,
        semantic_rules=None,        # 'csi' | 'keyword' | 'auto'/None | [(PATTERN, semantic), ...]
        hide_layer_prefixes=None,   # e.g. ["#", "X-", "00 -"] — switched off, restored after
        hide_2d_objects=True,       # hide curves/annotations/hatches for all passes, restored
        camera=None)                # {"location":[...], "target":[...], "up":[...], "lens_35mm": f}
-> {"out_dir", "n_objects", "size_px", "ruleset", "depth_meta", "files"}
```

Semantics come from layer names. Two built-in rule sets — `csi`
(CSI MasterFormat: `08-OPENINGS`→window/door, `06-02`→wall, `06-04`→roof, …)
and `keyword` (MULLION/GLASS/DOOR/WALL/…, E1-style). `auto` (default) sniffs
the doc's layer names. All document changes (object colors, hidden
objects/layers, display mode, grid/axes) are restored in a `finally` block.

## Running it

### a) Via the Rhino MCP (`run_python`)

```python
src = open(r"C:\Users\arshg\AI Architecture Rendering\spike\rhino_capture.py").read()
ns = {"__rhino_doc__": __rhino_doc__}
exec(compile(src, "rhino_capture.py", "exec"), ns)
print(ns["capture"](r"C:\...\spike\outputs\my_capture"))
```

Pass `camera={...}` to pin the view inside the atomic run (the hidden MCP
viewport can resize between calls — never split the capture across calls).

### b) Pasted into Rhino's ScriptEditor

Open the file in the ScriptEditor (Python 3) and run it — the
`__main__` block captures the active viewport to `spike/outputs/capture_out/`.
Or `import rhino_capture` (add `spike/` to `sys.path`) and call `capture(...)`
yourself. Without `__rhino_doc__` it falls back to `Rhino.RhinoDoc.ActiveDoc`.

### c) Future: Grasshopper component (GhPython)

A GhPython component with inputs `out_dir` (str) and `run` (bool), output
`summary`:

```python
import sys; sys.path.append(r"C:\...\spike")
import rhino_capture
if run:
    summary = str(rhino_capture.capture(out_dir))
```

Same module, same contract; Grasshopper supplies the doc via `ActiveDoc`.

## Verified

2026-06-12, `kCs_SampleHouseProject V1.3dm`, e2_house hero camera →
`spike/outputs/capture_test/`: **90.5%** of object pixels decoded exactly
(251 objects in frame), identical to the proven E2 reference capture.
