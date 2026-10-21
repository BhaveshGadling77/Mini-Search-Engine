import sys
from pathlib import Path

# Locate the compiled Worklet 2 module.
ROOT = Path(__file__).resolve().parent.parent.parent
W2_BUILD = ROOT  / "build"

sys.path.insert(0, str(W2_BUILD))

from wl2bridge import * 

print("Successfully imported Worklet 2!")