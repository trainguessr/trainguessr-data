"""Country generation CLI orchestration for Austria."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import requests
from common.config import load_rename_map
from common.io import publish_nodes
from countries.austria.catalogue import merge_catalogues
from countries.austria.operators import build_oebb_operator_index, load_oebb_gtfs
from countries.austria.scotty import ScottyResolver
from countries.austria.settings import (
    CACHE_DIR,
    DEFAULT_AUDIT,
    DEFAULT_MVO_CACHE,
    DEFAULT_OEBB_OPERATOR_AUDIT,
    DEFAULT_OEBB_OPERATOR_INDEX,
    DEFAULT_OUTPUT,
    DEFAULT_RESOLUTION_CACHE,
    GEONETZ_ARCHIVE,
    GEONETZ_FILTERED,
)
from countries.austria.sources import (
    _adopt_legacy_cache,
    _download_geonetz,
    download_mvo_snapshot,
    load_geonetz_nodes,
    load_mvo_snapshot,
    validate_mvo_wgs84,
)


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
        "--cache",
        action="store_true",
        help="reuse cached GeoNetz/MVO inputs and SCOTTY resolutions when available",
    )
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
    if not args.cache and not args.offline:
        # A normal generation is a clean refresh. Cache reuse is always opt-in.
        for cached in (GEONETZ_FILTERED, GEONETZ_ARCHIVE, DEFAULT_MVO_CACHE, DEFAULT_RESOLUTION_CACHE):
            cached.unlink(missing_ok=True)
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
    publish_nodes(args.output, output)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Austria: {len(geonetz_nodes)} GeoNetz + {audit['added_count']} MVO additions "
        f"= {len(output)} stations; {audit['unresolved_count']} MVO candidates unresolved"
    )
    _build_requested_oebb_index(args)
    return 0
