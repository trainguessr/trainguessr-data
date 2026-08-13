#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import io
import json
import logging as log
import math
import re
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

import requests

from common.config import load_rename_map
from common.io import load_ndjson, write_ndjson


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
AUSTRIA_CACHE = CACHE_DIR / "austria"
GEONETZ_URL = "https://data.oebb.at/dam/jcr:d4780bb2-390e-4288-b540-dff1ae1b27ae/GeoNetz_12-2024.zip"
MVO_WFS_URL = "https://wfs.arge-oevv.at/geoserver/pub/ows"
SCOTTY_STOP_URL = "https://fahrplan.oebb.at/bin/ajax-getstop.exe/dn"
DEFAULT_OUTPUT = ROOT / "nodes" / "nodes-austria-oebb.json"
DEFAULT_AUDIT = AUSTRIA_CACHE / "migration-audit.json"
DEFAULT_RESOLUTION_CACHE = AUSTRIA_CACHE / "scotty-resolutions.json"

_RAIL_MASK_POSITIONS = (0, 1)  # Eisenbahn, S-Bahn
_IFOPT_RE = re.compile(r"^at[-:]([0-9]+)[-:]([0-9]+)$", re.I)
_EVA_RE = re.compile(r"@L=0*([0-9]+)@")
_SUGGESTION_RE = re.compile(
    r"(?:SLs\.)?sls\s*=\s*(\{.*?\})\s*;\s*(?:SLs\.)?showSuggestion",
    re.S,
)


def _float(value: Any) -> float:
    return float(str(value).strip().replace(",", "."))


def _normal_name(value: str) -> str:
    value = value.casefold().replace("ß", "ss")
    value = re.sub(r"\bbahnhof\b", " ", value)
    value = re.sub(r"[^a-z0-9äöü]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_ifopt(value: Any) -> str:
    value = str(value or "").strip().casefold()
    match = _IFOPT_RE.fullmatch(value)
    if match:
        return f"at:{int(match.group(1))}:{int(match.group(2))}"
    return value


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _download_geonetz(session: requests.Session, timeout: int = 60) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filtered = CACHE_DIR / "austria_stations_filtered.json"
    if filtered.is_file():
        return filtered

    response = session.get(GEONETZ_URL, timeout=timeout)
    response.raise_for_status()
    archive = CACHE_DIR / "GeoNetz_12-2024.zip"
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive) as outer:
        outer.extractall(CACHE_DIR)
    inner_path = CACHE_DIR / "GeoNetz_12-2024" / "OEBB_NETWORK_GeoJSON.zip"
    with zipfile.ZipFile(inner_path) as inner:
        inner.extractall(CACHE_DIR)

    geojson_path = CACHE_DIR / "OEBB_NETWORK.json"
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    with filtered.open("w", encoding="utf-8", newline="\n") as handle:
        for feature in payload.get("features", []):
            properties = feature.get("properties", {})
            if "railStation" in str(properties.get("STP_TYPE", "")):
                handle.write(json.dumps(properties, ensure_ascii=False) + "\n")
    return filtered


def load_geonetz_nodes(path: Path, rename_map: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            feature = json.loads(line)
            eva = feature.get("EVA_NR")
            name = feature.get("STP_NAME", "")
            lat = feature.get("STP_LAT")
            lon = feature.get("STP_LON")
            if not eva or not name or not lat or not lon:
                continue
            name = rename_map.get(name, name)
            rows.append({
                "type": "node",
                "id": int(eva),
                "lat": _float(lat),
                "lon": _float(lon),
                "tags": {
                    "name": name,
                    "stp_id": feature.get("STP_ID", ""),
                    "ifopt_id": feature.get("IFOPT_ID", ""),
                    "stp_type": feature.get("STP_TYPE", ""),
                    "stp_short": feature.get("STP_SHORT", ""),
                    "bsts_id": feature.get("BSTS_ID", ""),
                    "plc": feature.get("PLC", ""),
                },
                "category": "austria_oebb",
            })
    return rows


def _open_mvo_csv(path: Path) -> io.TextIOBase:
    if zipfile.is_zipfile(path):
        archive = zipfile.ZipFile(path)
        members = [name for name in archive.namelist() if Path(name).name.casefold() == "haltestellen.csv"]
        if not members:
            archive.close()
            raise ValueError(f"{path}: haltestellen.csv not found")
        raw = archive.open(members[0])
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        original_close = text.close

        def close() -> None:
            original_close()
            archive.close()

        text.close = close  # type: ignore[method-assign]
        return text
    return path.open(encoding="utf-8-sig", newline="")


def load_mvo_csv(path: Path) -> list[dict[str, Any]]:
    handle = _open_mvo_csv(path)
    try:
        sample = handle.read(8192)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        return [dict(row) for row in csv.DictReader(handle, dialect=dialect)]
    finally:
        handle.close()


def validate_mvo_wgs84(rows: Iterable[dict[str, Any]]) -> None:
    coordinates: list[tuple[float, float]] = []
    for row in rows:
        try:
            lon = _float(row.get("hst_x"))
            lat = _float(row.get("hst_y"))
        except (TypeError, ValueError):
            continue
        coordinates.append((lon, lat))
    if not coordinates:
        raise ValueError("MVO input contains no numeric stop coordinates")
    plausible = sum(1 for lon, lat in coordinates if 8.0 <= lon <= 18.0 and 45.0 <= lat <= 50.0)
    if plausible / len(coordinates) < 0.5:
        raise ValueError(
            "MVO CSV/ZIP coordinates do not appear to be WGS84 longitude/latitude; "
            "use the live WFS or a WGS84 export"
        )


def _feature_type_from_capabilities(xml_text: str) -> str:
    root = ElementTree.fromstring(xml_text)
    candidates: list[tuple[int, str]] = []
    for feature in root.iter():
        if not feature.tag.endswith("FeatureType"):
            continue
        name = ""
        title = ""
        for child in feature:
            if child.tag.endswith("Name"):
                name = (child.text or "").strip()
            elif child.tag.endswith("Title"):
                title = (child.text or "").strip()
        if not name:
            continue
        haystack = f"{name} {title}".casefold()
        score = 2 if "haltestellen" in haystack else 1 if "haltest" in haystack else 0
        if score:
            candidates.append((score, name))
    if not candidates:
        raise ValueError("MVO WFS exposes no Haltestellen feature type")
    return sorted(candidates, reverse=True)[0][1]


def download_mvo_wfs(session: requests.Session, timeout: int = 60) -> list[dict[str, Any]]:
    AUSTRIA_CACHE.mkdir(parents=True, exist_ok=True)
    response = session.get(
        MVO_WFS_URL,
        params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
        timeout=timeout,
    )
    response.raise_for_status()
    feature_type = _feature_type_from_capabilities(response.text)

    page_size = 20_000
    start_index = 0
    all_features: list[dict[str, Any]] = []
    matched_total: int | None = None
    while True:
        response = session.get(
            MVO_WFS_URL,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": feature_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": page_size,
                "startIndex": start_index,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("MVO WFS did not return a GeoJSON feature list")
        page = [feature for feature in features if isinstance(feature, dict)]
        all_features.extend(page)

        if matched_total is None:
            try:
                matched_total = int(payload.get("numberMatched"))
            except (TypeError, ValueError):
                matched_total = None
        start_index += len(features)
        if not features or (matched_total is not None and start_index >= matched_total):
            break
        if len(features) < page_size and matched_total is None:
            break

    cache_payload = {
        "type": "FeatureCollection",
        "numberMatched": matched_total if matched_total is not None else len(all_features),
        "numberReturned": len(all_features),
        "features": all_features,
    }
    cache_path = AUSTRIA_CACHE / "mvo-haltestellen-wfs.json"
    cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False), encoding="utf-8")

    rows: list[dict[str, Any]] = []
    for feature in all_features:
        properties = dict(feature.get("properties") or {})
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            # GetFeature is explicitly requested in EPSG:4326, so use its
            # transformed geometry even if source-coordinate attributes exist.
            properties["hst_x"] = coordinates[0]
            properties["hst_y"] = coordinates[1]
        rows.append(properties)
    return rows


def _rail_mask(value: Any) -> bool:
    mask = re.sub(r"\s+", "", str(value or ""))
    return len(mask) >= 2 and all(char in "01" for char in mask) and any(mask[pos] == "1" for pos in _RAIL_MASK_POSITIONS)


def mvo_rail_candidates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        ifopt = normalize_ifopt(row.get("hst_globid"))
        name = str(row.get("hst_name") or "").strip()
        if not ifopt.startswith("at:") or not name or not _rail_mask(row.get("umst_agg_vm")):
            continue
        try:
            lon = _float(row.get("hst_x"))
            lat = _float(row.get("hst_y"))
        except (TypeError, ValueError):
            continue
        if not (45.0 <= lat <= 50.0 and 8.0 <= lon <= 18.0):
            continue
        item = dict(row)
        item["hst_globid"] = ifopt
        item["hst_x"] = lon
        item["hst_y"] = lat
        result.append(item)
    return result


def parse_scotty_suggestions(text: str) -> list[dict[str, Any]]:
    match = _SUGGESTION_RE.search(text)
    if not match:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("SCOTTY stop response has no suggestion object")
        raw = text[start:end + 1]
    else:
        raw = match.group(1)
    payload = json.loads(raw)
    suggestions = payload.get("suggestions") if isinstance(payload, dict) else None
    if not isinstance(suggestions, list):
        raise ValueError("SCOTTY stop response has no suggestions list")
    return [row for row in suggestions if isinstance(row, dict)]


def _suggestion_coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lon = _float(row.get("xcoord"))
        lat = _float(row.get("ycoord"))
    except (TypeError, ValueError):
        return None
    if abs(lon) > 180:
        lon /= 1_000_000
    if abs(lat) > 90:
        lat /= 1_000_000
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lat, lon


def select_scotty_suggestion(
    suggestions: Iterable[dict[str, Any]],
    *,
    name: str,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    wanted = _normal_name(name)
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for row in suggestions:
        if str(row.get("type", "1")) not in {"1", "station", "stop"}:
            continue
        match = _EVA_RE.search(str(row.get("id") or ""))
        coords = _suggestion_coordinates(row)
        candidate_name = str(row.get("value") or row.get("name") or "").strip()
        if not match or not coords or not candidate_name:
            continue
        distance = _haversine_m(lat, lon, *coords)
        similarity = SequenceMatcher(None, wanted, _normal_name(candidate_name)).ratio()
        if wanted == _normal_name(candidate_name):
            similarity = 1.0
        if distance > 2_000 or similarity < 0.72:
            continue
        ranked.append((similarity, distance, {
            "eva_id": int(match.group(1)),
            "name": candidate_name,
            "lat": coords[0],
            "lon": coords[1],
            "distance_m": round(distance, 1),
            "similarity": round(similarity, 4),
        }))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    best_similarity, best_distance, best = ranked[0]
    if best_similarity < 0.86 and best_distance > 750:
        return None
    if len(ranked) > 1:
        second_similarity, second_distance, _ = ranked[1]
        if abs(best_similarity - second_similarity) < 0.03 and abs(best_distance - second_distance) < 250:
            return None
    return best


class ScottyResolver:
    def __init__(
        self,
        session: requests.Session,
        cache_path: Path = DEFAULT_RESOLUTION_CACHE,
        *,
        offline: bool = False,
        timeout: int = 20,
    ) -> None:
        self.session = session
        self.cache_path = cache_path
        self.offline = offline
        self.timeout = timeout
        self.cache: dict[str, Any] = {}
        if cache_path.is_file():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self.cache = dict(payload.get("entries") or {})
            except (OSError, ValueError):
                self.cache = {}

    def resolve(self, row: dict[str, Any]) -> dict[str, Any] | None:
        key = normalize_ifopt(row.get("hst_globid"))
        cached = self.cache.get(key)
        if isinstance(cached, dict):
            return cached if cached.get("eva_id") else None
        if self.offline:
            return None
        name = str(row.get("hst_name") or "").strip()
        try:
            response = self.session.get(
                SCOTTY_STOP_URL,
                params={
                    "getstop": "1",
                    "REQ0JourneyStopsS0A": "255",
                    "REQ0JourneyStopsS0G": f"{name}?",
                    "REQ0JourneyStopsB": "20",
                    "js": "true",
                },
                headers={"User-Agent": "TrainGuessr station data generator"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            selected = select_scotty_suggestion(
                parse_scotty_suggestions(response.text),
                name=name,
                lat=_float(row["hst_y"]),
                lon=_float(row["hst_x"]),
            )
        except (requests.RequestException, ValueError) as exc:
            log.warning("Could not resolve Austrian stop %s (%s): %s", name, key, exc)
            return None
        if selected:
            self.cache[key] = selected
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"version": 1, "entries": self.cache}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return selected


def merge_catalogues(
    geonetz_nodes: list[dict[str, Any]],
    mvo_rows: Iterable[dict[str, Any]],
    resolver: ScottyResolver,
    rename_map: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing_by_ifopt = {
        normalize_ifopt(node.get("tags", {}).get("ifopt_id")): node
        for node in geonetz_nodes
        if normalize_ifopt(node.get("tags", {}).get("ifopt_id"))
    }
    used_ids = {str(node["id"]) for node in geonetz_nodes}
    new_nodes: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "geonetz_nodes": len(geonetz_nodes),
        "mvo_rail_candidates": 0,
        "matched_existing_ifopt": 0,
        "resolved_to_existing_eva": 0,
        "added": [],
        "unresolved": [],
    }
    for row in sorted(mvo_rail_candidates(mvo_rows), key=lambda item: (str(item.get("hst_name")), str(item.get("hst_globid")))):
        audit["mvo_rail_candidates"] += 1
        ifopt = normalize_ifopt(row.get("hst_globid"))
        if ifopt in existing_by_ifopt:
            audit["matched_existing_ifopt"] += 1
            continue
        resolution = resolver.resolve(row)
        if not resolution:
            audit["unresolved"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "municipality": row.get("hst_gem_name"),
                "reason": "no_unique_scotty_match",
            })
            continue
        eva_id = str(resolution["eva_id"])
        if eva_id in used_ids:
            audit["resolved_to_existing_eva"] += 1
            continue
        name = rename_map.get(str(row["hst_name"]), str(row["hst_name"]))
        node = {
            "type": "node",
            "id": int(eva_id),
            "lat": _float(row["hst_y"]),
            "lon": _float(row["hst_x"]),
            "tags": {
                "name": name,
                "ifopt_id": ifopt,
                "stp_type": "railStation",
                "mvo_hst_id": str(row.get("hst_id") or ""),
                "mvo_municipality": str(row.get("hst_gem_name") or ""),
                "mvo_mode_mask": str(row.get("umst_agg_vm") or ""),
                "source": "MVO Österreichweite Haltestellen",
                "scotty_resolution": "name_coordinate",
            },
            "category": "austria_oebb",
        }
        used_ids.add(eva_id)
        new_nodes.append(node)
        audit["added"].append({
            "id": int(eva_id),
            "ifopt_id": ifopt,
            "name": name,
            "resolved_name": resolution.get("name"),
            "distance_m": resolution.get("distance_m"),
            "similarity": resolution.get("similarity"),
        })
    audit["added_count"] = len(new_nodes)
    audit["unresolved_count"] = len(audit["unresolved"])
    audit["output_nodes"] = len(geonetz_nodes) + len(new_nodes)
    return geonetz_nodes + new_nodes, audit


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Austria rail stations from GeoNetz + MVO")
    parser.add_argument("--mvo-input", type=Path, help="MVO ZIP/haltestellen.csv instead of the live WFS")
    parser.add_argument("--geonetz-only", action="store_true", help="Rebuild the legacy ÖBB-only catalogue")
    parser.add_argument("--offline", action="store_true", help="Do not query SCOTTY for uncached MVO stops")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    session = requests.Session()
    rename_map = load_rename_map("austria")
    geonetz_source = _download_geonetz(session)
    geonetz_nodes = load_geonetz_nodes(geonetz_source, rename_map)
    if args.geonetz_only:
        write_ndjson(args.output, geonetz_nodes)
        return 0

    if args.mvo_input:
        mvo_rows = load_mvo_csv(args.mvo_input)
        validate_mvo_wgs84(mvo_rows)
    else:
        mvo_rows = download_mvo_wfs(session)
    resolver = ScottyResolver(session, offline=args.offline)
    output, audit = merge_catalogues(geonetz_nodes, mvo_rows, resolver, rename_map)
    write_ndjson(args.output, output)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Austria: {len(geonetz_nodes)} GeoNetz + {audit['added_count']} MVO additions "
        f"= {len(output)} stations; {audit['unresolved_count']} MVO candidates unresolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
