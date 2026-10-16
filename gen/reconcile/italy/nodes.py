"""Reviewed node edits and report loading for Italian providers."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from common.config import load_excluded_ids, load_rename_map
from common.io import ROOT, load_ndjson, publish_nodes
from common.validate import validate_nodes
from reconcile.italy.decisions import save_config
from reconcile.italy.settings import OPERATOR_NAMES, REVIEW_STATUSES


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


def update_node_name(operator: str, station_id: str, name: str) -> None:
    path = node_path(operator)
    rows = load_ndjson(path)
    for node in rows:
        if str(node.get("id")) == station_id:
            node.setdefault("tags", {})["name"] = name
            errors = validate_nodes(rows)
            if errors:
                raise ValueError("; ".join(errors))
            publish_nodes(path, rows)
            return
    raise ValueError(f"{operator}: station {station_id} is not in {path}")


def remove_node(operator: str, station_id: str) -> None:
    path = node_path(operator)
    rows = load_ndjson(path)
    kept = [row for row in rows if str(row.get("id")) != station_id]
    if len(kept) != len(rows):
        publish_nodes(path, kept)


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
        publish_nodes(path, nodes)
