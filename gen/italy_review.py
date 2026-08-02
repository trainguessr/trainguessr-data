#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

from common.config import load_country_config, load_excluded_ids, load_rename_map
from common.io import ROOT, load_ndjson, write_ndjson
from common.validate import validate_nodes


OPERATORS = ("fn", "tt", "fer", "eav", "rfi", "fse")
OPERATOR_NAMES = {
    "fn": "Ferrovienord",
    "tt": "Trentino Trasporti",
    "fer": "Ferrovie Emilia Romagna",
    "eav": "Ente Autonomo Volturno",
    "rfi": "RFI",
    "fse": "Ferrovie del Sud Est",
}
REVIEW_STATUSES = {
    "missing_coordinates",
    "reviewed_only_retained",
    "matched_name_difference",
    "manual_reviewed",
    "gtfs_name_missing",
    "excluded_or_unresolved",
}


def config_path() -> Path:
    return ROOT / "excludes" / "italy.json"


def save_config(config: dict[str, Any]) -> None:
    config_path().write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def node_path(operator: str) -> Path:
    return ROOT / "nodes" / f"nodes-italy-{operator}.json"


def load_review_rows(operator: str) -> list[dict[str, str]]:
    report = ROOT / "cache" / "italy" / operator / "reports" / "audit.csv"
    rows: list[dict[str, str]] = []
    if report.is_file():
        with report.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                status = str(row.get("status", ""))
                if status not in REVIEW_STATUSES:
                    continue
                if status == "excluded_or_unresolved":
                    status = "missing_coordinates"
                rows.append({
                    "id": str(row.get("id", "")),
                    "status": status,
                    "source_name": str(row.get("source_name") or row.get("name") or ""),
                    "reviewed_name": str(row.get("reviewed_name") or row.get("name") or ""),
                    "details": str(row.get("details") or row.get("reason") or ""),
                })

    if operator == "tt":
        gtfs = ROOT / "cache" / "italy" / "tt" / "reports" / "gtfs.csv"
        if gtfs.is_file():
            with gtfs.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("status") != "review_name_in_gtfs":
                        continue
                    rows.append({
                        "id": str(row.get("id", "")),
                        "status": "gtfs_name_missing",
                        "source_name": "",
                        "reviewed_name": str(row.get("reviewed_name", "")),
                        "details": "no exact normalized name in current GTFS",
                    })
    return rows


def review_key(operator: str, row: dict[str, str]) -> tuple[str, ...]:
    return (
        operator,
        row["id"],
        row["status"],
        row["source_name"],
        row["reviewed_name"],
    )


def saved_review_keys(config: dict[str, Any]) -> set[tuple[str, ...]]:
    return {
        (
            str(row.get("operator", "")),
            str(row.get("id", "")),
            str(row.get("status", "")),
            str(row.get("source_name", "")),
            str(row.get("reviewed_name", "")),
        )
        for row in config.get("reviews", [])
    }


def remember(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
    decision: str,
    *,
    save: bool = True,
) -> None:
    reviews = config.setdefault("reviews", [])
    key = review_key(operator, row)
    reviews[:] = [
        saved for saved in reviews
        if (
            str(saved.get("operator", "")),
            str(saved.get("id", "")),
            str(saved.get("status", "")),
            str(saved.get("source_name", "")),
            str(saved.get("reviewed_name", "")),
        ) != key
    ]
    reviews.append({
        "operator": operator,
        "id": row["id"],
        "status": row["status"],
        "source_name": row["source_name"],
        "reviewed_name": row["reviewed_name"],
        "decision": decision,
    })
    if save:
        save_config(config)


def update_node_name(operator: str, station_id: str, name: str) -> None:
    path = node_path(operator)
    rows = load_ndjson(path)
    for node in rows:
        if str(node.get("id")) == station_id:
            node.setdefault("tags", {})["name"] = name
            errors = validate_nodes(rows)
            if errors:
                raise ValueError("; ".join(errors))
            write_ndjson(path, rows)
            return
    raise ValueError(f"{operator}: station {station_id} is not in {path}")


def remove_node(operator: str, station_id: str) -> None:
    path = node_path(operator)
    rows = load_ndjson(path)
    kept = [row for row in rows if str(row.get("id")) != station_id]
    if len(kept) != len(rows):
        write_ndjson(path, kept)


def exclude_station(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
) -> None:
    excluded = config.setdefault("excluded", [])
    if row["id"] not in load_excluded_ids("italy", operator):
        excluded.append({
            "operator": operator,
            "id": row["id"],
            "name": row["source_name"] or row["reviewed_name"],
            "reason": "excluded_during_interactive_review",
        })
    save_config(config)
    remove_node(operator, row["id"])


def add_coordinates(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
    lat: float,
    lon: float,
) -> None:
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("coordinates are outside the valid range")
    manual = config.setdefault("manual_stations", [])
    manual[:] = [
        saved for saved in manual
        if not (
            str(saved.get("operator", "")) == operator
            and str(saved.get("id", "")) == row["id"]
        )
    ]
    name = load_rename_map("italy", operator).get(
        row["source_name"], row["source_name"]
    )
    manual.append({
        "operator": operator,
        "id": row["id"],
        "name": name,
        "lat": lat,
        "lon": lon,
        "reason": "coordinates_entered_during_interactive_review",
    })
    save_config(config)

    path = node_path(operator)
    nodes = load_ndjson(path)
    if not any(str(node.get("id")) == row["id"] for node in nodes):
        station_id: str | int = row["id"]
        if operator in {"eav", "rfi"} and row["id"].isdigit():
            station_id = int(row["id"])
        nodes.append({
            "type": "node",
            "id": station_id,
            "lat": lat,
            "lon": lon,
            "tags": {
                "name": name,
                "operator": OPERATOR_NAMES[operator],
            },
            "category": f"italy_{operator}",
        })
        errors = validate_nodes(nodes)
        if errors:
            raise ValueError("; ".join(errors))
        write_ndjson(path, nodes)


def prompt_coordinates() -> tuple[float, float] | None:
    value = input("Coordinates as latitude,longitude or d to defer: ").strip()
    if value.lower() == "d":
        return None
    try:
        lat_text, lon_text = value.split(",", 1)
        return float(lat_text.strip()), float(lon_text.strip())
    except ValueError:
        print("Enter two numbers separated by a comma.")
        return prompt_coordinates()


def review_operator(operator: str) -> int:
    config = load_country_config("italy")
    saved = saved_review_keys(config)
    rows = [
        row for row in load_review_rows(operator)
        if review_key(operator, row) not in saved
    ]
    excluded = load_excluded_ids("italy", operator)
    rows = [row for row in rows if row["id"] not in excluded]
    if not rows:
        print(f"{operator.upper()}: no new review items")
        return 0

    priority = {
        "missing_coordinates": 0,
        "manual_reviewed": 1,
        "reviewed_only_retained": 2,
        "gtfs_name_missing": 3,
        "matched_name_difference": 4,
    }
    rows.sort(key=lambda row: (priority[row["status"]], row["id"]))
    print(f"{operator.upper()}: {len(rows)} new review items")

    for index, row in enumerate(rows):
        name = row["source_name"] or row["reviewed_name"]
        print(f"\n[{row['status']}] {row['id']} {name}")
        if row["source_name"] and row["reviewed_name"] and row["source_name"] != row["reviewed_name"]:
            print(f"Source:   {row['source_name']}")
            print(f"Reviewed: {row['reviewed_name']}")
        if row["details"]:
            print(row["details"])

        if row["status"] == "missing_coordinates":
            choice = input("[c]oordinates, [e]xclude, [d]efer, [q]uit: ").strip().lower()
            if choice == "c":
                coordinates = prompt_coordinates()
                if coordinates is not None:
                    add_coordinates(config, operator, row, *coordinates)
                    remember(config, operator, row, "added_coordinates")
            elif choice == "e":
                exclude_station(config, operator, row)
                remember(config, operator, row, "excluded")
            elif choice == "q":
                return 1
            continue

        if row["status"] == "matched_name_difference":
            choice = input("[k]eep reviewed, use [s]ource, keep [a]ll names, [d]efer, [q]uit: ").strip().lower()
            if choice == "k":
                remember(config, operator, row, "keep_reviewed_name")
            elif choice == "s":
                update_node_name(operator, row["id"], row["source_name"])
                remember(config, operator, row, "use_source_name")
            elif choice == "a":
                for remaining in rows[index:]:
                    if remaining["status"] == "matched_name_difference":
                        remember(
                            config,
                            operator,
                            remaining,
                            "keep_reviewed_name",
                            save=False,
                        )
                save_config(config)
                print("Saved all remaining name confirmations.")
                return 0
            elif choice == "q":
                return 1
            continue

        if row["status"] == "reviewed_only_retained":
            choice = input("[k]eep, [e]xclude, [d]efer, [q]uit: ").strip().lower()
            if choice == "k":
                remember(config, operator, row, "keep_reviewed_station")
            elif choice == "e":
                exclude_station(config, operator, row)
                remember(config, operator, row, "excluded")
            elif choice == "q":
                return 1
            continue

        choice = input("[c]onfirm, [d]efer, [q]uit: ").strip().lower()
        if choice == "c":
            remember(config, operator, row, "confirmed")
        elif choice == "q":
            return 1
    return 0


def review_after_generation(operator: str) -> None:
    if not sys.stdin.isatty() or os.environ.get("TRAINGUESSR_SKIP_REVIEW") == "1":
        return
    review_operator(operator)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review new Italian provider records")
    parser.add_argument("operator", choices=[*OPERATORS, "all"])
    args = parser.parse_args()
    operators = OPERATORS if args.operator == "all" else (args.operator,)
    for operator in operators:
        if review_operator(operator):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
