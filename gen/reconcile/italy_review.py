#!/usr/bin/env python3
"""Interactive Italian provider review CLI."""
from pathlib import Path
import sys

GEN_ROOT = Path(__file__).resolve().parents[1]
if str(GEN_ROOT) not in sys.path:
    sys.path.insert(0, str(GEN_ROOT))

from reconcile.italy.review import main

if __name__ == "__main__":
    raise SystemExit(main())
