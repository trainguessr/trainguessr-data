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
        for line in infile:
            try:
                feature = json.loads(line.strip())
                
                # Extract required fields
                eva_nr = feature.get("EVA_NR")
                if not eva_nr:
                    print(f"Skipping feature with missing EVA_NR: {feature}")
                    continue
                
                lat = feature.get("STP_LAT")
                lon = feature.get("STP_LON")
                if not lat or not lon:
                    print(f"Skipping feature with missing coordinates: {feature}")
                    continue
                
                name = feature.get("STP_NAME", "")
                if not name:
                    print(f"Skipping feature with missing name: {feature}")
                    continue
                
                # Apply rename mapping if needed
                if name in rename_map:
                    name = rename_map[name]
                
                # Create output node
                node = {
                    "type": "node",
                    "id": int(eva_nr),
                    "lat": float(lat),
                    "lon": float(lon),
                    "tags": {
                        "name": name,
                        "stp_id": feature.get("STP_ID", ""),
                        "ifopt_id": feature.get("IFOPT_ID", ""),
                        "stp_type": feature.get("STP_TYPE", ""),
                        "stp_short": feature.get("STP_SHORT", ""),
                        "bsts_id": feature.get("BSTS_ID", ""),
                        "plc": feature.get("PLC", "")
                    },
                    "category": "austria_oebb"
                }
                
                outfile.write(json.dumps(node,
                                        ensure_ascii=False,
                                        separators=(',', ':')) + '\n')
            except Exception as e:
                print(f"Error processing feature: {e}")

if __name__ == "__main__":
    # https://data.oebb.at/dam/jcr:d4780bb2-390e-4288-b540-dff1ae1b27ae/GeoNetz_12-2024.zip
    # unzip GeoNetz_12-2024.zip
    # unzip GeoNetz_12-2024/OEBB_NETWORK_GeoJSON.zip
    # jq -c '.features[].properties' OEBB_NETWORK.json | grep railStation > intermediate.json
    # intermediate.json is the input file for this script
    import sys
    import requests
    import zipfile
    import subprocess

    cache_dir = "../cache"
    input_file = os.path.join(cache_dir, "austria_stations_filtered.json")
    output_file = "../nodes/nodes-austria-oebb.json"
    
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    if not os.path.exists(input_file):
        print("Downloading and preparing data...")
        url = "https://data.oebb.at/dam/jcr:d4780bb2-390e-4288-b540-dff1ae1b27ae/GeoNetz_12-2024.zip"
        response = requests.get(url)

        if response.status_code != 200:
            print(f"Failed to download data: {response.status_code}")
            sys.exit(1)

        zip_path = os.path.join(cache_dir, "GeoNetz_12-2024.zip")
        with open(zip_path, 'wb') as f:
            f.write(response.content)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)

        geojson_zip_path = os.path.join(cache_dir, "GeoNetz_12-2024", "OEBB_NETWORK_GeoJSON.zip")
        with zipfile.ZipFile(geojson_zip_path, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)

        geojson_path = os.path.join(cache_dir, "OEBB_NETWORK.json")
        intermediate_path = os.path.join(cache_dir, "austria_stations_filtered.json")
        with open(geojson_path, 'r', encoding='utf-8') as geojson_file, open(intermediate_path, 'w', encoding='utf-8') as intermediate_file:
            data = json.load(geojson_file)
            for feature in data.get("features", []):
                properties = feature.get("properties", {})
                if "railStation" in properties.get("STP_TYPE", ""):
                    intermediate_file.write(json.dumps(properties) + '\n')

    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-austria.txt")
    print(f"Loaded {len(rename_map)} rename rules")

    convert_from_json(input_file, output_file, rename_map)
    print(f"Conversion complete. Output written to {output_file}")