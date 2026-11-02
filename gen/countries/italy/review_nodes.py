"""Reviewed node edits and report loading for Italian providers."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from common.config import load_excluded_ids, load_rename_map
from common.io import ROOT, load_ndjson
from countries.italy.review_decisions import save_config
from countries.italy.review_settings import AUDIT_STATUS_CODES, REVIEW_STATUSES


def node_path(operator: str) -> Path:
    return ROOT / "nodes" / f"nodes-italy-{operator}.json"


def load_review_rows(operator: str) -> list[dict[str, str]]:
    report = ROOT / "cache" / "italy" / operator / "reports" / "audit.csv"
    rows: list[dict[str, str]] = []
    if report.is_file():
        with report.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                status = str(row.get("status", ""))
                status = AUDIT_STATUS_CODES.get(status, status)
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
                    "lat": str(row.get("lat") or ""),
                    "lon": str(row.get("lon") or ""),
                })

    if operator == "tt":
        gtfs = ROOT / "cache" / "italy" / "tt" / "reports" / "gtfs.csv"
        if gtfs.is_file():
            with gtfs.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("status") not in {"review_name_in_gtfs", "Name not in timetable"}:
                        continue
                    rows.append({
                        "id": str(row.get("id", "")),
                        "status": "gtfs_name_missing",
                        "source_name": "",
                        "reviewed_name": str(row.get("reviewed_name", "")),
                        "details": "This name does not appear in the current timetable.",
                    })
    return rows


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
            "reason": "Excluded after checking this station.",
        })
    save_config(config)


def add_coordinates(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
    lat: float,
    lon: float,
) -> None:
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Coordinates must be within the valid latitude and longitude ranges.")
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
        "reason": "Coordinates checked during station review.",
    })
    save_config(config)


def add_native_id(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
    station_id: str,
) -> None:
    """Save a manually checked FSE station with its exact ViaggiaTreno ID."""
    import re

    station_id = station_id.strip()
    if operator != "fse" or not re.fullmatch(r"S\d{5}", station_id):
        raise ValueError("Enter the exact ViaggiaTreno station ID, for example S13123.")
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, ValueError) as exc:
        raise ValueError("This station has no saved coordinates.") from exc
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Check this station's coordinates.")

    name = row["source_name"].strip()
    if not name:
        raise ValueError("This station has no saved name.")
    existing_nodes = load_ndjson(node_path(operator))
    for node in existing_nodes:
        if str(node.get("id")) == station_id:
            current_name = str(node.get("tags", {}).get("name", ""))
            if current_name.strip().casefold() != name.casefold():
                raise ValueError(
                    f"Check station ID {station_id}. It is already used for {current_name}."
                )

    manual = config.setdefault("manual_stations", [])
    for saved in manual:
        if saved.get("operator") == operator and str(saved.get("id")) == station_id:
            if str(saved.get("name", "")).strip().casefold() != name.casefold():
                raise ValueError(f"Check station ID {station_id}. It is already saved for another station.")
            return

    manual.append({
        "operator": operator,
        "id": station_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "reason": "Provider ID checked during station review.",
    })
    save_config(config)
