#!/usr/bin/env python3

import csv
import os
from pathlib import Path

from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file

def build_nodes(input_path: Path) -> list[dict]:
    nodes = []
    with input_path.open(encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        required = {"code", "name_long", "geo_lat", "geo_lng"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{input_path}: missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, 2):
            station_id = str(row.get("code") or "").strip()
            name = str(row.get("name_long") or "").strip()
            lat = str(row.get("geo_lat") or "").strip()
            lon = str(row.get("geo_lng") or "").strip()
            if not station_id or not name or not lat or not lon:
                raise ValueError(f"{input_path}:{line_number}: missing station ID, name, or coordinates")
            try:
                nodes.append({
                        "type": "node",
                        "id": station_id,
                        "lat": float(lat),
                        "lon": float(lon),
                        "tags": {
                            "name": name,
                            "uic": row.get("uic", ""),  # Original UIC ID is now in tags
                            "name_short": row.get("name_short", ""),
                            "name_medium": row.get("name_medium", ""),
                            "slug": row.get("slug", ""),
                            "type": row.get("type", "")
                        },
                        "category": "netherlands_all"
                    })
            except ValueError as exc:
                raise ValueError(f"{input_path}:{line_number}: invalid coordinates") from exc
    return sorted(nodes, key=lambda row: str(row["id"]))

def main(argv=None):
    import argparse
    import requests
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate Netherlands railway stations")
    add_cache_flag(parser)
    args = parser.parse_args(argv)

    country_cache = ROOT / "cache" / "netherlands"
    country_cache.mkdir(parents=True, exist_ok=True)
    current_input = country_cache / "stations.csv"
    legacy_input = ROOT / "cache" / "netherlands_stations.csv"
    if legacy_input.exists() and not current_input.exists():
        legacy_input.replace(current_input)
        print(f"Moved legacy cache artifact: {legacy_input.relative_to(ROOT)} -> {current_input.relative_to(ROOT)}")
    output_file = ROOT / "nodes" / "nodes-netherlands.json"

    if args.cache:
        require_cached_file(current_input, "Dutch station data")
        print("Using the saved Dutch station data.")
    else:
        print("Downloading Netherlands stations data...")
        url = "https://opendata.rijdendetreinen.nl/public/stations/stations-2023-09-nl.csv"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        temporary = current_input.with_suffix(".csv.tmp")
        temporary.write_text(response.text, encoding="utf-8")
        os.replace(temporary, current_input)
    publish_nodes(output_file, build_nodes(current_input))
    print(f"Conversion complete. Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
