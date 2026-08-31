import json
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

def transform_sbb_to_node_format(data, output_file, rename_map):
    """
    Transform SBB station JSON data into a simpler node format.
    
    Args:
        data: Input JSON data as a dictionary
        output_file: Path to output JSON file for transformed data
        rename_map: Dictionary mapping old names to new names
    """
    transformed_nodes = []
    
    for feature in data.get('features', []):
        if feature.get('type') == 'Feature' and 'geometry' in feature and 'properties' in feature:
            coordinates = feature['geometry'].get('coordinates', [0, 0])
            lon, lat = coordinates[0], coordinates[1]
            
            props = feature['properties']

            if props['meansoftransport'] != 'TRAIN':
                continue

            station_name = props.get('designationofficial', '')
            if station_name in rename_map:
                station_name = rename_map[station_name]
            
            station_id = props.get('number')
            if station_id in (None, ''):
                continue

            node = {
                "type": "node",
                "id": station_id,
                "lat": lat,
                "lon": lon,
                "tags": {
                    "name": station_name,
                    "operator": props.get('businessorganisationabbreviationde', 'SBB'),
                    "public_transport": "station",
                    "railway": "station",
                    "station": "train",
                    "train": "yes",
                    "wheelchair": "yes" if props.get('haltekante') == 'ok' else "limited",
                    "abbreviation": props.get('abbreviation', ''),
                    "isocountrycode": props.get('isocountrycode', 'CH'),
                    "canton": props.get('cantonname', ''),
                },
                "category": "switzerland_all"
            }
            
            if props.get('height'):
                node['tags']['height'] = str(props.get('height'))
            
            transformed_nodes.append(node)

    sorted_nodes = sorted(transformed_nodes, key=lambda x: x['id'])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for node in sorted_nodes:
            json.dump(node, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
    
    print(f"Transformed {len(transformed_nodes)} stations to {output_file}")

if __name__ == "__main__":
    import sys 
    import requests

    print("Downloading SBB station data...")

    response = requests.get(
        "https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson",
        timeout=60,
    )
    response.raise_for_status()
    input_file = response.text

    print("Transforming SBB station data...")

    data = json.loads(input_file)

    print("Loading rename mapping...")
    rename_map = load_rename_map("switzerland")
    print(f"Loaded {len(rename_map)} rename rules")

    transform_sbb_to_node_format(data, ROOT / "nodes" / "nodes-switzerland.json", rename_map)
