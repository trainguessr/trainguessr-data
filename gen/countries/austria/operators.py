"""GTFS operator index construction for Austria."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import sqlite3
import tempfile
import re
import zipfile
from pathlib import Path
from typing import Any
from countries.austria.settings import OEBB_RAIL_ROUTE_TYPES, _OEBB_GTFS_REQUIRED


def _gtfs_member_map(names: list[str]) -> dict[str, str] | None:
    """Return canonical GTFS filename -> archive member for one coherent directory."""
    normalized = [name.replace("\\", "/") for name in names if not name.endswith("/")]
    by_name: dict[str, list[str]] = {}
    for name in normalized:
        by_name.setdefault(Path(name).name.casefold(), []).append(name)
    for agency_member in by_name.get("agency.txt", []):
        prefix = agency_member[: -len("agency.txt")]
        mapping = {}
        for required in _OEBB_GTFS_REQUIRED:
            candidate = prefix + required
            if candidate not in normalized:
                break
            mapping[required] = candidate
        else:
            for optional in ("calendar.txt", "calendar_dates.txt", "feed_info.txt"):
                candidate = prefix + optional
                if candidate in normalized:
                    mapping[optional] = candidate
            return mapping
    return None


def _gtfs_rows(archive: zipfile.ZipFile, member: str | None) -> list[dict[str, str]]:
    if not member:
        return []
    raw = archive.read(member).decode("utf-8-sig", errors="replace")
    return [
        {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        for row in csv.DictReader(io.StringIO(raw))
    ]


def _read_gtfs_archive(archive: zipfile.ZipFile) -> dict[str, list[dict[str, str]]] | None:
    mapping = _gtfs_member_map(archive.namelist())
    if not mapping:
        return None
    return {
        "agency": _gtfs_rows(archive, mapping.get("agency.txt")),
        "routes": _gtfs_rows(archive, mapping.get("routes.txt")),
        "trips": _gtfs_rows(archive, mapping.get("trips.txt")),
        "stops": _gtfs_rows(archive, mapping.get("stops.txt")),
        "stop_times": _gtfs_rows(archive, mapping.get("stop_times.txt")),
        "calendar": _gtfs_rows(archive, mapping.get("calendar.txt")),
        "calendar_dates": _gtfs_rows(archive, mapping.get("calendar_dates.txt")),
        "feed_info": _gtfs_rows(archive, mapping.get("feed_info.txt")),
    }


def load_oebb_gtfs(path: Path) -> dict[str, Any]:
    """Load ÖBB GTFS from a root ZIP, wrapper directory, or one nested ZIP."""
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Not a GTFS ZIP: {path}")
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as outer:
        feed = _read_gtfs_archive(outer)
        if feed is None:
            inner_zips = [name for name in outer.namelist() if name.casefold().endswith(".zip")]
            matches: list[dict[str, list[dict[str, str]]]] = []
            for member in inner_zips:
                try:
                    with zipfile.ZipFile(io.BytesIO(outer.read(member))) as inner:
                        candidate = _read_gtfs_archive(inner)
                except zipfile.BadZipFile:
                    candidate = None
                if candidate is not None:
                    matches.append(candidate)
            if len(matches) == 1:
                feed = matches[0]
            elif len(matches) > 1:
                raise ValueError(
                    f"{path}: found {len(matches)} nested GTFS ZIPs; expected exactly one"
                )
        if feed is None:
            preview = ", ".join(outer.namelist()[:12])
            raise ValueError(
                f"{path}: ÖBB GTFS files not found at archive root, under one wrapper "
                f"directory, or in exactly one nested ZIP. First members: {preview}"
            )
    feed["sha256"] = source_sha256
    return feed


def _oebb_is_rail_route(row: dict[str, str]) -> bool:
    try:
        return int(row.get("route_type", "")) in OEBB_RAIL_ROUTE_TYPES
    except ValueError:
        return False


def _oebb_feed_bounds(feed: dict[str, Any]) -> tuple[str, str]:
    starts = [row.get("start_date", "") for row in feed["calendar"] if row.get("start_date")]
    ends = [row.get("end_date", "") for row in feed["calendar"] if row.get("end_date")]
    info = feed.get("feed_info") or []
    start = (info[0].get("feed_start_date") if info else "") or (min(starts) if starts else "")
    end = (info[0].get("feed_end_date") if info else "") or (max(ends) if ends else "")
    return start, end


def _oebb_station_ifopt(stop_id: str, parent_station: str) -> str:
    """Return the canonical Austrian IFOPT represented exactly by a GTFS stop.

    ÖBB models parent stop places as IDs such as ``Pat:47:1187`` while their
    platform children use ``at:47:1187:...``.  This normalizes only those
    structural GTFS identifiers; it never derives a station from names,
    coordinates, or proximity.
    """
    for value in (parent_station, stop_id):
        value = str(value or "").strip()
        if value.startswith("Pat:"):
            value = value[1:]
        match = re.match(r"^(at:\d+:\d+)(?::.*)?$", value)
        if match:
            return match.group(1)
    return ""


def _oebb_line_key(value: str) -> str:
    """Normalize an official route short name / SCOTTY line label."""
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def build_oebb_operator_index(feed: dict[str, Any], output: Path) -> dict[str, Any]:
    """Build the optional runtime operator-enrichment index from official ÖBB GTFS."""
    agencies = {row["agency_id"]: row for row in feed["agency"] if row.get("agency_id")}
    if not agencies:
        if len(feed["agency"]) != 1:
            raise ValueError("ÖBB GTFS does not expose a usable agency namespace")
        agencies = {"__default__": dict(feed["agency"][0], agency_id="__default__")}

    rail_routes: dict[str, dict[str, str]] = {}
    for row in feed["routes"]:
        route_id = row.get("route_id", "")
        if not route_id or not _oebb_is_rail_route(row):
            continue
        agency_id = row.get("agency_id", "")
        if not agency_id and len(agencies) == 1:
            agency_id = next(iter(agencies))
        if agency_id in agencies:
            rail_routes[route_id] = dict(row, agency_id=agency_id)

    trips = {
        row["trip_id"]: row
        for row in feed["trips"]
        if row.get("trip_id") and row.get("route_id") in rail_routes
    }
    stops = {row["stop_id"]: row for row in feed["stops"] if row.get("stop_id")}
    stop_times = [
        row for row in feed["stop_times"]
        if row.get("trip_id") in trips and row.get("stop_id") in stops
    ]
    calendar = {row["service_id"]: row for row in feed["calendar"] if row.get("service_id")}
    calendar_dates = [row for row in feed["calendar_dates"] if row.get("service_id")]

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix="austria-oebb-operators-", suffix=".sqlite", dir=output.parent
    )
    os.close(fd)
    temp = Path(temp_name)
    start, end = _oebb_feed_bounds(feed)
    metadata = {
        "version": "2",
        "provider": "oebb_gtfs_operator_enrichment",
        "source_page": "https://data.oebb.at/de/datensaetze~soll-fahrplan-gtfs~",
        "license": "CC BY 4.0",
        "source_sha256": feed["sha256"],
        "feed_start_date": start,
        "feed_end_date": end,
    }
    try:
        connection = sqlite3.connect(temp)
        with connection:
            connection.executescript("""
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE agencies(agency_id TEXT PRIMARY KEY, agency_name TEXT NOT NULL);
                CREATE TABLE routes(\n                    route_id TEXT PRIMARY KEY,\n                    agency_id TEXT NOT NULL,\n                    short_name TEXT NOT NULL,\n                    line_key TEXT NOT NULL\n                );
                CREATE TABLE trips(
                    trip_id TEXT PRIMARY KEY,
                    route_id TEXT NOT NULL,
                    service_id TEXT NOT NULL,
                    short_name TEXT NOT NULL
                );
                CREATE TABLE stops(
                    stop_id TEXT PRIMARY KEY,
                    parent_station TEXT NOT NULL,
                    stop_code TEXT NOT NULL,
                    station_ifopt TEXT NOT NULL
                );
                CREATE TABLE stop_times(trip_id TEXT NOT NULL, stop_id TEXT NOT NULL);
                CREATE TABLE calendar(
                    service_id TEXT PRIMARY KEY,
                    monday INTEGER NOT NULL, tuesday INTEGER NOT NULL,
                    wednesday INTEGER NOT NULL, thursday INTEGER NOT NULL,
                    friday INTEGER NOT NULL, saturday INTEGER NOT NULL,
                    sunday INTEGER NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL
                );
                CREATE TABLE calendar_dates(
                    service_id TEXT NOT NULL, date TEXT NOT NULL, exception_type INTEGER NOT NULL
                );
            """)
            connection.executemany("INSERT INTO metadata VALUES (?, ?)", sorted(metadata.items()))
            connection.executemany(
                "INSERT INTO agencies VALUES (?, ?)",
                [(key, row.get("agency_name", "").strip()) for key, row in sorted(agencies.items())],
            )
            connection.executemany(
                "INSERT INTO routes VALUES (?, ?, ?, ?)",
                [
                    (
                        key,
                        row["agency_id"],
                        row.get("route_short_name", "").strip(),
                        _oebb_line_key(row.get("route_short_name", "")),
                    )
                    for key, row in sorted(rail_routes.items())
                ],
            )
            connection.executemany(
                "INSERT INTO trips VALUES (?, ?, ?, ?)",
                [
                    (
                        trip_id, row["route_id"], row.get("service_id", ""),
                        row.get("trip_short_name", "").strip(),
                    )
                    for trip_id, row in sorted(trips.items())
                ],
            )
            connection.executemany(
                "INSERT INTO stops VALUES (?, ?, ?, ?)",
                [
                    (
                        key,
                        row.get("parent_station", "").strip(),
                        row.get("stop_code", "").strip(),
                        _oebb_station_ifopt(key, row.get("parent_station", "")),
                    )
                    for key, row in sorted(stops.items())
                ],
            )
            connection.executemany(
                "INSERT INTO stop_times VALUES (?, ?)",
                [(row["trip_id"], row["stop_id"]) for row in stop_times],
            )
            connection.executemany(
                "INSERT INTO calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        service_id,
                        *(int(row.get(day, "0") or 0) for day in (
                            "monday", "tuesday", "wednesday", "thursday",
                            "friday", "saturday", "sunday",
                        )),
                        row.get("start_date", ""), row.get("end_date", ""),
                    )
                    for service_id, row in sorted(calendar.items())
                ],
            )
            connection.executemany(
                "INSERT INTO calendar_dates VALUES (?, ?, ?)",
                [
                    (
                        row.get("service_id", ""), row.get("date", ""),
                        int(row.get("exception_type", "0") or 0),
                    )
                    for row in calendar_dates if row.get("exception_type", "").isdigit()
                ],
            )
            connection.executescript("""
                CREATE INDEX idx_oebb_trip_short ON trips(short_name);
                CREATE INDEX idx_oebb_route_line ON routes(line_key);
                CREATE INDEX idx_oebb_stop_ifopt ON stops(station_ifopt);
                CREATE INDEX idx_oebb_stop_times_stop ON stop_times(stop_id);
                CREATE INDEX idx_oebb_stop_times_trip ON stop_times(trip_id);
                CREATE INDEX idx_oebb_stops_parent ON stops(parent_station);
                CREATE INDEX idx_oebb_calendar_dates ON calendar_dates(service_id, date);
            """)
        connection.close()
        os.replace(temp, output)
        os.chmod(output, 0o644)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)

    with sqlite3.connect(output) as connection:
        short_ambiguous = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT t.short_name
                FROM trips t JOIN routes r ON r.route_id=t.route_id
                WHERE t.short_name <> ''
                GROUP BY t.short_name HAVING COUNT(DISTINCT r.agency_id) > 1
            )
        """).fetchone()[0]
        station_short_ambiguous = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT st.stop_id, t.short_name
                FROM stop_times st
                JOIN trips t ON t.trip_id=st.trip_id
                JOIN routes r ON r.route_id=t.route_id
                WHERE t.short_name <> ''
                GROUP BY st.stop_id, t.short_name
                HAVING COUNT(DISTINCT r.agency_id) > 1
            )
        """).fetchone()[0]
        station_line_ambiguous = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT s.station_ifopt, r.line_key
                FROM stop_times st
                JOIN stops s ON s.stop_id=st.stop_id
                JOIN trips t ON t.trip_id=st.trip_id
                JOIN routes r ON r.route_id=t.route_id
                WHERE s.station_ifopt <> '' AND r.line_key <> ''
                GROUP BY s.station_ifopt, r.line_key
                HAVING COUNT(DISTINCT r.agency_id) > 1
            )
        """).fetchone()[0]

    return {
        "agencies": len(agencies),
        "rail_routes": len(rail_routes),
        "rail_trips": len(trips),
        "trips_with_short_name": sum(
            bool(row.get("trip_short_name", "").strip()) for row in trips.values()
        ),
        "indexed_stop_times": len(stop_times),
        "short_names_with_multiple_agencies": short_ambiguous,
        "station_short_names_with_multiple_agencies": station_short_ambiguous,
        "station_line_names_with_multiple_agencies": station_line_ambiguous,
        "feed_start_date": start,
        "feed_end_date": end,
        "source_sha256": feed["sha256"],
    }
