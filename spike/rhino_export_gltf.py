r"""Rhino-side glTF/GLB export for the Option B web-3D configurator.

Runs INSIDE Rhino's Python (Rhino 8 CPython) via the Rhino MCP `run_python`
tool, mirroring spike/rhino_capture.py's usage pattern:

    import sys; sys.path.insert(0, r"...\spike")
    src = open(r"...\spike\rhino_export_gltf.py").read()
    ns = {"__rhino_doc__": __rhino_doc__}
    exec(compile(src, "rhino_export_gltf.py", "exec"), ns)
    print(ns["export"](r"...\spike\outputs\web3d_house"))

Produces, under out_dir:
  house_raw.glb   geometry; one node per object, node.name = "{semantic}__{i}"
  semantics.json  {ruleset, units, objects: {name -> {guid, layer, semantic, type}}}
  camera.json     same shape as rhino_capture (location/target/up/lens/frustum/size)

Semantic identity travels in the object NAME (the only channel Rhino's native
glTF exporter reliably preserves); spike/gltf_postprocess.py lifts it into
node.extras host-side. NON-DESTRUCTIVE: original object names are restored in a
finally (same save/restore idiom as rhino_capture's color passes). Reuses
rhino_capture's semantic rules (resolve_rules / semantic_from_layer).
"""
from __future__ import annotations

import json
import os
import struct
from collections import Counter

# Renderable object types worth exporting (skip Curve/Annotation/Hatch/Point noise).
RENDER_TYPES = {"Brep", "Extrusion", "Mesh", "SubD", "InstanceReference", "Surface"}


def glb_summary(path):
    """Parse a GLB's JSON chunk (no third-party deps) to self-verify an export."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return {"error": "not a GLB", "file_size": len(data)}
    json_len = struct.unpack_from("<I", data, 12)[0]  # first chunk = JSON
    j = json.loads(data[20:20 + json_len].decode("utf-8"))
    names = [n.get("name", "") for n in j.get("nodes", [])]
    sem = Counter(nm.split("__")[0] for nm in names if "__" in nm)
    return {
        "file_size": len(data),
        "n_nodes": len(j.get("nodes", [])),
        "n_meshes": len(j.get("meshes", [])),
        "n_named": sum(1 for nm in names if "__" in nm),
        "sem_tally": dict(sem),
        "sample_names": names[:14],
    }


def export(out_dir, semantic_rules="auto"):
    """Rename objects -> '{semantic}__{i}', write a GLB + semantics.json + camera.json.

    Returns a summary dict that includes glb_summary() so the caller can verify
    node count / naming / per-semantic tally without leaving Rhino.
    """
    import Rhino  # noqa: F401  (runtime only)
    from Rhino.FileIO import FileGltf, FileGltfWriteOptions

    doc = __rhino_doc__  # injected via the exec namespace (see module docstring)
    os.makedirs(out_dir, exist_ok=True)

    # Reuse the proven CSI/keyword ruleset from rhino_capture (spike/ on sys.path).
    import rhino_capture as rc
    all_layers = [doc.Layers[i].FullPath for i in range(doc.Layers.Count)]
    rule_name, rules = rc.resolve_rules(semantic_rules, all_layers)

    objs = [o for o in doc.Objects if str(o.ObjectType) in RENDER_TYPES]

    saved = []   # (guid, original_name) for restore
    table = {}   # name -> metadata
    try:
        for i, o in enumerate(objs):
            layer = doc.Layers[o.Attributes.LayerIndex].FullPath
            sem = rc.semantic_from_layer(layer, rules)
            name = "%s__%d" % (sem, i)
            attr = o.Attributes
            saved.append((o.Id, attr.Name))
            attr.Name = name
            doc.Objects.ModifyAttributes(o, attr, True)
            table[name] = {"guid": str(o.Id), "layer": layer,
                           "semantic": sem, "object_type": str(o.ObjectType)}
        doc.Views.Redraw()

        opts = FileGltfWriteOptions()
        opts.MapZToY = True            # Rhino Z-up -> glTF Y-up (-90deg about X)
        opts.ExportLayers = True       # layer hierarchy as parent nodes
        opts.ExportOpenMeshes = True   # single-surface walls export as open meshes
        opts.CullBackfaces = False     # keep both sides (DoubleSide in three.js)
        opts.ExportVertexNormals = True
        opts.ExportMaterials = False   # we assign our own PBR; dodges non-PBR crash
        opts.UseDracoCompression = False
        glb_path = os.path.join(out_dir, "house_raw.glb")
        ok = FileGltf.Write(glb_path, doc, opts)

        with open(os.path.join(out_dir, "semantics.json"), "w") as f:
            json.dump({"ruleset": rule_name, "units": str(doc.ModelUnitSystem),
                       "n_objects": len(objs), "objects": table}, f, indent=1)

        # camera.json — mirror of rhino_capture's block (lens + frustum near/far).
        vp = doc.Views.ActiveView.ActiveViewport
        cam = {
            "location": [vp.CameraLocation.X, vp.CameraLocation.Y, vp.CameraLocation.Z],
            "target": [vp.CameraTarget.X, vp.CameraTarget.Y, vp.CameraTarget.Z],
            "up": [vp.CameraUp.X, vp.CameraUp.Y, vp.CameraUp.Z],
            "lens_35mm": vp.Camera35mmLensLength,
            "frustum_raw": list(vp.GetFrustum()),
            "size_px": [vp.Size.Width, vp.Size.Height],
            "projection": "perspective" if vp.IsPerspectiveProjection else "parallel",
        }
        with open(os.path.join(out_dir, "camera.json"), "w") as f:
            json.dump(cam, f, indent=1)

        summary = {
            "ok": bool(ok), "glb": glb_path, "n_objects": len(objs),
            "ruleset": rule_name, "units": str(doc.ModelUnitSystem),
            "semantic_counts": dict(Counter(v["semantic"] for v in table.values())),
            "glb_summary": glb_summary(glb_path) if os.path.exists(glb_path) else None,
        }
        return summary
    finally:
        # Restore every original object name (fetch fresh by GUID).
        for gid, original in saved:
            obj = doc.Objects.FindId(gid)
            if obj is not None:
                a = obj.Attributes
                a.Name = original
                doc.Objects.ModifyAttributes(obj, a, True)
        doc.Views.Redraw()
