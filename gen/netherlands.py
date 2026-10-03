#!/usr/bin/env python3

import csv
import json
import sys
import os
from common.io import ROOT

def convert_nl_stations(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        try:
            reader = csv.DictReader(infile)
            
            for row in reader:
                try:
                    station_id = row.get("code")
                    if not station_id:
                        print(f"Skipping station with missing code: {row}")
                        continue
                    
                    name = row.get("name_long")
                    if not name:
                        print(f"Skipping station with missing name: {row}")
                        continue
                    
                    lat = row.get("geo_lat")
                    lon = row.get("geo_lng")
                    if not lat or not lon:
                        print(f"Skipping station with missing coordinates: {row}")
                        continue
                    
                    node = {
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
                    }
                    
                    outfile.write(json.dumps(node, ensure_ascii=False,
                                            separators=(',', ':')
                                             ) + '\n')
                    
                except Exception as e:
                    print(f"Error processing station: {e}")
                    
        except Exception as e:
            print(f"Error processing file: {e}")

def main(argv=None):
    import argparse
    import requests
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate Netherlands railway stations")
    parser.add_argument("--cache", action="store_true",
                        help="reuse cached station CSV instead of downloading again")
    args = parser.parse_args(argv)

    country_cache = ROOT / "cache" / "netherlands"
    country_cache.mkdir(parents=True, exist_ok=True)
    current_input = country_cache / "stations.csv"
    legacy_input = ROOT / "cache" / "netherlands_stations.csv"
    if legacy_input.exists() and not current_input.exists():
        legacy_input.replace(current_input)
        print(f"Moved legacy cache artifact: {legacy_input.relative_to(ROOT)} -> {current_input.relative_to(ROOT)}")
    output_file = str(ROOT / "nodes" / "nodes-netherlands.json")

    if not args.cache or not current_input.exists():
        print("Downloading Netherlands stations data...")
        url = "https://opendata.rijdendetreinen.nl/public/stations/stations-2023-09-nl.csv"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        temporary = current_input.with_suffix(".csv.tmp")
        temporary.write_text(response.text, encoding="utf-8")
        os.replace(temporary, current_input)
    else:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(current_input.stat().st_mtime, timezone.utc)
        print(f"Using cached Netherlands station data (age: {int(age.total_seconds() // 86400)} days)")

    convert_nl_stations(str(current_input), output_file)
    print(f"Conversion complete. Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
