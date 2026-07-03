#!/usr/bin/env python3
"""Compatibility wrapper for the canonical script in src/."""

from pathlib import Path
import runpy
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "decrypt_session_pipeline.py"

if str(TARGET.parent) not in sys.path:
    sys.path.insert(0, str(TARGET.parent))

runpy.run_path(str(TARGET), run_name="__main__")
