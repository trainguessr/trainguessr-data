"""Run a one-time reconstruction or research tool."""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parents[1]
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

TOOLS = {
    "finland": "bootstrap.finland",
    "france": "bootstrap.france",
    "france-capture": "bootstrap.france_capture",
    "germany": "bootstrap.germany.cli",
    "italy-viaggiatreno": "bootstrap.italy.viaggiatreno.cli",
    "spain-fgc-capture": "bootstrap.spain_fgc_capture",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a one-time research or reconstruction tool."
    )
    parser.add_argument("tool", choices=tuple(TOOLS))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    tool = importlib.import_module(TOOLS[parsed.tool])
    return int(tool.main(parsed.args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
