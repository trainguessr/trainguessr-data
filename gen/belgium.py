#!/usr/bin/env python3
"""Generate Belgian NMBS/SNCB stations from the iRail station catalogue."""
from __future__ import annotations

import requests

from common.config import load_exclusion_rules, require_reviewed_identity
from common.io import ROOT, publish_nodes

ENDPOINT = "https://api.irail.be/stations/?format=json&lang=en"
OUTPUT = ROOT / "nodes" / "nodes-belgium.json"


def build_nodes(payload: dict) -> list[dict]:
    excluded = load_exclusion_rules("belgium")
    nodes: list[dict] = []
    for station in payload.get("station", []):
        for key in ("standardname", "locationX", "locationY", "id"):
            if key not in station:
                raise ValueError(f"Missing {key!r} in station data")
        rule = excluded.get(str(station["id"]))
        if rule is not None:
            require_reviewed_identity(
                rule, station["standardname"], context=f"belgium:{station['id']}"
            )
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


def main() -> int:
    print("Fetching stations from iRail...")
    response = requests.get(ENDPOINT, timeout=60)
    response.raise_for_status()
    nodes = build_nodes(response.json())
    publish_nodes(OUTPUT, nodes)
    print(f"Wrote {len(nodes)} Belgian stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
