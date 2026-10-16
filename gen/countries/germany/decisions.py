"""Explicit reviewed decision lookup for Germany."""
from __future__ import annotations

import json
import os
from countries.germany.settings import BOARD_GROUPS_PATH, RECONCILIATION_PATH


def load_board_groups(path=BOARD_GROUPS_PATH):
    """Load reviewed DB Timetables EVA groups keyed by canonical station ID."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    groups = {}
    for row in payload.get("reviewed_board_groups", []):
        canonical_id = str(row.get("canonical_id") or "").strip()
        provider_ids = [str(value).strip() for value in row.get("provider_ids", []) if str(value).strip()]
        if not canonical_id or not provider_ids:
            raise ValueError(f"Invalid Germany board group: {row}")
        if canonical_id not in provider_ids:
            provider_ids.insert(0, canonical_id)
        groups[canonical_id] = {
            "name": str(row.get("name") or "").strip(),
            "provider_ids": list(dict.fromkeys(provider_ids)),
        }
    return groups


def load_reconciled_stations(path=RECONCILIATION_PATH):
    """Load reviewed DB EVA additions backed by a current timetable response."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Germany reconciliation data must be an object")

    stations = []
    seen_ids = set()
    for row in payload.get("outcomes", []):
        if not isinstance(row, dict):
            raise ValueError("Germany reconciliation outcome must be an object")
        if row.get("status") != "added_existing_provider":
            continue
        station_id = str(row.get("eva_id") or "").strip()
        name = str(row.get("name") or "").strip()
        evidence = row.get("evidence")
        if not station_id.isdigit() or not name:
            raise ValueError(f"Invalid Germany reconciliation station: {row}")
        if station_id in seen_ids:
            raise ValueError(f"Duplicate Germany reconciliation station: {station_id}")
        if str(row.get("db") or "").lower() != "true":
            raise ValueError(f"Germany station is not marked db=true: {station_id}")
        if not isinstance(evidence, dict):
            raise ValueError(f"Germany station has no evidence: {station_id}")
        probe = evidence.get("db_probe") if isinstance(evidence.get("db_probe"), dict) else evidence
        if probe.get("station_http_status") != 200 or probe.get("plan_http_status") != 200:
            raise ValueError(f"Germany station lacks successful API evidence: {station_id}")
        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Germany station has invalid coordinates: {station_id}") from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"Germany station coordinates are outside range: {station_id}")
        stations.append({
            "id": station_id,
            "name": name,
            "ril100": str(row.get("ds100") or ""),
            "location": {"latitude": latitude, "longitude": longitude},
            "source": str(row.get("source") or "reviewed-germany-akn-supplement"),
        })
        seen_ids.add(station_id)
    return stations
