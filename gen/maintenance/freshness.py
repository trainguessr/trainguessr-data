#!/usr/bin/env python3
"""Show when station files changed and which ones may need checking."""
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
    ("austria", "reviewed", "nodes/nodes-austria-oebb.json", "python3 -m gen.countries austria"),
    ("belgium", "official", "nodes/nodes-belgium.json", "python3 -m gen.countries belgium"),
    ("denmark", "official", "nodes/nodes-denmark.json", "python3 -m gen.countries denmark"),
    ("finland", "official", "nodes/nodes-finland.json", "python3 -m gen.countries finland"),
    ("france", "official", "nodes/nodes-france-sncf.json", "python3 -m gen.countries france"),
    ("germany", "reviewed", "nodes/nodes-germany.json", "python3 -m gen.countries germany"),
    ("italy/eav", "reviewed", "nodes/nodes-italy-eav.json", "python3 -m gen.countries italy generate eav"),
    ("italy/fer", "reviewed", "nodes/nodes-italy-fer.json", "python3 -m gen.countries italy generate fer"),
    ("italy/fn", "reviewed", "nodes/nodes-italy-fn.json", "python3 -m gen.countries italy generate fn"),
    ("italy/fse", "reviewed", "nodes/nodes-italy-fse.json", "python3 -m gen.countries italy generate fse"),
    ("italy/rfi", "reviewed", "nodes/nodes-italy-rfi.json", "python3 -m gen.countries italy generate rfi"),
    ("italy/sta", "reviewed", "nodes/nodes-italy-sta.json", "python3 -m gen.countries italy generate sta"),
    ("italy/tt", "reviewed", "nodes/nodes-italy-tt.json", "python3 -m gen.countries italy generate tt"),
    ("netherlands", "official", "nodes/nodes-netherlands.json", "python3 -m gen.countries netherlands"),
    ("norway", "official", "nodes/nodes-norway.json", "python3 -m gen.countries norway"),
    ("spain/renfe", "official", "nodes/nodes-spain-renfe.json", "python3 -m gen.countries spain"),
    ("spain/fgc", "official", "nodes/nodes-spain-fgc.json", "python3 -m gen.countries spain"),
    ("sweden", "official", "nodes/nodes-sweden.json", "python3 -m gen.countries sweden"),
    ("switzerland", "official", "nodes/nodes-switzerland.json", "python3 -m gen.countries switzerland"),
    ("uk", "official", "nodes/nodes-uk-nationalrail.json", "python3 -m gen.countries uk"),
]

# Existing source-specific expectations. Everything else is reported by age,
# without pretending that an upstream freshness SLA exists.
AGE_LIMITS = {"denmark": 14, "france": 7, "italy/sta": 90}


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
                "SELECT json_extract(data, '$.end_date') AS value FROM calendar "
                "UNION ALL SELECT date AS value FROM calendar_dates"
                ") WHERE value IS NOT NULL AND value != ''"
            ).fetchone()
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return None
    return str(row[0]) if row and row[0] else None


def print_table(rows: list[tuple[str, ...]]) -> None:
    """Align columns using the complete report, including timetable statuses."""
    headers = ("dataset", "source type", "file age (days)", "status", "command")
    widths = [max(len(row[column]) for row in [headers, *rows]) for column in range(len(headers))]
    for row in [headers, *rows]:
        print("  ".join(
            value.rjust(widths[column]) if column == 2 else value.ljust(widths[column])
            for column, value in enumerate(row)
        ).rstrip())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stale-after-days", type=int, default=30,
                        help="flag station files older than this many days (default: 30)")
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
            status = f"older than {limit} days"
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
            rows.append((label, "official", "-", "missing or unreadable", "python3 -m gen.countries spain"))
            due.append("python3 -m gen.countries spain")
        else:
            status = "expired" if end < today else f"current through {end}"
            rows.append((label, "official", "-", status, "python3 -m gen.countries spain"))
            if end < today:
                due.append("python3 -m gen.countries spain")

    print_table(rows)
    print("\nFile age shows when the station file last changed. It does not show when the provider data changed.")
    print("If the station file is unchanged, its file date stays the same. Check saved source dates for source age.")
    print("\nRerun from the repository root:")
    for command in dict.fromkeys(due):
        print(f"  {command}")
    return 1 if due else 0


if __name__ == "__main__":
    raise SystemExit(main())
