#!/usr/bin/env python3
"""Generate Finnish passenger railway stations from Fintraffic metadata."""
from __future__ import annotations

import argparse
import sys
import csv
import json
from pathlib import Path

import requests

from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file
from common.validate import validate_nodes

ENDPOINT = "https://rata.digitraffic.fi/api/v1/metadata/stations"
OUTPUT = ROOT / "nodes" / "nodes-finland.json"
REVIEW_FILE = ROOT / "overrides" / "finland-stations.csv"
CACHE_SOURCE = ROOT / "cache" / "finland" / "stations.json"


def load_stations(path: Path | None = None, *, use_cache: bool = False) -> list[dict]:
    if path is not None:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    elif use_cache:
        payload = json.loads(require_cached_file(CACHE_SOURCE, "Fintraffic station data").read_text(encoding="utf-8"))
    else:
        response = requests.get(ENDPOINT, headers={"Digitraffic-User": "trainguessr-data"}, timeout=60)
        response.raise_for_status()
        save_source_file(CACHE_SOURCE, response.content)
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Fintraffic station metadata must be an array")
    return payload


def load_reviewed_stations(path: Path = REVIEW_FILE) -> dict[str, dict]:
    reviewed: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            station_id = str(row.get("station_id", "")).strip()
            if not station_id:
                raise ValueError(f"{path}: a reviewed station is missing its ID")
            if station_id in reviewed:
                raise ValueError(f"{path}: duplicate reviewed station {station_id}")
            reviewed[station_id] = {
                "stationShortCode": station_id,
                "stationName": str(row.get("expected_name", "")).strip(),
                "stationUICCode": str(row.get("uic", "")).strip(),
                "type": str(row.get("type", "")).strip(),
            }
    return reviewed


def validate_reviewed_stations(stations: list[dict], reviewed: dict[str, dict]) -> list[str]:
    source_by_id = {
        str(row.get("stationShortCode", "")).strip(): row
        for row in stations
        if row.get("countryCode") == "FI"
    }
    errors: list[str] = []
    for station_id, review in sorted(reviewed.items()):
        source = source_by_id.get(station_id)
        if source is None:
            errors.append(f"reviewed station missing from metadata: {station_id}")
            continue
        expected_name = str(review.get("stationName", "")).strip()
        if expected_name and source.get("stationName") != expected_name:
            errors.append(f"reviewed station name changed: {station_id}")
        expected_type = str(review.get("type", "")).strip()
        if expected_type and source.get("type") != expected_type:
            errors.append(f"reviewed station type changed: {station_id}")
        expected_uic = str(review.get("stationUICCode", "")).strip()
        if expected_uic and str(source.get("stationUICCode", "")).strip() != expected_uic:
            errors.append(f"reviewed station UIC changed: {station_id}")
    return errors


def build_nodes(stations: list[dict], reviewed_stations: dict[str, dict] | None = None) -> list[dict]:
    reviewed = load_reviewed_stations() if reviewed_stations is None else reviewed_stations
    by_id: dict[str, dict] = {}
    for station in stations:
        if station.get("countryCode") != "FI":
            continue
        if station.get("type") not in ("STATION", "STOPPING_POINT"):
            continue
        station_id = str(station.get("stationShortCode", "")).strip()
        name = str(station.get("stationName", "")).strip()
        lat = station.get("latitude")
        lon = station.get("longitude")
        if not station_id or not name or lat in (None, "") or lon in (None, ""):
            continue
        tags = {
            "name": name,
            "uic": station.get("stationUICCode"),
            "station_type": station.get("type"),
            "operator": "Fintraffic",
        }
        if station.get("passengerTraffic") is False:
            tags["station_status"] = "no_current_passenger_traffic"
        by_id[station_id] = {
            "type": "node",
            "id": station_id,
            "lat": float(lat),
            "lon": float(lon),
            "tags": tags,
            "category": "finland_all",
        }
    return sorted(by_id.values(), key=lambda row: str(row["id"]))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="saved official metadata response")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    stations = load_stations(args.input, use_cache=args.cache)
    reviewed = load_reviewed_stations()
    review_errors = validate_reviewed_stations(stations, reviewed)
    if review_errors:
        for error in review_errors:
            print(f"ERROR: {error}")
        return 1
    nodes = build_nodes(stations, reviewed)
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    publish_nodes(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Finnish stations to {OUTPUT}")
    without_current_service = sum(
        row.get("tags", {}).get("station_status") == "no_current_passenger_traffic"
        for row in nodes
    )
    if without_current_service:
        print(f"Included {without_current_service} provider stations with no current passenger traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
