#!/usr/bin/env python3
"""Temporary deterministic rebuilds for manually assembled Italian datasets.

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
``missing_coordinates``.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import re
from pathlib import Path
from typing import Callable, Iterable

from common.config import load_country_config, load_excluded_ids
from common.io import ROOT, load_ndjson, write_csv
from common.normalize import normalize_name
from common.validate import validate_nodes
from common.manual_overrides import apply_coordinate_overrides, load_override_config


ITALY_CACHE = ROOT / "cache" / "italy"
COORDINATE_OVERRIDES = ROOT / "overrides" / "italy-coordinate-corrections.json"
OPERATOR_NAMES = {
    "fn": "Ferrovienord",
    "tt": "Trentino Trasporti",
    "fer": "Ferrovie Emilia Romagna",
    "eav": "Ente Autonomo Volturno",
    "rfi": "RFI",
}


def cache_path(operator: str, section: str, filename: str) -> Path:
    return ITALY_CACHE / operator / section / filename


def node_path(operator: str) -> Path:
    return ROOT / "nodes" / f"nodes-italy-{operator}.json"


def reviewed_nodes_path(operator: str) -> Path:
    """Use the tracked reviewed dataset, with cache as a bootstrap fallback."""
    committed = node_path(operator)
    if committed.exists():
        return committed

    cached = cache_path(operator, "reviewed", "nodes.json")
    if cached.exists():
        return cached

    raise FileNotFoundError(
        f"No reviewed seed exists for {operator}. Expected either:\n"
        f"  {cached}\n"
        f"or:\n"
        f"  {committed}"
    )


def audit_report_path(operator: str) -> Path:
    return cache_path(operator, "reports", "audit.csv")


def require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {description}:\n"
            f"  {path}\n\n"
            "Populate cache/italy first using the documented download or "
            "migration procedure."
        )
    return path


def parse_catalog_csv(
    path: Path,
    *,
    required_columns: Iterable[str] = ("id", "name"),
) -> list[dict[str, str]]:
    """Read a normalized provider catalog CSV."""

    require_file(path, "normalized station catalog")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")

        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"{path}: missing required columns: {', '.join(sorted(missing))}"
            )

        rows: list[dict[str, str]] = []

        for line_number, row in enumerate(reader, 2):
            station_id = str(row.get("id", "")).strip()
            name = str(row.get("name", "")).strip()

            if not station_id or not name:
                raise ValueError(
                    f"{path}:{line_number}: station id and name are required"
                )

            normalized = {
                key: str(value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            normalized["id"] = station_id
            normalized["name"] = name
            rows.append(normalized)

    return rows


def parse_fn() -> list[dict[str, str]]:
    return parse_catalog_csv(
        cache_path("fn", "derived", "stations.csv")
    )


def parse_tt() -> list[dict[str, str]]:
    path = require_file(
        cache_path("tt", "raw", "legacy-station-map.html"),
        "TT legacy station-ID map",
    )

    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(r"\s+", " ", name).strip(),
        }
        for name, station_id in re.findall(
            r'([^<\n]+)<div\s+id=["\']St(\d+)["\']',
            text,
            flags=re.IGNORECASE,
        )
    ]

    if not rows:
        raise ValueError(
            f"{path}: no TT station records were found; "
            "the provider page format may have changed"
        )

    return rows


def parse_fer() -> list[dict[str, str]]:
    path = cache_path("fer", "derived", "stations.csv")
    require_file(path, "normalized station catalog")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        first_row = next(csv.reader(handle), [])

    if first_row[:2] == ["id", "name"]:
        return parse_catalog_csv(path)

    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), 1):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                raise ValueError(f"{path}:{line_number}: expected id,name,line_code")
            rows.append({
                "id": row[0].strip(),
                "name": row[1].strip(),
                "line_code": row[2].strip() if len(row) > 2 else "",
            })
    return rows


def parse_eav() -> list[dict[str, str]]:
    catalog = cache_path("eav", "derived", "stations.csv")
    if catalog.is_file():
        return parse_catalog_csv(catalog)

    path = require_file(
        cache_path("eav", "raw", "stations-page.html"),
        "EAV station selector page",
    )

    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(
                r"\s+",
                " ",
                re.sub(r"<.*?>", "", name, flags=re.DOTALL),
            ).strip(),
        }
        for station_id, name in re.findall(
            r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if station_id.strip()
        and re.sub(r"<.*?>", "", name, flags=re.DOTALL).strip()
    ]

    if not rows:
        raise ValueError(
            f"{path}: no EAV station records were found; "
            "the provider page format may have changed"
        )

    return rows


def find_rfi_station_page() -> Path:
    """Use the canonical RFI page or the newest retained snapshot."""

    canonical = cache_path("rfi", "raw", "stations-page.html")
    if canonical.is_file():
        return canonical

    snapshots = sorted(
        (ITALY_CACHE / "rfi" / "raw" / "snapshots").glob("*.html")
    )

    if snapshots:
        return snapshots[-1]

    raise FileNotFoundError(
        "Missing RFI station page. Expected either:\n"
        f"  {canonical}\n"
        "or at least one HTML file under:\n"
        f"  {ITALY_CACHE / 'rfi' / 'raw' / 'snapshots'}"
    )


def parse_rfi() -> list[dict[str, str]]:
    path = find_rfi_station_page()
    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(
                r"\s+",
                " ",
                re.sub(r"<.*?>", "", name, flags=re.DOTALL),
            ).strip(),
        }
        for station_id, name in re.findall(
            r"<option[^>]*value=[\"']?([^\"' >]+)[\"']?[^>]*>"
            r"(.*?)</option>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if station_id.strip()
        and re.sub(r"<.*?>", "", name, flags=re.DOTALL).strip()
    ]

    if not rows:
        raise ValueError(
            f"{path}: no RFI station records were found; "
            "the provider page format may have changed"
        )

    return rows


PARSERS: dict[str, Callable[[], list[dict[str, str]]]] = {
    "fn": parse_fn,
    "tt": parse_tt,
    "fer": parse_fer,
    "eav": parse_eav,
    "rfi": parse_rfi,
}


def index_source_rows(
    operator: str,
    rows: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Index source rows without silently accepting duplicate provider IDs."""

    indexed: dict[str, dict[str, str]] = {}

    for row in rows:
        station_id = str(row.get("id", "")).strip()

        if not station_id:
            raise ValueError(f"{operator}: source catalog contains an empty ID")

        previous = indexed.get(station_id)

        if previous is not None and previous != row:
            raise ValueError(
                f"{operator}: duplicate source ID {station_id!r} has "
                f"conflicting records: {previous!r} and {row!r}"
            )

        indexed[station_id] = row

    return indexed


def write_preserving_seed(
    operator: str,
    seed_path: Path,
    output: list[dict],
) -> None:
    """Preserve unchanged reviewed records byte-for-byte where possible."""

    original_lines: dict[str, tuple[dict, str]] = {}

    for line_number, line in enumerate(
        seed_path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{seed_path}:{line_number}: invalid JSON: {exc}"
            ) from exc

        original_lines[str(row["id"])] = (row, line)

    target = node_path(operator)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output:
            original = original_lines.get(str(row["id"]))

            if original is not None and original[0] == row:
                handle.write(original[1])
            else:
                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )

            handle.write("\n")


def format_validation_issue(issue: object) -> str:
    message = getattr(issue, "message", None)
    code = getattr(issue, "code", None)
    index = getattr(issue, "index", None)

    parts = []

    if code:
        parts.append(str(code))

    if index is not None:
        parts.append(f"row {index}")

    if message:
        parts.append(str(message))

    return ": ".join(parts) if parts else str(issue)


def rebuild(
    operator: str,
    *,
    dry_run: bool = False,
) -> tuple[list[dict], list[dict]]:
    source_rows = PARSERS[operator]()
    source = index_source_rows(operator, source_rows)

    italy_config = load_country_config("italy")
    seed_path = reviewed_nodes_path(operator)
    seed_rows = load_ndjson(seed_path)
    seed_ids = {str(row["id"]) for row in seed_rows}
    for manual in italy_config.get("manual_stations", []):
        if manual.get("operator") != operator or str(manual.get("id")) in seed_ids:
            continue
        station_id: str | int = str(manual["id"])
        if operator in {"eav", "rfi"} and station_id.isdigit():
            station_id = int(station_id)
        seed_rows.append({
            "type": "node",
            "id": station_id,
            "lat": float(manual["lat"]),
            "lon": float(manual["lon"]),
            "tags": {
                "name": str(manual["name"]),
                "operator": OPERATOR_NAMES[operator],
            },
            "category": f"italy_{operator}",
        })
        seed_ids.add(str(station_id))

    excluded = {
        str(station_id)
        for station_id in load_excluded_ids("italy", operator)
    }
    excluded.update(
        str(review.get("id"))
        for review in italy_config.get("reviews", [])
        if review.get("operator") == operator
        and review.get("decision") == "excluded"
    )

    output: list[dict] = []
    audit: list[dict] = []

    expected_category = f"italy_{operator}"
    accepted_source_names = {
        (
            str(review.get("id", "")),
            str(review.get("source_name", "")),
            str(review.get("reviewed_name", "")),
        )
        for review in italy_config.get("reviews", [])
        if review.get("operator") == operator
        and review.get("status") == "matched_name_difference"
        and review.get("decision") == "use_source_name"
    }

    # Preserve reviewed order, coordinates and metadata. Provider data is
    # currently used only to verify identifiers and report name differences.
    for reviewed in seed_rows:
        station_id = str(reviewed["id"])

        if station_id in excluded:
            audit.append(
                {
                    "id": station_id,
                    "source_name": source.get(station_id, {}).get("name", ""),
                    "reviewed_name": reviewed.get("tags", {}).get("name", ""),
                    "status": "excluded",
                    "details": "listed in excludes/italy.json",
                }
            )
            continue

        node = copy.deepcopy(reviewed)

        if node.get("category") != expected_category:
            previous_category = node.get("category", "")
            node["category"] = expected_category

            if operator == "rfi":
                node.setdefault("tags", {})["operator"] = "RFI"

            category_detail = (
                f"category corrected from {previous_category!r} "
                f"to {expected_category!r}"
            )
        else:
            category_detail = ""

        output.append(node)

        source_row = source.get(station_id)
        reviewed_name = str(node.get("tags", {}).get("name", ""))

        if source_row is None:
            audit.append(
                {
                    "id": station_id,
                    "source_name": "",
                    "reviewed_name": reviewed_name,
                    "status": "reviewed_only_retained",
                    "details": (
                        "absent from current provider snapshot"
                        + (f"; {category_detail}" if category_detail else "")
                    ),
                }
            )
            continue

        source_name = str(source_row.get("name", ""))

        if (station_id, source_name, reviewed_name) in accepted_source_names:
            node.setdefault("tags", {})["name"] = source_name
            reviewed_name = source_name

        if normalize_name(source_name) == normalize_name(reviewed_name):
            status = "matched"
        else:
            status = "matched_name_difference"

        details = "provider ID match"

        if category_detail:
            details += f"; {category_detail}"

        audit.append(
            {
                "id": station_id,
                "source_name": source_name,
                "reviewed_name": reviewed_name,
                "status": status,
                "details": details,
            }
        )

    # Provider records not represented in the reviewed coordinate seed cannot
    # be added safely. Record them for manual coordinate review.
    for station_id, source_row in sorted(source.items()):
        if station_id in seed_ids:
            continue

        is_excluded = station_id in excluded

        audit.append(
            {
                "id": station_id,
                "source_name": source_row.get("name", ""),
                "reviewed_name": "",
                "status": "excluded" if is_excluded else "missing_coordinates",
                "details": (
                    "listed in excludes/italy.json"
                    if is_excluded
                    else "provider record has no reviewed coordinate match"
                ),
            }
        )

    override_config = load_override_config(COORDINATE_OVERRIDES)
    coordinate_overrides = [
        row for row in override_config.get("coordinate_overrides", [])
        if row.get("operator") == operator
    ]
    overridden_ids = apply_coordinate_overrides(
        output,
        coordinate_overrides,
        context=f"italy/{operator}",
    )
    if overridden_ids:
        for row in audit:
            if str(row.get("id")) in overridden_ids:
                details = str(row.get("details") or "")
                row["details"] = (
                    f"{details}; guarded coordinate override applied"
                    if details else "guarded coordinate override applied"
                )

    issues = validate_nodes(output)

    errors = [
        issue
        for issue in issues
        if getattr(issue, "level", "error") == "error"
    ]

    if errors:
        formatted = "; ".join(
            format_validation_issue(issue)
            for issue in errors
        )
        raise ValueError(f"{operator}: {formatted}")

    report = audit_report_path(operator)
    report.parent.mkdir(parents=True, exist_ok=True)

    write_csv(
        report,
        audit,
        [
            "id",
            "source_name",
            "reviewed_name",
            "status",
            "details",
        ],
    )

    if not dry_run:
        write_preserving_seed(operator, seed_path, output)

    return output, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operator",
        choices=[*PARSERS, "all"],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write audit reports but do not overwrite nodes/",
    )
    args = parser.parse_args()

    operators = (
        list(PARSERS)
        if args.operator == "all"
        else [args.operator]
    )

    for operator in operators:
        output, audit = rebuild(
            operator,
            dry_run=args.dry_run,
        )

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

        if not args.dry_run:
            from italy_review import review_after_generation
            review_after_generation(operator)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
