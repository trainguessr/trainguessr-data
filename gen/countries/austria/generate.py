"""Country generation CLI orchestration for Austria."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import requests
from common.config import load_rename_map
from common.io import add_cache_flag, publish_nodes, require_cached_file, load_ndjson
from countries.austria.catalogue import merge_catalogues, preserve_sta_tags
from countries.austria.operators import build_oebb_operator_index, load_oebb_gtfs
from countries.austria.scotty import ScottyResolver
from countries.austria.settings import (
    DEFAULT_AUDIT,
    DEFAULT_MVO_CACHE,
    DEFAULT_OEBB_OPERATOR_AUDIT,
    DEFAULT_OEBB_OPERATOR_INDEX,
    DEFAULT_OUTPUT,
    DEFAULT_RESOLUTION_CACHE,
)
from countries.austria.sources import (
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
    parser.add_argument("--mvo-sample", action="store_true",
                        help="explicitly use the public MVO sample (not a production freshness proof)")
    add_cache_flag(parser)
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


def report_unverified_mvo_stops(audit: dict[str, Any]) -> None:
    """Explain omitted rail candidates on stdout, not as an unexplained JSON task.

    This is a coverage warning, not a failed publication or an interactive
    review request. Evidence is still saved as JSON for reproducibility.
    """
    skipped = audit.get("unresolved", [])
    if not skipped:
        return
    print(
        f"Austria: {len(skipped)} MVO station records do not have a verified "
        "ÖBB station ID, so they were not added to the ÖBB station file."
    )
    reasons = {
        "provider_identity_missing": "railway stop kept separately; no working SCOTTY ID",
        "missing_cached_verification": "no saved successful station check",
        "no_unique_scotty_match": "no unique SCOTTY station match",
        "scotty_station_verification_failed": "SCOTTY board verification failed",
        "scotty_station_name_mismatch": "SCOTTY reports a different station name",
    }
    for row in skipped:
        name = " ".join(str(row.get("name") or "unnamed stop").split())
        ifopt = " ".join(str(row.get("ifopt_id") or "unknown IFOPT").split())
        reason = reasons.get(str(row.get("reason")), "identity not confirmed")
        if row.get("reason") == "provider_identity_missing" and row.get("operator"):
            reason += f" ({row['operator']})"
        print(f"  - {name} [{ifopt}]: {reason}")
    print(
        "Unmapped railway stops are kept in overrides/austria-unmapped-stations.csv. "
        "They are not exclusions. Do not substitute nearby stops or invent provider IDs."
    )


TRAINLINE_TAGS = {"uic": "trainline_uic_ref", "db_id": "db_station_id"}


def apply_trainline_identifiers(nodes) -> int:
    """Add the UIC/DB IDs Trainline publishes on the same row as an ÖBB ID."""
    from common.trainline import add_station_identifiers
    return add_station_identifiers(nodes, country="AT", key="obb_id", tags_by_field=TRAINLINE_TAGS)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.oebb_operator_index_only:
        if not args.oebb_gtfs:
            raise SystemExit("--oebb-operator-index-only requires --oebb-gtfs")
        _build_requested_oebb_index(args)
        return 0

    session = requests.Session()
    rename_map = load_rename_map("austria")
    # Never delete a working source snapshot before replacement is available.
    # GeoNetz is a dated, static archive, and exact SCOTTY resolutions remain
    # guarded by the existing provider identity checks.
    if args.cache:
        mvo_source = args.mvo_input or require_cached_file(DEFAULT_MVO_CACHE, "MVO station data")
        if not mvo_source.is_file():
            raise SystemExit(f"Saved MVO station data is missing: {mvo_source}")
        from countries.austria.sources import _validate_mvo_archive
        _validate_mvo_archive(mvo_source)
    else:
        if args.mvo_input:
            mvo_source = args.mvo_input
        else:
            try:
                mvo_source = download_mvo_snapshot(session, allow_public_sample=args.mvo_sample)
            except (requests.RequestException, ValueError) as exc:
                raise SystemExit(
                    f"Austria MVO source unavailable: {exc}. "
                    "Existing nodes and cached source snapshots were preserved. "
                    "Register and accept the official MVO licence, then configure "
                    "MVO_USERNAME/MVO_PASSWORD; alternatively use --cache, "
                    "--mvo-input PATH or opt into the sample with --mvo-sample."
                ) from exc
    mvo_rows, mvo_platforms = load_mvo_snapshot(mvo_source)
    validate_mvo_wgs84(mvo_rows)
    geonetz_source = _download_geonetz(session, allow_download=not args.cache)
    geonetz_nodes = load_geonetz_nodes(geonetz_source, rename_map)
    resolver = ScottyResolver(
        session,
        cache_path=DEFAULT_RESOLUTION_CACHE,
        offline=args.cache,
    )
    output, audit = merge_catalogues(geonetz_nodes, mvo_rows, mvo_platforms, resolver, rename_map)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.cache and any(row["reason"] == "missing_cached_verification" for row in audit["unresolved"]):
        raise ValueError("Saved station checks are missing. Run once without --cache to save successful SCOTTY checks. The station file was not changed.")
    if args.output.is_file():
        output = preserve_sta_tags(output, load_ndjson(args.output))
    applied = apply_trainline_identifiers(output)
    print(f"Trainline UIC/DB identifiers on {applied} ÖBB stations")
    publish_nodes(args.output, output)
    print(f"OK | austria | {len(output)} station identities; "
          f"{len(geonetz_nodes)} GeoNetz plus {audit['added_count']} MVO additions")
    report_unverified_mvo_stops(audit)
    _build_requested_oebb_index(args)
    return 0
