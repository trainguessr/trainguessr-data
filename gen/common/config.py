from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

ITALY_REVIEW_LABELS = {
    "missing_native_id": "Provider ID needed",
    "matched_name_difference": "Provider name changed",
    "reviewed_only_retained": "Missing from download",
    "missing_coordinates": "Coordinates needed",
    "gtfs_name_missing": "Name missing from timetable file",
    "manual_reviewed": "ID checked",
    "cross_border_france": "French border station",
    "provider_scope_review": "Check railway owner",
}
ITALY_DECISION_LABELS = {
    "keep_reviewed_name": "Keep current name",
    "confirmed": "Confirmed",
    "keep_reviewed_station": "Keep old station",
    "added_coordinates": "Coordinates checked",
    "excluded": "Exclude this station",
    "handled_by_france_with_rfi_fallback": "Listed in France; keep RFI ID as backup",
    "use_source_name": "Use downloaded name",
    "confirmed_fn": "Confirmed as an FN station",
    "not_fn": "Not an FN station",
    "added_native_id": "Added provider ID",
}


def _normal_name(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def reviewed_name(row: dict[str, Any]) -> str:
    """Return the source identity recorded by a reviewed override."""
    tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
    return str(row.get("expected_name") or row.get("name") or tags.get("name") or "").strip()


def _read_exclusion_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    evidence_refs = {
        str(row.get("evidence_ref") or "").strip()
        for row in source_rows
        if str(row.get("evidence_ref") or "").strip()
    }
    evidence_records: dict[str, Any] = {}
    if evidence_refs:
        evidence_path = ROOT / "gen" / "bootstrap" / "evidence" / "italy-exclusion-station-evidence.json"
        try:
            evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            if not isinstance(evidence_payload, dict):
                raise ValueError
            evidence_records = evidence_payload.get("records", {})
        except (OSError, ValueError) as exc:
            raise ValueError("Check the saved station evidence.") from exc
        if not isinstance(evidence_records, dict) or not evidence_refs.issubset(evidence_records):
            raise ValueError("Check the saved station evidence.")

    rows: list[dict[str, Any]] = []
    for line, row in enumerate(source_rows, 2):
        item: dict[str, Any] = {
            key: value.strip()
            for key, value in row.items()
            if value is not None
        }
        evidence_ref = str(item.get("evidence_ref") or "").strip()
        if evidence_ref:
            evidence = evidence_records[evidence_ref]
            if not isinstance(evidence, dict) or set(evidence) & set(item):
                raise ValueError(f"{path}:{line}: check the saved station evidence")
            item.update(evidence)
        rows.append(item)
    return rows


def load_country_config(country: str) -> dict[str, Any]:
    path = ROOT / "overrides" / "exclusions" / f"{country}.json"
    if path.is_file():
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    else:
        value = {}
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    if country == "italy":
        exclusion_path = ROOT / "overrides" / "exclusions" / "italy.csv"
        if exclusion_path.is_file():
            value["excluded"] = _read_exclusion_csv(exclusion_path)
        decisions_path = ROOT / "overrides" / "italy-decisions.csv"
        if decisions_path.is_file():
            value = {**value, "renamed": [], "manual_stations": [], "reviews": []}
            with decisions_path.open(encoding="utf-8-sig", newline="") as handle:
                for line, row in enumerate(csv.DictReader(handle), 2):
                    record = row.get("record", "").strip()
                    if record == "rename":
                        value["renamed"].append({
                            "operator": row["operator"], "from": row["from"], "to": row["to"]
                        })
                    elif record == "station":
                        item = {
                            "operator": row["operator"], "id": row["id"], "name": row["name"],
                            "lat": float(row["lat"]), "lon": float(row["lon"]), "reason": row["reason"],
                        }
                        for field in ("source", "source_url", "rfi_monitor_url", "viaggiatreno_url", "wikipedia_url"):
                            if row.get(field):
                                item[field] = row[field]
                        value["manual_stations"].append(item)
                    elif record == "review":
                        status_label = row.get("status", "")
                        decision_label = row.get("decision", "")
                        status = next((key for key, label in ITALY_REVIEW_LABELS.items() if label == status_label), None)
                        decision = next((key for key, label in ITALY_DECISION_LABELS.items() if label == decision_label), None)
                        if status is None or decision is None:
                            raise ValueError(f"{decisions_path}:{line}: check the review status and decision")
                        value["reviews"].append({
                            "operator": row["operator"], "id": row["id"], "status": status,
                            "source_name": row["source_name"], "reviewed_name": row["reviewed_name"],
                            "decision": decision, "details": row.get("details", ""),
                        })
                    else:
                        raise ValueError(f"{decisions_path}:{line}: check the decision type")
        coordinate_path = ROOT / "overrides" / "italy-coordinate-corrections.csv"
        if coordinate_path.is_file():
            coordinates = []
            with coordinate_path.open(encoding="utf-8-sig", newline="") as handle:
                for line, row in enumerate(csv.DictReader(handle), 2):
                    try:
                        tags = json.loads(row.get("tags_json") or "{}")
                        remove_tags = json.loads(row.get("remove_tags_json") or "[]")
                        if not isinstance(tags, dict) or not isinstance(remove_tags, list):
                            raise ValueError
                        coordinates.append({
                            "operator": row["operator"], "id": row["id"],
                            "expected_name": row["expected_name"], "lat": float(row["lat"]),
                            "lon": float(row["lon"]), "source": row["source"],
                            "source_url": row["source_url"], "reason": row["reason"],
                            "tags": tags, "remove_tags": remove_tags,
                        })
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        raise ValueError(f"{coordinate_path}:{line}: check the coordinate correction") from exc
            value["coordinate_overrides"] = coordinates
    return value


def load_rename_map(country: str, operator: str | None = None) -> dict[str, str]:
    rows = load_country_config(country).get("renamed", [])
    result: dict[str, str] = {}
    for row in rows:
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        if row.get("id") not in (None, ""):
            continue
        result[str(row["from"])] = str(row["to"])
    return result


def load_rename_id_map(country: str, operator: str | None = None) -> dict[str, str]:
    return {
        station_id: str(row["to"])
        for station_id, row in load_rename_id_rules(country, operator).items()
    }


def load_rename_id_rules(
    country: str,
    operator: str | None = None,
) -> dict[str, dict[str, Any]]:
    rows = load_country_config(country).get("renamed", [])
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        station_id = row.get("id")
        if station_id not in (None, ""):
            key = str(station_id)
            if key in result:
                raise ValueError(f"{country}: duplicate ID rename for station {key}")
            if not str(row.get("from") or "").strip() or not str(row.get("to") or "").strip():
                raise ValueError(f"{country}: ID rename {key} requires from and to names")
            result[key] = row
    return result


def load_excluded_ids(country: str, operator: str | None = None) -> set[str]:
    return set(load_exclusion_rules(country, operator))


def load_exclusion_rules(
    country: str,
    operator: str | None = None,
) -> dict[str, dict[str, Any]]:
    csv_path = ROOT / "overrides" / "exclusions" / f"{country}.csv"
    if csv_path.is_file():
        rows = _read_exclusion_csv(csv_path)
    else:
        rows = load_country_config(country).get("excluded", [])
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{country}: every exclusion must be an object")
        row_operator = row.get("operator")
        if operator is not None and row_operator != operator:
            continue
        station_id = row.get("id")
        if station_id not in (None, ""):
            key = str(station_id)
            if key in result:
                raise ValueError(f"{country}: duplicate exclusion for station ID {key}")
            result[key] = row
    return result


def require_reviewed_identity(
    rule: dict[str, Any],
    actual_name: object,
    *,
    context: str,
) -> None:
    """Fail when a destructive reviewed rule no longer names its source row."""
    expected_name = reviewed_name(rule)
    if not expected_name:
        raise ValueError(f"{context}: Check this station. The saved station name is missing.")
    actual = str(actual_name or "").strip()
    if _normal_name(actual) != _normal_name(expected_name):
        raise ValueError(
            f"{context}: Check this station. The saved name is {expected_name!r}; "
            f"the source now says {actual!r}."
        )
