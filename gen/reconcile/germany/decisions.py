"""Explicit reviewed decision lookup for Germany."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from reconcile.germany.io import _read_json
from reconcile.germany.settings import REVIEWED_STATION_OVERRIDES


def load_reviewed_station_overrides(
    path: Path = REVIEWED_STATION_OVERRIDES,
) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Germany station overrides must be an object: {path}")
    mappings = payload.get("mappings", {})
    if not isinstance(mappings, dict):
        raise ValueError(f"Germany station overrides must contain a mappings object: {path}")
    result: dict[str, dict[str, Any]] = {}
    for parent, mapping in mappings.items():
        parent_id = str(parent).strip()
        if not parent_id or not isinstance(mapping, dict):
            raise ValueError(f"Invalid Germany station override: {parent}: {mapping}")
        provider_ids = [
            str(value).strip()
            for value in mapping.get("provider_ids", [])
            if str(value).strip()
        ]
        if not provider_ids or any(not value.isdigit() for value in provider_ids):
            raise ValueError(f"Invalid Germany station override IDs: {parent}: {mapping}")
        result[parent_id] = {
            **mapping,
            "provider_ids": list(dict.fromkeys(provider_ids)),
        }
    return result


def load_reviewed_gap_notes(
    path: Path = REVIEWED_STATION_OVERRIDES,
) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Germany station overrides must be an object: {path}")
    notes = payload.get("gap_notes", {})
    if not isinstance(notes, dict):
        raise ValueError(f"Germany station overrides must contain gap_notes: {path}")
    result: dict[str, dict[str, Any]] = {}
    for parent, note in notes.items():
        parent_id = str(parent).strip()
        if not parent_id or not isinstance(note, dict) or not str(note.get("reason") or "").strip():
            raise ValueError(f"Invalid Germany gap note: {parent}: {note}")
        result[parent_id] = dict(note)
    return result
