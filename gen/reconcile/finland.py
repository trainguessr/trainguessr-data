#!/usr/bin/env python3
"""Reconcile Fintraffic's no-current-traffic Finnish railway records.

The official station metadata is the identity source.  Infrastructure, OSM,
and live-board observations are evidence only; they do not replace the native
Fintraffic station short code.  Records without high-confidence passenger-site
evidence stay as explicit unresolved outcomes instead of being silently added
or discarded.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from common.io import ROOT, logical_path


STATIONS_ENDPOINT = "https://rata.digitraffic.fi/api/v1/metadata/stations"
INFRASTRUCTURE_ENDPOINT = (
    "https://rata.digitraffic.fi/infra-api/latest/"
    "rautatieliikennepaikat.json?count=4000"
)
HISTORICAL_INFRASTRUCTURE_ENDPOINT = (
    "https://rata.digitraffic.fi/infra-api/0.8/rautatieliikennepaikat.json"
    "?time=2010-01-01T00:00:00Z%2F2030-01-01T00:00:00Z"
    "&propertyName=tunniste,objektinVoimassaoloaika,haetunDatanVoimassaoloaika,"
    "tyyppi,nimi,lyhenne,uicKoodi,lupapaikka,raiteet,virallinenSijainti"
)
PARTS_ENDPOINT = (
    "https://rata.digitraffic.fi/infra-api/latest/"
    "liikennepaikanosat.json?count=4000"
)
PLATFORMS_ENDPOINT = (
    "https://rata.digitraffic.fi/infra-api/latest/laiturit.json?count=4000"
)
LIVE_ENDPOINT = "https://rata.digitraffic.fi/api/v1/live-trains/station/{code}"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
)

AUDIT_FILE = ROOT / "docs" / "review" / "finland-reconciliation.json"
REVIEW_FILE = ROOT / "overrides" / "finland-review.json"
CACHE_DIR = ROOT / "cache" / "finland"
HISTORICAL_CACHE_FILE = CACHE_DIR / "rautatieliikennepaikat-history.json"

REQUEST_HEADERS = {
    "Accept": "application/json",
    "Digitraffic-User": "trainguessr-data",
    "User-Agent": "trainguessr-data/finland-physical-audit",
}
LIVE_PARAMS = {
    "arrived_trains": 0,
    "arriving_trains": 1,
    "departed_trains": 0,
    "departing_trains": 1,
    "include_nonstopping": "false",
    "train_categories": "Commuter,Long-distance",
}
OSM_RADIUS_METRES = 1_000.0
OPERATIONAL_NAME_MARKERS = (
    "tavara",
    "lajittelu",
    "ratapiha",
    "väliratapiha",
    "oikoraide",
    "erkanemisvaihde",
    "vaihde",
    "raide",
    "satama",
    "saha",
    "tehdas",
    "kaivos",
    "raja",
)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _flatten_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    rows: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
        elif isinstance(value, dict):
            rows.append(value)
    return rows


def _interval_end(value: Any) -> datetime | None:
    text = str(value or "").split("/")[-1]
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _deduplicate_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("tunniste") or ""),
            str(record.get("objektinVoimassaoloaika") or ""),
            str(record.get("tyyppi") or ""),
            str(record.get("nimi") or ""),
            str(record.get("uicKoodi") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _fetch_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()


def _load_source(
    session: requests.Session,
    input_path: Path | None,
    cache_path: Path,
    endpoint: str,
    refresh: bool,
) -> tuple[Any, str]:
    if input_path is not None:
        return _read_json(input_path), logical_path(input_path)
    if cache_path.is_file() and not refresh:
        return _read_json(cache_path), logical_path(cache_path)
    payload = _fetch_json(session, endpoint)
    _write_json(cache_path, payload)
    return payload, logical_path(cache_path)


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _text_values(tags: dict[str, Any]) -> list[str]:
    return [
        str(tags.get(key) or "").strip()
        for key in (
            "name",
            "name:fi",
            "name:sv",
            "name:en",
            "official_name",
            "railway:name",
            "ref",
            "railway:ref",
            "uic_ref",
            "gtfs:id",
            "gtfs:stop_code",
            "local_ref",
            "short_name",
        )
        if str(tags.get(key) or "").strip()
    ]


def _location(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    geometry = element.get("geometry")
    if not isinstance(geometry, list):
        return None
    points = [
        (float(point["lat"]), float(point["lon"]))
        for point in geometry
        if isinstance(point, dict) and point.get("lat") is not None and point.get("lon") is not None
    ]
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    latitude = math.radians((lat1 + lat2) / 2.0)
    x = math.radians(lon2 - lon1) * math.cos(latitude)
    y = math.radians(lat2 - lat1)
    return 6_371_000.0 * math.hypot(x, y)


def _uic_matches(value: Any, uic: Any) -> bool:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits or uic in (None, ""):
        return False
    try:
        number = int(uic)
    except (TypeError, ValueError):
        return False
    accepted = {
        str(number),
        f"100{number:04d}",
        f"1{number:06d}",
        f"10{number:05d}",
    }
    return digits in accepted


def _code_matches(tags: dict[str, Any], code: str) -> bool:
    target = _normalise(code)
    return bool(target) and any(_normalise(value) == target for value in _text_values(tags))


def _name_matches(tags: dict[str, Any], name: str) -> bool:
    target = _normalise(name)
    if not target:
        return False
    return any(target == _normalise(value) for value in _text_values(tags))


def _is_passenger_osm_feature(tags: dict[str, Any]) -> bool:
    if tags.get("railway") not in {"station", "halt", "stop", "platform"}:
        return False
    if any(
        tags.get(key) in {"yes", "station", "halt", "stop", "light_rail"}
        for key in ("subway", "tram", "light_rail", "station")
    ):
        return False
    return tags.get("train") == "yes"


def _lifecycle_flags(tags: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key, value in tags.items():
        key_text = str(key).casefold()
        value_text = str(value).casefold()
        if any(marker in key_text for marker in ("demolished", "razed", "removed", "destroyed", "abandoned")):
            flags.append(f"{key}={value}")
        elif key_text in {"disused", "railway:disused"} and value_text in {"yes", "station", "halt", "stop"}:
            flags.append(f"{key}={value}")
    return sorted(set(flags))


def _osm_url(element: dict[str, Any]) -> str:
    return f"https://www.openstreetmap.org/{element.get('type', 'node')}/{element.get('id')}"


def _summarise_osm(element: dict[str, Any], distance: float | None = None) -> dict[str, Any]:
    tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
    result: dict[str, Any] = {
        "url": _osm_url(element),
        "osm_type": element.get("type"),
        "osm_id": element.get("id"),
        "railway": tags.get("railway", ""),
        "name": tags.get("name", ""),
        "railway_name": tags.get("railway:name", ""),
        "uic_ref": tags.get("uic_ref", ""),
        "ref": tags.get("ref", ""),
        "train": tags.get("train", ""),
        "operator": tags.get("operator", ""),
        "network": tags.get("network", ""),
    }
    if distance is not None:
        result["distance_m"] = round(distance, 1)
    return {key: value for key, value in result.items() if value not in ("", None, [])}


def load_osm_elements(paths: Iterable[Path]) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        payload = _read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("elements"), list):
            source_elements = payload["elements"]
        elif isinstance(payload, list):
            source_elements = payload
        else:
            raise ValueError(f"OSM input must contain an elements array: {path}")
        for element in source_elements:
            if not isinstance(element, dict):
                continue
            key = (str(element.get("type", "")), str(element.get("id", "")))
            if key in seen:
                continue
            seen.add(key)
            elements.append(element)
    return elements


def _infrastructure_summary(record: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "record_id": record.get("tunniste", ""),
        "record_type": record.get("tyyppi") or (
            "liikennepaikanosa" if source == "liikennepaikanosat" else ""
        ),
        "name": record.get("nimi", ""),
        "abbreviation": record.get("lyhenne", ""),
        "uic": record.get("uicKoodi"),
        "parent_id": record.get("liikennepaikka", ""),
        "permission_place": record.get("lupapaikka"),
        "validity": record.get("objektinVoimassaoloaika", ""),
        "data_validity": record.get("haetunDatanVoimassaoloaika", ""),
        "track_count": len(record.get("raiteet") or []),
        "track_ids": list(record.get("raiteet") or []),
    }


def _platform_summary(platform: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": platform.get("tunniste", ""),
        "validity": platform.get("objektinVoimassaoloaika", ""),
        "identifier": platform.get("tunnus", ""),
        "description": platform.get("kuvaus", ""),
        "commercial_number": platform.get("kaupallinenNumero", ""),
        "parent_place": platform.get("rautatieliikennepaikka", ""),
        "parent_part": platform.get("liikennepaikanosa") or platform.get("liikennepaikanOsa", ""),
        "track_ids": list(platform.get("raiteet") or []),
    }


def build_infrastructure_index(
    infrastructure_payload: Any,
    parts_payload: Any,
    platforms_payload: Any,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_uic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in _flatten_records(infrastructure_payload):
        if record.get("uicKoodi") not in (None, ""):
            by_uic[str(record["uicKoodi"])].append(
                _infrastructure_summary(record, "rautatieliikennepaikat")
            )
    for record in _flatten_records(parts_payload):
        if record.get("uicKoodi") not in (None, ""):
            by_uic[str(record["uicKoodi"])].append(
                _infrastructure_summary(record, "liikennepaikanosat")
            )

    platforms_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for platform in _flatten_records(platforms_payload):
        if str(platform.get("tyyppi") or "").casefold() != "henkilo":
            continue
        for key in (
            "rautatieliikennepaikka",
            "liikennepaikka",
            "rautatieliikennepaikanosa",
            "liikennepaikanosa",
            "liikennepaikanOsa",
        ):
            parent = str(platform.get(key) or "")
            if parent:
                platforms_by_parent[parent].append(platform)

    for records in by_uic.values():
        for record in records:
            record_id = str(record.get("record_id") or "")
            platform_rows = platforms_by_parent.get(record_id, [])
            record["person_platforms"] = [
                _platform_summary(platform) for platform in platform_rows
            ]
            record["person_platform_count"] = len(platform_rows)
    return by_uic, platforms_by_parent


def _candidate_osm_evidence(
    candidate: dict[str, Any],
    elements: list[dict[str, Any]],
) -> dict[str, Any]:
    nearby: list[dict[str, Any]] = []
    identity: list[dict[str, Any]] = []
    strong: list[dict[str, Any]] = []
    lifecycle: list[dict[str, Any]] = []
    lifecycle_identity: list[dict[str, Any]] = []
    candidate_lat = float(candidate["latitude"])
    candidate_lon = float(candidate["longitude"])
    for element in elements:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        if tags.get("railway") not in {"station", "halt", "stop", "platform"}:
            continue
        location = _location(element)
        distance = None
        if location is not None:
            distance = _distance_m(candidate_lat, candidate_lon, location[0], location[1])
        uic_match = _uic_matches(tags.get("uic_ref"), candidate.get("stationUICCode"))
        code_match = _code_matches(tags, str(candidate.get("stationShortCode") or ""))
        name_match = _name_matches(tags, str(candidate.get("stationName") or ""))
        passenger = _is_passenger_osm_feature(tags)
        nearby_match = distance is not None and distance <= OSM_RADIUS_METRES
        identity_match = (
            (uic_match and (distance is None or distance <= 2_000.0))
            or (code_match and (distance is None or distance <= 500.0))
            or (name_match and (distance is None or distance <= 500.0))
        )
        if not nearby_match and not identity_match:
            continue
        summary = _summarise_osm(element, distance)
        summary["uic_match"] = uic_match
        summary["code_match"] = code_match
        summary["name_match"] = name_match
        summary["passenger_feature"] = passenger
        summary["identity_match"] = [
            field
            for field, matched in (
                ("uic_ref", uic_match),
                ("station_short_code", code_match),
                ("name", name_match),
            )
            if matched
        ]
        if nearby_match:
            nearby.append(summary)
        if identity_match:
            identity.append(summary)
        flags = _lifecycle_flags(tags)
        if flags and (nearby_match or identity_match):
            summary["lifecycle_flags"] = flags
            lifecycle.append(summary)
            if identity_match:
                lifecycle_identity.append(summary)
        # A nearby native identity match is required before OSM can promote a
        # candidate. A UIC match may be slightly farther away because the
        # provider point can represent a traffic place rather than a platform.
        strong_uic_match = uic_match and (distance is None or distance <= 2_000.0)
        strong_local_match = (code_match or name_match) and (
            distance is None or distance <= 500.0
        )
        if passenger and (strong_uic_match or strong_local_match):
            strong.append(summary)
    nearby.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    identity.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    strong.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    lifecycle.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    lifecycle_identity.sort(key=lambda row: (row.get("distance_m", OSM_RADIUS_METRES + 1), str(row.get("osm_id"))))
    return {
        "nearby_features": nearby[:12],
        "identity_features": identity[:12],
        "strong_passenger_features": strong[:8],
        "lifecycle_features": lifecycle[:8],
        "lifecycle_identity_features": lifecycle_identity[:8],
        "nearby_count": len(nearby),
        "identity_count": len(identity),
        "strong_passenger_count": len(strong),
        "lifecycle_identity_count": len(lifecycle_identity),
    }


def _passenger_event_count(payload: Any, code: str) -> int:
    if not isinstance(payload, list):
        return 0
    count = 0
    for train in payload:
        if not isinstance(train, dict):
            continue
        for row in train.get("timeTableRows", []):
            if not isinstance(row, dict) or row.get("stationShortCode") != code:
                continue
            if row.get("type") not in {"ARRIVAL", "DEPARTURE"}:
                continue
            if row.get("trainStopping") is False or row.get("commercialStop") is False:
                continue
            count += 1
    return count


def load_live_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def probe_live_board(
    session: requests.Session,
    code: str,
    cache: dict[str, dict[str, Any]],
    cache_path: Path,
    refresh: bool,
    delay: float,
) -> dict[str, Any]:
    if code in cache and not refresh:
        return cache[code]
    result: dict[str, Any] = {
        "endpoint": LIVE_ENDPOINT.format(code=code),
        "queried_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    try:
        response = session.get(
            LIVE_ENDPOINT.format(code=code),
            params=LIVE_PARAMS,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        result["http_status"] = response.status_code
        if response.status_code == 200:
            payload = response.json()
            result["response_type"] = type(payload).__name__
            result["train_count"] = len(payload) if isinstance(payload, list) else 0
            result["passenger_event_count"] = _passenger_event_count(payload, code)
        else:
            result["error"] = response.text[:240]
    except (requests.RequestException, ValueError) as exc:
        result["http_status"] = None
        result["error"] = f"{type(exc).__name__}: {exc}"
    cache[code] = result
    _write_json(cache_path, cache)
    if delay > 0:
        time.sleep(delay)
    return result


def _grid_bboxes(bbox: tuple[float, float, float, float], divisions: int) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    divisions = max(1, divisions)
    rows: list[tuple[float, float, float, float]] = []
    for row in range(divisions):
        cell_south = south + (north - south) * row / divisions
        cell_north = south + (north - south) * (row + 1) / divisions
        for column in range(divisions):
            cell_west = west + (east - west) * column / divisions
            cell_east = west + (east - west) * (column + 1) / divisions
            rows.append((cell_south, cell_west, cell_north, cell_east))
    return rows


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    return (
        "[out:json][timeout:180];"
        f"(nwr[\"railway\"~\"^(station|halt|stop|platform)$\"]"
        f"({south},{west},{north},{east}););out center tags;"
    )


def fetch_overpass_batches(
    session: requests.Session,
    bbox: tuple[float, float, float, float],
    divisions: int,
    delay: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    elements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    endpoint_index = 0
    for index, cell in enumerate(_grid_bboxes(bbox, divisions)):
        query = _overpass_query(cell)
        success = False
        for attempt in range(len(OVERPASS_ENDPOINTS)):
            endpoint = OVERPASS_ENDPOINTS[(endpoint_index + attempt) % len(OVERPASS_ENDPOINTS)]
            try:
                response = session.post(endpoint, data=query, timeout=240)
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
                endpoint_index = (endpoint_index + attempt + 1) % len(OVERPASS_ENDPOINTS)
                success = True
                break
            except (requests.RequestException, ValueError) as exc:
                errors.append({
                    "cell": index,
                    "endpoint": endpoint,
                    "attempt": attempt + 1,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                time.sleep(min(30.0, 2.0 * (attempt + 1)))
        if not success:
            continue
        if delay > 0:
            time.sleep(delay)
    return elements, errors


def _load_existing_review(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("Finland review data must be an object")
    rows = payload.get("reviewed_extant_no_service", [])
    if not isinstance(rows, list):
        raise ValueError("Finland reviewed stations must be an array")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("stationShortCode") or "").strip()
        if code:
            result[code] = row
    return result


def _candidate_rows(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in stations
            if row.get("countryCode") == "FI"
            and row.get("type") in {"STATION", "STOPPING_POINT"}
            and not row.get("passengerTraffic")
        ],
        key=lambda row: str(row.get("stationShortCode") or ""),
    )


def _evidence_urls(osm: dict[str, Any]) -> list[str]:
    return [str(row["url"]) for row in osm.get("strong_passenger_features", []) if row.get("url")]


def _expired_historical_infrastructure(
    payload: Any,
    as_of: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    as_of = as_of or datetime.now(timezone.utc)
    by_uic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in _deduplicate_records(_flatten_records(payload)):
        uic = record.get("uicKoodi")
        ended_at = _interval_end(record.get("objektinVoimassaoloaika"))
        if uic in (None, "") or ended_at is None or ended_at >= as_of:
            continue
        summary = _infrastructure_summary(record, "rautatieliikennepaikat_history")
        summary["ended_at"] = record.get("objektinVoimassaoloaika", "").split("/")[-1]
        by_uic[str(uic)].append(summary)
    return by_uic


def _operational_name_markers(name: Any) -> list[str]:
    normalised = _normalise(name)
    return [
        marker
        for marker in OPERATIONAL_NAME_MARKERS
        if re.search(rf"(?:^| ){re.escape(_normalise(marker))}(?: |$)", normalised)
    ]


def _operational_signals(
    candidate: dict[str, Any],
    infrastructure: list[dict[str, Any]],
    osm: dict[str, Any],
) -> list[str]:
    signals: list[str] = []
    markers = _operational_name_markers(candidate.get("stationName"))
    if markers:
        signals.append(f"official_name_markers:{','.join(markers)}")

    record_types = {str(row.get("record_type") or "") for row in infrastructure}
    if record_types & {"liikennepaikanosa", "linjavaihde"} and not any(
        row.get("person_platform_count", 0) for row in infrastructure
    ):
        signals.append("official_station_part_without_exact_person_platform")

    current_places = [row for row in infrastructure if row.get("record_type") == "liikennepaikka"]
    if (
        current_places
        and all(row.get("permission_place") is not True for row in current_places)
        and not any(row.get("person_platform_count", 0) for row in infrastructure)
        and not osm.get("strong_passenger_count", 0)
    ):
        signals.append("official_liikennepaikka_without_passenger_facility")
    return signals


def _former_passenger_signals(
    infrastructure: list[dict[str, Any]],
    historical_infrastructure: list[dict[str, Any]],
) -> list[str]:
    signals: list[str] = []
    if any(row.get("permission_place") is True for row in infrastructure):
        signals.append("official_permission_place")
    historical_stations = [
        row for row in historical_infrastructure
        if row.get("record_type") in {"liikennepaikka", "seisake"}
    ]
    if historical_stations:
        signals.append("ended_official_station_or_stop_record")
    return signals


def _cohort_for_outcome(
    status: str,
    candidate: dict[str, Any],
    infrastructure: list[dict[str, Any]],
    historical_infrastructure: list[dict[str, Any]],
    operational_signals: list[str],
) -> str:
    if status == "added_existing_provider":
        return "retained_extant_passenger_site"
    if status == "dismantled_exclusion":
        return "explicit_lifecycle_exclusion"
    if status == "not_passenger_station":
        if _operational_name_markers(candidate.get("stationName")):
            return "official_operational_name"
        if any(row.get("record_type") == "liikennepaikanosa" for row in infrastructure):
            return "official_station_part_without_passenger_platform"
        return "official_liikennepaikka_without_passenger_facility"
    if historical_infrastructure:
        return "possible_former_passenger_historical"
    if any(row.get("permission_place") is True for row in infrastructure):
        return "possible_former_passenger_permission_place"
    if candidate.get("type") == "STOPPING_POINT":
        return "stopping_point_manual_review"
    if operational_signals:
        return "manual_review_with_operational_signals"
    return "manual_physical_review"


def reconcile(
    stations: list[dict[str, Any]],
    infrastructure_payload: Any,
    parts_payload: Any,
    platforms_payload: Any,
    osm_elements: list[dict[str, Any]],
    existing_review: dict[str, dict[str, Any]],
    live_by_code: dict[str, dict[str, Any]] | None = None,
    historical_infrastructure_payload: Any = None,
) -> dict[str, Any]:
    by_uic, _ = build_infrastructure_index(infrastructure_payload, parts_payload, platforms_payload)
    live_by_code = live_by_code or {}
    historical_by_uic = _expired_historical_infrastructure(historical_infrastructure_payload)
    outcomes: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for candidate in _candidate_rows(stations):
        code = str(candidate.get("stationShortCode") or "").strip()
        uic = str(candidate.get("stationUICCode") or "")
        infrastructure = by_uic.get(uic, [])
        historical_infrastructure = historical_by_uic.get(uic, [])
        osm = _candidate_osm_evidence(candidate, osm_elements)
        live = live_by_code.get(code)
        operational_signals = _operational_signals(candidate, infrastructure, osm)
        former_signals = _former_passenger_signals(infrastructure, historical_infrastructure)
        classification_signals = {
            "metadata_passenger_traffic": bool(candidate.get("passengerTraffic")),
            "metadata_type": candidate.get("type", ""),
            "official_record_types": sorted({
                str(row.get("record_type") or "") for row in infrastructure
            }),
            "exact_person_platform_count": sum(
                int(row.get("person_platform_count", 0) or 0) for row in infrastructure
            ),
            "operational_signals": operational_signals,
            "former_passenger_signals": former_signals,
            "osm_nearby_count": osm.get("nearby_count", 0),
            "osm_identity_count": osm.get("identity_count", 0),
            "osm_strong_passenger_count": osm.get("strong_passenger_count", 0),
            "osm_lifecycle_identity_count": osm.get("lifecycle_identity_count", 0),
            "historical_infrastructure_count": len(historical_infrastructure),
        }
        if code in existing_review:
            status = "added_existing_provider"
            confidence = "high"
            decision_source = "existing_review"
            reason = "Previously reviewed physical passenger-site evidence is kept."
        elif live and live.get("http_status") == 200 and live.get("passenger_event_count", 0) > 0:
            status = "added_existing_provider"
            confidence = "high"
            decision_source = "digitraffic_live_passenger_event"
            reason = "The native Fintraffic code returned a commercial passenger stop event."
        elif any(row.get("person_platform_count", 0) for row in infrastructure):
            status = "added_existing_provider"
            confidence = "high"
            decision_source = "official_person_platform"
            reason = "The exact official infrastructure record has a current person platform."
        elif osm.get("strong_passenger_count", 0):
            status = "added_existing_provider"
            confidence = "high"
            decision_source = "osm_native_identity_match"
            reason = "OSM contains a nearby train passenger feature matching the native code, UIC, or name."
        elif osm.get("lifecycle_identity_count", 0):
            status = "dismantled_exclusion"
            confidence = "high"
            decision_source = "osm_lifecycle_identity_match"
            reason = "A native-identity OSM railway feature carries an explicit lifecycle/discontinuation tag."
        elif operational_signals:
            status = "not_passenger_station"
            confidence = "medium"
            decision_source = "official_operational_infrastructure"
            reason = (
                "Current Fintraffic metadata reports no passenger traffic, and the exact official "
                "infrastructure/name evidence identifies an operational railway point without a "
                "current person platform or matching passenger feature; this is not a claim about "
                "all historical passenger service."
            )
        elif live and live.get("http_status") not in (None, 200):
            status = "provider_verification_blocked_live_board"
            confidence = "insufficient"
            decision_source = "provider_error"
            reason = "The official native board request failed; available evidence does not safely distinguish the physical status."
        elif not infrastructure:
            status = "unresolved"
            confidence = "insufficient"
            decision_source = "official_identity_only"
            reason = "Official station identity exists, but no matching current infrastructure or independent physical evidence was found in the supplied sources."
        elif former_signals:
            status = "unresolved"
            confidence = "insufficient"
            decision_source = "possible_former_passenger_site"
            reason = (
                "Official infrastructure signals a possible former passenger site, but the supplied "
                "current person-platform, historical, and physical evidence does not show "
                "whether a playable passenger facility still exists."
            )
        else:
            status = "unresolved"
            confidence = "insufficient"
            decision_source = "evidence_inconclusive"
            reason = "The official infrastructure register confirms a railway identity, but supplied evidence does not distinguish extant passenger access, dismantlement, or an operational-only point."

        infrastructure_evidence = {
            "matched": bool(infrastructure),
            "records": infrastructure,
            "source_url": INFRASTRUCTURE_ENDPOINT,
        }
        evidence: dict[str, Any] = {
            "metadata": {
                "source_url": STATIONS_ENDPOINT,
                "passengerTraffic": bool(candidate.get("passengerTraffic")),
                "station_type": candidate.get("type"),
            },
            "infrastructure": infrastructure_evidence,
            "historical_infrastructure": {
                "matched": bool(historical_infrastructure),
                "records": historical_infrastructure,
                "source_url": HISTORICAL_INFRASTRUCTURE_ENDPOINT,
            },
            "osm": osm,
        }
        if live is not None:
            evidence["live_board"] = live
        outcome = {
            "stationShortCode": code,
            "stationName": candidate.get("stationName", ""),
            "stationUICCode": candidate.get("stationUICCode"),
            "type": candidate.get("type", ""),
            "latitude": candidate.get("latitude"),
            "longitude": candidate.get("longitude"),
            "status": status,
            "confidence": confidence,
            "decision_source": decision_source,
            "reason": reason,
            "cohort": _cohort_for_outcome(
                status,
                candidate,
                infrastructure,
                historical_infrastructure,
                operational_signals,
            ),
            "classification_signals": classification_signals,
            "evidence": evidence,
        }
        if code in existing_review:
            outcome["review"] = existing_review[code]
        outcomes.append(outcome)
        if status == "added_existing_provider":
            review = dict(existing_review.get(code, {}))
            review.setdefault("stationShortCode", code)
            review.setdefault("stationName", candidate.get("stationName", ""))
            review.setdefault("stationUICCode", candidate.get("stationUICCode"))
            review.setdefault("type", candidate.get("type", ""))
            review.setdefault("infrastructure_record", bool(infrastructure))
            if "physical_evidence" not in review:
                review["physical_evidence"] = _evidence_urls(osm)
            review.setdefault("provider_verification", decision_source)
            review.setdefault("status", status)
            retained.append(review)

    counts = Counter(row["status"] for row in outcomes)
    cohorts = Counter(row["cohort"] for row in outcomes)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "reconciled_with_explicit_unresolved",
        "source_urls": {
            "metadata": STATIONS_ENDPOINT,
            "infrastructure": INFRASTRUCTURE_ENDPOINT,
            "historical_infrastructure": HISTORICAL_INFRASTRUCTURE_ENDPOINT,
            "parts": PARTS_ENDPOINT,
            "platforms": PLATFORMS_ENDPOINT,
            "live_board": LIVE_ENDPOINT,
        },
        "counts": {
            "official_metadata_records": len(stations),
            "finnish_metadata_records": sum(row.get("countryCode") == "FI" for row in stations),
            "candidate_records": len(outcomes),
            "candidate_statuses": dict(sorted(counts.items())),
            "candidate_cohorts": dict(sorted(cohorts.items())),
            "candidate_types": dict(sorted(Counter(row.get("type", "") for row in outcomes).items())),
            "infrastructure_records": len(_flatten_records(infrastructure_payload)),
            "infrastructure_types": dict(sorted(Counter(
                row.get("tyyppi", "") for row in _flatten_records(infrastructure_payload)
            ).items())),
            "historical_infrastructure_records": sum(len(rows) for rows in historical_by_uic.values()),
            "infrastructure_part_records": len(_flatten_records(parts_payload)),
            "person_platform_records": sum(
                str(row.get("tyyppi") or "").casefold() == "henkilo"
                for row in _flatten_records(platforms_payload)
            ),
            "osm_elements": len(osm_elements),
            "retained_extant_no_service": len(retained),
        },
        "retained_extant_no_service": sorted(
            retained, key=lambda row: str(row.get("stationShortCode") or "")
        ),
        "outcomes": outcomes,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations-input", type=Path, help="saved Fintraffic metadata response")
    parser.add_argument("--infrastructure-input", type=Path, help="saved infrastructure response")
    parser.add_argument("--historical-infrastructure-input", type=Path, help="saved versioned infrastructure response")
    parser.add_argument("--parts-input", type=Path, help="saved station-parts response")
    parser.add_argument("--platforms-input", type=Path, help="saved platform response")
    parser.add_argument("--osm-input", type=Path, action="append", default=[], help="saved OSM/Overpass response; repeatable")
    parser.add_argument("--probe-live", action="store_true", help="probe each native station code")
    parser.add_argument("--refresh", action="store_true", help="refresh official source caches")
    parser.add_argument("--refresh-history", action="store_true", help="refresh the versioned infrastructure cache")
    parser.add_argument("--refresh-live", action="store_true", help="ignore cached live-board statuses")
    parser.add_argument("--live-delay", type=float, default=0.15)
    parser.add_argument("--overpass-bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"), help="query this bbox in split/retried Overpass batches")
    parser.add_argument("--overpass-divisions", type=int, default=4)
    parser.add_argument("--overpass-delay", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=AUDIT_FILE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    session = requests.Session()
    stations_payload, stations_source = _load_source(
        session, args.stations_input, CACHE_DIR / "stations.json", STATIONS_ENDPOINT, args.refresh
    )
    infrastructure_payload, infrastructure_source = _load_source(
        session,
        args.infrastructure_input,
        CACHE_DIR / "rautatieliikennepaikat.json",
        INFRASTRUCTURE_ENDPOINT,
        args.refresh,
    )
    historical_infrastructure_payload, historical_infrastructure_source = _load_source(
        session,
        args.historical_infrastructure_input,
        HISTORICAL_CACHE_FILE,
        HISTORICAL_INFRASTRUCTURE_ENDPOINT,
        args.refresh or args.refresh_history,
    )
    parts_payload, parts_source = _load_source(
        session, args.parts_input, CACHE_DIR / "liikennepaikanosat.json", PARTS_ENDPOINT, args.refresh
    )
    platforms_payload, platforms_source = _load_source(
        session, args.platforms_input, CACHE_DIR / "laiturit.json", PLATFORMS_ENDPOINT, args.refresh
    )
    stations = stations_payload if isinstance(stations_payload, list) else []
    if not stations:
        raise ValueError("Fintraffic station metadata must be a non-empty array")

    osm_paths = list(args.osm_input)
    overpass_errors: list[dict[str, Any]] = []
    if args.overpass_bbox:
        overpass_elements, overpass_errors = fetch_overpass_batches(
            session,
            tuple(args.overpass_bbox),
            args.overpass_divisions,
            args.overpass_delay,
        )
        overpass_path = CACHE_DIR / "osm-overpass-latest.json"
        _write_json(overpass_path, {"elements": overpass_elements})
        osm_paths.append(overpass_path)
    osm_elements = load_osm_elements(osm_paths) if osm_paths else []

    live_cache_path = CACHE_DIR / "live-board-status.json"
    live_cache = load_live_cache(live_cache_path)
    live_by_code: dict[str, dict[str, Any]] = {}
    candidates = _candidate_rows(stations)
    if args.probe_live:
        for index, candidate in enumerate(candidates, 1):
            code = str(candidate.get("stationShortCode") or "").strip()
            live_by_code[code] = probe_live_board(
                session, code, live_cache, live_cache_path, args.refresh_live, args.live_delay
            )
            if index % 25 == 0:
                print(f"Probed {index}/{len(candidates)} Finland native station boards")
    else:
        live_by_code = {code: live_cache[code] for code in (str(row.get("stationShortCode") or "") for row in candidates) if code in live_cache}

    existing_review = _load_existing_review(REVIEW_FILE)
    audit = reconcile(
        stations,
        infrastructure_payload,
        parts_payload,
        platforms_payload,
        osm_elements,
        existing_review,
        live_by_code,
        historical_infrastructure_payload,
    )
    audit["source_files"] = {
        "metadata": stations_source,
        "infrastructure": infrastructure_source,
        "historical_infrastructure": historical_infrastructure_source,
        "parts": parts_source,
        "platforms": platforms_source,
        "osm": [logical_path(path) for path in osm_paths],
    }
    audit["overpass_errors"] = overpass_errors
    _write_json(args.output, audit)
    print(
        f"Finland reconciliation: {audit['counts']['candidate_records']} candidates; "
        f"{audit['counts']['candidate_statuses']}"
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
