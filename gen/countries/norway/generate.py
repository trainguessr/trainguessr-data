#!/usr/bin/env python3
"""Generate Norwegian railway stop places from Entur's National Stop Register."""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from common.config import (
    load_exclusion_rules, load_rename_id_rules, load_rename_map,
    require_reviewed_identity,
)
from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file
from common.validate import validate_nodes

ENDPOINT = "https://api.entur.io/stop-places/v1/read/stop-places"
OUTPUT = ROOT / "nodes" / "nodes-norway.json"
LOOKUP_OUTPUT = ROOT / "lookup" / "lookup-norway.json"
CACHE_SOURCE = ROOT / "cache" / "norway" / "stop-places.json"
DEFAULT_CLIENT_NAME = "trainguessr-data"
_CLIENT_NAME_RE = re.compile(r"^[a-z0-9_]+-[a-z0-9_-]+$")


def _client_name() -> str:
    value = str(os.getenv("ENTUR_CLIENT_NAME", DEFAULT_CLIENT_NAME)).strip().casefold()
    return value if _CLIENT_NAME_RE.fullmatch(value) else DEFAULT_CLIENT_NAME


def load_stop_places(path: Path | None = None, *, use_cache: bool = False) -> list[dict[str, Any]]:
    if path is not None:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError("Saved Entur stop-place response must be an array")
        return [row for row in payload if isinstance(row, dict)]
    if use_cache:
        path = require_cached_file(CACHE_SOURCE, "Entur stop-place data")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path}: expected a station list")
        return [row for row in payload if isinstance(row, dict)]

    rows: list[dict[str, Any]] = []
    skip = 0
    page_size = 1000
    headers = {
        "Accept": "application/json",
        "ET-Client-Name": _client_name(),
        "User-Agent": "trainguessr-data/norway-stations",
    }
    while True:
        response = requests.get(
            ENDPOINT,
            params={
                "count": page_size,
                "skip": skip,
                "transportModes": "RAIL",
                "stopPlaceType": "RAIL_STATION",
            },
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Entur stop-place response must be an array")
        page = [row for row in payload if isinstance(row, dict)]
        rows.extend(page)
        if len(page) < page_size:
            break
        skip += len(page)
    save_source_file(CACHE_SOURCE, json.dumps(rows, ensure_ascii=False).encode("utf-8"))
    return rows


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("text") or "").strip()
    return str(value or "").strip()


def _is_active_rail_stop(stop: dict[str, Any]) -> bool:
    status = str(stop.get("status_BasicModificationDetailsGroup") or stop.get("status") or "ACTIVE").upper()
    if status not in {"", "ACTIVE"}:
        return False
    stop_type = str(stop.get("stopPlaceType") or "").upper()
    if stop_type and stop_type != "RAIL_STATION":
        return False
    mode = str(stop.get("transportMode") or "").upper()
    if mode in {"RAIL", "INTERCITY_RAIL"}:
        return True
    modes = stop.get("transportModes") or []
    if isinstance(modes, str):
        modes = [modes]
    return any(str(item).upper() in {"RAIL", "INTERCITY_RAIL"} for item in modes)


def _uic_code(stop: dict[str, Any]) -> str:
    """The UIC code Entur publishes in the stop place's keyList, if well formed."""
    values = (stop.get("keyList") or {}).get("keyValue") or []
    if isinstance(values, dict):
        values = [values]
    codes = {str(item.get("value") or "").strip() for item in values if item.get("key") == "uicCode"}
    return codes.pop() if len(codes) == 1 and re.fullmatch(r"\d{7}", next(iter(codes))) else ""


def _in_norway(stop: dict[str, Any]) -> bool:
    """Entur places Norwegian stops in a Kartverket (KVE) municipality."""
    ref = str((stop.get("topographicPlaceRef") or {}).get("ref") or "")
    return ref.startswith("KVE:")


def build_nodes(stops: list[dict[str, Any]], lookup: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Norwegian stop places; Entur's stops abroad go to ``lookup`` when given."""
    excluded = load_exclusion_rules("norway")
    rename_by_name = load_rename_map("norway")
    rename_id_rules = load_rename_id_rules("norway")
    rename_by_id = {station_id: str(rule["to"]) for station_id, rule in rename_id_rules.items()}
    result: dict[str, dict[str, Any]] = {}
    abroad: dict[str, dict[str, Any]] = {}
    for stop in stops:
        if not _is_active_rail_stop(stop):
            continue
        station_id = str(stop.get("id") or "").strip()
        if not station_id.startswith("NSR:StopPlace:"):
            continue
        source_name = _text(stop.get("name"))
        foreign = not _in_norway(stop)
        rule = excluded.get(station_id)
        if rule is not None and not foreign:
            continue
        if station_id in rename_id_rules:
            require_reviewed_identity(
                {"expected_name": rename_id_rules[station_id]["from"]},
                source_name,
                context=f"norway rename:{station_id}",
            )
        name = source_name if foreign else (
            rename_by_id.get(station_id) or rename_by_name.get(source_name) or source_name)
        location = (stop.get("centroid") or {}).get("location") or {}
        lat = location.get("latitude")
        lon = location.get("longitude")
        if not name or lat in (None, "") or lon in (None, ""):
            continue
        tags = {
            "name": name,
            "transport_mode": "rail",
            "stop_place_type": "railStation",
            "public_code": str(stop.get("publicCode") or "").strip(),
            "rail_submode": str(stop.get("railSubmode") or "").strip().casefold(),
            "source": "Entur NSR",
            "uic_ref": _uic_code(stop),
        }
        tags = {key: value for key, value in tags.items() if value}
        (abroad if foreign else result)[station_id] = {
            "type": "node",
            "id": station_id,
            "lat": float(lat),
            "lon": float(lon),
            "tags": tags,
            "category": "norway_all",
        }
    # A UIC code published on two stop places identifies neither.
    claims = Counter(row["tags"].get("uic_ref") for row in (*result.values(), *abroad.values()))
    for row in (*result.values(), *abroad.values()):
        tags = row["tags"]
        if tags.get("uic_ref") and claims[tags["uic_ref"]] > 1:
            del tags["uic_ref"]
        elif tags.get("uic_ref"):
            tags.update(uic_granularity="stop", uic_crosswalk_source="Entur NSR keyList uicCode")
    if lookup is not None:
        lookup.extend(sorted(abroad.values(), key=lambda row: (str(row["tags"]["name"]).casefold(), str(row["id"]))))
    return sorted(result.values(), key=lambda row: (str(row["tags"]["name"]).casefold(), str(row["id"])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="saved Entur /stop-places response")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    lookup: list[dict[str, Any]] = []
    nodes = build_nodes(load_stop_places(args.input, use_cache=args.cache), lookup)
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    publish_nodes(OUTPUT, nodes)
    LOOKUP_OUTPUT.parent.mkdir(exist_ok=True)
    publish_nodes(LOOKUP_OUTPUT, lookup)
    print(f"Wrote {len(nodes)} Norwegian railway stop places to {OUTPUT}")
    print(f"Wrote {len(lookup)} stop places abroad to {LOOKUP_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
