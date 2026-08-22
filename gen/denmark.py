#!/usr/bin/env python3
"""Download and generate Danish railway stations from Rejseplanen GTFS."""
from __future__ import annotations

import csv
import io
import os
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests

from common.io import ROOT, write_ndjson
from common.validate import validate_nodes

GTFS_URL = "https://www.rejseplanen.info/labs/GTFS.zip"
CACHE_DIR = ROOT / "cache" / "denmark"
GTFS_ARCHIVE = CACHE_DIR / "rejseplanen-gtfs.zip"
OUTPUT = ROOT / "nodes" / "nodes-denmark.json"
API_ROOT = "https://www.rejseplanen.dk/api"
USER_AGENT = "TrainGuessr-data/1.0"
CACHE_MAX_AGE_SECONDS = 14 * 24 * 60 * 60


def download_gtfs(*, session: requests.Session | None = None) -> Path:
    """Download the current official static feed into the ignored data cache."""
    temporary = GTFS_ARCHIVE.with_suffix(".zip.tmp")
    if (
        GTFS_ARCHIVE.is_file()
        and time.time() - GTFS_ARCHIVE.stat().st_mtime < CACHE_MAX_AGE_SECONDS
    ):
        if zipfile.is_zipfile(GTFS_ARCHIVE):
            temporary.unlink(missing_ok=True)
            return GTFS_ARCHIVE

    client = session or requests.Session()
    close_client = session is None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with client.get(
            GTFS_URL,
            stream=True,
            timeout=(10, 180),
            headers={"User-Agent": USER_AGENT},
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if not zipfile.is_zipfile(temporary):
            raise RuntimeError(f"Rejseplanen did not return a GTFS ZIP: {GTFS_URL}")
        os.replace(temporary, GTFS_ARCHIVE)
        return GTFS_ARCHIVE
    finally:
        temporary.unlink(missing_ok=True)
        if close_client:
            client.close()


def _table(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    raw = archive.read(name).decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(raw)))


def _iter_table(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as raw:
        with io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="") as text:
            yield from csv.DictReader(text)


def _normalise_stop_id(value: str | None) -> str:
    value = str(value or "").strip()
    if value.isdigit():
        return value.lstrip("0") or "0"
    return value


def build_nodes(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        stops: dict[str, dict[str, str]] = {}
        for row in _table(archive, "stops.txt"):
            stop_id = _normalise_stop_id(row.get("stop_id"))
            if not stop_id:
                continue
            row["stop_id"] = stop_id
            row["parent_station"] = _normalise_stop_id(row.get("parent_station"))
            stops[stop_id] = row
        routes = {row["route_id"]: row for row in _table(archive, "routes.txt") if row.get("route_id")}
        trips = {row["trip_id"]: row for row in _table(archive, "trips.txt") if row.get("trip_id")}

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
        station_to_children: dict[str, set[str]] = {}
        for row in _iter_table(archive, "stop_times.txt"):
            if row.get("trip_id") not in rail_trips:
                continue
            stop_id = _normalise_stop_id(row.get("stop_id"))
            if not stop_id:
                continue
            stop = stops.get(stop_id, {})
            station_id = stop.get("parent_station", "").strip() or stop_id
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


def validate_live_access(station_id: str, *, session: requests.Session | None = None) -> None:
    """Smoke-test both API 2.0 board directions with the configured access key."""
    access_id = os.getenv("REJSEPLANEN_API_KEY", "").strip()
    if not access_id:
        raise RuntimeError(
            "REJSEPLANEN_API_KEY is required to validate the generated Danish station"
        )

    client = session or requests.Session()
    close_client = session is None
    try:
        for endpoint, key in (
            ("departureBoard", "Departure"),
            ("arrivalBoard", "Arrival"),
        ):
            response = client.get(
                f"{API_ROOT}/{endpoint}",
                params={
                    "accessId": access_id,
                    "id": station_id,
                    "format": "json",
                    "duration": 60,
                    "maxJourneys": 1,
                },
                timeout=12,
                headers={"User-Agent": "trainguessr/denmark-generator"},
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError(f"Rejseplanen {endpoint} returned invalid JSON") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
                raise RuntimeError(f"Rejseplanen {endpoint} returned an invalid board")
    finally:
        if close_client:
            client.close()


def main() -> int:
    archive = download_gtfs()
    nodes = build_nodes(archive)
    if not nodes:
        print("ERROR: Rejseplanen GTFS input produced no railway stations")
        return 1
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    validate_live_access(str(nodes[0]["id"]))
    write_ndjson(OUTPUT, nodes)
    print(f"Prepared current Rejseplanen GTFS at {archive}")
    print(f"Validated Rejseplanen API 2.0 using station {nodes[0]['id']}")
    print(f"Wrote {len(nodes)} Danish railway stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
