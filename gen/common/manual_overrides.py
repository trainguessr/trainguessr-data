"""Guarded manual station corrections.

Manual corrections are deliberately strict: an override must still match the
expected station name and ID, otherwise generation fails instead of silently
applying a stale correction to a renamed/reused provider record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _norm_name(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def load_override_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
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
            raise ValueError(f"{context}: coordinate override requires id and expected_name")
        row = by_id.get(station_id)
        if row is None:
            raise ValueError(
                f"{context}: stale coordinate override {station_id}: station ID is no longer generated"
            )
        actual_name = str((row.get("tags") or {}).get("name") or "")
        if _norm_name(actual_name) != _norm_name(expected_name):
            raise ValueError(
                f"{context}: stale coordinate override {station_id}: expected name "
                f"{expected_name!r}, generated name is {actual_name!r}; review before regenerating"
            )
        try:
            lat = float(override["lat"])
            lon = float(override["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{context}: invalid coordinates for override {station_id}") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"{context}: out-of-range coordinates for override {station_id}")
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


def require_alias(
    rows_by_id: dict[str, dict[str, Any]],
    *,
    alias_id: str,
    alias_name: str,
    canonical_id: str,
    canonical_name: str,
    context: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a guarded alias/canonical pair or fail loudly when source identity changed."""
    alias = rows_by_id.get(str(alias_id))
    canonical = rows_by_id.get(str(canonical_id))
    if alias is None:
        raise ValueError(f"{context}: stale alias {alias_id}: alias station is no longer generated")
    if canonical is None:
        raise ValueError(
            f"{context}: stale alias {alias_id}->{canonical_id}: canonical station is no longer generated"
        )
    actual_alias = str((alias.get("tags") or {}).get("name") or "")
    actual_canonical = str((canonical.get("tags") or {}).get("name") or "")
    if _norm_name(actual_alias) != _norm_name(alias_name):
        raise ValueError(
            f"{context}: stale alias {alias_id}: expected {alias_name!r}, got {actual_alias!r}"
        )
    if _norm_name(actual_canonical) != _norm_name(canonical_name):
        raise ValueError(
            f"{context}: stale alias target {canonical_id}: expected {canonical_name!r}, "
            f"got {actual_canonical!r}"
        )
    return alias, canonical
