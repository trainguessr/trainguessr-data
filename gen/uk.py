#!/usr/bin/env python3

import json
import os
from pathlib import Path

from common.io import ROOT, publish_nodes

from common.config import load_rename_map

def build_nodes(input_path: Path, rename_map: dict[str, str]) -> list[dict]:
    with input_path.open(encoding="utf-8") as infile:
        data = json.load(infile)
    if not isinstance(data, list):
        raise ValueError(f"{input_path}: expected a station list")
    nodes = []
    for index, station in enumerate(data, 1):
        if not isinstance(station, dict):
            raise ValueError(f"{input_path}: station {index} is not an object")
        station_id = str(station.get("crsCode") or "").strip()
        name = str(station.get("stationName") or "").strip()
        lat = station.get("lat")
        lon = station.get("long")
        if not station_id or not name or lat in (None, "") or lon in (None, ""):
            raise ValueError(f"{input_path}: station {index} lacks identity, name, or coordinates")
        try:
            nodes.append({
                        "type": "node",
                        "id": station_id,
                        "lat": float(lat),
                        "lon": float(lon),
                        "tags": {
                            "name": rename_map.get(name, name),
                        },
                        "category": "uk_national_rail"
                    })
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{input_path}: station {index} has invalid coordinates") from exc
    return sorted(nodes, key=lambda row: str(row["id"]))

def main(argv=None):
    import argparse
    import requests
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate UK National Rail stations")
    parser.add_argument("--cache", action="store_true",
                        help="reuse cached station JSON instead of downloading again")
    args = parser.parse_args(argv)

    input_path = ROOT / "cache" / "uk" / "stations.json"
    output_file = ROOT / "nodes" / "nodes-uk-nationalrail.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.cache or not input_path.exists():
        print("Downloading UK station data...")
        response = requests.get("https://raw.githubusercontent.com/davwheat/uk-railway-stations/refs/heads/main/stations.json", timeout=60)
        response.raise_for_status()
        json.loads(response.text)
        temporary = input_path.with_suffix(".json.tmp")
        temporary.write_text(response.text, encoding="utf-8")
        os.replace(temporary, input_path)
    else:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(input_path.stat().st_mtime, timezone.utc)
        print(f"Using cached UK station data (age: {int(age.total_seconds() // 86400)} days)")

    print("Loading rename mapping...")
    rename_map = load_rename_map("uk")
    print(f"Loaded {len(rename_map)} rename rules")
    publish_nodes(output_file, build_nodes(input_path, rename_map))
    print(f"Conversion complete. Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
