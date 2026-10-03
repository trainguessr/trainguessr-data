#!/usr/bin/env python3

import json
import sys
import os
from common.io import ROOT

from common.config import load_rename_map

def load_rename_mapping(rename_file):
    """
    Load the rename mapping from a text file.
    
    Args:
        rename_file: Path to the rename file
        
    Returns:
        Dictionary mapping old names to new names
    """
    rename_map = {}
    if os.path.exists(rename_file):
        with open(rename_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ',' in line:
                    old_name, new_name = line.split(',', 1)
                    rename_map[old_name] = new_name
    return rename_map

def convert_uk_stations(input_path, output_path, rename_map):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        try:
            data = json.load(infile)
            
            for station in data:
                try:
                    station_id = station.get("crsCode")
                    if not station_id:
                        print(f"Skipping station with missing ID: {station}")
                        continue
                    
                    name = station.get("stationName")
                    if not name:
                        print(f"Skipping station with missing name: {station}")
                        continue
                    
                    if name in rename_map:
                        name = rename_map[name]
                    
                    lat = station.get("lat")
                    lon = station.get("long")
                    if not lat or not lon:
                        print(f"Skipping station with missing coordinates: {station}")
                        continue
                    
                    node = {
                        "type": "node",
                        "id": station_id,
                        "lat": float(lat),
                        "lon": float(lon),
                        "tags": {
                            "name": name,
                        },
                        "category": "uk_national_rail"
                    }
                    
                    outfile.write(json.dumps(node,
                                            ensure_ascii=False, separators=(',', ':')
                                             ) + '\n')
                    
                except Exception as e:
                    print(f"Error processing station: {e}")
                    
        except json.JSONDecodeError:
            print("Invalid JSON format in input file")
        except Exception as e:
            print(f"Error processing file: {e}")

def main(argv=None):
    import argparse
    import requests
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate UK National Rail stations")
    parser.add_argument("--cache", action="store_true",
                        help="reuse cached station JSON instead of downloading again")
    args = parser.parse_args(argv)

    input_path = ROOT / "cache" / "uk" / "stations.json"
    output_file = str(ROOT / "nodes" / "nodes-uk-nationalrail.json")
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
    convert_uk_stations(str(input_path), output_file, rename_map)
    print(f"Conversion complete. Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
