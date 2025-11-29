#!/usr/bin/env python3

import json
import sys
import os

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
                    # Extract and validate required fields
                    station_id = station.get("crsCode")
                    if not station_id:
                        print(f"Skipping station with missing ID: {station}")
                        continue
                    
                    name = station.get("stationName")
                    if not name:
                        print(f"Skipping station with missing name: {station}")
                        continue
                    
                    # Apply rename mapping if needed
                    if name in rename_map:
                        name = rename_map[name]
                    
                    lat = station.get("lat")
                    lon = station.get("long")
                    if not lat or not lon:
                        print(f"Skipping station with missing coordinates: {station}")
                        continue
                    
                    # Create node object
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

if __name__ == "__main__":
    import os
    import requests

    input_file = "../cache/uk_stations.json"
    output_file = "../nodes/nodes-uk-nationalrail.json"

    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        data = requests.get("https://raw.githubusercontent.com/davwheat/uk-railway-stations/refs/heads/main/stations.json").text
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(data)
    
    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-uk-nationalrail.txt")
    print(f"Loaded {len(rename_map)} rename rules")
    
    convert_uk_stations(input_file, output_file, rename_map)
    print(f"Conversion complete. Output written to {output_file}")
