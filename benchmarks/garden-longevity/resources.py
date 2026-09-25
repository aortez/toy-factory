#!/usr/bin/env python3
"""Compatibility entry point for the maintained host resource analyzer."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
from garden_resources import analyze, analyze_stream, budget, main, require  # noqa: E402,F401


if __name__ == "__main__":
    raise SystemExit(main())
