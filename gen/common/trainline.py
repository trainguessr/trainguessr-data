"""Pinned Trainline station snapshot: provider IDs published on one row.

Names and coordinates are never used to link stations. A row links its IDs
only when each of those IDs appears on no other candidate row.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from common.io import ROOT

# Downloaded and pinned by the Italian RFI generator; shared by other countries.
SOURCE_PATH = ROOT / "cache/italy/rfi/raw/trainline-stations.csv"


def load_rows(path: Path = SOURCE_PATH) -> tuple[list[dict], str]:
    """Read the pinned snapshot; a missing snapshot returns no rows."""
    if not path.is_file():
        return [], ""
    metadata = json.loads(path.with_suffix(".source.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Trainline station identifiers: cached source checksum differs")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";")), str(metadata["revision"])


ID_PATTERNS = {"trenitalia_rtvt_id": r"S\d{5}", "renfe_id": r"\d{5}", "atoc_id": r"[A-Z]{3}"}


def unique_station_rows(rows, *, country: str, key: str, id_fields: tuple[str, ...],
                        foreign: bool = False) -> dict[str, dict]:
    """Index real station rows by ``key`` when the key and all IDs are unique.

    ``foreign`` selects rows outside ``country`` instead of inside it.
    """
    def valid(field, value):
        return re.fullmatch(ID_PATTERNS.get(field, r"\d{7}"), value) is not None

    candidates = defaultdict(list)
    seen = defaultdict(set)
    for row in rows:
        value = str(row.get(key) or "").strip()
        if ((row.get("country") == country) == foreign or row.get("is_city") != "f" or row.get("same_as")
                or not valid(key, value) or not str(row.get("id") or "").isdigit()):
            continue
        if any(row.get(field) and not valid(field, row[field]) for field in id_fields):
            continue
        candidates[value].append(dict(row))
        for field in id_fields:
            if row.get(field):
                seen[(field, row[field])].add(value)
    return {value: records[0] for value, records in candidates.items()
            if len(records) == 1 and all(len(seen[(field, records[0][field])]) == 1
                                         for field in id_fields if records[0].get(field))}


def apply_station_identifiers(nodes, index, revision, tags_by_field) -> int:
    """Add IDs Trainline publishes on the same row as each node's exact ID."""
    applied = 0
    for node in nodes:
        record = index.get(str(node["id"]))
        if record is None:
            continue
        tags = node["tags"]
        source = f"trainline-stations:{revision}:{record['id']}"
        tags.update({tag: record[field] for field, tag in tags_by_field.items() if record.get(field)})
        tags.update(trainline_station_id=record["id"], station_identity_source=source)
        if record.get("uic") and not tags.get("uic_ref"):
            tags.update(uic_ref=record["uic"], uic_granularity="stop", uic_crosswalk_source=source)
        applied += 1
    return applied


def add_station_identifiers(nodes, *, country: str, key: str, tags_by_field) -> int:
    """Look up each node's own ID as ``key`` in the pinned snapshot and tag it."""
    rows, revision = load_rows()
    index = unique_station_rows(rows, country=country, key=key, id_fields=tuple(tags_by_field))
    return apply_station_identifiers(nodes, index, revision, tags_by_field)
