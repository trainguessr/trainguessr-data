"""Checked station corrections.

Each correction must still match the saved station ID and name. If they
changed, generation stops so a correction is not applied to another station.
"""
from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any, Iterable


def _norm_name(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def load_override_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    if path.suffix.lower() == ".csv":
        rows = []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for line, row in enumerate(csv.DictReader(handle), 2):
                try:
                    tags = json.loads(row.get("tags_json") or "{}")
                    remove_tags = json.loads(row.get("remove_tags_json") or "[]")
                    if not isinstance(tags, dict) or not isinstance(remove_tags, list):
                        raise ValueError
                    rows.append({
                        "operator": row["operator"], "id": row["id"],
                        "expected_name": row["expected_name"], "lat": float(row["lat"]),
                        "lon": float(row["lon"]), "reason": row["reason"],
                        "source": row["source"], "source_url": row["source_url"],
                        "tags": tags, "remove_tags": remove_tags,
                    })
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"{path}:{line}: check this coordinate correction") from exc
        return {"coordinate_overrides": rows}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: override file must contain a JSON object")
    return payload


def apply_coordinate_overrides(
    rows: list[dict[str, Any]],
    overrides: Iterable[dict[str, Any]],
    *,
    context: str,
) -> set[str]:
    """Apply coordinates only when both provider ID and expected name still match."""
    by_id = {str(row.get("id")): row for row in rows}
    used: set[str] = set()

    for override in overrides:
        station_id = str(override.get("id", "")).strip()
        expected_name = str(override.get("expected_name", "")).strip()
        if not station_id or not expected_name:
            raise ValueError(f"{context}: Check this station ID and its saved name.")
        row = by_id.get(station_id)
        if row is None:
            raise ValueError(
                f"{context}: Check station ID {station_id}. It is missing from the downloaded station list."
            )
        actual_name = str((row.get("tags") or {}).get("name") or "")
        if _norm_name(actual_name) != _norm_name(expected_name):
            raise ValueError(
                f"{context}: Check station ID {station_id}. The saved name is {expected_name!r}; "
                f"the downloaded name is {actual_name!r}."
            )
        try:
            lat = float(override["lat"])
            lon = float(override["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{context}: Check the coordinates for station ID {station_id}.") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"{context}: Check the coordinates for station ID {station_id}.")
        row["lat"] = lat
        row["lon"] = lon
        tags = row.setdefault("tags", {})
        for key in override.get("remove_tags", []):
            tags.pop(str(key), None)
        for key, value in (override.get("tags") or {}).items():
            tags[str(key)] = value
        tags["coordinate_override"] = True
        used.add(station_id)

    return used



def apply_name_overrides(
    rows: list[dict[str, Any]],
    overrides: Iterable[dict[str, Any]],
    *,
    context: str,
) -> set[str]:
    """Rename rows only when provider ID and current source name still match."""
    by_id = {str(row.get("id")): row for row in rows}
    used: set[str] = set()
    for override in overrides:
        station_id = str(override.get("id", "")).strip()
        expected_name = str(override.get("expected_name", "")).strip()
        new_name = str(override.get("name", "")).strip()
        if not station_id or not expected_name or not new_name:
            raise ValueError(f"{context}: Check the station ID and the two saved names.")
        row = by_id.get(station_id)
        if row is None:
            raise ValueError(f"{context}: Check station ID {station_id}. It is missing from the downloaded station list.")
        actual_name = str((row.get("tags") or {}).get("name") or "")
        if _norm_name(actual_name) != _norm_name(expected_name):
            raise ValueError(
                f"{context}: Check station ID {station_id}. The saved name is {expected_name!r}; "
                f"the downloaded name is {actual_name!r}."
            )
        row.setdefault("tags", {})["name"] = new_name
        used.add(station_id)
    return used

def require_alias(
    rows_by_id: dict[str, dict[str, Any]],
    *,
    alias_id: str,
    alias_name: str,
    canonical_id: str,
    canonical_name: str,
    context: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the checked station pair or stop if either station changed."""
    alias = rows_by_id.get(str(alias_id))
    canonical = rows_by_id.get(str(canonical_id))
    if alias is None:
        raise ValueError(f"{context}: Check station ID {alias_id}. It is missing from the downloaded station list.")
    if canonical is None:
        raise ValueError(
            f"{context}: Check station ID {canonical_id}. It is missing from the downloaded station list."
        )
    actual_alias = str((alias.get("tags") or {}).get("name") or "")
    actual_canonical = str((canonical.get("tags") or {}).get("name") or "")
    if _norm_name(actual_alias) != _norm_name(alias_name):
        raise ValueError(
            f"{context}: Check station ID {alias_id}. The saved name is {alias_name!r}; "
            f"the downloaded name is {actual_alias!r}."
        )
    if _norm_name(actual_canonical) != _norm_name(canonical_name):
        raise ValueError(
            f"{context}: Check station ID {canonical_id}. The saved name is {canonical_name!r}; "
            f"the downloaded name is {actual_canonical!r}."
        )
    return alias, canonical
