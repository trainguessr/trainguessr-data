#!/usr/bin/env python3
"""Generate Spanish Renfe stations and a compact static GTFS timetable index.

Inputs are the official Renfe Cercanias and long-distance GTFS ZIP archives.
The generated provider index is consumed by trainguessr's Renfe GTFS-RT adapter.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import tempfile
import zipfile
import shutil

import requests
from pathlib import Path
from collections.abc import Iterable
from typing import Any

from common.io import ROOT, write_ndjson
from common.validate import validate_nodes

OUTPUT = ROOT / "nodes" / "nodes-spain-renfe.json"
CACHE_ROOT = ROOT / "cache" / "spain"
INDEX_OUTPUT = ROOT / "cache" / "spain.sqlite"

RENFE_CKAN_API = "https://data.renfe.com/api/3/action/resource_show"
RENFE_RESOURCES = {
    "cercanias": "6f1523c6-a9e3-48e3-9ace-bb107a762be6",
    "ld": "25d6b043-9e47-4f99-bd91-edd51d782450",
}
EXCLUSIONS = ROOT / "excludes" / "spain.json"
REVIEWED_DUPLICATES = ROOT / "overrides" / "spain-reviewed-duplicate-names.json"



def _download_official_feed(feed_name: str, *, session: requests.Session | None = None) -> Path:
    """Discover and download a current official Renfe GTFS resource into cache/."""
    if feed_name not in RENFE_RESOURCES:
        raise ValueError(f"Unknown Renfe feed: {feed_name}")
    client = session or requests.Session()
    close_client = session is None
    try:
        metadata = client.get(
            RENFE_CKAN_API,
            params={"id": RENFE_RESOURCES[feed_name]},
            timeout=(5, 30),
            headers={"User-Agent": "TrainGuessr-data/1.0"},
        )
        metadata.raise_for_status()
        payload = metadata.json()
        if not payload.get("success") or not isinstance(payload.get("result"), dict):
            raise RuntimeError(f"Renfe metadata lookup failed for {feed_name}")
        url = str(payload["result"].get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            raise RuntimeError(f"Renfe metadata returned no download URL for {feed_name}")

        feed_cache = CACHE_ROOT / feed_name
        extract_dir = feed_cache / "gtfs"
        archive_path = feed_cache / "gtfs.zip"
        feed_cache.mkdir(parents=True, exist_ok=True)
        tmp_path = archive_path.with_suffix(".zip.tmp")
        try:
            with client.get(
                url, stream=True, timeout=(10, 120),
                headers={"User-Agent": "TrainGuessr-data/1.0"},
            ) as response:
                response.raise_for_status()
                with tmp_path.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if not zipfile.is_zipfile(tmp_path):
                raise RuntimeError(f"Renfe {feed_name} resource is not a ZIP archive")
            os.replace(tmp_path, archive_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        staging = feed_cache / ".gtfs-new"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            # Renfe GTFS is flat, but reject traversal if that ever changes.
            for member in archive.infolist():
                target = (staging / member.filename).resolve()
                if staging.resolve() not in target.parents and target != staging.resolve():
                    raise RuntimeError("Unsafe path in Renfe GTFS archive")
            archive.extractall(staging)
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.replace(staging, extract_dir)
        return archive_path
    finally:
        if close_client:
            client.close()


def fetch_official_feeds() -> list[tuple[str, Path]]:
    """Fetch both official Renfe static feeds, retaining ZIPs and extracted GTFS in cache/."""
    with requests.Session() as session:
        return [
            (name, _download_official_feed(name, session=session))
            for name in ("cercanias", "ld")
        ]

def _read_table(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        raw = archive.read(name)
    except KeyError:
        return []
    text = raw.decode("utf-8-sig", errors="replace")
    return [_clean_row(row) for row in csv.DictReader(io.StringIO(text))]


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    # Current Renfe files pad selected headers and values with spaces.
    return {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}


def _iter_archive_table(path: Path, name: str) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        with archive.open(name) as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="") as text:
                for row in csv.DictReader(text):
                    yield _clean_row(row)


def load_feed(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        feed = {
            name[:-4]: _read_table(archive, name)
            for name in (
                "agency.txt", "stops.txt", "routes.txt", "trips.txt",
                "calendar.txt", "calendar_dates.txt",
            )
        }
    feed["_archive_path"] = path
    return feed


def _stop_times(feed: dict[str, Any]) -> Iterable[dict[str, str]]:
    if "stop_times" in feed:
        return feed["stop_times"]
    return _iter_archive_table(Path(feed["_archive_path"]), "stop_times.txt")


def _excluded_playable_station_ids() -> set[str]:
    if not EXCLUSIONS.is_file():
        return set()
    payload = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    rows = payload.get("excluded", []) if isinstance(payload, dict) else []
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") not in (None, "")
    }



def _reviewed_duplicate_station_ids() -> set[str]:
    if not REVIEWED_DUPLICATES.is_file():
        return set()
    payload = json.loads(REVIEWED_DUPLICATES.read_text(encoding="utf-8"))
    rows = payload.get("reviewed", []) if isinstance(payload, dict) else []
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("decision") != "retain_distinct":
            continue
        result.update(str(value) for value in row.get("ids", []) if value not in (None, ""))
    return result

def build(feeds: list[tuple[str, dict[str, Any]]]) -> tuple[list[dict], dict]:
    reviewed_duplicate_ids = _reviewed_duplicate_station_ids()
    nodes: dict[str, dict[str, Any]] = {}
    index: dict[str, Any] = {
        "version": 1,
        "source": "Renfe official GTFS",
        "stations": {},
        "routes": {},
        "trips": {},
        "station_trips": {},
        "calendar": {},
        "calendar_dates": [],
    }

    for feed_name, feed in feeds:
        prefix = f"{feed_name}:"
        stops = {row.get("stop_id", ""): row for row in feed["stops"] if row.get("stop_id")}
        children: dict[str, list[str]] = {}
        for stop_id, row in stops.items():
            parent = row.get("parent_station", "").strip()
            if parent:
                children.setdefault(parent, []).append(stop_id)

        agency_names = {
            row.get("agency_id", ""): row.get("agency_name", "")
            for row in feed["agency"]
        }
        rail_route_ids: set[str] = set()
        for row in feed["routes"]:
            route_id = row.get("route_id", "").strip()
            if not route_id:
                continue
            try:
                route_type = int(row.get("route_type") or -1)
            except ValueError:
                continue
            if route_type != 2 and not 100 <= route_type <= 199:
                continue
            rail_route_ids.add(route_id)
            rid = prefix + route_id
            index["routes"][rid] = {
                "short_name": row.get("route_short_name", ""),
                "long_name": row.get("route_long_name", ""),
                "route_type": row.get("route_type", ""),
                "agency": agency_names.get(row.get("agency_id", ""), ""),
            }

        station_alias: dict[str, str] = {}
        for stop_id, row in stops.items():
            parent = row.get("parent_station", "").strip()
            station_id = parent or stop_id
            station_alias[stop_id] = station_id

        served: set[str] = set()
        trip_rows: dict[str, dict[str, str]] = {}
        for row in feed["trips"]:
            trip_id = row.get("trip_id", "").strip()
            if trip_id and row.get("route_id", "").strip() in rail_route_ids:
                trip_rows[trip_id] = row

        times_by_trip: dict[str, list[dict[str, Any]]] = {}
        for row in _stop_times(feed):
            trip_id = row.get("trip_id", "").strip()
            stop_id = row.get("stop_id", "").strip()
            if trip_id not in trip_rows or not stop_id:
                continue
            station_id = station_alias.get(stop_id, stop_id)
            served.add(station_id)
            try:
                sequence = int(row.get("stop_sequence") or 0)
            except ValueError:
                sequence = 0
            times_by_trip.setdefault(trip_id, []).append({
                "stop_id": stop_id,
                "station_id": station_id,
                "arrival_time": row.get("arrival_time", ""),
                "departure_time": row.get("departure_time", ""),
                "stop_sequence": sequence,
            })

        for trip_id, row in trip_rows.items():
            trip_stops = sorted(times_by_trip.get(trip_id, []), key=lambda item: item["stop_sequence"])
            if not trip_stops:
                continue
            tid = prefix + trip_id
            route_id = row.get("route_id", "")
            index["trips"][tid] = {
                "source_trip_id": trip_id,
                "source_feed": feed_name,
                "service_id": prefix + row.get("service_id", ""),
                "route_id": prefix + route_id,
                "short_name": row.get("trip_short_name", ""),
                "headsign": row.get("trip_headsign", ""),
                "stops": trip_stops,
            }
            for station_id in {str(item["station_id"]) for item in trip_stops}:
                index["station_trips"].setdefault(station_id, []).append(tid)

        for row in feed["calendar"]:
            service_id = row.get("service_id", "").strip()
            if service_id:
                index["calendar"][prefix + service_id] = {
                    key: row.get(key, "")
                    for key in ("monday", "tuesday", "wednesday", "thursday", "friday",
                                "saturday", "sunday", "start_date", "end_date")
                }
        for row in feed["calendar_dates"]:
            service_id = row.get("service_id", "").strip()
            if service_id:
                index["calendar_dates"].append({
                    "service_id": prefix + service_id,
                    "date": row.get("date", ""),
                    "exception_type": row.get("exception_type", ""),
                })

        for station_id in sorted(served):
            row = stops.get(station_id)
            if row is None:
                candidates = [stops[s] for s in children.get(station_id, []) if s in stops]
                row = candidates[0] if candidates else None
            if row is None:
                continue
            name = str(row.get("stop_name") or "").strip()
            lat_raw, lon_raw = row.get("stop_lat"), row.get("stop_lon")
            if not name or lat_raw in (None, "") or lon_raw in (None, ""):
                continue
            try:
                lat, lon = float(lat_raw), float(lon_raw)
            except (TypeError, ValueError):
                continue
            node_id = station_id
            aliases = sorted(set(children.get(station_id, [])) | {station_id})
            if node_id not in nodes:
                nodes[node_id] = {
                    "type": "node",
                    "id": node_id,
                    "lat": lat,
                    "lon": lon,
                    "tags": {
                        "name": name,
                        "stop_ids": aliases,
                        "renfe_stop_id": station_id,
                        "feeds": [feed_name],
                        **({"audit_duplicate_name_reviewed": True}
                           if node_id in reviewed_duplicate_ids else {}),
                    },
                    "category": "spain_renfe",
                }
            else:
                tags = nodes[node_id]["tags"]
                tags["stop_ids"] = sorted(set(tags["stop_ids"]) | set(aliases))
                tags["feeds"] = sorted(set(tags["feeds"]) | {feed_name})
            station_row = index["stations"].setdefault(node_id, {
                "name": name,
                "stop_ids": [],
                "feeds": [],
            })
            station_row["stop_ids"] = sorted(set(station_row["stop_ids"]) | set(aliases))
            station_row["feeds"] = sorted(set(station_row["feeds"]) | {feed_name})

    excluded = _excluded_playable_station_ids()
    playable_nodes = [row for station_id, row in nodes.items() if station_id not in excluded]
    return sorted(playable_nodes, key=lambda row: str(row["id"])), index


def write_index(index: dict[str, Any], output: Path) -> None:
    """Write the normalized SQLite index atomically for runtime use."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, database_name = tempfile.mkstemp(prefix="spain-gtfs-", suffix=".sqlite", dir=output.parent)
    os.close(fd)
    database = Path(database_name)
    try:
        connection = sqlite3.connect(database)
        with connection:
            connection.executescript("""
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE stations (id TEXT PRIMARY KEY, name TEXT NOT NULL, stop_ids TEXT NOT NULL);
                CREATE TABLE routes (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE calendar (service_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE calendar_dates (service_id TEXT NOT NULL, date TEXT NOT NULL, exception_type TEXT NOT NULL);
                CREATE TABLE trips (
                    id TEXT PRIMARY KEY, source_trip_id TEXT NOT NULL, source_feed TEXT NOT NULL,
                    service_id TEXT NOT NULL, route_id TEXT NOT NULL, short_name TEXT, headsign TEXT
                );
                CREATE TABLE stop_times (
                    trip_id TEXT NOT NULL, stop_id TEXT NOT NULL, station_id TEXT NOT NULL,
                    arrival_time TEXT, departure_time TEXT, stop_sequence INTEGER NOT NULL
                );
            """)
            connection.execute("INSERT INTO metadata VALUES (?, ?)", ("version", str(index["version"])))
            connection.execute("INSERT INTO metadata VALUES (?, ?)", ("source", str(index["source"])))
            connection.executemany(
                "INSERT INTO stations VALUES (?, ?, ?)",
                ((station_id, row["name"], json.dumps(row.get("stop_ids") or []))
                 for station_id, row in index["stations"].items()),
            )
            connection.executemany(
                "INSERT INTO routes VALUES (?, ?)",
                ((route_id, json.dumps(row, ensure_ascii=False, separators=(",", ":")))
                 for route_id, row in index["routes"].items()),
            )
            connection.executemany(
                "INSERT INTO calendar VALUES (?, ?)",
                ((service_id, json.dumps(row, separators=(",", ":")))
                 for service_id, row in index["calendar"].items()),
            )
            connection.executemany(
                "INSERT INTO calendar_dates VALUES (?, ?, ?)",
                ((row["service_id"], row["date"], row["exception_type"])
                 for row in index["calendar_dates"]),
            )
            for trip_id, row in index["trips"].items():
                connection.execute(
                    "INSERT INTO trips VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (trip_id, row["source_trip_id"], row["source_feed"], row["service_id"],
                     row["route_id"], row.get("short_name", ""), row.get("headsign", "")),
                )
                connection.executemany(
                    "INSERT INTO stop_times VALUES (?, ?, ?, ?, ?, ?)",
                    ((trip_id, stop["stop_id"], stop["station_id"], stop["arrival_time"],
                      stop["departure_time"], stop["stop_sequence"]) for stop in row["stops"]),
                )
            connection.executescript("""
                CREATE INDEX stop_times_station ON stop_times(station_id);
                CREATE INDEX stop_times_stop ON stop_times(stop_id);
                CREATE INDEX stop_times_trip ON stop_times(trip_id, stop_sequence);
            """)
        connection.close()
        os.replace(database, output)
        database = None
    finally:
        if database is not None:
            database.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cercanias", type=Path,
                        help="Override download with a local Renfe Cercanias/Rodalies GTFS ZIP")
    parser.add_argument("--long-distance", type=Path,
                        help="Override download with a local Renfe high-speed/long-/medium-distance GTFS ZIP")
    parser.add_argument("--no-download", action="store_true",
                        help="Require both local --cercanias and --long-distance inputs")
    args = parser.parse_args()
    if args.no_download:
        if not args.cercanias or not args.long_distance:
            parser.error("--no-download requires both local GTFS ZIP arguments")
        inputs = [("cercanias", args.cercanias), ("ld", args.long_distance)]
    elif args.cercanias or args.long_distance:
        if not args.cercanias or not args.long_distance:
            parser.error("provide both local GTFS ZIPs, or neither to download current Renfe data")
        inputs = [("cercanias", args.cercanias), ("ld", args.long_distance)]
    else:
        inputs = fetch_official_feeds()
    feeds = [(name, load_feed(path)) for name, path in inputs if path is not None]
    nodes, index = build(feeds)
    if not nodes or not index["trips"]:
        print("ERROR: Renfe GTFS inputs produced no railway stations or trips")
        return 1
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    write_ndjson(OUTPUT, nodes)
    write_index(index, INDEX_OUTPUT)
    print(f"Wrote {len(nodes)} Spanish stations to {OUTPUT}")
    print(f"Wrote static timetable index to {INDEX_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
