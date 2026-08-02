from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_country_config(country: str) -> dict[str, Any]:
    path = ROOT / "excludes" / f"{country}.json"
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def load_rename_map(country: str, operator: str | None = None) -> dict[str, str]:
    rows = load_country_config(country).get("renamed", [])
    result: dict[str, str] = {}
    for row in rows:
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        result[str(row["from"])] = str(row["to"])
    return result


def load_excluded_ids(country: str, operator: str | None = None) -> set[str]:
    rows = load_country_config(country).get("excluded", [])
    result: set[str] = set()
    for row in rows:
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        station_id = row.get("id")
        if station_id not in (None, ""):
            result.add(str(station_id))
    return result
