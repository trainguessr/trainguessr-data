"""Deterministic reviewed-coordinate rebuilds for Italian provider datasets.

Inputs are stored under::

    cache/italy/<operator>/
        raw/
        derived/
        reviewed/
        reports/

The generator reconciles provider station IDs with reviewed coordinate records,
validates the resulting dataset, and overwrites the corresponding file under
``nodes/``.

If ``cache/italy/<operator>/reviewed/nodes.json`` does not exist, the current
committed node dataset is used as the reviewed seed. This makes the first run
possible from a normal repository checkout.

No station is added from a provider catalog unless reviewed coordinates already
exist. Source-only records are written to the audit report as
``missing_coordinates`` unless an explicit review decision records that the
station is handled by another provider."""
from __future__ import annotations

import argparse
from typing import Callable
from common.config import load_country_config, load_exclusion_rules
from common.io import ROOT, load_ndjson
from common.manual_overrides import load_override_config
from countries.italy.reviewed.decisions import index_source_rows
from countries.italy.reviewed.paths import audit_report_path, reviewed_nodes_path, node_path
from countries.italy.reviewed.publication import write_reviewed_output
from countries.italy.reviewed.settings import COORDINATE_OVERRIDES
from countries.italy.reviewed.classification import classify_reviewed, apply_reviewed_coordinates, prepare_reviewed_seed
from countries.italy.reviewed.crosswalks import (
    apply_station_uic_crosswalks,
    load_station_uic_crosswalks,
)
from countries.italy.reviewed.sources import parse_eav, parse_fer, parse_fn, parse_rfi, parse_tt


PARSERS: dict[str, Callable[[], list[dict[str, str]]]] = {
    "fn": parse_fn,
    "tt": parse_tt,
    "fer": parse_fer,
    "eav": parse_eav,
    "rfi": parse_rfi,
}


def rebuild(operator: str, *, dry_run: bool = False) -> tuple[list[dict], list[dict]]:
    source = index_source_rows(operator, PARSERS[operator]())
    italy_config = load_country_config("italy")
    seed_path = reviewed_nodes_path(operator)
    seed_rows = load_ndjson(seed_path)
    seed_rows = prepare_reviewed_seed(operator, seed_rows, italy_config)
    exclusion_rules = load_exclusion_rules("italy", operator)
    output, audit = classify_reviewed(operator, source, seed_rows, italy_config, exclusion_rules)
    override_config = load_override_config(COORDINATE_OVERRIDES)
    coordinate_overrides = [
        row for row in override_config.get("coordinate_overrides", [])
        if row.get("operator") == operator
    ]
    apply_reviewed_coordinates(operator, output, audit, coordinate_overrides)
    apply_station_uic_crosswalks(operator, output, load_station_uic_crosswalks())
    write_reviewed_output(operator, seed_path, output, audit, dry_run=dry_run)
    return output, audit


def checked_rebuild(operator: str, *, dry_run: bool = False) -> tuple[list[dict], list[dict], int]:
    """Check every recorded decision before replacing the station file."""
    from common.io import publish_nodes
    from countries.italy.review import pending_review_rows

    output, audit = rebuild(operator, dry_run=True)
    pending = pending_review_rows(operator)
    if pending:
        labels = {
            "missing_native_id": "check station ID",
            "missing_coordinates": "check coordinates",
            "provider_scope_review": "check railway owner",
            "reviewed_only_retained": "not found in the new download; kept the old station",
            "matched_name_difference": "check station name",
            "manual_reviewed": "check station ID",
            "gtfs_name_missing": "name missing from timetable",
        }
        examples = ", ".join(
            f"{row['id']} ({labels.get(row['status'], 'check station')})"
            for row in pending[:5]
        )
        print(f"Check these {len(pending)} station details for {operator.upper()} "
              f"({examples}). The station file is unchanged. Run "
              f"python3 -m gen.countries italy review {operator}, then generate again.")
        return output, audit, 2
    if not dry_run:
        publish_nodes(node_path(operator), output)
    return output, audit, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operator",
        choices=[*PARSERS, "all"],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="check the result and save a report, but keep the station file unchanged",
    )
    args = parser.parse_args(argv)

    operators = (
        list(PARSERS)
        if args.operator == "all"
        else [args.operator]
    )

    for operator in operators:
        output, audit, status = checked_rebuild(operator, dry_run=args.dry_run)
        if status:
            return status

        review_count = sum(
            row["status"]
            in {
                "missing_coordinates",
                "reviewed_only_retained",
                "matched_name_difference",
            }
            for row in audit
        )

        action = "would write" if args.dry_run else "wrote"

        print(
            f"{operator.upper()}: {action} {len(output)} stations; "
            f"{review_count} review items; "
            f"audit: {audit_report_path(operator).relative_to(ROOT)}"
        )


    return 0
