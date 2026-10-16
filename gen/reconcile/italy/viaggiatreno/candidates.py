"""Passenger candidate classification for Italian providers."""
from __future__ import annotations

from typing import Any


def fmt(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def candidate_list(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = record.get("candidates")
    if isinstance(candidates, list):
        return [c for c in candidates if isinstance(c, dict)]

    nearby = record.get("nearby")
    if isinstance(nearby, list):
        return [c for c in nearby if isinstance(c, dict)]

    if record.get("vt_station_id"):
        return [{
            "id": record.get("vt_station_id"),
            "name": record.get("vt_name"),
            "distance_m": record.get("distance_m"),
            "name_score": record.get("name_score"),
        }]
    return []


def proposed(record: dict[str, Any]) -> tuple[str | None, str | None]:
    sid = record.get("vt_station_id")
    name = record.get("vt_name")
    sid = str(sid).strip() if sid else None
    name = str(name).strip() if name else None
    return sid, name


def decision_from_candidate(
    record: dict[str, Any],
    sid: str,
    name: str | None,
    *,
    method_override: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    selected = None
    for c in candidate_list(record):
        if str(c.get("id") or "").strip() == sid:
            selected = c
            break

    return {
        "action": "accept",
        "vt_station_id": sid,
        "vt_name": name or (selected or {}).get("name") or record.get("vt_name"),
        "region": (selected or {}).get("region") or record.get("region"),
        "distance_m": (selected or {}).get("distance_m", record.get("distance_m")),
        "name_score": (selected or {}).get("name_score", record.get("name_score")),
        "method": method_override or record.get("method") or "interactive_review",
        "note": note or "accepted_interactively",
        "source_bucket": record.get("_bucket"),
    }
