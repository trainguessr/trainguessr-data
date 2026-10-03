#!/usr/bin/env python3

import json
import sys
import os
import argparse
import shutil
from common.io import ROOT
from common.config import load_excluded_ids, load_rename_id_map, load_rename_map


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

def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _child(element, name):
    return next((child for child in element if _local_name(child.tag) == name), None)


def _path_text(element, *names):
    current = element
    for name in names:
        current = _child(current, name)
        if current is None:
            return ""
    return (current.text or "").strip()


def convert_from_xml(input_path, output_path, rename_map):
    """Stream NeTEx StopPlace records instead of materialising the 70k-stop tree."""
    import xml.etree.ElementTree as ET
    from collections import Counter

    excluded_ids = load_excluded_ids("sweden")
    rename_id_map = load_rename_id_map("sweden")
    print(f"Loaded {len(excluded_ids)} excluded station IDs")
    seen, nodes = set(), []
    modes, skipped = Counter(), Counter()

    for _event, element in ET.iterparse(input_path, events=("end",)):
        if _local_name(element.tag) != "StopPlace":
            continue
        try:
            name = _path_text(element, "Name")
            lon = _path_text(element, "Centroid", "Location", "Longitude")
            lat = _path_text(element, "Centroid", "Location", "Latitude")
            mode = _path_text(element, "TransportMode")
            modes[mode or "(missing)"] += 1
            if not lat or not lon:
                skipped["missing coordinates"] += 1; continue
            if not name:
                skipped["missing name"] += 1; continue
            if mode not in ("metro", "rail"):
                skipped[f"mode:{mode or '(missing)'}"] += 1; continue

            key_values = {}
            key_list = _child(element, "keyList")
            if key_list is not None:
                for item in key_list:
                    if _local_name(item.tag) == "KeyValue":
                        key = _path_text(item, "Key")
                        value = _path_text(item, "Value")
                        if key and value:
                            key_values[key] = value
            station_id = key_values.get("rikshallplats")
            if not station_id:
                skipped["missing station ID"] += 1; continue
            if station_id in seen:
                skipped["duplicate station ID"] += 1; continue
            if not station_id.startswith("740"):
                skipped["foreign station ID"] += 1; continue
            if station_id in excluded_ids:
                skipped["excluded station ID"] += 1; continue

            tags = {
                "name": rename_id_map.get(station_id, rename_map.get(name, name)),
                "short_name": _path_text(element, "ShortName"),
                "private_code": _path_text(element, "PrivateCode"),
                "transport_mode": mode,
                "stop_place_type": _path_text(element, "StopPlaceType"),
                "weighting": _path_text(element, "Weighting"),
            }
            alt_names = _child(element, "alternativeNames")
            if alt_names is not None:
                for item in alt_names:
                    if _local_name(item.tag) != "AlternativeName":
                        continue
                    tags.setdefault("alt_name", _path_text(item, "Name"))
                    tags.setdefault("abbreviation", _path_text(item, "Abbreviation"))
                    break
            for key in ("owner", "sellable"):
                if key in key_values:
                    tags[key] = key_values[key]
            if "trafikverket-signatures" in key_values:
                tags["abbreviation"] = key_values["trafikverket-signatures"]
            tags = {key: value for key, value in tags.items() if value}

            seen.add(station_id)
            nodes.append({
                "type": "node", "id": int(station_id),
                "lat": float(lat), "lon": float(lon),
                "tags": tags, "category": "sweden_all",
            })
        except Exception:
            skipped["malformed StopPlace"] += 1
        finally:
            element.clear()

    nodes.sort(key=lambda node: node["id"])
    with open(output_path, "w", encoding="utf-8") as outfile:
        for node in nodes:
            outfile.write(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Parsed {sum(modes.values())} stop places; wrote {len(nodes)} railway/metro stations")
    print("Modes: " + ", ".join(f"{name}={count}" for name, count in sorted(modes.items())))
    if skipped:
        print("Filtered: " + ", ".join(f"{name}={count}" for name, count in sorted(skipped.items())))



def main(argv=None):
    import requests
    import zipfile
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate Swedish railway stations")
    parser.add_argument("--cache", action="store_true",
                        help="reuse cached NeTEx source and derived conversions")
    args = parser.parse_args(argv)

    cache_dir = str(ROOT / "cache" / "sweden")
    zip_file = os.path.join(cache_dir, "stops.zip")
    xml_file = os.path.join(cache_dir, "_stops.xml")
    output_file = str(ROOT / "nodes" / "nodes-sweden.json")

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    if not args.cache:
        for cached in (zip_file, xml_file):
            if os.path.isdir(cached):
                shutil.rmtree(cached)
            elif os.path.exists(cached):
                os.remove(cached)

    if not os.path.exists(zip_file):
        print("Downloading Sweden stops data...")
        api_key = os.environ.get("TRAFIKLAB_API_KEY_STOPS")
        if not api_key:
            print("Please set the TRAFIKLAB_API_KEY_STOPS environment variable.")
            print("Get your API key from: https://www.trafiklab.se/")
            sys.exit(1)
        
        try:
            response = requests.get(
                "https://opendata.samtrafiken.se/stopsregister-netex-sweden/sweden.zip",
                params={"key": api_key},
                headers={"Accept-Encoding": "gzip"},
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException:
            print("Failed to download Sweden stops data.")
            sys.exit(1)
        
        if response.status_code != 200:
            print(f"Failed to download data: {response.status_code}")
            sys.exit(1)
        
        with open(zip_file, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded to {zip_file}")
    else:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(os.path.getmtime(zip_file), timezone.utc)
        print(f"Using cached Sweden source (age: {int(age.total_seconds() // 86400)} days)")

    if not os.path.exists(xml_file):
        print("Extracting NeTEx stop-place XML...")
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            members = [name for name in zip_ref.namelist() if name.endswith("_stops.xml")]
            if len(members) != 1:
                print(f"Expected one *_stops.xml in source archive, found {len(members)}")
                return 1
            with zip_ref.open(members[0]) as source, open(xml_file, "wb") as target:
                shutil.copyfileobj(source, target)
        print(f"Extracted to {xml_file}")

    print("Converting to node format...")
    
    print("Loading rename mapping...")
    rename_map = load_rename_map("sweden")
    print(f"Loaded {len(rename_map)} rename rules")
    
    convert_from_xml(xml_file, output_file, rename_map)
    print(f"Done! Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
