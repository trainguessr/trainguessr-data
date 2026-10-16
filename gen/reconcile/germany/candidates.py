"""Passenger candidate classification for Germany."""
from __future__ import annotations

import csv
import io
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from reconcile.germany.matching import _float_pair


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
