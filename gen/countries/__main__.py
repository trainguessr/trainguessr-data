"""Run a country station generator from its package."""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
import requests

GEN_DIR = Path(__file__).resolve().parents[1]
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

COUNTRIES = (
    "austria", "belgium", "denmark", "finland", "france", "germany",
    "italy", "netherlands", "norway", "spain", "sweden", "switzerland", "uk",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download, review and publish one country's station dataset."
    )
    parser.add_argument("country", choices=COUNTRIES)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    generator = importlib.import_module(f"countries.{parsed.country}.generate")
    previous_program = sys.argv[0]
    sys.argv[0] = f"python3 -m gen.countries {parsed.country}"
    try:
        try:
            return int(generator.main(parsed.args) or 0)
        except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    finally:
        sys.argv[0] = previous_program


if __name__ == "__main__":
    raise SystemExit(main())
