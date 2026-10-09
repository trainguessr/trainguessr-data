from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _normal_name(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def reviewed_name(row: dict[str, Any]) -> str:
    """Return the source identity recorded by a reviewed override."""
    tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
    return str(row.get("expected_name") or row.get("name") or tags.get("name") or "").strip()


def load_country_config(country: str) -> dict[str, Any]:
    path = ROOT / "overrides" / "exclusions" / f"{country}.json"
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
        if row.get("id") not in (None, ""):
            continue
        result[str(row["from"])] = str(row["to"])
    return result


def load_rename_id_map(country: str, operator: str | None = None) -> dict[str, str]:
    return {
        station_id: str(row["to"])
        for station_id, row in load_rename_id_rules(country, operator).items()
    }


def load_rename_id_rules(
    country: str,
    operator: str | None = None,
) -> dict[str, dict[str, Any]]:
    rows = load_country_config(country).get("renamed", [])
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        station_id = row.get("id")
        if station_id not in (None, ""):
            key = str(station_id)
            if key in result:
                raise ValueError(f"{country}: duplicate ID rename for station {key}")
            if not str(row.get("from") or "").strip() or not str(row.get("to") or "").strip():
                raise ValueError(f"{country}: ID rename {key} requires from and to names")
            result[key] = row
    return result


def load_excluded_ids(country: str, operator: str | None = None) -> set[str]:
    return set(load_exclusion_rules(country, operator))


def load_exclusion_rules(
    country: str,
    operator: str | None = None,
) -> dict[str, dict[str, Any]]:
    rows = load_country_config(country).get("excluded", [])
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{country}: every exclusion must be an object")
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        station_id = row.get("id")
        if station_id not in (None, ""):
            key = str(station_id)
            if key in result:
                raise ValueError(f"{country}: duplicate exclusion for station ID {key}")
            result[key] = row
    return result


def require_reviewed_identity(
    rule: dict[str, Any],
    actual_name: object,
    *,
    context: str,
) -> None:
    """Fail when a destructive reviewed rule no longer names its source row."""
    expected_name = reviewed_name(rule)
    if not expected_name:
        raise ValueError(f"{context}: reviewed override has no expected station name")
    actual = str(actual_name or "").strip()
    if _normal_name(actual) != _normal_name(expected_name):
        raise ValueError(
            f"{context}: stale reviewed override: expected {expected_name!r}, "
            f"source now reports {actual!r}"
        )
