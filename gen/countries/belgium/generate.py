#!/usr/bin/env python3
"""Generate Belgian NMBS/SNCB stations from the iRail station catalogue."""
from __future__ import annotations

import argparse
import json
import requests

from common.config import load_exclusion_rules
from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file

ENDPOINT = "https://api.irail.be/stations/?format=json&lang=en"
OUTPUT = ROOT / "nodes" / "nodes-belgium.json"
CACHE_SOURCE = ROOT / "cache" / "belgium" / "stations.json"


def build_nodes(payload: dict) -> list[dict]:
    excluded = load_exclusion_rules("belgium")
    nodes: list[dict] = []
    for station in payload.get("station", []):
        for key in ("standardname", "locationX", "locationY", "id"):
            if key not in station:
                raise ValueError(f"Missing {key!r} in station data")
        rule = excluded.get(str(station["id"]))
        if rule is not None:
            continue
        nodes.append({
            "type": "node",
            "id": station["id"],
            "lat": float(station["locationY"]),
            "lon": float(station["locationX"]),
            "tags": {"name": station["standardname"]},
            "category": "belgium_all",
        })
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
    nodes = build_nodes(payload)
    publish_nodes(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Belgian stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
