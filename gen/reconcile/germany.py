#!/usr/bin/env python3
"""Reconcile German GTFS rail stop places with the DB station namespace.

The GTFS.de/DELFI feed is used to define the current rail passenger candidate
set.  It is not used to manufacture runtime IDs.  New ``germany_all`` nodes
are emitted only after the DB Timetables station and plan endpoints accept a
native EVA identity. Existing station aliases and stale cache records stay
explicit audit outcomes rather than being silently changed.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import io
import json
import math
import os
import re
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

import requests

from common.io import ROOT, load_ndjson, logical_path


GTFS_URL = "https://download.gtfs.de/germany/rv_free/latest.zip"
GTFS_FEED_PAGE = "https://gtfs.de/en/feeds/germany/"
DB_BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
DB_STATION_URL = f"{DB_BASE_URL}/station/{{eva}}"
DB_PLAN_URL = f"{DB_BASE_URL}/plan/{{eva}}/{{slot}}"
DB_WILDCARD_URL = f"{DB_BASE_URL}/station/*"
BOUNDARY_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_DEU_0.json"
OSM_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

GERMANY_CACHE = ROOT / "cache" / "germany"
GTFS_ARCHIVE = GERMANY_CACHE / "rv-latest.zip"
DB_SNAPSHOT = GERMANY_CACHE / "db-stations-current.xml"
BOUNDARY_CACHE = GERMANY_CACHE / "deu.geo.json"
STALE_OSM_CACHE = GERMANY_CACHE / "osm-stale.json"
CATALOGUE = GERMANY_CACHE / "full.json"
NODES = ROOT / "nodes" / "nodes-germany.json"
AUDIT_FILE = ROOT / "docs" / "review" / "germany-reconciliation.json"
REVIEWED_STATION_OVERRIDES = ROOT / "overrides" / "germany-station-mappings.json"

DEFAULT_PLAN_SLOT = "260828/13"
REQUEST_HEADERS = {
    "Accept": "application/xml",
    "User-Agent": "TrainGuessr-data/germany-reconciliation",
}
OSM_RADIUS_METRES = 1_000.0
OSM_BATCH_SIZE = 1
OSM_REQUEST_TIMEOUT = (10.0, 120.0)
NODE_MATCH_RADIUS_METRES = 1_200.0

GENERIC_NAME_TOKENS = {
    "a",
    "am",
    "bf",
    "bhf",
    "bahnhof",
    "haltepunkt",
    "halt",
    "hbf",
    "hp",
    "station",
    "fr",
    "s",
    "u",
}
SEPARATE_PROVIDER_MARKERS = (
    "angelner dampfeisenbahn",
    "bergwerksbahn",
    "brohltalbahn",
    "dampfnostalgie",
    "dampfeisenbahn",
    "harzer schmalspurbahn",
    "ilztalbahn",
    "kandertalbahn",
    "kleinbahn",
    "mainschleifenbahn",
    "mecklenburgische baederbahn",
    "molli",
    "museumsbahn",
    "oechsle",
    "parkeisenbahn",
    "partyzug",
    "pressnitztalbahn",
    "rhoen zuegle",
    "schmalspurbahn",
    "sdg saechsische dampfeisenbahngesellschaft",
    "touristische bahnen",
    "wanderbahn",
    "zugspitzbahn",
    "verkehrsbetriebe grafschaft hoya",
    "selfkantbahn",
    "kuckucksbahnel",
    "chiemseebahn",
    "waldeisenbahn",
    "museumsbf",
    "mittelsachsen 527",
    "zvon oberlausitz niederschlesien linie a",
    "zvon oberlausitz niederschlesien linie b",
)
TOKEN_EXPANSIONS = {
    "d": ("dusseldorf",),
    "du": ("duisburg",),
    "do": ("dortmund",),
    "lu": ("ludwigshafen",),
    "ka": ("karlsruhe",),
    "fn": ("friedrichshafen",),
    "sz": ("salzgitter",),
    "pw": ("porta", "westfalica"),
    "fds": ("freudenstadt",),
    "n": ("nuernberg",),
    "me": ("mettmann",),
    "gla": ("gelsenkirchen",),
    "gl": ("gleis",),
    "ob": ("oberer",),
    "unt": ("unterer",),
    "st": ("saint",),
    "nordbf": ("nordbahnhof",),
    "ostbf": ("ostbahnhof",),
    "sudbf": ("sudbahnhof",),
    "stadion": ("erzgebirgsstadion",),
    "westbf": ("westbahnhof",),
}
LIFECYCLE_MARKERS = (
    "abandoned",
    "closed",
    "demolished",
    "destroyed",
    "disused",
    "removed",
    "razed",
)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_bytes(
    session: requests.Session,
    url: str,
    path: Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: tuple[float, float] = (10.0, 180.0),
) -> Path:
    response = session.get(url, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    _write_bytes(path, response.content)
    return path


def ensure_gtfs_archive(
    path: Path = GTFS_ARCHIVE,
    *,
    session: requests.Session | None = None,
    refresh: bool = False,
) -> Path:
    if path.is_file() and zipfile.is_zipfile(path) and not refresh:
        return path
    client = session or requests.Session()
    close_client = session is None
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with client.get(
            GTFS_URL,
            stream=True,
            timeout=(10.0, 180.0),
            headers={"User-Agent": REQUEST_HEADERS["User-Agent"]},
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if not zipfile.is_zipfile(temporary):
            raise ValueError(f"GTFS source is not a ZIP archive: {GTFS_URL}")
        os.replace(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)
        if close_client:
            client.close()


def ensure_boundary(
    path: Path = BOUNDARY_CACHE,
    *,
    session: requests.Session | None = None,
    refresh: bool = False,
) -> Path:
    if path.is_file() and not refresh:
        return path
    client = session or requests.Session()
    close_client = session is None
    try:
        return _download_bytes(client, BOUNDARY_URL, path, timeout=(10.0, 60.0))
    finally:
        if close_client:
            client.close()


def _iter_table(archive: zipfile.ZipFile, filename: str) -> Iterable[dict[str, str]]:
    with archive.open(filename) as raw:
        with io.TextIOWrapper(
            raw, encoding="utf-8-sig", errors="replace", newline=""
        ) as text:
            yield from csv.DictReader(text)


def _table(archive: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    try:
        return list(_iter_table(archive, filename))
    except KeyError:
        return []


def _float_pair(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        latitude = float(row.get("stop_lat") or "")
        longitude = float(row.get("stop_lon") or "")
    except (TypeError, ValueError):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


def _root_stop_id(stop_id: str, stops: dict[str, dict[str, str]]) -> str:
    current = stop_id
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        parent = str(stops.get(current, {}).get("parent_station") or "").strip()
        if not parent or parent not in stops:
            return current
        current = parent
    return current or stop_id


def _route_label(route: dict[str, str]) -> str:
    return str(
        route.get("route_short_name")
        or route.get("route_long_name")
        or route.get("route_id")
        or ""
    ).strip()


def _boundary_geometry(payload: Any) -> list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    """Return polygon exteriors and holes as (longitude, latitude) pairs."""
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        geometries = [
            feature.get("geometry")
            for feature in payload.get("features", [])
            if isinstance(feature, dict)
        ]
    elif isinstance(payload, dict) and payload.get("type") == "Feature":
        geometries = [payload.get("geometry")]
    else:
        geometries = [payload]

    polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]] = []
    for geometry in geometries:
        if not isinstance(geometry, dict):
            continue
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon":
            polygon_values = [coordinates]
        elif geometry_type == "MultiPolygon":
            polygon_values = coordinates or []
        else:
            continue
        for polygon in polygon_values:
            if not isinstance(polygon, list) or not polygon:
                continue
            rings: list[list[tuple[float, float]]] = []
            for ring in polygon:
                if not isinstance(ring, list):
                    continue
                points: list[tuple[float, float]] = []
                for point in ring:
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        continue
                    try:
                        points.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError):
                        continue
                if len(points) >= 3:
                    rings.append(points)
            if rings:
                polygons.append((rings[0], rings[1:]))
    return polygons


def _inside_ring(point: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index - 1]
        x2, y2 = ring[index]
        if ((y1 > y) != (y2 > y)) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _in_boundary(
    location: tuple[float, float],
    polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]],
) -> bool:
    latitude, longitude = location
    point = (longitude, latitude)
    return any(
        _inside_ring(point, exterior)
        and not any(_inside_ring(point, hole) for hole in holes)
        for exterior, holes in polygons
    )


def _normalise(value: Any) -> str:
    text = str(value or "").replace("ß", "ss").replace("ø", "oe").replace("Ø", "Oe")
    text = re.sub(r"\bb\.s[- ]", "bad salzuflen ", text, flags=re.IGNORECASE)
    text = re.sub(r"\ba\.?\s+k\.?\b", "am Kaiserstuhl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.?\s+k\.?\b", "im Kaiserstuhl", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b([^\W\d_]+)str\.?(?=\s|$|[(),/+:-])",
        r"\1strasse",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bstr\.?\b", "strasse", text, flags=re.IGNORECASE)
    text = re.sub(r"\brh\.?\b", "rhein", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.?\s+s\.?\b", "im", text, flags=re.IGNORECASE)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def name_tokens(value: Any) -> frozenset[str]:
    tokens = _normalise(value).split()
    filtered = [token for token in tokens if token not in GENERIC_NAME_TOKENS]
    if len(filtered) > 1:
        filtered = [token for token in filtered if token != "s"]
    expanded: list[str] = []
    for token in filtered:
        expanded.extend(TOKEN_EXPANSIONS.get(token, (token,)))
    return frozenset(expanded)


def name_key(value: Any) -> str:
    return " ".join(sorted(name_tokens(value)))


def name_score(first: Any, second: Any) -> float:
    first_tokens = name_tokens(first)
    second_tokens = name_tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    if first_tokens == second_tokens:
        return 1.0
    pairs: list[tuple[float, str, str]] = []
    for first_token in first_tokens:
        for second_token in second_tokens:
            if first_token == second_token:
                similarity = 1.0
            elif min(len(first_token), len(second_token)) >= 4:
                similarity = difflib.SequenceMatcher(
                    None, first_token, second_token
                ).ratio()
                if first_token.startswith(second_token) or second_token.startswith(first_token):
                    similarity = max(similarity, 0.82)
            else:
                similarity = 0.0
            if similarity >= 0.72:
                pairs.append((similarity, first_token, second_token))
    pairs.sort(reverse=True)
    matched_first: set[str] = set()
    matched_second: set[str] = set()
    similarities: list[float] = []
    for similarity, first_token, second_token in pairs:
        if first_token in matched_first or second_token in matched_second:
            continue
        matched_first.add(first_token)
        matched_second.add(second_token)
        similarities.append(similarity)
    if not similarities:
        return 0.0
    score = sum(similarities) / len(first_tokens | second_tokens)
    shared_tokens = first_tokens & second_tokens
    if len(shared_tokens) >= 3 or (
        len(shared_tokens) >= 2
        and max(len(first_tokens), len(second_tokens)) <= 3
    ):
        score = max(score, 0.72)
    if len(matched_first) == len(first_tokens):
        score = max(
            score,
            0.72 if min(len(first_tokens), len(second_tokens)) == 1 else 0.86,
        )
    return score


def _is_strong_name_match(first: Any, second: Any, *, score: float | None = None) -> bool:
    first_key = name_key(first)
    second_key = name_key(second)
    if not first_key or not second_key:
        return False
    if first_key == second_key:
        return True
    if (score if score is not None else name_score(first, second)) < 0.72:
        return False
    shared = name_tokens(first) & name_tokens(second)
    if len(shared) >= 2:
        return True
    return (
        len(shared) == 1
        and len(next(iter(shared))) >= 5
        and min(len(name_tokens(first)), len(name_tokens(second))) == 1
    )


def distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude = math.radians((first[0] + second[0]) / 2.0)
    x = math.radians(second[1] - first[1]) * math.cos(latitude)
    y = math.radians(second[0] - first[0])
    return 6_371_000.0 * math.hypot(x, y)


def build_gtfs_candidates(
    archive_path: Path,
    boundary_polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    with zipfile.ZipFile(archive_path) as archive:
        agencies = {
            str(row.get("agency_id") or ""): row
            for row in _table(archive, "agency.txt")
            if row.get("agency_id")
        }
        routes = {
            str(row.get("route_id") or ""): row
            for row in _table(archive, "routes.txt")
            if row.get("route_id")
        }
        trips = {
            str(row.get("trip_id") or ""): row
            for row in _table(archive, "trips.txt")
            if row.get("trip_id")
        }
        stops = {
            str(row.get("stop_id") or ""): row
            for row in _table(archive, "stops.txt")
            if row.get("stop_id")
        }

        route_type_counts = Counter(str(row.get("route_type") or "") for row in routes.values())
        rail_routes = {
            route_id
            for route_id, row in routes.items()
            if str(row.get("route_type") or "").strip() == "2"
        }
        rail_trips = {
            trip_id
            for trip_id, row in trips.items()
            if str(row.get("route_id") or "") in rail_routes
        }
        places: dict[str, dict[str, Any]] = {}
        stop_time_rows = 0
        missing_stop_rows = 0
        for row in _iter_table(archive, "stop_times.txt"):
            trip_id = str(row.get("trip_id") or "")
            if trip_id not in rail_trips:
                continue
            stop_id = str(row.get("stop_id") or "")
            stop = stops.get(stop_id)
            if not stop:
                missing_stop_rows += 1
                continue
            parent_id = _root_stop_id(stop_id, stops)
            parent = stops.get(parent_id, stop)
            route_id = str(trips[trip_id].get("route_id") or "")
            route = routes.get(route_id, {})
            agency_id = str(route.get("agency_id") or "")
            place = places.setdefault(
                parent_id,
                {
                    "gtfs_parent_station": parent_id,
                    "gtfs_stop_ids": set(),
                    "gtfs_stop_names": set(),
                    "agency_ids": set(),
                    "agency_names": set(),
                    "route_ids": set(),
                    "route_names": set(),
                    "rail_stop_time_count": 0,
                    "passenger_stop_time_count": 0,
                    "stop": parent,
                },
            )
            place["gtfs_stop_ids"].add(stop_id)
            if stop.get("stop_name"):
                place["gtfs_stop_names"].add(str(stop["stop_name"]).strip())
            if parent.get("stop_name"):
                place["gtfs_stop_names"].add(str(parent["stop_name"]).strip())
            if agency_id:
                place["agency_ids"].add(agency_id)
                if agencies.get(agency_id, {}).get("agency_name"):
                    place["agency_names"].add(str(agencies[agency_id]["agency_name"]).strip())
            if route_id:
                place["route_ids"].add(route_id)
            label = _route_label(route)
            if label:
                place["route_names"].add(label)
            place["rail_stop_time_count"] += 1
            if (
                str(row.get("pickup_type") or "0").strip() != "1"
                or str(row.get("drop_off_type") or "0").strip() != "1"
            ):
                place["passenger_stop_time_count"] += 1
            stop_time_rows += 1

    candidates: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    for parent_id, raw in sorted(places.items()):
        stop = raw["stop"]
        location = _float_pair(stop)
        name = str(stop.get("stop_name") or "").strip()
        if not name:
            names = sorted(raw["gtfs_stop_names"])
            name = names[0] if names else parent_id
        row = {
            "gtfs_parent_station": parent_id,
            "gtfs_stop_ids": sorted(raw["gtfs_stop_ids"]),
            "gtfs_stop_names": sorted(raw["gtfs_stop_names"]),
            "name": name,
            "latitude": location[0] if location else None,
            "longitude": location[1] if location else None,
            "agency_ids": sorted(raw["agency_ids"]),
            "agency_names": sorted(raw["agency_names"]),
            "route_ids": sorted(raw["route_ids"]),
            "route_names": sorted(raw["route_names"]),
            "rail_stop_time_count": raw["rail_stop_time_count"],
            "passenger_stop_time_count": raw["passenger_stop_time_count"],
            "location_type": str(stop.get("location_type") or ""),
        }
        if not raw["passenger_stop_time_count"]:
            row["scope_reason"] = "not_passenger_station"
            out_of_scope.append(row)
        elif location is None:
            row["scope_reason"] = "missing_or_invalid_coordinates"
            out_of_scope.append(row)
        elif _in_boundary(location, boundary_polygons):
            candidates.append(row)
        else:
            row["scope_reason"] = "outside_germany_boundary"
            out_of_scope.append(row)

    metadata = {
        "agency_records": len(agencies),
        "route_records": len(routes),
        "route_type_counts": dict(sorted(route_type_counts.items())),
        "rail_route_type": "2",
        "rail_routes": len(rail_routes),
        "trip_records": len(trips),
        "rail_trips": len(rail_trips),
        "stop_records": len(stops),
        "rail_stop_time_rows": stop_time_rows,
        "rail_stop_time_rows_with_missing_stop": missing_stop_rows,
        "all_rail_parent_stop_places": len(places),
        "german_parent_stop_places": len(candidates),
        "out_of_scope_parent_stop_places": len(out_of_scope),
        "non_passenger_parent_stop_places": sum(
            not raw["passenger_stop_time_count"] for raw in places.values()
        ),
    }
    return metadata, candidates, out_of_scope


def _local_tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _numeric_ids(value: Any) -> list[str]:
    result: list[str] = []
    for part in re.split(r"[|,; ]+", str(value or "")):
        part = part.strip()
        if part.isdigit() and part not in result:
            result.append(part)
    return result


def parse_station_xml(xml: bytes | str) -> list[dict[str, Any]]:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = ElementTree.fromstring(xml)
    records: list[dict[str, Any]] = []
    for element in root.iter():
        if _local_tag(element) != "station":
            continue
        attributes = dict(element.attrib)
        ids = []
        ids.extend(_numeric_ids(attributes.get("eva")))
        ids.extend(_numeric_ids(attributes.get("meta")))
        records.append(
            {
                "eva": str(attributes.get("eva") or "").strip(),
                "meta": str(attributes.get("meta") or "").strip(),
                "ids": list(dict.fromkeys(ids)),
                "name": str(attributes.get("name") or "").strip(),
                "ds100": str(attributes.get("ds100") or "").strip(),
                "db": str(attributes.get("db") or "").casefold() == "true",
                "attributes": attributes,
            }
        )
    return records


def load_station_snapshot(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    records = parse_station_xml(path.read_bytes())
    namespace = {station_id for record in records for station_id in record["ids"]}
    return records, namespace


def _snapshot_indexes(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = name_key(record.get("name"))
        if key:
            by_name[key].append(record)
        for token in name_tokens(record.get("name")):
            if len(token) >= 3:
                by_token[token].append(record)
    return {"by_name": by_name, "by_token": by_token}


def snapshot_matches(
    name: str,
    indexes: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exact = list(indexes["by_name"].get(name_key(name), []))
    tokens = name_tokens(name)
    possible: dict[tuple[str, str, str], dict[str, Any]] = {}
    for token in tokens:
        for record in indexes["by_token"].get(token, []):
            key = (
                str(record.get("eva") or ""),
                str(record.get("meta") or ""),
                str(record.get("name") or ""),
            )
            possible[key] = record
    scored = [
        (name_score(name, record.get("name")), record)
        for record in possible.values()
        if name_score(name, record.get("name")) >= 0.45
    ]
    scored.sort(key=lambda item: (-item[0], not item[1].get("db"), item[1].get("name", "")))
    ordered: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in [
        *sorted(exact, key=lambda row: (not row.get("db"), row.get("name", ""))),
        *(record for _, record in scored),
    ]:
        key = (
            str(record.get("eva") or ""),
            str(record.get("meta") or ""),
            str(record.get("name") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        ordered.append(record)
    return ordered[:20]


def _best_snapshot_matches(name: str, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [
        (name_score(name, record.get("name")), record)
        for record in records
    ]
    strong = [(score, record) for score, record in scored if score >= 0.72]
    if not strong:
        return []
    best_score = max(score for score, _ in strong)
    best = [record for score, record in strong if abs(score - best_score) < 1e-9]
    best_exact_token_count = max(
        len(name_tokens(name) & name_tokens(record.get("name")))
        for record in best
    )
    best = [
        record
        for record in best
        if len(name_tokens(name) & name_tokens(record.get("name")))
        == best_exact_token_count
    ]
    exact = [record for record in best if name_key(name) == name_key(record.get("name"))]
    if exact:
        return exact

    groups: list[set[str]] = []
    for record in best:
        identifiers = set(str(value) for value in record.get("ids", []) if str(value))
        overlapping = [group for group in groups if group & identifiers]
        if not overlapping:
            groups.append(identifiers)
            continue
        merged = set(identifiers)
        for group in overlapping:
            merged.update(group)
            groups.remove(group)
        groups.append(merged)
    if len(groups) != 1:
        return []
    return best


def _candidate_station_names(candidate: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for value in [candidate.get("name"), *(candidate.get("gtfs_stop_names") or [])]:
        name = str(value or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def candidate_snapshot_matches(
    candidate: dict[str, Any],
    indexes: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Match a GTFS stop place using every name carried by its stop hierarchy.

    GTFS parent display names are often generic ("... Bahnhof") while a child
    stop carries the exact DB spelling ("...(Württ)").  Restricting namespace
    lookup to the chosen parent name creates false provider gaps.
    """
    all_matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    best_matches: list[dict[str, Any]] = []
    best_alias: str | None = None
    best_rank: tuple[int, int, float, int] | None = None

    for alias_index, alias in enumerate(_candidate_station_names(candidate)):
        alias_matches = snapshot_matches(alias, indexes, records)
        for record in alias_matches:
            key = (
                str(record.get("eva") or ""),
                str(record.get("meta") or ""),
                str(record.get("name") or ""),
            )
            if key not in seen:
                seen.add(key)
                all_matches.append(record)

        strong = _best_snapshot_matches(alias, alias_matches)
        if not strong:
            continue
        score = max(name_score(alias, record.get("name")) for record in strong)
        exact = int(
            any(name_key(alias) == name_key(record.get("name")) for record in strong)
        )
        has_db_identity = int(any(record.get("db") is True for record in strong))
        rank = (exact, has_db_identity, score, -alias_index)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_matches = strong
            best_alias = alias

    # Put the selected matches first so the persisted evidence clearly shows
    # which namespace identity drove provider probing.
    ordered: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str]] = set()
    for record in [*best_matches, *all_matches]:
        key = (
            str(record.get("eva") or ""),
            str(record.get("meta") or ""),
            str(record.get("name") or ""),
        )
        if key in selected_keys:
            continue
        selected_keys.add(key)
        ordered.append(record)
    return ordered[:20], best_matches, best_alias


def _values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _values(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _values(child)
    elif value not in (None, ""):
        yield str(value)


def load_generated_identity_index(path: Path = NODES) -> dict[str, Any]:
    rows = load_ndjson(path)
    by_id: dict[str, str] = {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        canonical_id = str(row.get("id") or "").strip()
        if not canonical_id:
            continue
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        ids = [canonical_id]
        for key in ("provider_place_ids", "further_ids", "provider_ids"):
            ids.extend(_values(tags.get(key)))
        for station_id in ids:
            if station_id:
                by_id[station_id] = canonical_id
        by_name[name_key(tags.get("name"))].append(row)
    return {"rows": rows, "by_id": by_id, "by_name": by_name}


def load_catalogue_index(path: Path = CATALOGUE) -> dict[str, Any]:
    rows = _read_json(path) if path.is_file() else []
    if not isinstance(rows, list):
        raise ValueError(f"Germany station catalogue must be an array: {path}")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        station_id = str(row.get("id") or "").strip()
        if station_id:
            by_id[station_id] = row
        for alias in row.get("additionalIds") or []:
            alias = str(alias).strip()
            if alias:
                by_id[alias] = row
    return {"rows": rows, "by_id": by_id}


def _grid_key(latitude: float, longitude: float) -> tuple[int, int]:
    return int(math.floor(latitude * 10)), int(math.floor(longitude * 10))


def build_node_grid(rows: Iterable[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    grid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            location = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        grid[_grid_key(*location)].append(row)
    return grid


def nearby_nodes(
    candidate: dict[str, Any],
    grid: dict[tuple[int, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if candidate.get("latitude") is None or candidate.get("longitude") is None:
        return []
    location = float(candidate["latitude"]), float(candidate["longitude"])
    latitude_key, longitude_key = _grid_key(*location)
    matches: list[tuple[float, float, dict[str, Any]]] = []
    for latitude_delta in (-1, 0, 1):
        for longitude_delta in (-1, 0, 1):
            for row in grid.get((latitude_key + latitude_delta, longitude_key + longitude_delta), []):
                try:
                    row_location = float(row["lat"]), float(row["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                distance = distance_m(location, row_location)
                score = name_score(candidate.get("name"), (row.get("tags") or {}).get("name"))
                strong_name = score >= 0.72 and distance <= NODE_MATCH_RADIUS_METRES
                close_name = score >= 0.33 and distance <= 300.0
                shared_tokens = name_tokens(candidate.get("name")) & name_tokens(
                    (row.get("tags") or {}).get("name")
                )
                coordinate_name = (
                    distance <= 100.0
                    and any(len(token) >= 5 for token in shared_tokens)
                )
                if strong_name or close_name or coordinate_name:
                    matches.append((score, distance, row))
    matches.sort(key=lambda item: (-item[0], item[1], str(item[2].get("id"))))
    return [row for _, _, row in matches[:8]]


def _preferred_provider_ids(records: Iterable[dict[str, Any]], limit: int = 8) -> list[str]:
    ids: list[str] = []
    for record in records:
        values = list(record.get("ids") or [])
        values.sort(key=lambda value: (not (len(value) == 7 and value.startswith("80")), len(value), value))
        for value in values:
            if value not in ids:
                ids.append(value)
    return ids[:limit]


def _provider_group(agency_names: Iterable[str]) -> str:
    text = _normalise(" ".join(agency_names))
    if any(marker in text for marker in SEPARATE_PROVIDER_MARKERS):
        return "separate_heritage_or_tourist_rail"
    return "regional_or_mainline_rail"


def _verification_state(result: dict[str, Any]) -> str:
    status = result.get("http_status")
    if result.get("verification_state"):
        return str(result["verification_state"])
    if status in (401, 403):
        return "provider_verification_blocked_auth"
    if status in (429, 500, 502, 503, 504) or status is None:
        return "provider_verification_blocked_access"
    if status == 200 and result.get("db") is True:
        return "verified"
    if status == 404:
        return "provider_incompatible"
    return "provider_incompatible"


class DbProbe:
    def __init__(
        self,
        *,
        cache_dir: Path = GERMANY_CACHE / "db-probes",
        session: requests.Session | None = None,
        delay: float = 0.15,
        refresh: bool = False,
        plan_slots: Iterable[str] = (DEFAULT_PLAN_SLOT,),
    ) -> None:
        self.cache_dir = cache_dir
        self.session = session or requests.Session()
        self.delay = max(0.0, delay)
        self.refresh = refresh
        self.plan_slots = list(dict.fromkeys(str(slot) for slot in plan_slots if str(slot).strip()))
        self.client_id = (
            os.getenv("DB_API_TIMETABLES_CLIENTID")
            or os.getenv("DB_API_RISBOARDS_CLIENTID", "")
        )
        self.secret = (
            os.getenv("DB_API_TIMETABLES_SECRET")
            or os.getenv("DB_API_RISBOARDS_CLIENTSECRET", "")
        )
        self.headers = {
            **REQUEST_HEADERS,
            "DB-Client-ID": self.client_id,
            "DB-Api-Key": self.secret,
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def auth_configured(self) -> bool:
        return bool(self.client_id and self.secret)

    def _blocked(self, url: str, reason: str) -> dict[str, Any]:
        return {
            "url": url,
            "http_status": None,
            "verification_state": reason,
        }

    def _pause(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    def station(self, eva: str) -> dict[str, Any]:
        eva = str(eva).strip()
        path = self.cache_dir / f"station-{eva}.json"
        url = DB_STATION_URL.format(eva=eva)
        if path.is_file() and not self.refresh:
            return _read_json(path)
        if not self.auth_configured:
            result = self._blocked(url, "provider_verification_blocked_auth")
            _write_json(path, result)
            return result
        result: dict[str, Any] = {"url": url, "requested_eva": eva}
        try:
            response = self.session.get(url, headers=self.headers, timeout=(5.0, 30.0))
            result["http_status"] = response.status_code
            result["response_bytes"] = len(response.content)
            if response.status_code == 200:
                records = parse_station_xml(response.content)
                if not records:
                    result["verification_state"] = "provider_incompatible"
                    result["error"] = "successful response contained no station element"
                else:
                    station = records[0]
                    result.update(
                        {
                            "eva": station.get("eva"),
                            "meta": station.get("meta"),
                            "name": station.get("name"),
                            "ds100": station.get("ds100"),
                            "db": station.get("db"),
                            "verification_state": _verification_state(
                                {"http_status": 200, "db": station.get("db")}
                            ),
                        }
                    )
                    _write_bytes(self.cache_dir / f"station-{eva}.xml", response.content)
            elif response.status_code in (401, 403):
                result["verification_state"] = "provider_verification_blocked_auth"
            elif response.status_code in (429, 500, 502, 503, 504):
                result["verification_state"] = "provider_verification_blocked_access"
            elif response.status_code == 404:
                result["verification_state"] = "provider_incompatible"
            else:
                result["verification_state"] = "provider_verification_blocked_access"
        except (requests.RequestException, ValueError, ElementTree.ParseError) as exc:
            result["http_status"] = None
            result["verification_state"] = "provider_verification_blocked_access"
            result["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(path, result)
        self._pause()
        return result

    def plan(self, eva: str, slot: str) -> dict[str, Any]:
        eva = str(eva).strip()
        slot = str(slot).strip()
        safe_slot = slot.replace("/", "-")
        path = self.cache_dir / f"plan-{eva}-{safe_slot}.json"
        url = DB_PLAN_URL.format(eva=eva, slot=slot)
        if path.is_file() and not self.refresh:
            return _read_json(path)
        if not self.auth_configured:
            result = self._blocked(url, "provider_verification_blocked_auth")
            result["slot"] = slot
            _write_json(path, result)
            return result
        result: dict[str, Any] = {"url": url, "slot": slot, "requested_eva": eva}
        try:
            response = self.session.get(url, headers=self.headers, timeout=(5.0, 30.0))
            result["http_status"] = response.status_code
            result["response_bytes"] = len(response.content)
            if response.status_code == 200:
                try:
                    ElementTree.fromstring(response.content)
                except ElementTree.ParseError as exc:
                    result["verification_state"] = "provider_verification_blocked_access"
                    result["error"] = f"invalid XML: {exc}"
                else:
                    result["verification_state"] = "verified"
                    _write_bytes(self.cache_dir / f"plan-{eva}-{safe_slot}.xml", response.content)
            elif response.status_code in (401, 403):
                result["verification_state"] = "provider_verification_blocked_auth"
            elif response.status_code in (429, 500, 502, 503, 504):
                result["verification_state"] = "provider_verification_blocked_access"
            elif response.status_code == 404:
                result["verification_state"] = "provider_incompatible"
            else:
                result["verification_state"] = "provider_verification_blocked_access"
        except (requests.RequestException, ValueError) as exc:
            result["http_status"] = None
            result["verification_state"] = "provider_verification_blocked_access"
            result["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(path, result)
        self._pause()
        return result

    def resolve(
        self,
        provider_ids: Iterable[str],
        *,
        expected_name: str | None = None,
        expected_name_aliases: Iterable[str] = (),
    ) -> dict[str, Any]:
        station_checks: list[dict[str, Any]] = []
        plan_checks: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        aliases = [str(value).strip() for value in expected_name_aliases if str(value or "").strip()]
        expected_names = [str(expected_name).strip()] if str(expected_name or "").strip() else []
        expected_names.extend(aliases)
        for provider_id in list(dict.fromkeys(str(value) for value in provider_ids)):
            station = self.station(provider_id)
            station_checks.append(station)
            if station.get("http_status") != 200 or station.get("db") is not True:
                continue
            if expected_names and not any(
                _is_strong_name_match(name, station.get("name"))
                for name in expected_names
            ) and not any(
                _is_strong_name_match(station.get("name"), alias)
                for alias in aliases
            ):
                station["name_match"] = False
                station["verification_state"] = "provider_incompatible"
                continue
            station["name_match"] = True if expected_name else None
            plans = [self.plan(provider_id, slot) for slot in self.plan_slots]
            plan_checks.extend(plans)
            if any(plan.get("http_status") == 200 for plan in plans):
                selected = station
                break
        return {
            "station_checks": station_checks,
            "plan_checks": plan_checks,
            "selected_station": selected,
            "selected_eva": selected.get("eva") if selected else None,
            "station_http_status": selected.get("http_status") if selected else None,
            "plan_http_status": 200 if any(row.get("http_status") == 200 for row in plan_checks) else None,
        }


def _station_summaries(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        result.append(
            {
                key: record.get(key)
                for key in ("eva", "meta", "ids", "name", "ds100", "db")
                if record.get(key) not in (None, "", [])
            }
        )
    return result


def _probe_summary(probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "station_checks": [
            {
                key: row.get(key)
                for key in (
                    "requested_eva",
                    "url",
                    "http_status",
                    "response_bytes",
                    "eva",
                    "meta",
                    "name",
                    "name_match",
                    "ds100",
                    "db",
                    "verification_state",
                    "error",
                )
                if row.get(key) not in (None, "")
            }
            for row in probe.get("station_checks", [])
        ],
        "plan_checks": [
            {
                key: row.get(key)
                for key in (
                    "requested_eva",
                    "slot",
                    "url",
                    "http_status",
                    "response_bytes",
                    "verification_state",
                    "error",
                )
                if row.get(key) not in (None, "")
            }
            for row in probe.get("plan_checks", [])
        ],
        "selected_eva": probe.get("selected_eva"),
        "station_http_status": probe.get("station_http_status"),
        "plan_http_status": probe.get("plan_http_status"),
    }


def _node_match_summary(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        result.append(
            {
                "node_id": str(row.get("id") or ""),
                "name": tags.get("name", ""),
                "provider_place_ids": list(_values(tags.get("provider_place_ids"))),
                "further_ids": list(_values(tags.get("further_ids"))),
                "latitude": row.get("lat"),
                "longitude": row.get("lon"),
            }
        )
    return result


def _outcome(
    candidate: dict[str, Any],
    *,
    status: str,
    reason: str,
    provider_group: str,
    evidence: dict[str, Any],
    provider_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "gtfs_parent_station": candidate["gtfs_parent_station"],
        "gtfs_stop_ids": candidate["gtfs_stop_ids"],
        "gtfs_stop_names": candidate["gtfs_stop_names"],
        "name": candidate["name"],
        "latitude": candidate["latitude"],
        "longitude": candidate["longitude"],
        "agency_ids": candidate["agency_ids"],
        "agency_names": candidate["agency_names"],
        "route_ids": candidate["route_ids"],
        "route_names": candidate["route_names"],
        "rail_stop_time_count": candidate["rail_stop_time_count"],
        "status": status,
        "provider_group": provider_group,
        "reason": reason,
        "evidence": evidence,
    }
    if provider_id:
        row["eva_id"] = provider_id
        row["db"] = "true"
        row["source"] = "reviewed-germany-current-provider"
        for station in evidence.get("db_probe", {}).get("station_checks", []):
            if str(station.get("requested_eva") or "") == provider_id:
                if station.get("ds100"):
                    row["ds100"] = station["ds100"]
                break
    return row


def _preserved_rows(previous_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    preserved: dict[str, dict[str, Any]] = {}
    for row in previous_audit.get("outcomes", []) if isinstance(previous_audit, dict) else []:
        if not isinstance(row, dict):
            continue
        if (
            row.get("status") == "added_existing_provider"
            and row.get("source") == "reviewed-germany-current-provider"
        ):
            parent = str(row.get("gtfs_parent_station") or "").strip()
            if parent:
                preserved[parent] = row
            continue
        # Keep reviewed additions stable after they have been integrated into
        # the generated catalogue. The first Germany pass predates the full
        # ledger and has no explicit source field, so its AKN prefix is also
        # kept for compatibility.
        if row.get("source") not in ("reviewed-germany-akn-supplement", None):
            continue
        if row.get("source") is None and (
            "agency_names" in row or "provider_group" in row
        ):
            continue
        parent = str(row.get("gtfs_parent_station") or "").strip()
        if parent:
            preserved[parent] = row
    return preserved


def _lifecycle_flags(tags: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key, value in tags.items():
        text = _normalise(f"{key} {value}")
        if any(marker in text for marker in LIFECYCLE_MARKERS):
            flags.append(f"{key}={value}")
    return sorted(set(flags))


def _osm_location(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("lat") is not None and element.get("lon") is not None:
        try:
            return float(element["lat"]), float(element["lon"])
        except (TypeError, ValueError):
            return None
    center = element.get("center")
    if isinstance(center, dict) and center.get("lat") is not None and center.get("lon") is not None:
        try:
            return float(center["lat"]), float(center["lon"])
        except (TypeError, ValueError):
            return None
    return None


def _osm_summary(element: dict[str, Any], distance: float) -> dict[str, Any]:
    tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
    summary = {
        "url": f"https://www.openstreetmap.org/{element.get('type', 'node')}/{element.get('id')}",
        "osm_type": element.get("type"),
        "osm_id": element.get("id"),
        "distance_m": round(distance, 1),
        "railway": tags.get("railway", ""),
        "name": tags.get("name", ""),
        "railway_name": tags.get("railway:name", ""),
        "uic_ref": tags.get("uic_ref", ""),
        "ref": tags.get("ref", ""),
        "train": tags.get("train", ""),
        "operator": tags.get("operator", ""),
        "network": tags.get("network", ""),
        "lifecycle_flags": _lifecycle_flags(tags),
    }
    return {key: value for key, value in summary.items() if value not in ("", [], None)}


def _stale_osm_evidence(
    record: dict[str, Any],
    elements: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        location = float(record["latitude"]), float(record["longitude"])
    except (KeyError, TypeError, ValueError):
        return {"nearby_features": [], "nearby_count": 0, "lifecycle_count": 0}
    nearby = []
    for element in elements:
        element_location = _osm_location(element)
        if element_location is None:
            continue
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        if tags.get("railway") not in {"station", "halt", "stop", "platform"}:
            continue
        distance = distance_m(location, element_location)
        if distance <= OSM_RADIUS_METRES:
            nearby.append(_osm_summary(element, distance))
    nearby.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    lifecycle = [row for row in nearby if row.get("lifecycle_flags")]
    return {
        "nearby_features": nearby[:20],
        "nearby_count": len(nearby),
        "lifecycle_count": len(lifecycle),
        "extant_passenger_feature_count": sum(
            row.get("train") == "yes" and row.get("railway") in {"station", "halt", "stop"}
            for row in nearby
        ),
    }


def _osm_query(records: list[dict[str, Any]]) -> str:
    clauses = []
    for record in records:
        clauses.append(
            "nwr[\"railway\"~\"^(station|halt|stop|platform)$\"]"
            f"(around:{int(OSM_RADIUS_METRES)},{record['latitude']},{record['longitude']});"
        )
    return "[out:json][timeout:180];(" + "".join(clauses) + ");out center tags;"


def fetch_stale_osm(
    records: list[dict[str, Any]],
    *,
    path: Path = STALE_OSM_CACHE,
    session: requests.Session | None = None,
    refresh: bool = False,
    delay: float = 1.0,
) -> dict[str, Any]:
    if path.is_file() and not refresh:
        payload = _read_json(path)
        return payload if isinstance(payload, dict) else {"elements": [], "errors": []}
    client = session or requests.Session()
    close_client = session is None
    elements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    try:
        for batch_start in range(0, len(records), OSM_BATCH_SIZE):
            batch = records[batch_start:batch_start + OSM_BATCH_SIZE]
            query = _osm_query(batch)
            success = False
            for endpoint in OSM_ENDPOINTS:
                try:
                    response = client.post(
                        endpoint,
                        data=query,
                        headers={
                            "Accept": "application/json",
                            "User-Agent": "TrainGuessr-data/1.0 (station audit)",
                        },
                        timeout=OSM_REQUEST_TIMEOUT,
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise requests.HTTPError(f"HTTP {response.status_code}")
                    response.raise_for_status()
                    payload = response.json()
                    for element in payload.get("elements", []) if isinstance(payload, dict) else []:
                        if not isinstance(element, dict):
                            continue
                        key = (str(element.get("type", "")), str(element.get("id", "")))
                        if key not in seen:
                            seen.add(key)
                            elements.append(element)
                    success = True
                    break
                except (requests.RequestException, ValueError) as exc:
                    errors.append(
                        {
                            "batch_start": batch_start,
                            "endpoint": endpoint,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            if not success:
                continue
            if delay > 0:
                time.sleep(delay)
    finally:
        if close_client:
            client.close()
    payload = {
        "source_url": OSM_ENDPOINTS[0],
        "radius_metres": OSM_RADIUS_METRES,
        "queried_records": len(records),
        "elements": elements,
        "errors": errors,
    }
    _write_json(path, payload)
    return payload


def _stale_records(
    catalogue: dict[str, Any],
    generated: dict[str, Any],
    namespace: set[str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for primary in catalogue["rows"]:
        if not isinstance(primary, dict):
            continue
        primary_id = str(primary.get("id") or "").strip()
        identifiers = [(primary_id, "primary")]
        identifiers.extend((str(alias).strip(), "additionalIds") for alias in primary.get("additionalIds") or [])
        for station_id, role in identifiers:
            if not station_id or station_id in namespace or station_id in seen:
                continue
            seen.add(station_id)
            location = primary.get("location") if isinstance(primary.get("location"), dict) else {}
            result.append(
                {
                    "cached_id": station_id,
                    "cache_role": role,
                    "catalogue_primary_id": primary_id,
                    "name": primary.get("name", ""),
                    "ds100": primary.get("ril100", ""),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "catalogue_record": {
                        key: primary.get(key)
                        for key in ("id", "additionalIds", "name", "ril100", "nr", "location")
                        if primary.get(key) not in (None, "", [])
                    },
                    "generated_canonical_id": generated["by_id"].get(station_id),
                }
            )
    return sorted(result, key=lambda row: str(row["cached_id"]))


def reconcile(
    *,
    archive_path: Path = GTFS_ARCHIVE,
    boundary_path: Path = BOUNDARY_CACHE,
    station_snapshot_path: Path = DB_SNAPSHOT,
    catalogue_path: Path = CATALOGUE,
    nodes_path: Path = NODES,
    previous_audit: dict[str, Any] | None = None,
    db_probe: DbProbe | None = None,
    probe_stale_osm: dict[str, Any] | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    boundary = _boundary_geometry(_read_json(boundary_path))
    gtfs_metadata, candidates, out_of_scope = build_gtfs_candidates(archive_path, boundary)
    station_records, namespace = load_station_snapshot(station_snapshot_path)
    snapshot_indexes = _snapshot_indexes(station_records)
    generated = load_generated_identity_index(nodes_path)
    catalogue = load_catalogue_index(catalogue_path)
    reviewed_station_overrides = load_reviewed_station_overrides()
    reviewed_gap_notes = load_reviewed_gap_notes()
    node_grid = build_node_grid(generated["rows"])
    previous = previous_audit or {}
    preserved = _preserved_rows(previous)
    candidate_parent_ids = {row["gtfs_parent_station"] for row in candidates}
    preserved_rows = [
        preserved[parent] for parent in preserved if parent in candidate_parent_ids
    ]
    preserved_parent_ids = {str(row.get("gtfs_parent_station")) for row in preserved_rows}
    probe = db_probe or DbProbe()
    outcomes: list[dict[str, Any]] = []
    added_provider_ids: set[str] = set(generated["by_id"])
    feed_hash = sha256(archive_path)

    # Keep the manually verified AKN prefix byte-for-byte compatible with the
    # existing generator order while replacing the rest with the full audit.
    outcomes.extend(preserved_rows)
    for index, candidate in enumerate(
        (row for row in candidates if row["gtfs_parent_station"] not in preserved_parent_ids),
        1,
    ):
        matches, strong_matches, matched_alias = candidate_snapshot_matches(
            candidate, snapshot_indexes, station_records
        )
        reviewed_override = reviewed_station_overrides.get(
            str(candidate["gtfs_parent_station"])
        )
        if reviewed_override:
            override_ids = set(reviewed_override["provider_ids"])
            override_matches = [
                record
                for record in station_records
                if override_ids.intersection(str(value) for value in record.get("ids", []))
            ]
            if not override_matches:
                raise ValueError(
                    "Reviewed Germany station override is absent from the current DB namespace: "
                    f"{candidate['gtfs_parent_station']} -> {sorted(override_ids)}"
                )
            matches = [
                *override_matches,
                *[
                    record
                    for record in matches
                    if record not in override_matches
                ],
            ]
            strong_matches = override_matches
            matched_alias = str(reviewed_override.get("name_alias") or candidate["name"])
        probe_matches = strong_matches
        provider_ids = _preferred_provider_ids(probe_matches)
        node_matches = nearby_nodes(candidate, node_grid)
        evidence: dict[str, Any] = {
            "gtfs": {
                "feed_url": GTFS_URL,
                "feed_sha256": feed_hash,
                "route_type": "2",
                "rail_stop_time_count": candidate["rail_stop_time_count"],
                "parent_location_type": candidate["location_type"],
            },
            "db_namespace_matches": _station_summaries(matches),
            "generated_node_matches": _node_match_summary(node_matches),
            "cached_catalogue_matches": [
                station_id
                for record in matches
                for station_id in record.get("ids", [])
                if station_id in catalogue["by_id"]
            ],
        }
        if matched_alias:
            evidence["db_namespace_match_alias"] = matched_alias
        if reviewed_override:
            evidence["reviewed_station_override"] = {
                key: value
                for key, value in reviewed_override.items()
                if key != "provider_ids"
            }
        provider_group = _provider_group(
            [
                *candidate["agency_names"],
                *candidate["route_names"],
                candidate["name"],
            ]
        )
        reviewed_gap_note = reviewed_gap_notes.get(
            str(candidate["gtfs_parent_station"])
        )
        if node_matches:
            canonical_id = str(node_matches[0].get("id"))
            outcomes.append(
                _outcome(
                    candidate,
                    status="already_represented",
                    reason=(
                        "The GTFS passenger stop place matches an existing generated station by name and physical coordinates; no duplicate node is created."
                    ),
                    provider_group=provider_group,
                    evidence={**evidence, "canonical_node_id": canonical_id},
                )
            )
        elif not provider_ids:
            status = (
                "new_provider_needed"
                if provider_group == "separate_heritage_or_tourist_rail"
                else "provider_gap"
            )
            reason = (
                "The current DB namespace has no name candidate; the GTFS agency identifies a separate railway system."
                if status == "new_provider_needed"
                else "The current DB namespace has no candidate for this current German GTFS rail stop place."
            )
            if reviewed_gap_note:
                reason = reviewed_gap_note["reason"]
                evidence["reviewed_gap_note"] = reviewed_gap_note
            outcomes.append(
                _outcome(
                    candidate,
                    status=status,
                    reason=reason,
                    provider_group=provider_group,
                    evidence=evidence,
                )
            )
        else:
            probe_aliases = list(_candidate_station_names(candidate))
            probe_aliases.extend(
                str(match.get("name") or "").strip()
                for match in strong_matches
                if str(match.get("name") or "").strip()
            )
            probe_result = probe.resolve(
                provider_ids,
                expected_name=candidate["name"],
                expected_name_aliases=list(dict.fromkeys(probe_aliases)),
            )
            evidence["db_probe"] = _probe_summary(probe_result)
            selected_eva = str(probe_result.get("selected_eva") or "").strip()
            blocked_states = {
                _verification_state(row)
                for row in [
                    *probe_result.get("station_checks", []),
                    *probe_result.get("plan_checks", []),
                ]
                if _verification_state(row).startswith("provider_verification_blocked_")
            }
            if selected_eva:
                if selected_eva in added_provider_ids:
                    status = "alias_member_existing_station_complex"
                    reason = "The verified DB EVA is already represented by a generated station or earlier candidate outcome."
                else:
                    status = "added_existing_provider"
                    reason = "The direct DB station response returned db=true and at least one sampled DB plan response returned HTTP 200."
                    added_provider_ids.add(selected_eva)
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=reason,
                        provider_group=provider_group,
                        evidence=evidence,
                        provider_id=selected_eva if status == "added_existing_provider" else None,
                    )
                )
            elif blocked_states:
                status = sorted(blocked_states)[0]
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=(
                            "Direct DB identity verification was blocked; the audit keeps the GTFS passenger candidate without a guessed ID."
                        ),
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
            elif any(
                row.get("http_status") == 200 and row.get("db") is True
                for row in probe_result.get("station_checks", [])
            ):
                outcomes.append(
                    _outcome(
                        candidate,
                        status="unresolved",
                        reason=(
                            "A direct DB station identity was accepted, but none of the sampled plan hours returned a plan document; the native ID is not promoted without stronger current evidence."
                        ),
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
            else:
                status = (
                    "new_provider_needed"
                    if provider_group == "separate_heritage_or_tourist_rail"
                    else "provider_gap"
                )
                reason = (
                    "The candidate is part of a separate railway system and no verified DB runtime identity was found."
                    if status == "new_provider_needed"
                    else "DB namespace candidates were tested, but no current db=true station with a sampled plan response was verified."
                )
                if reviewed_gap_note:
                    reason = reviewed_gap_note["reason"]
                    evidence["reviewed_gap_note"] = reviewed_gap_note
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=reason,
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
        if progress and index % 25 == 0:
            print(f"Reconciled {index}/{len(candidates) - len(preserved_parent_ids)} Germany GTFS station places")

    stale = _stale_records(catalogue, generated, namespace)
    osm_elements = (probe_stale_osm or {}).get("elements", []) if isinstance(probe_stale_osm, dict) else []
    stale_outcomes: list[dict[str, Any]] = []
    for record in stale:
        direct = probe.resolve([record["cached_id"]])
        direct_summary = _probe_summary(direct)
        osm = _stale_osm_evidence(record, osm_elements)
        direct_station = next(
            (row for row in direct.get("station_checks", []) if row.get("http_status") == 200),
            None,
        )
        if direct_station and direct_station.get("db") is True:
            status = "already_represented"
            reason = "The cached ID is absent from the wildcard namespace but the direct current DB station endpoint still returns db=true."
        elif record.get("generated_canonical_id") and record.get("generated_canonical_id") != record.get("cached_id"):
            status = "alias_member_existing_station_complex"
            reason = "The stale cached identity is kept as an alias of an existing generated station; absence from the current wildcard namespace is not deletion evidence."
        elif any(row.get("lifecycle_flags") for row in osm.get("nearby_features", [])) and not osm.get("extant_passenger_feature_count"):
            status = "dismantled_exclusion"
            reason = "OSM/ORM nearby railway features carry explicit gone-lifecycle signals without an extant passenger feature; removal still requires a deliberate generator exclusion."
        elif osm.get("extant_passenger_feature_count"):
            status = "provider_gap"
            reason = "Physical passenger-rail evidence still exists near the historical DB identity, but no current direct db=true identity was verified."
        else:
            blocked_states = {
                _verification_state(row)
                for row in [*direct.get("station_checks", []), *direct.get("plan_checks", [])]
                if _verification_state(row).startswith("provider_verification_blocked_")
            }
            status = sorted(blocked_states)[0] if blocked_states else "unresolved"
            reason = (
                "Direct DB verification was blocked; no deletion decision is made."
                if blocked_states
                else "Neither current direct DB identity nor nearby OSM/ORM passenger evidence supports a safe lifecycle decision."
            )
        stale_outcomes.append(
            {
                **record,
                "status": status,
                "reason": reason,
                "evidence": {
                    "current_db_namespace_contains_id": record["cached_id"] in namespace,
                    "direct_db": direct_summary,
                    "osm": osm,
                },
            }
        )

    candidate_statuses = Counter(row.get("status") for row in outcomes)
    stale_statuses = Counter(row.get("status") for row in stale_outcomes)
    primary_stale = sum(row.get("cache_role") == "primary" for row in stale)
    alias_stale = sum(row.get("cache_role") != "primary" for row in stale)
    source_files = {
        "gtfs_archive": logical_path(archive_path),
        "cached_station_catalogue": logical_path(catalogue_path),
        "current_db_station_namespace": logical_path(station_snapshot_path),
        "germany_boundary": logical_path(boundary_path),
        "generated_nodes": logical_path(nodes_path),
    }
    if probe_stale_osm is not None:
        source_files["stale_osm_capture"] = logical_path(STALE_OSM_CACHE)
    review = {
        "db_auth_configured": probe.auth_configured,
        "db_plan_slots": list(probe.plan_slots),
        "db_probe_delay_seconds": probe.delay,
        "physical_evidence_rule": "GTFS scheduled route_type=2 usage defines current passenger candidates; stale identities additionally require OSM/ORM lifecycle review.",
    }
    if probe_stale_osm is not None:
        review["osm_capture"] = {
            "queried_records": probe_stale_osm.get("queried_records"),
            "elements": len(probe_stale_osm.get("elements", [])),
            "errors": len(probe_stale_osm.get("errors", [])),
            "batch_size": OSM_BATCH_SIZE,
            "complete": not probe_stale_osm.get("errors"),
        }
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "audit_with_explicit_unresolved",
        "scope": "German-boundary GTFS.de/DELFI route_type=2 rail parent stop places with at least one passenger boarding or alighting event",
        "source_urls": {
            "gtfs_feed_page": GTFS_FEED_PAGE,
            "gtfs_feed": GTFS_URL,
            "db_station_api": DB_STATION_URL,
            "db_plan_api": DB_PLAN_URL,
            "db_station_namespace": DB_WILDCARD_URL,
            "boundary": BOUNDARY_URL,
            "osm": OSM_ENDPOINTS[0],
        },
        "source_files": source_files,
        "source_sha256": {
            "gtfs_archive": sha256(archive_path),
            "cached_station_catalogue": sha256(catalogue_path),
            "current_db_station_namespace": sha256(station_snapshot_path),
            "germany_boundary": sha256(boundary_path),
            "generated_nodes": sha256(nodes_path),
        },
        "review": review,
        "counts": {
            **gtfs_metadata,
            "current_db_station_records": len(station_records),
            "current_db_namespace_ids": len(namespace),
            "generated_nodes_before_reconciliation": len(generated["rows"]),
            "generated_provider_ids_before_reconciliation": len(generated["by_id"]),
            "candidate_records": len(outcomes),
            "candidate_statuses": dict(sorted(candidate_statuses.items())),
            "candidate_provider_groups": dict(sorted(Counter(
                str(row.get("provider_group") or "preserved_legacy") for row in outcomes
            ).items())),
            "verified_additions": candidate_statuses.get("added_existing_provider", 0),
            "out_of_scope_records": len(out_of_scope),
            "cached_primary_ids": sum(bool(str(row.get("id") or "").strip()) for row in catalogue["rows"]),
            "cached_provider_ids": len(catalogue["by_id"]),
            "cached_primary_ids_absent_from_current_db_namespace": primary_stale,
            "cached_alias_ids_absent_from_current_db_namespace": alias_stale,
            "cached_ids_absent_from_current_db_namespace": len(stale),
            "stale_statuses": dict(sorted(stale_statuses.items())),
            "stale_records": len(stale_outcomes),
        },
        "out_of_scope": out_of_scope,
        "outcomes": outcomes,
        "stale_cached_id_outcomes": stale_outcomes,
    }


def _default_plan_slots() -> list[str]:
    # Keep the review date explicit and deterministic for the current source
    # snapshot; callers can supply another date/hour through --plan-slot.
    return [DEFAULT_PLAN_SLOT]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs-input", type=Path, default=GTFS_ARCHIVE)
    parser.add_argument("--boundary-input", type=Path, default=BOUNDARY_CACHE)
    parser.add_argument("--db-input", type=Path, default=DB_SNAPSHOT)
    parser.add_argument("--catalogue-input", type=Path, default=CATALOGUE)
    parser.add_argument("--nodes-input", type=Path, default=NODES)
    parser.add_argument("--output", type=Path, default=AUDIT_FILE)
    parser.add_argument("--plan-slot", action="append", help="DB plan date/hour, e.g. 260828/13; repeatable")
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--refresh", action="store_true", help="refresh static source caches")
    parser.add_argument("--refresh-probes", action="store_true", help="ignore cached DB station/plan probe results")
    parser.add_argument("--probe-stale-osm", action="store_true", help="query/cache bounded OSM/ORM evidence for stale IDs")
    parser.add_argument("--refresh-stale-osm", action="store_true", help="refresh the stale-ID OSM/ORM capture")
    parser.add_argument("--osm-delay", type=float, default=1.0)
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    with requests.Session() as session:
        gtfs = ensure_gtfs_archive(args.gtfs_input, session=session, refresh=args.refresh)
        boundary = ensure_boundary(args.boundary_input, session=session, refresh=args.refresh)
        if not args.db_input.is_file():
            if not (os.getenv("DB_API_TIMETABLES_CLIENTID") or os.getenv("DB_API_RISBOARDS_CLIENTID")):
                raise SystemExit(f"Missing current DB XML snapshot and DB credentials: {args.db_input}")
            response = session.get(
                DB_WILDCARD_URL,
                headers={
                    **REQUEST_HEADERS,
                    "DB-Client-ID": os.getenv("DB_API_TIMETABLES_CLIENTID") or os.getenv("DB_API_RISBOARDS_CLIENTID", ""),
                    "DB-Api-Key": os.getenv("DB_API_TIMETABLES_SECRET") or os.getenv("DB_API_RISBOARDS_CLIENTSECRET", ""),
                },
                timeout=(5.0, 120.0),
            )
            response.raise_for_status()
            _write_bytes(args.db_input, response.content)
        previous = _read_json(args.output) if args.output.is_file() else {}
        plan_slots = args.plan_slot or _default_plan_slots()
        db_probe = DbProbe(
            session=session,
            delay=args.delay,
            refresh=args.refresh_probes,
            plan_slots=plan_slots,
        )
        station_records, namespace = load_station_snapshot(args.db_input)
        generated = load_generated_identity_index(args.nodes_input)
        catalogue = load_catalogue_index(args.catalogue_input)
        stale = _stale_records(catalogue, generated, namespace)
        osm_payload = None
        if args.probe_stale_osm:
            osm_payload = fetch_stale_osm(
                stale,
                session=session,
                refresh=args.refresh_stale_osm,
                delay=args.osm_delay,
            )
        audit = reconcile(
            archive_path=gtfs,
            boundary_path=boundary,
            station_snapshot_path=args.db_input,
            catalogue_path=args.catalogue_input,
            nodes_path=args.nodes_input,
            previous_audit=previous,
            db_probe=db_probe,
            probe_stale_osm=osm_payload,
            progress=args.progress,
        )
        _write_json(args.output, audit)
    print(
        f"Germany reconciliation: {audit['counts']['candidate_records']} candidates; "
        f"{audit['counts']['candidate_statuses']}"
    )
    print(
        f"Stale cache IDs: {audit['counts']['stale_records']}; "
        f"{audit['counts']['stale_statuses']}"
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
