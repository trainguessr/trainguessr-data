"""Stale catalogue evidence and conservative classification for Germany."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable
import requests
from reconcile.germany.io import _read_json, _write_json
from reconcile.germany.matching import _normalise, distance_m
from reconcile.germany.settings import (
    LIFECYCLE_MARKERS,
    OSM_BATCH_SIZE,
    OSM_ENDPOINTS,
    OSM_RADIUS_METRES,
    OSM_REQUEST_TIMEOUT,
    STALE_OSM_CACHE,
)


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
