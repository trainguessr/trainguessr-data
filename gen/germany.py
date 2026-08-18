#!/usr/bin/env python3

import json
import io
import os
import tarfile
from datetime import datetime, timezone

import requests

from common.config import load_rename_map


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GERMANY_CACHE = os.path.join(ROOT, "cache", "germany")
NPM_REGISTRY_URL = "https://registry.npmjs.org/db-stations/latest"
BOARD_GROUPS_PATH = os.path.join(ROOT, "overrides", "germany-board-groups.json")


def _cache_age(path):
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(
        os.path.getmtime(path), timezone.utc
    )
    seconds = max(0, int(age.total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def ensure_station_cache(cache_dir=GERMANY_CACHE, session=None):
    """Ensure db-stations data exists, downloading the current npm package if needed."""
    os.makedirs(cache_dir, exist_ok=True)
    full_path = os.path.join(cache_dir, "full.json")
    data_path = os.path.join(cache_dir, "data.json")
    if os.path.exists(full_path) and os.path.exists(data_path):
        print(f"Using cached Germany station data (full.json age: {_cache_age(full_path)})")
        return full_path

    session = session or requests.Session()
    metadata_response = session.get(NPM_REGISTRY_URL, timeout=30)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    version = metadata.get("version", "unknown")
    tarball_url = metadata.get("dist", {}).get("tarball")
    if not tarball_url:
        raise ValueError("npm metadata for db-stations contains no package tarball")

    print(f"Downloading db-stations {version} from npm...")
    package_response = session.get(tarball_url, timeout=120)
    package_response.raise_for_status()
    with tarfile.open(fileobj=io.BytesIO(package_response.content), mode="r:gz") as archive:
        members = {}
        for name in ("package/full.json", "package/data.json"):
            member = archive.getmember(name)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"db-stations package is missing {name}")
            payload = extracted.read()
            json.loads(payload)
            members[name.rsplit("/", 1)[-1]] = payload

    for filename, payload in members.items():
        temporary = os.path.join(cache_dir, f".{filename}.tmp")
        with open(temporary, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, os.path.join(cache_dir, filename))
    print(f"Cached db-stations {version} (full.json age: {_cache_age(full_path)})")
    return full_path



def load_board_groups(path=BOARD_GROUPS_PATH):
    """Load reviewed DB Timetables EVA groups keyed by canonical station ID."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    groups = {}
    for row in payload.get("reviewed_board_groups", []):
        canonical_id = str(row.get("canonical_id") or "").strip()
        provider_ids = [str(value).strip() for value in row.get("provider_ids", []) if str(value).strip()]
        if not canonical_id or not provider_ids:
            raise ValueError(f"Invalid Germany board group: {row}")
        if canonical_id not in provider_ids:
            provider_ids.insert(0, canonical_id)
        groups[canonical_id] = {
            "name": str(row.get("name") or "").strip(),
            "provider_ids": list(dict.fromkeys(provider_ids)),
        }
    return groups

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

def convert_from_json(input_path, output_path, rename_map, board_groups=None):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        data = json.load(infile)
        board_groups = board_groups or {}
        seen_board_groups = set()
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
                
                tags = {
                    "name": name,
                    "ril100": ril100,
                    "station_nr": str(nr),
                    "weight": str(weight),
                    "operator": operator_name,
                    "city": address.get("city", ""),
                    "zipcode": address.get("zipcode", ""),
                    "street": address.get("street", "")
                }
                group = board_groups.get(str(station_id))
                if group:
                    expected_name = group.get("name")
                    if expected_name and expected_name != name:
                        raise ValueError(
                            f"Germany board group {station_id} expected {expected_name!r}, got {name!r}"
                        )
                    tags["provider_place_ids"] = group["provider_ids"]
                    seen_board_groups.add(str(station_id))

                # Create output node
                node = {
                    "type": "node",
                    "id": int(station_id),
                    "lat": float(lat),
                    "lon": float(lon),
                    "tags": tags,
                    "category": "germany_all"
                }

                outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
            except Exception as e:
                print(f"Error processing station: {e}")
        missing_groups = sorted(set(board_groups) - seen_board_groups)
        if missing_groups:
            raise ValueError(
                "Germany board groups reference stations absent from source: "
                + ", ".join(missing_groups)
            )

if __name__ == "__main__":
    input_file = ensure_station_cache()
    output_file = os.path.join(ROOT, "nodes", "nodes-germany.json")

    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_map("germany")
    print(f"Loaded {len(rename_map)} rename rules")
    
    board_groups = load_board_groups()
    print(f"Loaded {len(board_groups)} reviewed multi-EVA board groups")
    convert_from_json(input_file, output_file, rename_map, board_groups)
    print(f"Conversion complete. Output written to {output_file}")
