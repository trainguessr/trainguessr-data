#!/usr/bin/env python3
"""Report generator type and freshness of generated TrainGuessr datasets."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.io import ROOT

# "automated" means the primary fetched source contains provider identity and
# geographic coordinates together. "heuristic" means generation must reconcile
# provider identity with a separate geographic/source catalogue.
DATASETS = [
    ("austria", "heuristic", "nodes/nodes-austria-oebb.json", "python3 gen/austria.py"),
    ("belgium", "automated", "nodes/nodes-belgium.json", "python3 gen/belgium.py"),
    ("denmark", "automated", "nodes/nodes-denmark.json", "python3 gen/denmark.py"),
    ("finland", "automated", "nodes/nodes-finland.json", "python3 gen/finland.py"),
    ("france", "automated", "nodes/nodes-france-sncf.json", "python3 gen/france.py"),
    ("germany", "automated", "nodes/nodes-germany.json", "python3 gen/germany.py"),
    ("italy/eav", "heuristic", "nodes/nodes-italy-eav.json", "python3 gen/italy.py generate eav"),
    ("italy/fer", "heuristic", "nodes/nodes-italy-fer.json", "python3 gen/italy.py generate fer"),
    ("italy/fn", "heuristic", "nodes/nodes-italy-fn.json", "python3 gen/italy.py generate fn"),
    ("italy/fse", "heuristic", "nodes/nodes-italy-fse.json", "python3 gen/italy.py generate fse"),
    ("italy/rfi", "heuristic", "nodes/nodes-italy-rfi.json", "python3 gen/italy.py generate rfi"),
    ("italy/sta", "heuristic", "nodes/nodes-italy-sta.json", "python3 gen/italy.py generate sta"),
    ("italy/tt", "heuristic", "nodes/nodes-italy-tt.json", "python3 gen/italy.py generate tt"),
    ("netherlands", "automated", "nodes/nodes-netherlands.json", "python3 gen/netherlands.py"),
    ("norway", "automated", "nodes/nodes-norway.json", "python3 gen/norway.py"),
    ("spain/renfe", "automated", "nodes/nodes-spain-renfe.json", "python3 gen/spain.py"),
    ("spain/fgc", "automated", "nodes/nodes-spain-fgc.json", "python3 gen/spain.py"),
    ("sweden", "automated", "nodes/nodes-sweden.json", "python3 gen/sweden.py"),
    ("switzerland", "automated", "nodes/nodes-switzerland.json", "python3 gen/switzerland.py"),
    ("uk", "automated", "nodes/nodes-uk-nationalrail.json", "python3 gen/uk.py"),
]

# Existing source-specific expectations. Everything else is reported by age,
# without pretending that an upstream freshness SLA exists.
AGE_LIMITS = {"denmark": 14, "france": 7}


def age_days(path: Path, now: datetime) -> int | None:
    if not path.is_file():
        return None
    stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return max(0, int((now - stamp).total_seconds() // 86400))


def sqlite_calendar_end(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(path) as db:
            row = db.execute(
                "SELECT max(value) FROM ("
                "SELECT json_extract(payload, '$.end_date') AS value FROM calendar "
                "UNION ALL SELECT date AS value FROM calendar_dates"
                ") WHERE value IS NOT NULL AND value != ''"
            ).fetchone()
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return None
    return str(row[0]) if row and row[0] else None


def print_table(rows: list[tuple[str, ...]]) -> None:
    """Align columns using the complete report, including timetable statuses."""
    headers = ("dataset", "kind", "age_days", "status", "command")
    widths = [max(len(row[column]) for row in [headers, *rows]) for column in range(len(headers))]
    for row in [headers, *rows]:
        print("  ".join(
            value.rjust(widths[column]) if column == 2 else value.ljust(widths[column])
            for column, value in enumerate(row)
        ).rstrip())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stale-after-days", type=int, default=30,
                        help="fallback review threshold where no source-specific limit exists")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y%m%d")

    rows = []
    due = []
    for name, kind, relative, command in DATASETS:
        age = age_days(ROOT / relative, now)
        limit = AGE_LIMITS.get(name, args.stale_after_days)
        if age is None:
            status = "missing"
        elif age > limit:
            status = f"stale>{limit}d"
        else:
            status = "current"
        rows.append((name, kind, str(age) if age is not None else "-", status, command))
        if status != "current":
            due.append(command)

    for label, relative in (
        ("spain/renfe timetable", "cache/spain.sqlite"),
        ("spain/fgc timetable", "cache/spain-fgc.sqlite"),
    ):
        end = sqlite_calendar_end(ROOT / relative)
        if end is None:
            rows.append((label, "automated", "-", "index-missing/unreadable", "python3 gen/spain.py"))
            due.append("python3 gen/spain.py")
        else:
            status = "expired" if end < today else f"calendar-through-{end}"
            rows.append((label, "automated", "-", status, "python3 gen/spain.py"))
            if end < today:
                due.append("python3 gen/spain.py")

    print_table(rows)
    print("\nRerun:")
    for command in dict.fromkeys(due):
        print(f"  {command}")
    return 1 if due else 0


if __name__ == "__main__":
    raise SystemExit(main())
