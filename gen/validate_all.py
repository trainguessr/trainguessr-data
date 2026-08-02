#!/usr/bin/env python3
from __future__ import annotations

from common.io import ROOT
from common.validate import validate_file


def main() -> int:
    failures = 0
    paths = sorted((ROOT / "nodes").glob("nodes-*.json"))
    for path in paths:
        errors = validate_file(path)
        print(f"{path.relative_to(ROOT)}: {len(errors)} errors")
        for error in errors:
            print(f"  {error}")
        failures += len(errors)
    print(f"Validated {len(paths)} datasets; {failures} errors")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
