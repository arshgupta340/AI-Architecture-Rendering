r"""Host-side GLB post-process for the Option B web-3D configurator.

Lifts the semantic identity that spike/rhino_export_gltf.py encoded into object
NAMES ("{semantic}__{i}") up into glTF `node.extras` so three.js exposes it as
`mesh.userData`. Pure-Python GLB read/modify/write — NO third-party deps
(pygltflib install is blocked in this env), only the stdlib + the proven
ruleset in spike/rhino_capture.py.

Semantic is resolved TOP-DOWN per node and propagated to descendant meshes:
  1. node named "{sem}__{i}" present in semantics.json  -> authoritative semantic
     (+ guid + full layer path).
  2. otherwise, a layer-hierarchy node (ExportLayers=True kept these) folds its
     name into an accumulated layer path -> rhino_capture.semantic_from_layer.
     This recovers the 26 window InstanceReference blocks Rhino flattened: their
     meshes still sit under the "08 - OPENINGS" layer node -> "window".
  3. else inherit the parent's resolved semantic.

`extras.semantic` is written on every mesh-bearing node so the web app can
group meshes by element class without any further lookups.

Run:  spike\.venv\Scripts\python.exe spike/gltf_postprocess.py \
        [in.glb] [semantics.json] [out.glb]
Defaults operate on spike/outputs/web3d_house/.
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find rhino_capture
import rhino_capture as rc  # noqa: E402  (pure-python ruleset; Rhino import is guarded)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "outputs", "web3d_house")
OBJ_RE = re.compile(r"^([a-zA-Z_]+)__\d+$")


def read_glb(path):
    """Return (gltf_dict, bin_bytes) from a binary GLB."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        raise ValueError("not a GLB: %s" % path)
    off, json_chunk, bin_chunk = 12, None, None
    while off < len(data):
        clen = struct.unpack_from("<I", data, off)[0]
        ctype = data[off + 4:off + 8]
        chunk = data[off + 8:off + 8 + clen]
        off += 8 + clen
        if ctype == b"JSON":
            json_chunk = chunk
        elif ctype[:3] == b"BIN":
            bin_chunk = chunk
    return json.loads(json_chunk.decode("utf-8")), bin_chunk


def write_glb(path, gltf, bin_bytes):
    """Write a binary GLB from a gltf dict + (optional) BIN chunk."""
    jb = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    chunks = [(b"JSON", jb)]
    if bin_bytes is not None:
        bb = bin_bytes + b"\x00" * ((4 - len(bin_bytes) % 4) % 4)
        chunks.append((b"BIN\x00", bb))
    total = 12 + sum(8 + len(c) for _, c in chunks)
    with open(path, "wb") as f:
        f.write(b"glTF")
        f.write(struct.pack("<II", 2, total))
        for ctype, c in chunks:
            f.write(struct.pack("<I", len(c)))
            f.write(ctype)
            f.write(c)


def inject_semantics(gltf, objects, rules):
    """Write extras.semantic on every mesh node; return (stats, n_unmatched)."""
    nodes = gltf.get("nodes", [])
    roots = []
    for s in gltf.get("scenes", []):
        roots += s.get("nodes", [])
    if not roots:
        children = {c for n in nodes for c in n.get("children", [])}
        roots = [i for i in range(len(nodes)) if i not in children]

    stats, unmatched = Counter(), []

    def own(node):
        """(semantic, layer_segment, guid, full_layer) from a node's own name."""
        nm = node.get("name", "") or ""
        m = OBJ_RE.match(nm)
        if m and nm in objects:
            o = objects[nm]
            return o["semantic"], None, o.get("guid"), o.get("layer")
        if m:
            return m.group(1), None, None, None
        return None, (nm or None), None, None  # treat as a layer segment

    def dfs(idx, inherited, layer_path):
        n = nodes[idx]
        sem, seg, guid, full_layer = own(n)
        lp = layer_path
        if sem is None and seg:
            lp = (layer_path + "::" + seg) if layer_path else seg
            s = rc.semantic_from_layer(lp, rules)
            sem = s if s != "other" else None
        resolved = sem or inherited
        if "mesh" in n:
            if resolved:
                ex = n.get("extras") or {}
                ex["semantic"] = resolved
                if guid:
                    ex["guid"] = guid
                if full_layer or lp:
                    ex["layer"] = full_layer or lp
                n["extras"] = ex
                stats[resolved] += 1
            else:
                unmatched.append(idx)
        for c in n.get("children", []):
            dfs(c, resolved, lp)

    for r in roots:
        dfs(r, None, "")
    return stats, len(unmatched)


def main():
    in_glb = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DEFAULT_DIR, "house_raw.glb")
    sem_json = sys.argv[2] if len(sys.argv) > 2 else os.path.join(DEFAULT_DIR, "semantics.json")
    out_glb = sys.argv[3] if len(sys.argv) > 3 else os.path.join(DEFAULT_DIR, "house.glb")

    meta = json.loads(open(sem_json, encoding="utf-8").read())
    rules = rc.RULESETS.get(meta.get("ruleset", "csi"), rc.CSI_RULES)
    objects = meta["objects"]

    gltf, bin_bytes = read_glb(in_glb)
    n_mesh_nodes = sum(1 for n in gltf.get("nodes", []) if "mesh" in n)
    stats, n_unmatched = inject_semantics(gltf, objects, rules)
    write_glb(out_glb, gltf, bin_bytes)

    report = {
        "in_glb": in_glb,
        "out_glb": out_glb,
        "out_size_mb": round(os.path.getsize(out_glb) / 1e6, 2),
        "n_nodes": len(gltf.get("nodes", [])),
        "n_mesh_nodes": n_mesh_nodes,
        "mesh_nodes_tagged": sum(stats.values()),
        "mesh_nodes_unmatched": n_unmatched,
        "semantic_tally": dict(stats),
    }
    print(json.dumps(report, indent=2))
    if n_unmatched > n_mesh_nodes * 0.10:
        print("WARNING: %d/%d mesh nodes have no semantic (>10%%)" %
              (n_unmatched, n_mesh_nodes), file=sys.stderr)


if __name__ == "__main__":
    main()
