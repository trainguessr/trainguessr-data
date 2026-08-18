#!/usr/bin/env python3
"""Generate Danish railway stations from the official Rejseplanen GTFS ZIP."""
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path
from typing import Any

from common.io import ROOT, write_ndjson
from common.validate import validate_nodes

OUTPUT = ROOT / "nodes" / "nodes-denmark.json"


def _table(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    raw = archive.read(name).decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(raw)))


def build_nodes(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        stops = {row["stop_id"]: row for row in _table(archive, "stops.txt") if row.get("stop_id")}
        routes = {row["route_id"]: row for row in _table(archive, "routes.txt") if row.get("route_id")}
        trips = {row["trip_id"]: row for row in _table(archive, "trips.txt") if row.get("trip_id")}
        stop_times = _table(archive, "stop_times.txt")

    # GTFS route_type 2 is rail; extended 100-199 are railway services.
    rail_routes: set[str] = set()
    for route_id, row in routes.items():
        try:
            route_type = int(row.get("route_type") or -1)
        except ValueError:
            continue
        if route_type == 2 or 100 <= route_type <= 199:
            rail_routes.add(route_id)

    rail_trips = {
        trip_id for trip_id, row in trips.items()
        if row.get("route_id") in rail_routes
    }
    served_stop_ids = {
        row.get("stop_id", "")
        for row in stop_times
        if row.get("trip_id") in rail_trips and row.get("stop_id")
    }

    station_to_children: dict[str, set[str]] = {}
    for stop_id in served_stop_ids:
        row = stops.get(stop_id, {})
        station_id = row.get("parent_station", "").strip() or stop_id
        station_to_children.setdefault(station_id, set()).add(stop_id)

    result: dict[str, dict[str, Any]] = {}
    for station_id, child_ids in station_to_children.items():
        # Rejseplanen documents Danish railway station IDs as seven-digit 86xxxxx IDs.
        # This also excludes Swedish/German stops carried by cross-border services.
        if len(station_id) != 7 or not station_id.startswith("86"):
            continue
        row = stops.get(station_id)
        if row is None:
            row = next((stops[item] for item in sorted(child_ids) if item in stops), None)
        if row is None:
            continue
        name = str(row.get("stop_name") or "").strip()
        try:
            lat, lon = float(row.get("stop_lat") or ""), float(row.get("stop_lon") or "")
        except ValueError:
            continue
        if not name:
            continue
        result[station_id] = {
            "type": "node",
            "id": station_id,
            "lat": lat,
            "lon": lon,
            "tags": {
                "name": name,
                "stop_ids": sorted(child_ids | {station_id}),
                "source": "Rejseplanen GTFS",
            },
            "category": "denmark_all",
        }
    return sorted(result.values(), key=lambda row: str(row["id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="official Rejseplanen GTFS ZIP")
    args = parser.parse_args()
    nodes = build_nodes(args.input)
    if not nodes:
        print("ERROR: Rejseplanen GTFS input produced no railway stations")
        return 1
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    write_ndjson(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Danish railway stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
