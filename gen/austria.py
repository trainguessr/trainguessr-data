#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import logging as log
import math
import os
import re
import statistics
import zipfile
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import requests

from common.config import load_rename_map
from common.io import write_ndjson


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
AUSTRIA_CACHE = CACHE_DIR / "austria"
GEONETZ_URL = "https://data.oebb.at/dam/jcr:d4780bb2-390e-4288-b540-dff1ae1b27ae/GeoNetz_12-2024.zip"
MVO_CATALOGUE_URL = "https://www.mobilitaetsdaten.gv.at/daten/%C3%B6sterreichweite-haltestellen"
MVO_DATASETS_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets?tagIds=&tagFilterModeInclusive=false"
MVO_METADATA_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets/{dataset_id}"
MVO_FILE_URL = "https://data.mobilitaetsverbuende.at/api/public/v1/data-sets/{dataset_id}/{year}/file"
MVO_TOKEN_URL = "https://user.mobilitaetsverbuende.at/auth/realms/dbp-public/protocol/openid-connect/token"
SCOTTY_STOP_URL = "https://fahrplan.oebb.at/bin/ajax-getstop.exe/dn"
SCOTTY_BOARD_URL = "https://fahrplan.oebb.at/bin/stboard.exe/dn"
DEFAULT_OUTPUT = ROOT / "nodes" / "nodes-austria-oebb.json"
DEFAULT_AUDIT = AUSTRIA_CACHE / "migration-audit.json"
DEFAULT_RESOLUTION_CACHE = AUSTRIA_CACHE / "scotty-resolutions.json"
DEFAULT_MVO_CACHE = AUSTRIA_CACHE / "mvo-haltestellen.zip"

_RAIL_MASK_POSITIONS = (0, 1)  # Eisenbahn, S-Bahn
_IFOPT_RE = re.compile(r"^at[-:]([0-9]+)[-:]([0-9]+)$", re.I)
_EVA_RE = re.compile(r"@L=0*([0-9]+)@")
_SUGGESTION_RE = re.compile(
    r"(?:SLs\.)?sls\s*=\s*(\{.*?\})\s*;\s*(?:SLs\.)?showSuggestion",
    re.S,
)
_MVO_SAMPLE_RE = re.compile(
    r'href=["\']([^"\']+/sites/default/files/metadataset/sample_data/[^"\']+\.zip)["\']',
    re.I,
)
_REPLACEMENT_LINE_RE = re.compile(r"^(?:SEV(?:\s+.*)?|SV\s*\d+[A-Z]*|xxx)$", re.I)
_RAIL_LINE_RE = re.compile(
    r"^(?:S\s*\d+[A-Z]*|R\s*\d+|REX\s*\d+|RJX?\s*\d*|ICE?\s*\d*|EC\s*\d*|"
    r"EN\s*\d*|WEST\s*\d*|D(?:Z)?\s*\d*|ZB\s*\d+|CJX\s*\d+|IR\s*\d+|"
    r"NJ\s*\d+|WB\s*\d+|RB\s*\d+|RX\s*\d+|LEX\s*\d+|WVB|WHB|REB|CAT|ATB\s*\d+|STB)$",
    re.I,
)
_REVIEWED_NAMES = {
    "at:46:6625": ("Mariazell", "Mariazell Bahnhof", "Mariazell Bahnhof [in St.Sebastian]"),
    "at:47:2217": ("Mayrhofen", "Mayrhofen im Zillertal Bahnhof", "Mayrhofen Bahnhof"),
    "at:43:7371": ("St. Pölten Alpenbahnhof-Kaiserwald", "St.Pölten Alpenbahnhof-Kaiserwald"),
}
_REVIEWED_LIGHT_RAIL_IFOPTS = {"at:47:65344"}  # Fulpmes / Stubaitalbahn
_VIENNA = ZoneInfo("Europe/Vienna")


def _float(value: Any) -> float:
    return float(str(value).strip().replace(",", "."))


def _normal_name(value: str) -> str:
    value = html.unescape(value).casefold().replace("ß", "ss")
    value = re.sub(r"\b(?:bahnhof|bahnhst|hbf)\b", " ", value)
    value = re.sub(r"\((?:stmk|tirol|oö|nö|sbg|ktn)\)", " ", value)
    value = re.sub(r"\[in\s+[^\]]+\]", " ", value)
    value = re.sub(r"\bst\s*\.\s*", "st ", value)
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
        for line in handle:
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


def _zip_member_rows(path: Path, member_name: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if Path(name).name.casefold() == member_name.casefold()]
        if len(members) != 1:
            raise ValueError(f"{path}: expected exactly one {member_name}")
        with archive.open(members[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(8192)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            except csv.Error:
                dialect = csv.excel
            return [dict(row) for row in csv.DictReader(handle, dialect=dialect)]


def load_mvo_snapshot(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not zipfile.is_zipfile(path):
        raise ValueError("MVO input must be a ZIP containing haltestellen.csv and steige.csv")
    return _zip_member_rows(path, "haltestellen.csv"), _zip_member_rows(path, "steige.csv")


def _validate_mvo_archive(path: Path) -> None:
    stops, platforms = load_mvo_snapshot(path)
    if not stops or not platforms:
        raise ValueError("MVO archive contains no stops or platforms")
    required_stops = {"hst_id", "hst_name", "hst_globid", "hst_x", "hst_y", "umst_agg_vm"}
    required_platforms = {"hst_id", "stg_globid", "stg_x", "stg_y", "umst_vm", "linien", "extids_obb"}
    if not required_stops.issubset(stops[0]) or not required_platforms.issubset(platforms[0]):
        raise ValueError("MVO archive schema is missing required stop/platform columns")
    validate_mvo_wgs84(stops)


def _download_to_cache(session: requests.Session, url: str, path: Path, **kwargs) -> Path:
    response = session.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(response.content)
    try:
        _validate_mvo_archive(temporary)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def download_mvo_snapshot(session: requests.Session, output: Path = DEFAULT_MVO_CACHE) -> Path:
    username = os.getenv("MVO_USERNAME")
    password = os.getenv("MVO_PASSWORD")
    if username and password:
        token_response = session.post(
            MVO_TOKEN_URL,
            data={
                "client_id": "dbp-public-ui",
                "username": username,
                "password": password,
                "grant_type": "password",
                "scope": "openid",
            },
            timeout=30,
        )
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if not token:
            raise ValueError("MVO authentication returned no access token")
        datasets_response = session.get(MVO_DATASETS_URL, timeout=30)
        datasets_response.raise_for_status()
        datasets = datasets_response.json()
        dataset = next(
            (
                item for item in datasets
                if str(item.get("nameDe", "")).casefold() == "haltestellen (csv)"
            ),
            None,
        )
        if not dataset:
            raise ValueError("MVO dataset catalogue contains no Haltestellen (CSV) dataset")
        dataset_id = str(dataset["id"])
        metadata = session.get(MVO_METADATA_URL.format(dataset_id=dataset_id), timeout=30)
        metadata.raise_for_status()
        versions = metadata.json().get("activeVersions") or []
        years = sorted((str(item.get("year")) for item in versions if str(item.get("year", "")).isdigit()), reverse=True)
        if not years:
            raise ValueError("MVO metadata exposes no active dataset year")
        log.info("Downloading authenticated MVO production snapshot for %s", years[0])
        return _download_to_cache(
            session,
            MVO_FILE_URL.format(dataset_id=dataset_id, year=years[0]),
            output,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/zip"},
        )

    catalogue = session.get(MVO_CATALOGUE_URL, timeout=30)
    catalogue.raise_for_status()
    match = _MVO_SAMPLE_RE.search(catalogue.text)
    if not match:
        raise ValueError("Official MVO catalogue page contains no public sample ZIP")
    sample_url = urljoin(MVO_CATALOGUE_URL, html.unescape(match.group(1)))
    log.info("Downloading public MVO catalogue sample %s", sample_url)
    return _download_to_cache(session, sample_url, output)


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
            "use a WGS84 export"
        )


def _rail_mask(value: Any) -> bool:
    mask = re.sub(r"\s+", "", str(value or ""))
    return len(mask) >= 2 and all(char in "01" for char in mask) and any(mask[pos] == "1" for pos in _RAIL_MASK_POSITIONS)


def _line_tokens(value: Any) -> list[str]:
    return [token.strip() for token in str(value or "").split(",") if token.strip()]


def _real_rail_platform(platform: dict[str, Any], *, allow_light_rail: bool = False) -> bool:
    tokens = _line_tokens(platform.get("linien"))
    conventional_rail = _rail_mask(platform.get("umst_vm"))
    reviewed_light_rail = allow_light_rail and "STB" in {token.upper() for token in tokens}
    if not conventional_rail and not reviewed_light_rail:
        return False
    return any(
        not _REPLACEMENT_LINE_RE.fullmatch(token) and _RAIL_LINE_RE.fullmatch(token)
        for token in tokens
    )


def _platform_eva(platform: dict[str, Any]) -> int | None:
    value = re.sub(r"\D", "", str(platform.get("extids_obb") or ""))
    if len(value) == 7 and not value.startswith("0"):
        return int(value)
    return None


def mvo_rail_candidates(
    rows: Iterable[dict[str, Any]],
    platforms: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    platforms_by_stop: dict[str, list[dict[str, Any]]] = {}
    if platforms is not None:
        for platform in platforms:
            platforms_by_stop.setdefault(str(platform.get("hst_id") or ""), []).append(platform)

    result: list[dict[str, Any]] = []
    for row in rows:
        ifopt = normalize_ifopt(row.get("hst_globid"))
        name = str(row.get("hst_name") or "").strip()
        if not ifopt.startswith("at:") or not name:
            continue
        qualifying_platforms = [
            platform for platform in platforms_by_stop.get(str(row.get("hst_id") or ""), [])
            if _real_rail_platform(
                platform,
                allow_light_rail=ifopt in _REVIEWED_LIGHT_RAIL_IFOPTS,
            )
        ]
        if not qualifying_platforms:
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
        if qualifying_platforms:
            evas = {_platform_eva(platform) for platform in qualifying_platforms}
            evas.discard(None)
            if len(evas) != 1:
                continue
            item["platform_eva_id"] = evas.pop()
            item["rail_lines"] = sorted({
                token for platform in qualifying_platforms for token in _line_tokens(platform.get("linien"))
                if _RAIL_LINE_RE.fullmatch(token) and not _REPLACEMENT_LINE_RE.fullmatch(token)
            })
            item["rail_platform_ifopts"] = sorted({
                str(platform.get("stg_globid") or "") for platform in qualifying_platforms
                if platform.get("stg_globid")
            })
            platform_lats = [_float(platform["stg_y"]) for platform in qualifying_platforms]
            platform_lons = [_float(platform["stg_x"]) for platform in qualifying_platforms]
            item["rail_lat"] = statistics.median(platform_lats)
            item["rail_lon"] = statistics.median(platform_lons)
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
    expected_eva: int | None = None,
    aliases: Iterable[str] = (),
) -> dict[str, Any] | None:
    wanted_names = {_normal_name(name), *(_normal_name(alias) for alias in aliases)}
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for row in suggestions:
        if str(row.get("type", "1")) not in {"1", "station", "stop"}:
            continue
        match = _EVA_RE.search(str(row.get("id") or ""))
        coords = _suggestion_coordinates(row)
        candidate_name = str(row.get("value") or row.get("name") or "").strip()
        if not match or not coords or not candidate_name:
            continue
        eva_id = int(match.group(1))
        if expected_eva is not None and eva_id != expected_eva:
            continue
        distance = _haversine_m(lat, lon, *coords)
        normalized_candidate = _normal_name(candidate_name)
        similarity = max(SequenceMatcher(None, wanted, normalized_candidate).ratio() for wanted in wanted_names)
        if normalized_candidate in wanted_names:
            similarity = 1.0
        if distance > 2_000 or similarity < 0.72:
            continue
        ranked.append((similarity, distance, {
            "eva_id": eva_id,
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
                if isinstance(payload, dict) and payload.get("version") == 2:
                    self.cache = dict(payload.get("entries") or {})
            except (OSError, ValueError):
                self.cache = {}

    def resolve(self, row: dict[str, Any]) -> dict[str, Any] | None:
        key = normalize_ifopt(row.get("hst_globid"))
        expected_eva = row.get("platform_eva_id")
        if expected_eva:
            return {
                "eva_id": int(expected_eva),
                "name": str(row.get("hst_name") or ""),
                "lat": _float(row.get("rail_lat", row["hst_y"])),
                "lon": _float(row.get("rail_lon", row["hst_x"])),
                "distance_m": 0.0,
                "similarity": 1.0,
                "method": "platform_eva",
            }
        cached = self.cache.get(key)
        if isinstance(cached, dict):
            if cached.get("eva_id"):
                return cached
        if self.offline:
            return None
        name = str(row.get("hst_name") or "").strip()
        aliases = _REVIEWED_NAMES.get(key, ())
        search_name = aliases[1] if len(aliases) > 1 else name
        try:
            response = self.session.get(
                SCOTTY_STOP_URL,
                params={
                    "getstop": "1",
                    "REQ0JourneyStopsS0A": "255",
                    "REQ0JourneyStopsS0G": f"{search_name}?",
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
                lat=_float(row.get("rail_lat", row["hst_y"])),
                lon=_float(row.get("rail_lon", row["hst_x"])),
                expected_eva=int(expected_eva) if expected_eva else None,
                aliases=aliases,
            )
        except (requests.RequestException, ValueError) as exc:
            log.warning("Could not resolve Austrian stop %s (%s): %s", name, key, exc)
            return None
        if selected:
            self.cache[key] = selected
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"version": 2, "entries": self.cache}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return selected


def verify_scotty_station(
    session: requests.Session,
    eva_id: int,
    timeout: int = 20,
    attempts: int = 3,
) -> dict[str, Any] | None:
    now = datetime.now(_VIENNA)
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                SCOTTY_BOARD_URL,
                params={
                    "L": "vs_scotty.vs_liveticker",
                    "evaId": str(eva_id),
                    "boardType": "dep",
                    "time": now.strftime("%H:%M"),
                    "productsFilter": "1111111111111",
                    "additionalTime": "12",
                    "disableEquivs": "yes",
                    "maxJourneys": "3",
                    "outputMode": "tickerDataOnly",
                    "start": "yes",
                    "selectDate": "today",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            text = response.text.replace("journeysObj = ", "", 1).strip()
            payload = json.loads(text)
            if str(payload.get("stationEvaId")) != str(eva_id):
                return None
            return {
                "station_name": html.unescape(str(payload.get("stationName") or "")),
                "journey_count": len(payload.get("journey") or []),
            }
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError) as exc:
            if attempt == attempts:
                log.warning("Could not verify SCOTTY station %s after %s attempts: %s", eva_id, attempts, exc)
    return None


def merge_catalogues(
    geonetz_nodes: list[dict[str, Any]],
    mvo_rows: Iterable[dict[str, Any]],
    mvo_platforms: Iterable[dict[str, Any]],
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
        "failed_board_verification": 0,
        "added": [],
        "unresolved": [],
    }
    for row in sorted(mvo_rail_candidates(mvo_rows, mvo_platforms), key=lambda item: (str(item.get("hst_name")), str(item.get("hst_globid")))):
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
        verification = verify_scotty_station(resolver.session, int(eva_id), resolver.timeout)
        if not verification:
            audit["failed_board_verification"] += 1
            audit["unresolved"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "reason": "scotty_station_verification_failed",
            })
            continue
        reviewed_names = _REVIEWED_NAMES.get(ifopt, ())
        source_name = str(row["hst_name"])
        name = reviewed_names[0] if reviewed_names else re.sub(
            r"\s+(?:Bahnhof|Bahnhst)$", "", source_name, flags=re.I
        )
        name = rename_map.get(source_name, name)
        node = {
            "type": "node",
            "id": int(eva_id),
            "lat": _float(row.get("rail_lat", row["hst_y"])),
            "lon": _float(row.get("rail_lon", row["hst_x"])),
            "tags": {
                "name": name,
                "ifopt_id": ifopt,
                "stp_type": "railStation",
                "mvo_hst_id": str(row.get("hst_id") or ""),
                "mvo_municipality": str(row.get("hst_gem_name") or ""),
                "mvo_mode_mask": str(row.get("umst_agg_vm") or ""),
                "mvo_source_name": source_name,
                "mvo_rail_lines": ",".join(row.get("rail_lines") or []),
                "mvo_rail_platform_ifopts": ",".join(row.get("rail_platform_ifopts") or []),
                "source": "MVO Österreichweite Haltestellen",
                "scotty_name": verification["station_name"],
                "scotty_resolution": "platform_eva_confirmed",
                "scotty_board_status": "board_available" if verification["journey_count"] else "valid_eva_empty_board",
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
            "board_journeys": verification["journey_count"],
        })
    audit["added_count"] = len(new_nodes)
    audit["unresolved_count"] = len(audit["unresolved"])
    audit["output_nodes"] = len(geonetz_nodes) + len(new_nodes)
    return geonetz_nodes + new_nodes, audit


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Austria rail stations from GeoNetz and MVO")
    parser.add_argument("--mvo-input", type=Path, help="Use this MVO ZIP instead of downloading the official dataset")
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
    mvo_source = args.mvo_input or download_mvo_snapshot(session)
    mvo_rows, mvo_platforms = load_mvo_snapshot(mvo_source)
    validate_mvo_wgs84(mvo_rows)
    resolver = ScottyResolver(session, offline=args.offline)
    output, audit = merge_catalogues(geonetz_nodes, mvo_rows, mvo_platforms, resolver, rename_map)
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
