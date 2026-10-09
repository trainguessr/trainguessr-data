#!/usr/bin/env python3
"""Generate Norwegian railway stop places from Entur's National Stop Register."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from common.config import (
    load_exclusion_rules, load_rename_id_rules, load_rename_map,
    require_reviewed_identity,
)
from common.io import ROOT, publish_nodes
from common.validate import validate_nodes

ENDPOINT = "https://api.entur.io/stop-places/v1/read/stop-places"
OUTPUT = ROOT / "nodes" / "nodes-norway.json"
DEFAULT_CLIENT_NAME = "trainguessr-data"
_CLIENT_NAME_RE = re.compile(r"^[a-z0-9_]+-[a-z0-9_-]+$")


def _client_name() -> str:
    value = str(os.getenv("ENTUR_CLIENT_NAME", DEFAULT_CLIENT_NAME)).strip().casefold()
    return value if _CLIENT_NAME_RE.fullmatch(value) else DEFAULT_CLIENT_NAME


def load_stop_places(path: Path | None = None) -> list[dict[str, Any]]:
    if path is not None:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("Saved Entur stop-place response must be an array")
        return [row for row in payload if isinstance(row, dict)]

    rows: list[dict[str, Any]] = []
    skip = 0
    page_size = 1000
    headers = {
        "Accept": "application/json",
        "ET-Client-Name": _client_name(),
        "User-Agent": "trainguessr-data/norway-stations",
    }
    while True:
        response = requests.get(
            ENDPOINT,
            params={
                "count": page_size,
                "skip": skip,
                "transportModes": "RAIL",
                "stopPlaceType": "RAIL_STATION",
            },
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Entur stop-place response must be an array")
        page = [row for row in payload if isinstance(row, dict)]
        rows.extend(page)
        if len(page) < page_size:
            break
        skip += len(page)
    return rows


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("text") or "").strip()
    return str(value or "").strip()


def _is_active_rail_stop(stop: dict[str, Any]) -> bool:
    status = str(stop.get("status_BasicModificationDetailsGroup") or stop.get("status") or "ACTIVE").upper()
    if status not in {"", "ACTIVE"}:
        return False
    stop_type = str(stop.get("stopPlaceType") or "").upper()
    if stop_type and stop_type != "RAIL_STATION":
        return False
    mode = str(stop.get("transportMode") or "").upper()
    if mode in {"RAIL", "INTERCITY_RAIL"}:
        return True
    modes = stop.get("transportModes") or []
    if isinstance(modes, str):
        modes = [modes]
    return any(str(item).upper() in {"RAIL", "INTERCITY_RAIL"} for item in modes)


def build_nodes(stops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    excluded = load_exclusion_rules("norway")
    rename_by_name = load_rename_map("norway")
    rename_id_rules = load_rename_id_rules("norway")
    rename_by_id = {station_id: str(rule["to"]) for station_id, rule in rename_id_rules.items()}
    result: dict[str, dict[str, Any]] = {}
    for stop in stops:
        if not _is_active_rail_stop(stop):
            continue
        station_id = str(stop.get("id") or "").strip()
        if not station_id.startswith("NSR:StopPlace:"):
            continue
        source_name = _text(stop.get("name"))
        rule = excluded.get(station_id)
        if rule is not None:
            require_reviewed_identity(rule, source_name, context=f"norway:{station_id}")
            continue
        if station_id in rename_id_rules:
            require_reviewed_identity(
                {"expected_name": rename_id_rules[station_id]["from"]},
                source_name,
                context=f"norway rename:{station_id}",
            )
        name = rename_by_id.get(station_id) or rename_by_name.get(source_name) or source_name
        location = (stop.get("centroid") or {}).get("location") or {}
        lat = location.get("latitude")
        lon = location.get("longitude")
        if not name or lat in (None, "") or lon in (None, ""):
            continue
        tags = {
            "name": name,
            "transport_mode": "rail",
            "stop_place_type": "railStation",
            "public_code": str(stop.get("publicCode") or "").strip(),
            "rail_submode": str(stop.get("railSubmode") or "").strip().casefold(),
            "source": "Entur NSR",
        }
        tags = {key: value for key, value in tags.items() if value}
        result[station_id] = {
            "type": "node",
            "id": station_id,
            "lat": float(lat),
            "lon": float(lon),
            "tags": tags,
            "category": "norway_all",
        }
    return sorted(result.values(), key=lambda row: (str(row["tags"]["name"]).casefold(), str(row["id"])))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="saved Entur /stop-places response")
    args = parser.parse_args()
    nodes = build_nodes(load_stop_places(args.input))
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    publish_nodes(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Norwegian railway stop places to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
