#!/usr/bin/env python3

import json
import sys
import os

excludes = "../changes/excluded-sweden.json"

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

seen = set()
def convert_from_json(input_path, output_path, rename_map):
    # Load excludes first
    excluded_ids = set()
    if os.path.exists(excludes):
        with open(excludes, 'r', encoding='utf-8') as exfile:
            lines = exfile.readlines()
            for line in lines:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    excluded_ids.add(int(entry['id']))

    nodes = []
    with open(input_path, 'r', encoding='utf-8') as infile:
        for line in infile:
            try:
                feature = json.loads(line.strip())
                
                # Extract coordinates
                centroid = feature.get("Centroid", {})
                location = centroid.get("Location", {})
                lon = location.get("Longitude")
                lat = location.get("Latitude")
                
                if not lat or not lon:
                    print(f"Skipping feature with missing coordinates: {feature}")
                    continue
                
                # Extract name
                name = feature.get("Name", "")
                if not name:
                    print(f"Skipping feature with missing name: {feature}")
                    continue
                
                # Apply rename mapping if needed
                if name in rename_map:
                    name = rename_map[name]
                
                # Extract other useful information
                short_name = feature.get("ShortName", "")
                private_code = feature.get("PrivateCode", "")
                transport_mode = feature.get("TransportMode", "")

                if transport_mode != "rail":
                    print(f"Skipping feature with unsupported transport mode: {transport_mode}")
                    continue
                
                stop_place_type = feature.get("StopPlaceType", "")
                weighting = feature.get("Weighting", "")
                
                # Extract alternative names if available
                alt_names = {}
                if "alternativeNames" in feature and "AlternativeName" in feature["alternativeNames"]:
                    alt_name = feature["alternativeNames"]["AlternativeName"]
                    if "Name" in alt_name:
                        alt_names["alt_name"] = alt_name["Name"]
                    if "Abbreviation" in alt_name:
                        alt_names["abbreviation"] = alt_name["Abbreviation"]
                
                # Extract key-value pairs from keyList
                key_values = {}
                if "keyList" in feature and "KeyValue" in feature["keyList"]:
                    for kv in feature["keyList"]["KeyValue"]:
                        if "Key" in kv and "Value" in kv:
                            key_values[kv["Key"]] = kv["Value"]
                
                # Create tags dictionary
                tags = {
                    "name": name,
                    "short_name": short_name,
                    "private_code": private_code,
                    "transport_mode": transport_mode,
                    "stop_place_type": stop_place_type,
                    "weighting": weighting,
                }
                
                # Add alternative names to tags if available
                tags.update(alt_names)
                
                # Add selected key-values to tags
                important_keys = ["owner", "sellable"]
                for key in important_keys:
                    if key in key_values:
                        tags[key] = key_values[key]

                station_id = key_values["rikshallplats"]
                if not station_id:
                    print(f"Skipping feature with missing station ID: {feature}")
                    continue
                if station_id in seen:
                    print(f"Skipping duplicate station ID: {station_id}")
                    continue
                if int(station_id) in excluded_ids:
                    print(f"Skipping excluded station ID: {station_id}")
                    continue
                seen.add(station_id)
                del key_values["rikshallplats"]
                
                # Add abbreviation from key-values if available
                if "trafikverket-signatures" in key_values:
                    tags["abbreviation"] = key_values["trafikverket-signatures"]
                
                # Clean empty values from tags
                tags = {k: v for k, v in tags.items() if v}
                
                # Create output node
                node = {
                    "type": "node",
                    "id": int(station_id),
                    "lat": float(lat),
                    "lon": float(lon),
                    "tags": tags,
                    "category": "sweden_all"
                }
                nodes.append(node)
            except Exception as e:
                print(f"Error processing feature: {e}")  

        nodes.sort(key=lambda x: x['id']) 

        with open(output_path, 'w', encoding='utf-8') as outfile:
            for node in nodes:
                outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == "__main__":
    import requests
    import zipfile
    import subprocess
    
    cache_dir = "../cache"
    zip_file = os.path.join(cache_dir, "sweden.zip")
    xml_file = os.path.join(cache_dir, "_stops.xml")
    json_file = os.path.join(cache_dir, "sweden_full.json")
    jlines_file = os.path.join(cache_dir, "sweden_jlines.json")
    output_file = "../nodes/nodes-sweden.json"

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    # Download the data if not already cached
    if not os.path.exists(zip_file):
        print("Downloading Sweden stops data...")
        api_key = os.environ.get("TRAFIKLAB_API_KEY_STOPS")
        if not api_key:
            print("Please set the TRAFIKLAB_API_KEY_STOPS environment variable.")
            print("Get your API key from: https://www.trafiklab.se/")
            sys.exit(1)
        
        url = f"https://opendata.samtrafiken.se/stopsregister-netex-sweden/sweden.zip?key={api_key}"
        response = requests.get(url, headers={"Accept-Encoding": "gzip"})
        
        if response.status_code != 200:
            print(f"Failed to download data: {response.status_code}")
            sys.exit(1)
        
        with open(zip_file, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded to {zip_file}")

    # Extract the zip file
    if not os.path.exists(xml_file):
        print("Extracting zip file...")
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)
        print(f"Extracted to {cache_dir}")

    # Convert XML to JSON using yq
    if not os.path.exists(json_file):
        print("Converting XML to JSON...")
        try:
            # yq -p=xml -o=json _stops.xml
            result = subprocess.run(
                ['yq', '-p=xml', '-o=json', xml_file],
                capture_output=True,
                text=True,
                check=True
            )
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            print(f"Converted to {json_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error converting XML to JSON. Make sure 'yq' is installed: brew install yq")
            print(f"Error: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print("'yq' command not found. Install it with: brew install yq")
            sys.exit(1)

    # Extract stop places and convert to JSON lines
    if not os.path.exists(jlines_file):
        print("Extracting stop places...")
        try:
            # Load the full JSON and extract StopPlace array
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stop_places = data['PublicationDelivery']['dataObjects']['SiteFrame']['stopPlaces']['StopPlace']
            
            # Write each stop place as a JSON line
            with open(jlines_file, 'w', encoding='utf-8') as f:
                for stop in stop_places:
                    json.dump(stop, f, ensure_ascii=False)
                    f.write('\n')
            
            print(f"Extracted {len(stop_places)} stop places to {jlines_file}")
        except Exception as e:
            print(f"Error extracting stop places: {e}")
            sys.exit(1)

    # Convert to final format
    print("Converting to node format...")
    
    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-sweden.txt")
    print(f"Loaded {len(rename_map)} rename rules")
    
    convert_from_json(jlines_file, output_file, rename_map)
    print(f"Done! Output written to {output_file}")