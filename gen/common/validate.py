from __future__ import annotations

from collections import Counter
from math import isfinite
from pathlib import Path
from typing import Any, Iterable

from .io import load_ndjson


def validate_nodes(rows: Iterable[dict[str, Any]]) -> list[str]:
    rows = list(rows)
    errors: list[str] = []
    ids: list[str] = []
    categories: set[str] = set()
    for index, row in enumerate(rows, 1):
        for field in ("type", "id", "lat", "lon", "tags", "category"):
            if field not in row:
                errors.append(f"row {index}: missing {field}")
        if row.get("type") != "node":
            errors.append(f"row {index}: type must be node")
        station_id = str(row.get("id", "")).strip()
        if not station_id:
            errors.append(f"row {index}: empty id")
        ids.append(station_id)
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        if not str(tags.get("name", "")).strip():
            errors.append(f"row {index}: empty name")
        for key, low, high in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
            try:
                value = float(row.get(key))
            except (TypeError, ValueError):
                errors.append(f"row {index}: invalid {key}")
                continue
            if not isfinite(value) or not low <= value <= high:
                errors.append(f"row {index}: {key} outside range")
        category = str(row.get("category", "")).strip()
        if category:
            categories.add(category)
    for station_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate id {station_id}: {count} occurrences")
    if len(categories) > 1:
        errors.append(f"mixed categories: {sorted(categories)}")
    return errors


def validate_file(path: Path) -> list[str]:
    return validate_nodes(load_ndjson(path))
