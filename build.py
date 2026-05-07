"""Build LeanPDF using PyInstaller (one-folder by default).

Usage:
    python build.py            # one-folder build (recommended for first runs)
    python build.py --onefile  # single-file build (slower startup, harder to debug)

One-folder is preferred initially because:
    - Startup is much faster — no extraction step.
    - Crashes show real file paths, easier to diagnose.
    - You can ship the folder zipped.

Once stable, you can switch to --onefile for distribution simplicity.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "app" / "main.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LeanPDF with PyInstaller.")
    parser.add_argument("--onefile", action="store_true", help="Build a single-file executable.")
    parser.add_argument("--clean", action="store_true", help="Remove dist/ and build/ first.")
    args = parser.parse_args()

    if args.clean:
        for p in (DIST, BUILD):
            if p.exists():
                shutil.rmtree(p)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "LeanPDF",
        str(ENTRY),
    ]
    if args.onefile:
        cmd.insert(-1, "--onefile")
    else:
        cmd.insert(-1, "--onedir")

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
