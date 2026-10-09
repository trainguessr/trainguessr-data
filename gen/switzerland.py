#!/usr/bin/env python3
"""Generate Swiss train stations from the official service-point GeoJSON."""
from __future__ import annotations

import json
from common.io import ROOT, publish_nodes

from common.config import load_rename_map

def build_nodes(data, rename_map):
    """
    Transform SBB station JSON data into a simpler node format.
    
    Args:
        data: Input JSON data as a dictionary
        rename_map: Dictionary mapping old names to new names
    """
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise ValueError("Swiss source must contain a features list")
    transformed_nodes = []
    
    for index, feature in enumerate(data["features"], 1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"Swiss feature {index} is not a GeoJSON Feature")
        geometry = feature.get("geometry")
        props = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(props, dict):
            raise ValueError(f"Swiss feature {index} lacks geometry or properties")
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError(f"Swiss feature {index} has invalid coordinates")
        lon, lat = coordinates[0], coordinates[1]
            
        if "meansoftransport" not in props:
            raise ValueError(f"Swiss feature {index} lacks meansoftransport")
        if props['meansoftransport'] != 'TRAIN':
            continue

        station_name = str(props.get('designationofficial') or '').strip()
        station_name = rename_map.get(station_name, station_name)
            
        station_id = props.get('number')
        if station_id in (None, '') or not station_name:
            raise ValueError(f"Swiss train feature {index} lacks station number or name")

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

    return sorted(transformed_nodes, key=lambda x: x['id'])

def main() -> int:
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

    output = ROOT / "nodes" / "nodes-switzerland.json"
    nodes = build_nodes(data, rename_map)
    publish_nodes(output, nodes)
    print(f"Transformed {len(nodes)} stations to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
