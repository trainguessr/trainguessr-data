"""Command-line review orchestration for Germany."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import requests
from reconcile.germany.db import (
    DbProbe,
    load_catalogue_index,
    load_generated_identity_index,
    load_station_snapshot,
)
from reconcile.germany.io import _read_json, _write_bytes, _write_json, ensure_boundary, ensure_gtfs_archive
from reconcile.germany.settings import (
    AUDIT_FILE,
    BOUNDARY_CACHE,
    CATALOGUE,
    DB_SNAPSHOT,
    DB_WILDCARD_URL,
    DEFAULT_PLAN_SLOT,
    GTFS_ARCHIVE,
    NODES,
    REQUEST_HEADERS,
)
from reconcile.germany.stale import _stale_records, fetch_stale_osm
from reconcile.germany.workflow import reconcile


def _default_plan_slots() -> list[str]:
    # Keep the review date explicit and deterministic for the current source
    # snapshot; callers can supply another date/hour through --plan-slot.
    return [DEFAULT_PLAN_SLOT]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs-input", type=Path, default=GTFS_ARCHIVE)
    parser.add_argument("--boundary-input", type=Path, default=BOUNDARY_CACHE)
    parser.add_argument("--db-input", type=Path, default=DB_SNAPSHOT)
    parser.add_argument("--catalogue-input", type=Path, default=CATALOGUE)
    parser.add_argument("--nodes-input", type=Path, default=NODES)
    parser.add_argument("--output", type=Path, default=AUDIT_FILE)
    parser.add_argument("--plan-slot", action="append", help="DB plan date/hour, e.g. 260828/13; repeatable")
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--refresh", action="store_true", help="refresh static source caches")
    parser.add_argument("--refresh-probes", action="store_true", help="ignore cached DB station/plan probe results")
    parser.add_argument("--probe-stale-osm", action="store_true", help="query/cache bounded OSM/ORM evidence for stale IDs")
    parser.add_argument("--refresh-stale-osm", action="store_true", help="refresh the stale-ID OSM/ORM capture")
    parser.add_argument("--osm-delay", type=float, default=1.0)
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    with requests.Session() as session:
        gtfs = ensure_gtfs_archive(args.gtfs_input, session=session, refresh=args.refresh)
        boundary = ensure_boundary(args.boundary_input, session=session, refresh=args.refresh)
        if not args.db_input.is_file():
            if not (os.getenv("DB_API_TIMETABLES_CLIENTID") or os.getenv("DB_API_RISBOARDS_CLIENTID")):
                raise SystemExit(f"Missing current DB XML snapshot and DB credentials: {args.db_input}")
            response = session.get(
                DB_WILDCARD_URL,
                headers={
                    **REQUEST_HEADERS,
                    "DB-Client-ID": os.getenv("DB_API_TIMETABLES_CLIENTID") or os.getenv("DB_API_RISBOARDS_CLIENTID", ""),
                    "DB-Api-Key": os.getenv("DB_API_TIMETABLES_SECRET") or os.getenv("DB_API_RISBOARDS_CLIENTSECRET", ""),
                },
                timeout=(5.0, 120.0),
            )
            response.raise_for_status()
            _write_bytes(args.db_input, response.content)
        previous = _read_json(args.output) if args.output.is_file() else {}
        plan_slots = args.plan_slot or _default_plan_slots()
        db_probe = DbProbe(
            session=session,
            delay=args.delay,
            refresh=args.refresh_probes,
            plan_slots=plan_slots,
        )
        station_records, namespace = load_station_snapshot(args.db_input)
        generated = load_generated_identity_index(args.nodes_input)
        catalogue = load_catalogue_index(args.catalogue_input)
        stale = _stale_records(catalogue, generated, namespace)
        osm_payload = None
        if args.probe_stale_osm:
            osm_payload = fetch_stale_osm(
                stale,
                session=session,
                refresh=args.refresh_stale_osm,
                delay=args.osm_delay,
            )
        audit = reconcile(
            archive_path=gtfs,
            boundary_path=boundary,
            station_snapshot_path=args.db_input,
            catalogue_path=args.catalogue_input,
            nodes_path=args.nodes_input,
            previous_audit=previous,
            db_probe=db_probe,
            probe_stale_osm=osm_payload,
            progress=args.progress,
        )
        _write_json(args.output, audit)
    print(
        f"Germany reconciliation: {audit['counts']['candidate_records']} candidates; "
        f"{audit['counts']['candidate_statuses']}"
    )
    print(
        f"Stale cache IDs: {audit['counts']['stale_records']}; "
        f"{audit['counts']['stale_statuses']}"
    )
    print(f"Wrote {args.output}")
    return 0
