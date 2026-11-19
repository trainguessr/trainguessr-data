#!/usr/bin/env python3
"""Generate Swiss train stations from the official service-point GeoJSON."""
from __future__ import annotations

import json
import argparse
import requests
from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file

from common.config import load_rename_map

def build_nodes(data, rename_map, sectors=None):
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
        modes = {mode.strip() for mode in str(props.get('meansoftransport') or '').split('|')}
        if 'TRAIN' not in modes:
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
            
        sloid = str(props.get('sloid') or '').strip()
        if sloid:
            node['tags']['sloid'] = sloid

        if props.get('height'):
            node['tags']['height'] = str(props.get('height'))

        tracks = (sectors or {}).get(str(station_id))
        if tracks:
            node['tags']['sbb_platform_sectors'] = sectors_tag(tracks)
            
        transformed_nodes.append(node)

    return sorted(transformed_nodes, key=lambda x: x['id'])

SOURCE_URL = "https://data.sbb.ch/api/v2/catalog/datasets/haltestelle-haltekante/exports/geojson"
CACHE_SOURCE = ROOT / "cache" / "switzerland" / "stations.geojson"
SECTORS_URL = "https://data.sbb.ch/api/explore/v2.1/catalog/datasets/sektortafel/exports/json"
CACHE_SECTORS = ROOT / "cache" / "switzerland" / "sektortafel.json"


def platform_sectors(signs) -> dict[str, dict[str, str]]:
    """Return {uic: {customer track: ordered sector letters}} from SBB sector signs.

    Each sign carries the sector letter on its front and back ("-" at a platform
    end). Letters run alphabetically along a platform; a skipped letter (Bern 49
    has no I) is accepted only where a sign joins the two letters directly. Any
    other gap, a sign joining non-neighbouring letters, or a non-letter value
    drops that platform rather than guessing its order.
    """
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for sign in signs:
        uic = str(sign.get("bpuic") or "").strip()
        track = str(sign.get("kundengleisnummer") or "").strip()
        if not uic or not track:
            continue
        front = str(sign.get("sektor_vorderseite") or "").strip()
        back = str(sign.get("sektor_ruckseiter") or "").strip()
        grouped.setdefault((uic, track), []).append((front, back))
    result: dict[str, dict[str, str]] = {}
    for (uic, track), pairs in grouped.items():
        letters = {value for pair in pairs for value in pair} - {"-"}
        if len(letters) < 2 or any(len(value) != 1 or not "A" <= value <= "Z" for value in letters):
            continue
        order = sorted(letters)
        position = {value: index for index, value in enumerate(order)}
        joined = {frozenset(pair) for pair in pairs if pair[0] != pair[1] and "-" not in pair}
        if any(abs(position[a] - position[b]) != 1 for a, b in map(tuple, joined)):
            continue
        if any(ord(right) - ord(left) != 1 and frozenset((left, right)) not in joined
               for left, right in zip(order, order[1:])):
            continue
        result.setdefault(uic, {})[track] = "".join(order)
    return result


def sectors_tag(tracks: dict[str, str]) -> str:
    """Encode tracks as "8:ABCDEFGH;49:GHJKLMN", numeric tracks first."""
    def key(track):
        return (0, int(track), track) if track.isdigit() else (1, 0, track)
    return ";".join(f"{track}:{tracks[track]}" for track in sorted(tracks, key=key))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    if args.cache:
        input_file = require_cached_file(CACHE_SOURCE, "Swiss station data").read_text(encoding="utf-8")
        sector_file = require_cached_file(CACHE_SECTORS, "SBB sector signs").read_text(encoding="utf-8")
    else:
        print("Downloading Swiss station data...")
        response = requests.get(SOURCE_URL, timeout=60)
        response.raise_for_status()
        input_file = response.text
        save_source_file(CACHE_SOURCE, response.content)
        print("Downloading SBB sector signs...")
        response = requests.get(SECTORS_URL, timeout=120)
        response.raise_for_status()
        sector_file = response.text
        save_source_file(CACHE_SECTORS, response.content)

    print("Transforming SBB station data...")

    data = json.loads(input_file)

    print("Loading rename mapping...")
    rename_map = load_rename_map("switzerland")
    print(f"Loaded {len(rename_map)} rename rules")

    output = ROOT / "nodes" / "nodes-switzerland.json"
    sectors = platform_sectors(json.loads(sector_file))
    print(f"Platform sector chains for {sum(map(len, sectors.values()))} tracks at {len(sectors)} stations")
    nodes = build_nodes(data, rename_map, sectors)
    publish_nodes(output, nodes)
    print(f"Transformed {len(nodes)} stations to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
