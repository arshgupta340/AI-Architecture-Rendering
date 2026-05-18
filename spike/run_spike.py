"""
run_spike.py — one-shot setup + launch script for the spike.

IMPORTANT: Always run from inside the .venv (Python 3.12):
  .venv\Scripts\activate          # Windows PowerShell
  python run_spike.py setup
  python run_spike.py run

Usage:
  python run_spike.py setup   # uploads Modal secret, checks test asset
  python run_spike.py run     # fires modal run modal_app.py with defaults
  python run_spike.py run --prompt "..." --click-x 500 --click-y 400
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def setup():
    print("\n[1/4] Installing Modal CLI...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "modal", "python-dotenv", "google-genai", "Pillow"])

    print("\n[2/4] Checking Modal authentication...")
    result = subprocess.run(["modal", "token", "new"], capture_output=True)
    if result.returncode != 0:
        print("  -> Run: modal token new")
        print("     This opens a browser to link your Modal account.")

    print("\n[3/4] Uploading Google API key to Modal secrets...")
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key or api_key == "paste_your_key_here":
        print("  ERROR: Set GOOGLE_API_KEY in spike/.env first, then re-run.")
        sys.exit(1)
    subprocess.check_call([
        "modal", "secret", "create", "arch-spike",
        f"GOOGLE_API_KEY={api_key}",
        "--force",
    ])
    print("  Secret 'arch-spike' created on Modal.")

    print("\n[4/4] Checking test material asset...")
    asset_dir = Path("test_assets")
    asset_dir.mkdir(exist_ok=True)
    travertine = asset_dir / "travertine.jpg"
    if not travertine.exists():
        print("  Downloading a sample travertine swatch from ambientCG...")
        import urllib.request
        urllib.request.urlretrieve(
            "https://ambientcg.com/get?file=Travertine005_1K-JPG.zip",
            "test_assets/travertine.zip",
        )
        import zipfile
        with zipfile.ZipFile("test_assets/travertine.zip") as z:
            for name in z.namelist():
                if "Color" in name and name.endswith(".jpg"):
                    data = z.read(name)
                    travertine.write_bytes(data)
                    print(f"  Extracted: {travertine}")
                    break
        Path("test_assets/travertine.zip").unlink()
    else:
        print(f"  Test asset already present: {travertine}")

    print("\nSetup complete. Now run: python run_spike.py run")


def run(extra_args):
    cmd = ["modal", "run", "modal_app.py"] + extra_args
    print(f"\nLaunching: {' '.join(cmd)}\n")
    subprocess.check_call(cmd)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "setup":
        setup()
    elif args[0] == "run":
        run(args[1:])
    else:
        print(__doc__)
