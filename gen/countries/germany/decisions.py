"""Explicit reviewed decision lookup for Germany."""
from __future__ import annotations

import json
import os
import csv
from countries.germany.settings import BOARD_GROUPS_PATH, REVIEWED_STATIONS_PATH


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


def load_reconciled_stations(path=REVIEWED_STATIONS_PATH):
    """Load reviewed DB station additions with their source links."""
    if not os.path.exists(path):
        return []
    stations = []
    seen_ids = set()
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            station_id = str(row.get("id") or "").strip()
            name = str(row.get("expected_name") or "").strip()
            if not station_id.isdigit() or not name:
                raise ValueError(f"{path}: station ID and name are required")
            if station_id in seen_ids:
                raise ValueError(f"{path}: duplicate station ID {station_id}")
            if not row.get("station_url") or not row.get("plan_url"):
                raise ValueError(f"{path}: station {station_id} is missing source links")
            if row.get("station_status") != "200" or row.get("plan_status") != "200":
                raise ValueError(f"{path}: station {station_id} is missing successful source checks")
            try:
                latitude = float(row["lat"])
                longitude = float(row["lon"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}: station {station_id} has invalid coordinates") from exc
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError(f"{path}: station {station_id} coordinates are outside range")
            stations.append({
                "id": station_id,
                "name": name,
                "ril100": str(row.get("ds100") or ""),
                "location": {"latitude": latitude, "longitude": longitude},
                "source": str(row.get("source") or row.get("station_url") or "reviewed DB station"),
            })
            seen_ids.add(station_id)
    return stations
