#!/usr/bin/env python3

import csv
import json
import sys
import os

def convert_nl_stations(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        try:
            # Skip the header row and use csv reader
            reader = csv.DictReader(infile)
            
            for row in reader:
                try:
                    # Extract and validate required fields
                    # Use "code" as the primary ID (changed from "uic")
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
                    
                    # Create node object with "code" as ID
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

if __name__ == "__main__":
    import requests

    input_file = "../cache/netherlands_stations.csv"
    output_file = "../nodes/nodes-netherlands.json"

    if not os.path.exists(input_file):
        print("Downloading Netherlands stations data...")
        url = "https://opendata.rijdendetreinen.nl/public/stations/stations-2023-09-nl.csv"
        response = requests.get(url)
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
    
    convert_nl_stations(input_file, output_file)
    print(f"Conversion complete. Output written to {output_file}")
