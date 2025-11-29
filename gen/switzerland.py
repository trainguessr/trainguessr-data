import json
import random
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

def transform_sbb_to_node_format(data, output_file, rename_map):
    """
    Transform SBB station JSON data into a simpler node format.
    
    Args:
        data: Input JSON data as a dictionary
        output_file: Path to output JSON file for transformed data
        rename_map: Dictionary mapping old names to new names
    """
    # Read the input file
    transformed_nodes = []
    
    # Iterate through features
    for feature in data.get('features', []):
        if feature.get('type') == 'Feature' and 'geometry' in feature and 'properties' in feature:
            # Get coordinates from geometry
            coordinates = feature['geometry'].get('coordinates', [0, 0])
            lon, lat = coordinates[0], coordinates[1]
            
            # Get properties
            props = feature['properties']

            if props['meansoftransport'] != 'TRAIN':
                continue

            # Get the station name and apply rename mapping if needed
            station_name = props.get('designationofficial', '')
            if station_name in rename_map:
                station_name = rename_map[station_name]
            
            # Create transformed node
            node = {
                "type": "node",
                "id": props.get('number', random.randint(10000000, 99999999)),  # Use number or generate random ID
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
            
            # Add optional fields if they exist
            if props.get('height'):
                node['tags']['height'] = str(props.get('height'))
                
            # if props.get('didok_url'):
            #     node['tags']['website'] = props.get('didok_url')
            
            transformed_nodes.append(node)

    sorted_nodes = sorted(transformed_nodes, key=lambda x: x['id'])
    
    # Write the output to a file
    with open(output_file, 'w', encoding='utf-8') as f:
        for node in sorted_nodes:
            json.dump(node, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
    
    print(f"Transformed {len(transformed_nodes)} stations to {output_file}")

if __name__ == "__main__":
    import sys 
    import requests

    print("Downloading SBB station data...")

    input_file = requests.get(
        "https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson"
    ).text

    print("Transforming SBB station data...")

    data = json.loads(input_file)

    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-switzerland.txt")
    print(f"Loaded {len(rename_map)} rename rules")

    # Transform the data
    transform_sbb_to_node_format(data, "../nodes/nodes-switzerland.json", rename_map)