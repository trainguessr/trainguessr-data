"""Explicit reviewed decision lookup for Italian providers."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from common.config import ITALY_DECISION_LABELS, ITALY_REVIEW_LABELS
from common.io import ROOT, write_csv


def config_path() -> Path:
    return ROOT / "overrides" / "exclusions" / "italy.csv"


def save_config(config: dict[str, Any]) -> None:
    exclusion_fields = [
        "operator", "id", "name", "reason", "source", "source_url", "osm_url",
        "osm_railway_url", "osm_bus_url", "viaggiatreno_url", "fal_url",
        "rfi_monitor_url", "definition_url", "wikipedia_url", "evidence_ref",
    ]
    direct_fields = set(exclusion_fields)
    exclusion_rows = []
    for row in config.get("excluded", []):
        item = {field: row.get(field, "") for field in direct_fields}
        nested_evidence = set(row) - direct_fields
        if nested_evidence and not item["evidence_ref"]:
            raise ValueError("Check the saved station evidence.")
        exclusion_rows.append(item)
    write_csv(config_path(), exclusion_rows, exclusion_fields)
    rows = []
    for row in config.get("renamed", []):
        rows.append({"record": "rename", **row})
    for row in config.get("manual_stations", []):
        item = {"record": "station", **row}
        if item.get("reason", "").startswith("coordinates_entered_during"):
            item["reason"] = "Coordinates entered during station review."
        rows.append(item)
    for row in config.get("reviews", []):
        status = row.get("status")
        decision = row.get("decision")
        if status not in ITALY_REVIEW_LABELS or decision not in ITALY_DECISION_LABELS:
            raise ValueError("Check the saved station review before saving it.")
        item = {"record": "review", **row}
        item["status"] = ITALY_REVIEW_LABELS[status]
        item["decision"] = ITALY_DECISION_LABELS[decision]
        if item.get("details", "").startswith("French Cuneo"):
            item["details"] = "This station is also listed in France. Keep the RFI ID as a backup."
        rows.append(item)
    fields = [
        "record", "operator", "id", "from", "to", "name", "lat", "lon", "reason",
        "source", "source_url", "rfi_monitor_url", "viaggiatreno_url", "wikipedia_url",
        "status", "source_name", "reviewed_name", "decision", "details",
    ]
    write_csv(ROOT / "overrides" / "italy-decisions.csv", rows, fields)


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
