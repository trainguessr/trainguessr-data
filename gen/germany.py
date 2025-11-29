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

def convert_from_json(input_path, output_path, rename_map):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        data = json.load(infile)
        for station in data:
            try:
                # Extract required fields
                station_id = station.get("id")
                if not station_id:
                    print(f"Skipping station with missing ID: {station}")
                    continue
                
                # Get coordinates
                location = station.get("location", {})
                lat = location.get("latitude")
                lon = location.get("longitude")
                if not lat or not lon:
                    print(f"Skipping station with missing coordinates: {station}")
                    continue
                
                name = station.get("name", "")
                if not name:
                    print(f"Skipping station with missing name: {station}")
                    continue
                
                # Apply rename mapping if needed
                if name in rename_map:
                    name = rename_map[name]
                
                # Get additional data for tags
                ril100 = station.get("ril100", "")
                nr = station.get("nr", "")
                weight = station.get("weight", "")
                
                # Get operator info if available
                operator_name = ""
                if "operator" in station and station["operator"] and "name" in station["operator"]:
                    operator_name = station["operator"]["name"]
                
                # Get address info if available
                address = {}
                if "address" in station:
                    address = station["address"]
                
                # Create output node
                node = {
                    "type": "node",
                    "id": int(station_id),
                    "lat": float(lat),
                    "lon": float(lon),
                    "tags": {
                        "name": name,
                        "ril100": ril100,
                        "station_nr": str(nr),
                        "weight": str(weight),
                        "operator": operator_name,
                        "city": address.get("city", ""),
                        "zipcode": address.get("zipcode", ""),
                        "street": address.get("street", "")
                    },
                    "category": "germany_all"
                }
                
                outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
            except Exception as e:
                print(f"Error processing station: {e}")

if __name__ == "__main__":
    input_file = "../cache/germany/full.json"
    output_file = "../nodes/nodes-germany.json"
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        sys.exit(1)
    
    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-germany.txt")
    print(f"Loaded {len(rename_map)} rename rules")
    
    convert_from_json(input_file, output_file, rename_map)
    print(f"Conversion complete. Output written to {output_file}")
