"""Tests for Worklet 1: Crawler & Document Model."""

import sys
from pathlib import Path

# Link tests to wl1/crawler components
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))
