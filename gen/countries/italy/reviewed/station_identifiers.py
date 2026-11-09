"""Exact Italian provider identifiers published together by Trainline.

Names and coordinates are descriptive only. An existing RFI node's reviewed
ViaggiaTreno ID selects a unique station row; no IDs are constructed from digits.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from common.io import ROOT

SOURCE_PATH = ROOT / "cache/italy/rfi/raw/trainline-stations.csv"
TAG_FIELDS = {"uic": "trainline_uic_ref", "obb_id": "oebb_station_id", "db_id": "db_station_id"}


def load_station_identifiers(path: Path = SOURCE_PATH) -> tuple[dict[str, dict], str]:
    """Read the pinned cached source; a missing snapshot leaves seed data intact."""
    if not path.is_file():
        return {}, ""
    metadata = json.loads(path.with_suffix(".source.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Trainline station identifiers: cached source checksum differs")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return index_station_identifiers(csv.DictReader(handle, delimiter=";")), str(metadata["revision"])


def index_station_identifiers(rows) -> dict[str, dict]:
    """Keep only unique Italian station records and unique foreign station IDs."""
    candidates = defaultdict(list)
    foreign = defaultdict(set)
    for row in rows:
        vt = str(row.get("trenitalia_rtvt_id") or "").strip()
        if (row.get("country") != "IT" or row.get("is_city") != "f" or row.get("same_as")
                or not re.fullmatch(r"S\d{5}", vt) or not str(row.get("id") or "").isdigit()):
            continue
        if any(value and not re.fullmatch(r"\d{7}", value)
               for value in (str(row.get(field) or "") for field in TAG_FIELDS)):
            continue
        candidates[vt].append(dict(row))
        for field in TAG_FIELDS:
            value = row.get(field)
            if value:
                foreign[(field, value)].add(vt)
    return {vt: records[0] for vt, records in candidates.items()
            if len(records) == 1 and all(len(foreign[(field, records[0][field])]) == 1
                                         for field in TAG_FIELDS if records[0].get(field))}


def apply_station_identifiers(nodes: list[dict], index: dict[str, dict], revision: str) -> int:
    """Enrich every exactly linked RFI node; retain established UIC aliases."""
    applied = 0
    vt_counts = defaultdict(int)
    for node in nodes:
        vt_counts[str(node.get("tags", {}).get("viaggiatreno_station_id") or "")] += 1
    for node in nodes:
        tags = node.get("tags") or {}
        vt = str(tags.get("viaggiatreno_station_id") or "")
        record = index.get(vt)
        if record is None or vt_counts[vt] != 1 or node.get("category") != "italy_rfi":
            continue
        updates = {tag: record[field] for field, tag in TAG_FIELDS.items() if record.get(field)}
        for tag, value in updates.items():
            if tags.get(tag) and tags[tag] != value:
                raise ValueError(f"RFI {node['id']}: conflicting explicit {tag}; review source change")
        updates.update(trainline_station_id=record["id"],
                       station_identity_source=f"trainline-stations:{revision}:{record['id']}")
        # Existing reviewed UIC aliases (including historical HAFAS aliases)
        # remain unchanged; the independently published code stays explicit.
        if not tags.get("uic_ref") and record.get("uic"):
            updates.update(uic_ref=record["uic"], uic_granularity="stop",
                           uic_crosswalk_source=updates["station_identity_source"])
        tags.update(updates)
        node["tags"] = tags
        applied += 1
    return applied
