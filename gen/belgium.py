#!/usr/bin/env python3
"""Generate Belgian NMBS/SNCB stations from the iRail station catalogue."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from common.config import load_excluded_ids
from common.io import ROOT

ENDPOINT = "https://api.irail.be/stations/?format=json&lang=en"
OUTPUT = ROOT / "nodes" / "nodes-belgium.json"


def build_nodes(payload: dict) -> list[dict]:
    excluded = load_excluded_ids("belgium")
    nodes: list[dict] = []
    for station in payload.get("station", []):
        for key in ("standardname", "locationX", "locationY", "id"):
            if key not in station:
                raise ValueError(f"Missing {key!r} in station data")
        if station["id"] in excluded:
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for node in nodes:
            handle.write(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(nodes)} Belgian stations to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
