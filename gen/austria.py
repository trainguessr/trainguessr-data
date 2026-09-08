#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import html
import hashlib
import io
import json
import logging as log
import math
import os
import shutil
import sqlite3
import tempfile
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

from common.config import load_country_config, load_excluded_ids, load_rename_map
from common.io import write_ndjson


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
AUSTRIA_CACHE = CACHE_DIR / "austria"
TEMP_CACHE = CACHE_DIR / "temp"
AUSTRIA_TEMP = TEMP_CACHE / "austria"
GEONETZ_FILTERED = AUSTRIA_CACHE / "austria_stations_filtered.json"
GEONETZ_ARCHIVE = AUSTRIA_CACHE / "GeoNetz_12-2024.zip"
GEONETZ_TEMP = AUSTRIA_TEMP / "geonetz"
DEFAULT_OEBB_OPERATOR_INDEX = CACHE_DIR / "austria-oebb-operators.sqlite"
DEFAULT_OEBB_OPERATOR_AUDIT = AUSTRIA_CACHE / "oebb-operator-index-audit.json"
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
    "at:45:54150": ("Neukirchen am Großvenediger", "Neukirchen am Großvenediger Bahnhof"),
    "at:45:54263": ("Rettenbach im Pinzgau", "Rettenbach im Pinzgau Bahnhst"),
    "at:45:54201": ("Stuhlfelden Heilbad Burgwies", "Heilbad Burgwies", "Heilbad Burgwies Bahnhst"),
    "at:45:54358": ("Lengdorf", "Lengdorf im Pinzgau", "Lengdorf im Pinzgau Bahnhst"),
    "at:45:56408": ("Seekirchen Stadt", "Seekirchen/Wallersee Stadt", "Seekirchen/Wallersee Stadt Bahnhst"),
    "at:43:72002": ("Weitersfeld (NÖ)", "Weitersfeld im Waldviertel", "Weitersfeld im Waldviertel Bahnhof"),
    "at:46:3147": ("Wies Markt", "Wies in Stmk Markt", "Wies in Stmk Markt Bahnhof"),
    "at:42:3916": ("Dellach im Gailtal", "Dellach im Gailtal", "Dellach im Gailtal Alter Bahnhof"),
    "at:42:3915": ("Gundersheim im Gailtal", "Gundersheim im Gailtal", "Gundersheim Alter Bahnhof"),
    "at:42:6166": ("St. Daniel", "St.Daniel", "St. Daniel B111"),
    "at:42:6172": ("Kirchbach im Gailtal", "Kirchbach im Gailtal Ortsmitte", "Kirchbach (Hermagor) Ortsmitte"),
    "at:42:3918": ("Kötschach-Mauthen", "Kötschach-Mauthen Alter Bahnhof"),
    "at:42:3911": ("Rattendorf-Jenig", "Rattendorf", "Rattendorf-Jenig Alter Bahnhof"),
    "at:42:7381": ("Waidegg", "Waidegg Ortsmitte", "Waidegg Ortsmitte"),
    "at:42:3909": ("Watschig", "Watschig B111", "Watschig Alter Bahnhof"),
    "at:42:6183": ("Postran", "Postran B111", "Postran B111"),
    "at:42:6180": ("Tröpolach", "Tröpolach Gailbrücke", "Tröpolach Gailbrücke"),
    "at:43:4876": ("Stetten Fossilienwelt", "Stetten b.Korneuburg Fossilienwelt Bahnhof"),
    "at:43:6004": ("Hochschneeberg", "Hochschneeberg Bahnhof"),
    "at:43:6005": ("Hengsthütte", "Hengsthütte Bahnhst"),
    "at:43:6006": ("Baumgartner", "Baumgartner Bahnhst"),
    "at:43:6056": ("Hengsttal", "Puchberg am Schneeberg Hengsttal Bahnhst"),
    "at:43:17223": ("Pfaffenschlag", "Pfaffenschlag b.Lunz Nostalgiebahnhof"),
    "at:43:17227": ("Gasthof zur Paula", "Holzapfel Gh Zur Paula Nostalgiebahnhof"),
    "at:43:70101": ("Gaming", "Gaming Nostalgiebahnhof"),
    "at:43:70103": ("Holzapfel", "Holzapfel Nostalgiebahnhof"),
    "at:43:70104": ("Lunz am See Amonhaus", "Lunz am See Amonhaus"),
    "at:43:70106": ("Reichenau an der Rax Kurhaus", "Reichenau an der Rax Kurhaus Bahnhst"),
    "at:43:70107": ("Reichenau an der Rax Lokalbahn", "Reichenau an der Rax Bahnhof"),
    "at:43:70108": ("Hirschwang/Rax Haaberg", "Reichenau an der Rax Haaberg Bahnhof"),
    "at:43:70109": ("Hirschwang/Rax Bahnhof", "Hirschwang an der Rax Bahnhof"),
    "at:43:7437": ("Kienberg", "Kienberg/Erlauf"),
    "at:43:7917": ("Lunz am See Nostalgiebahnhof", "Lunz am See Nostalgiebahnhof"),
    "at:43:71978": ("Draisinenalm Grafensulz", "Grafensulz Draisinenalm Bahnhst"),
    "at:43:71979": ("Schletz", "Schletz Bahnhst"),
    "at:43:71980": ("Asparn an der Zaya", "Asparn/Zaya Draisinenbahnhof"),
    "at:43:71981": ("Mistelbach Interspar", "Mistelbach/Zaya Interspar Bahnhst"),
}
_REVIEWED_LIGHT_RAIL_IFOPTS = {"at:47:65344"}  # Fulpmes / Stubaitalbahn
_VIENNA = ZoneInfo("Europe/Vienna")


def _float(value: Any) -> float:
    return float(str(value).strip().replace(",", "."))


def _cache_age(path: Path) -> str:
    seconds = max(0, int((datetime.now().timestamp() - path.stat().st_mtime)))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


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


def _load_mvo_overrides() -> tuple[set[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    excluded = {
        normalize_ifopt(value)
        for value in load_excluded_ids("austria", "mvo")
    }
    aliases: dict[str, dict[str, Any]] = {}
    for row in load_country_config("austria").get("mvo_aliases", []):
        if not isinstance(row, dict):
            raise ValueError("austria: every mvo_aliases entry must be an object")
        ifopt = normalize_ifopt(row.get("id"))
        canonical_id = str(row.get("canonical_id") or "").strip()
        if not ifopt.startswith("at:") or not canonical_id:
            raise ValueError(f"austria: invalid MVO alias {row!r}")
        aliases[ifopt] = row
    resolutions: dict[str, dict[str, Any]] = {}
    for row in load_country_config("austria").get("mvo_resolutions", []):
        if not isinstance(row, dict):
            raise ValueError("austria: every mvo_resolutions entry must be an object")
        ifopt = normalize_ifopt(row.get("id"))
        provider_id = str(row.get("provider_id") or "").strip()
        expected_name = str(row.get("expected_name") or "").strip()
        if not ifopt.startswith("at:") or not provider_id.isdigit() or not expected_name:
            raise ValueError(f"austria: invalid MVO resolution {row!r}")
        resolutions[ifopt] = row
    return excluded, aliases, resolutions


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _adopt_legacy_cache(old: Path, new: Path) -> Path:
    """Move an old root-level cache artifact into its durable country directory."""
    if new.exists() or not old.exists():
        return new
    new.parent.mkdir(parents=True, exist_ok=True)
    old.replace(new)
    try:
        old_label = old.relative_to(ROOT)
        new_label = new.relative_to(ROOT)
    except ValueError:
        old_label, new_label = old, new
    print(f"Moved legacy cache artifact: {old_label} -> {new_label}")
    return new


def _download_geonetz(session: requests.Session, timeout: int = 60) -> Path:
    AUSTRIA_CACHE.mkdir(parents=True, exist_ok=True)
    _adopt_legacy_cache(CACHE_DIR / "austria_stations_filtered.json", GEONETZ_FILTERED)
    _adopt_legacy_cache(CACHE_DIR / "GeoNetz_12-2024.zip", GEONETZ_ARCHIVE)
    if GEONETZ_FILTERED.is_file():
        print(f"Using cached GeoNetz station data (age: {_cache_age(GEONETZ_FILTERED)})")
        return GEONETZ_FILTERED

    if not GEONETZ_ARCHIVE.is_file():
        response = session.get(GEONETZ_URL, timeout=timeout)
        response.raise_for_status()
        GEONETZ_ARCHIVE.write_bytes(response.content)

    shutil.rmtree(GEONETZ_TEMP, ignore_errors=True)
    outer_dir = GEONETZ_TEMP / "outer"
    inner_dir = GEONETZ_TEMP / "inner"
    outer_dir.mkdir(parents=True, exist_ok=True)
    inner_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(GEONETZ_ARCHIVE) as outer:
            outer.extractall(outer_dir)
        inner_matches = list(outer_dir.rglob("OEBB_NETWORK_GeoJSON.zip"))
        if len(inner_matches) != 1:
            raise ValueError(
                f"{GEONETZ_ARCHIVE}: expected exactly one OEBB_NETWORK_GeoJSON.zip, "
                f"found {len(inner_matches)}"
            )
        with zipfile.ZipFile(inner_matches[0]) as inner:
            inner.extractall(inner_dir)
        geojson_matches = list(inner_dir.rglob("OEBB_NETWORK.json"))
        if len(geojson_matches) != 1:
            raise ValueError(
                f"{inner_matches[0]}: expected exactly one OEBB_NETWORK.json, "
                f"found {len(geojson_matches)}"
            )
        payload = json.loads(geojson_matches[0].read_text(encoding="utf-8"))
        with GEONETZ_FILTERED.open("w", encoding="utf-8", newline="\n") as handle:
            for feature in payload.get("features", []):
                properties = feature.get("properties", {})
                if "railStation" in str(properties.get("STP_TYPE", "")):
                    handle.write(json.dumps(properties, ensure_ascii=False) + "\n")
    finally:
        shutil.rmtree(GEONETZ_TEMP, ignore_errors=True)
    return GEONETZ_FILTERED

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
        path = _download_to_cache(
            session,
            MVO_FILE_URL.format(dataset_id=dataset_id, year=years[0]),
            output,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/zip"},
        )
        print(f"Cached authenticated MVO snapshot (age: {_cache_age(path)})")
        return path

    catalogue = session.get(MVO_CATALOGUE_URL, timeout=30)
    catalogue.raise_for_status()
    match = _MVO_SAMPLE_RE.search(catalogue.text)
    if not match:
        raise ValueError("Official MVO catalogue page contains no public sample ZIP")
    sample_url = urljoin(MVO_CATALOGUE_URL, html.unescape(match.group(1)))
    log.info("Downloading public MVO catalogue sample %s", sample_url)
    path = _download_to_cache(session, sample_url, output)
    print(f"Cached public MVO sample (age: {_cache_age(path)})")
    return path


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
    reviewed_resolutions = _load_mvo_overrides()[2]
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
        if not qualifying_platforms and ifopt not in reviewed_resolutions:
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
            if len(evas) > 1:
                continue
            if evas:
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
        else:
            # A reviewed physical station may be temporarily represented only by
            # replacement-service, bus-only, or unclassified MVO platforms.
            item["reviewed_rail_override"] = True
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
        self.reviewed_evas = _load_mvo_overrides()[2]
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
        reviewed = self.reviewed_evas.get(key)
        if reviewed:
            return {
                "eva_id": int(reviewed["provider_id"]),
                "name": reviewed["expected_name"],
                "lat": _float(row.get("rail_lat", row["hst_y"])),
                "lon": _float(row.get("rail_lon", row["hst_x"])),
                "distance_m": reviewed.get("distance_m"),
                "similarity": 1.0,
                "method": "reviewed_provider_id",
                "expected_provider_name": reviewed["expected_name"],
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
        "aliases": [],
        "excluded": [],
        "unresolved": [],
    }
    mvo_excluded_ifopts, mvo_aliases, _ = _load_mvo_overrides()
    existing_by_id = {str(node["id"]): node for node in geonetz_nodes}
    for row in sorted(mvo_rail_candidates(mvo_rows, mvo_platforms), key=lambda item: (str(item.get("hst_name")), str(item.get("hst_globid")))):
        audit["mvo_rail_candidates"] += 1
        ifopt = normalize_ifopt(row.get("hst_globid"))
        if ifopt in existing_by_ifopt:
            audit["matched_existing_ifopt"] += 1
            continue
        if ifopt in mvo_excluded_ifopts:
            audit["excluded"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "municipality": row.get("hst_gem_name"),
                "reason": "reviewed_scope_exclusion",
            })
            continue
        alias = mvo_aliases.get(ifopt)
        if alias:
            canonical_id = str(alias["canonical_id"])
            canonical = existing_by_id.get(canonical_id)
            expected_name = str(alias.get("expected_name") or "")
            canonical_expected_name = str(alias.get("canonical_expected_name") or "")
            if canonical is None:
                raise ValueError(f"austria: stale MVO alias {ifopt}->{canonical_id}: canonical node is missing")
            if _normal_name(str(row.get("hst_name") or "")) != _normal_name(expected_name):
                raise ValueError(
                    f"austria: stale MVO alias {ifopt}: expected {expected_name!r}, got {row.get('hst_name')!r}"
                )
            actual_canonical_name = str(canonical.get("tags", {}).get("name") or "")
            if _normal_name(actual_canonical_name) != _normal_name(canonical_expected_name):
                raise ValueError(
                    f"austria: stale MVO alias target {canonical_id}: expected "
                    f"{canonical_expected_name!r}, got {actual_canonical_name!r}"
                )
            audit["resolved_to_existing_eva"] += 1
            audit["aliases"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "canonical_id": int(canonical_id),
                "reason": alias.get("reason", "reviewed_provider_alias"),
            })
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
        if resolver.offline:
            verification = {
                "station_name": str(
                    resolution.get("expected_provider_name")
                    or resolution.get("name")
                    or row.get("hst_name")
                    or ""
                ),
                "journey_count": 0,
            }
            board_status = "offline_cached_resolution"
        else:
            verification = verify_scotty_station(resolver.session, int(eva_id), resolver.timeout)
            if not verification:
                audit["failed_board_verification"] += 1
                audit["unresolved"].append({
                    "ifopt_id": ifopt,
                    "name": row.get("hst_name"),
                    "reason": "scotty_station_verification_failed",
                })
                continue
            board_status = "board_available" if verification["journey_count"] else "valid_eva_empty_board"
        expected_provider_name = resolution.get("expected_provider_name")
        if expected_provider_name and _normal_name(verification["station_name"]) != _normal_name(str(expected_provider_name)):
            audit["failed_board_verification"] += 1
            audit["unresolved"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "reason": "scotty_station_name_mismatch",
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
                "scotty_resolution": resolution.get("method", "platform_eva_confirmed"),
                "scotty_board_status": board_status,
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
    audit["alias_count"] = len(audit["aliases"])
    audit["excluded_count"] = len(audit["excluded"])
    audit["unresolved_count"] = len(audit["unresolved"])
    audit["output_nodes"] = len(geonetz_nodes) + len(new_nodes)
    return geonetz_nodes + new_nodes, audit



OEBB_RAIL_ROUTE_TYPES = {2, *range(100, 200)}
_OEBB_GTFS_REQUIRED = {"agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt"}


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


def _build_requested_oebb_index(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.oebb_gtfs:
        return None
    stats = build_oebb_operator_index(load_oebb_gtfs(args.oebb_gtfs), args.oebb_operator_index)
    args.oebb_operator_audit.parent.mkdir(parents=True, exist_ok=True)
    args.oebb_operator_audit.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "ÖBB operator index: "
        f"{stats['rail_trips']} rail trips, "
        f"{stats['station_short_names_with_multiple_agencies']} "
        "station/train-number agency ambiguities"
    )
    return stats


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Austria rail stations from GeoNetz and MVO")
    parser.add_argument("--mvo-input", type=Path, help="Use this MVO ZIP instead of downloading the official dataset")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only cached GeoNetz/MVO inputs and persisted or reviewed SCOTTY resolutions",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument(
        "--oebb-gtfs",
        type=Path,
        help="Official ÖBB GTFS ZIP, downloaded after accepting ÖBB's terms; builds optional operator enrichment",
    )
    parser.add_argument(
        "--oebb-operator-index",
        type=Path,
        default=DEFAULT_OEBB_OPERATOR_INDEX,
        help="Runtime SQLite output (root cache is reserved for deployable runtime indexes)",
    )
    parser.add_argument(
        "--oebb-operator-audit",
        type=Path,
        default=DEFAULT_OEBB_OPERATOR_AUDIT,
        help="Durable country audit JSON",
    )
    parser.add_argument(
        "--oebb-operator-index-only",
        action="store_true",
        help="Build only the ÖBB GTFS operator index; requires --oebb-gtfs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.oebb_operator_index_only:
        if not args.oebb_gtfs:
            raise SystemExit("--oebb-operator-index-only requires --oebb-gtfs")
        _build_requested_oebb_index(args)
        return 0

    session = requests.Session()
    rename_map = load_rename_map("austria")
    if args.offline:
        offline_geonetz = CACHE_DIR / "austria" / "austria_stations_filtered.json"
        _adopt_legacy_cache(CACHE_DIR / "austria_stations_filtered.json", offline_geonetz)
        geonetz_source = offline_geonetz
        if not geonetz_source.is_file():
            raise SystemExit(f"Offline Austria generation requires cached GeoNetz data: {geonetz_source}")
    else:
        geonetz_source = _download_geonetz(session)
    geonetz_nodes = load_geonetz_nodes(geonetz_source, rename_map)
    if args.offline:
        mvo_source = args.mvo_input or DEFAULT_MVO_CACHE
        if not mvo_source.is_file():
            raise SystemExit(f"Offline Austria generation requires a cached MVO ZIP: {mvo_source}")
    else:
        mvo_source = args.mvo_input or download_mvo_snapshot(session)
    mvo_rows, mvo_platforms = load_mvo_snapshot(mvo_source)
    validate_mvo_wgs84(mvo_rows)
    resolver = ScottyResolver(
        session,
        cache_path=DEFAULT_RESOLUTION_CACHE,
        offline=args.offline,
    )
    output, audit = merge_catalogues(geonetz_nodes, mvo_rows, mvo_platforms, resolver, rename_map)
    write_ndjson(args.output, output)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Austria: {len(geonetz_nodes)} GeoNetz + {audit['added_count']} MVO additions "
        f"= {len(output)} stations; {audit['unresolved_count']} MVO candidates unresolved"
    )
    _build_requested_oebb_index(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
