"""Source acquisition and parsing for Austria."""
from __future__ import annotations

import csv
import html
import io
import json
import logging as log
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
import requests
from common.io import ROOT
from countries.austria.identity import _float
from countries.austria.settings import (
    AUSTRIA_CACHE,
    CACHE_DIR,
    DEFAULT_MVO_CACHE,
    GEONETZ_ARCHIVE,
    GEONETZ_FILTERED,
    GEONETZ_TEMP,
    GEONETZ_URL,
    MVO_CATALOGUE_URL,
    MVO_DATASETS_URL,
    MVO_FILE_URL,
    MVO_METADATA_URL,
    MVO_TOKEN_URL,
    _MVO_SAMPLE_RE,
)


def _cache_age(path: Path) -> str:
    seconds = max(0, int((datetime.now().timestamp() - path.stat().st_mtime)))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


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
