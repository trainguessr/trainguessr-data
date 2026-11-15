#!/usr/bin/env python3
"""Generate Belgian NMBS/SNCB stations from the iRail station catalogue."""
from __future__ import annotations

import argparse
import json
import re
import requests

from common.config import load_exclusion_rules
from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file

ENDPOINT = "https://api.irail.be/stations/?format=json&lang=en"
OUTPUT = ROOT / "nodes" / "nodes-belgium.json"
# Excluded rows are not playable, but their IDs let trains cross the border.
LOOKUP_OUTPUT = ROOT / "lookup" / "lookup-belgium.json"
CACHE_SOURCE = ROOT / "cache" / "belgium" / "stations.json"


def published_uic(station: dict) -> str | None:
    """UIC from iRail's station URI, only when it agrees with the station ID."""
    match = re.fullmatch(r"http://irail\.be/stations/NMBS/00(\d{7})", str(station.get("@id") or ""))
    if match and station["id"] == f"BE.NMBS.00{match.group(1)}":
        return match.group(1)
    return None


def build_nodes(payload: dict, lookup: list[dict] | None = None) -> list[dict]:
    excluded = load_exclusion_rules("belgium")
    nodes: list[dict] = []
    for station in payload.get("station", []):
        for key in ("standardname", "locationX", "locationY", "id"):
            if key not in station:
                raise ValueError(f"Missing {key!r} in station data")
        tags = {"name": station["standardname"]}
        if uic := published_uic(station):
            tags.update(uic_ref=uic, uic_granularity="stop", uic_crosswalk_source="irail-station-uri")
        node = {
            "type": "node",
            "id": station["id"],
            "lat": float(station["locationY"]),
            "lon": float(station["locationX"]),
            "tags": tags,
            "category": "belgium_all",
        }
        if excluded.get(str(station["id"])) is not None:
            if lookup is not None:
                lookup.append(node)
            continue
        nodes.append(node)
    if lookup is not None:
        lookup.sort(key=lambda row: (row["tags"]["name"], str(row["id"])))
    return sorted(nodes, key=lambda row: (row["tags"]["name"], str(row["id"])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    if args.cache:
        payload = json.loads(require_cached_file(CACHE_SOURCE, "Belgian station data").read_text(encoding="utf-8"))
    else:
        print("Downloading Belgian station data...")
        response = requests.get(ENDPOINT, timeout=60)
        response.raise_for_status()
        save_source_file(CACHE_SOURCE, response.content)
        payload = response.json()
    lookup: list[dict] = []
    nodes = build_nodes(payload, lookup)
    publish_nodes(OUTPUT, nodes)
    LOOKUP_OUTPUT.parent.mkdir(exist_ok=True)
    publish_nodes(LOOKUP_OUTPUT, lookup)
    print(f"Wrote {len(nodes)} Belgian stations to {OUTPUT}")
    print(f"Wrote {len(lookup)} lookup-only stations to {LOOKUP_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
