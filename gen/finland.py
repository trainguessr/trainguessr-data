#!/usr/bin/env python3
"""Generate Finnish passenger railway stations from Fintraffic metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from common.io import ROOT, write_ndjson
from common.validate import validate_nodes

ENDPOINT = "https://rata.digitraffic.fi/api/v1/metadata/stations"
OUTPUT = ROOT / "nodes" / "nodes-finland.json"


def load_stations(path: Path | None = None) -> list[dict]:
    if path is not None:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        response = requests.get(ENDPOINT, headers={"Digitraffic-User": "trainguessr-data"}, timeout=60)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Fintraffic station metadata must be an array")
    return payload


def build_nodes(stations: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for station in stations:
        if station.get("countryCode") != "FI" or not station.get("passengerTraffic"):
            continue
        if station.get("type") not in ("STATION", "STOPPING_POINT"):
            continue
        station_id = str(station.get("stationShortCode", "")).strip()
        name = str(station.get("stationName", "")).strip()
        lat = station.get("latitude")
        lon = station.get("longitude")
        if not station_id or not name or lat in (None, "") or lon in (None, ""):
            continue
        by_id[station_id] = {
            "type": "node",
            "id": station_id,
            "lat": float(lat),
            "lon": float(lon),
            "tags": {
                "name": name,
                "uic": station.get("stationUICCode"),
                "station_type": station.get("type"),
                "operator": "Fintraffic",
            },
            "category": "finland_all",
        }
    return sorted(by_id.values(), key=lambda row: str(row["id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="saved official metadata response")
    args = parser.parse_args()
    nodes = build_nodes(load_stations(args.input))
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    write_ndjson(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Finnish stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
