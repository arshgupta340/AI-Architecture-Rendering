r"""Vendor a CC0 HDRI from Poly Haven into the web app (offline, no drei CDN).

Run: spike\.venv\Scripts\python.exe spike/ingest_hdri.py [slug] [res]
Defaults: venice_sunset @ 2k -> apps/web3d-prototype/public/hdri/sky.hdr
"""
from __future__ import annotations

import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "apps", "web3d-prototype", "public", "hdri"))


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "venice_sunset"
    res = sys.argv[2] if len(sys.argv) > 2 else "2k"
    url = f"https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{res}/{slug}_{res}.hdr"
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, "sky.hdr")
    print(f"downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "web3d-mvp-hdri"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    print(f"saved {dest}  ({len(data) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
