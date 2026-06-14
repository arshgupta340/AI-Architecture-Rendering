"""Fetch CC0 entourage GLBs from poly.pizza (Quaternius Stylized Nature MegaKit).

Two-step per model: GET https://poly.pizza/m/{slug} (HTML, browser UA) -> regex the
real CDN url https://static.poly.pizza/{uuid}.glb -> download THAT. Validate 'glTF'
magic on every file. stdlib only.
"""
import os
import re
import sys
import json
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, "public", "entourage")
BUNDLE_URL = "https://poly.pizza/bundle/Stylized-Nature-MegaKit-T34GZFA0fm"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def harvest_bundle():
    """Return list of (slug, display_name) from the bundle page.

    Links are React-Router <Link to="/m/{slug}">{Name}<  (not plain href).
    """
    html = get(BUNDLE_URL)
    pairs = re.findall(r'to="/m/([A-Za-z0-9_-]+)">([^<]{0,40})', html)
    # dedupe by slug, keep order
    seen, out = set(), []
    for slug, name in pairs:
        if slug not in seen:
            seen.add(slug)
            out.append((slug, name.strip()))
    return out, html


def resolve_glb(slug):
    """GET model page, return (cdn_url, title)."""
    html = get(f"https://poly.pizza/m/{slug}")
    m = re.search(r'https://static\.poly\.pizza/([A-Za-z0-9_-]+)\.glb', html)
    if not m:
        return None, None
    cdn = m.group(0)
    tm = re.search(r'<title>([^<]+)</title>', html)
    title = (tm.group(1) if tm else slug).split("|")[0].split("-")[0].strip()
    return cdn, title


def sanitize(name):
    n = re.sub(r'[^A-Za-z0-9]+', "_", name).strip("_")
    return n or "asset"


def download_glb(cdn, dest):
    data = get(cdn, binary=True)
    if data[:4] != b"glTF":
        raise ValueError(f"not a glb (magic={data[:4]!r})")
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


# classify a slug/title into tree | bush | skip
TREE_RE = re.compile(r'\b(tree|pine|birch|oak|palm|willow|spruce|fir|maple|conifer)\b', re.I)
BUSH_RE = re.compile(r'\b(bush|shrub|fern|hedge|clover|tall.?grass)\b', re.I)


def main():
    want_trees = int(os.environ.get("N_TREES", "8"))
    want_bushes = int(os.environ.get("N_BUSHES", "4"))
    pairs, _ = harvest_bundle()
    print(f"bundle: {len(pairs)} model links", file=sys.stderr)
    manifest = {"trees": [], "bushes": []}
    for slug, bundle_name in pairs:
        if len(manifest["trees"]) >= want_trees and len(manifest["bushes"]) >= want_bushes:
            break
        name = bundle_name or slug
        is_tree = bool(TREE_RE.search(name))
        is_bush = bool(BUSH_RE.search(name))
        kind = None
        if is_tree and len(manifest["trees"]) < want_trees:
            kind = "trees"
        elif is_bush and len(manifest["bushes"]) < want_bushes:
            kind = "bushes"
        if not kind:
            continue
        try:
            cdn, title = resolve_glb(slug)
        except Exception as e:
            print(f"  resolve fail {slug}: {e}", file=sys.stderr)
            continue
        if not cdn:
            print(f"  no cdn url for {slug} ({name})", file=sys.stderr)
            continue
        fname = sanitize(name) + ".glb"
        dest = os.path.join(ENT, kind, fname)
        # avoid dupe filenames
        if os.path.exists(dest):
            fname = sanitize(name) + "_" + slug[:6] + ".glb"
            dest = os.path.join(ENT, kind, fname)
        try:
            n = download_glb(cdn, dest)
        except Exception as e:
            print(f"  dl fail {slug} ({name}): {e}", file=sys.stderr)
            continue
        manifest[kind].append({"slug": slug, "name": name, "file": fname, "url": cdn, "bytes": n})
        print(f"  [{kind}] {name} -> {fname} ({n} bytes)", file=sys.stderr)
        time.sleep(0.25)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
