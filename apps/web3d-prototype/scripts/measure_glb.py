"""Measure the world-space bbox of GLB(s) by walking the glTF node tree and
transforming every POSITION accessor's min/max corners. stdlib only (struct/json).

Prints: file<TAB>height<TAB>width<TAB>depth  (model units, glTF +Y up).
We need the Y-extent (height) to normalize each species to real feet.
"""
import sys
import os
import json
import struct

GLB_MAGIC = b"glTF"

# glTF componentType -> (struct fmt, byte size)
CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
NUMC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    assert data[:4] == GLB_MAGIC, "not a glb"
    # header 12 bytes, then chunks: [len(4) type(4) data]
    off = 12
    gltf, bin_chunk = None, None
    while off < len(data):
        clen = struct.unpack_from("<I", data, off)[0]
        ctype = data[off + 4:off + 8]
        cdata = data[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            gltf = json.loads(cdata.decode("utf-8"))
        elif ctype == b"BIN\x00":
            bin_chunk = cdata
        off += 8 + clen
    return gltf, bin_chunk


def mat_mul(a, b):
    # column-major 4x4 (glTF convention)
    r = [0.0] * 16
    for c in range(4):
        for row in range(4):
            s = 0.0
            for k in range(4):
                s += a[k * 4 + row] * b[c * 4 + k]
            r[c * 4 + row] = s
    return r


def trs_matrix(node):
    if "matrix" in node:
        return list(node["matrix"])
    t = node.get("translation", [0, 0, 0])
    r = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = r
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    sx, sy, sz = s
    return [
        (1 - 2 * (yy + zz)) * sx, (2 * (xy + wz)) * sx, (2 * (xz - wy)) * sx, 0,
        (2 * (xy - wz)) * sy, (1 - 2 * (xx + zz)) * sy, (2 * (yz + wx)) * sy, 0,
        (2 * (xz + wy)) * sz, (2 * (yz - wx)) * sz, (1 - 2 * (xx + yy)) * sz, 0,
        t[0], t[1], t[2], 1,
    ]


def xform(m, p):
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def bbox(path):
    gltf, _ = load_glb(path)
    accessors = gltf.get("accessors", [])
    meshes = gltf.get("meshes", [])
    nodes = gltf.get("nodes", [])
    scenes = gltf.get("scenes", [])
    scene = gltf.get("scene", 0)
    roots = scenes[scene]["nodes"] if scenes else range(len(nodes))

    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3

    def walk(ni, parent):
        node = nodes[ni]
        world = mat_mul(parent, trs_matrix(node))
        if "mesh" in node:
            for prim in meshes[node["mesh"]].get("primitives", []):
                pi = prim.get("attributes", {}).get("POSITION")
                if pi is None:
                    continue
                acc = accessors[pi]
                if "min" in acc and "max" in acc:
                    mn, mx = acc["min"], acc["max"]
                    corners = [
                        (mn[0], mn[1], mn[2]), (mx[0], mn[1], mn[2]),
                        (mn[0], mx[1], mn[2]), (mn[0], mn[1], mx[2]),
                        (mx[0], mx[1], mn[2]), (mx[0], mn[1], mx[2]),
                        (mn[0], mx[1], mx[2]), (mx[0], mx[1], mx[2]),
                    ]
                    for cpt in corners:
                        wp = xform(world, cpt)
                        for k in range(3):
                            lo[k] = min(lo[k], wp[k])
                            hi[k] = max(hi[k], wp[k])
        for ch in node.get("children", []):
            walk(ch, world)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for r in roots:
        walk(r, ident)
    return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]), (lo, hi)


def main():
    for path in sys.argv[1:]:
        try:
            (w, h, d), (lo, hi) = bbox(path)
            print(f"{os.path.basename(path)}\theight={h:.3f}\twidth={w:.3f}\tdepth={d:.3f}\tymin={lo[1]:.3f}\tymax={hi[1]:.3f}")
        except Exception as e:
            print(f"{os.path.basename(path)}\tERROR {e}")


if __name__ == "__main__":
    main()
