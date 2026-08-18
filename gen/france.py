#!/usr/bin/env python3

import json
import csv
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

from common.config import load_country_config, load_excluded_ids, load_rename_map
from common.io import ROOT

SOURCE_URL = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe/Berlin"
CACHE = ROOT / "cache" / "sncf.json"
OUTPUT = ROOT / "nodes" / "nodes-france-sncf.json"
SUPPLEMENTS = ROOT / "sources" / "france" / "cuneo-ventimiglia.json"

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

def convert_from_json(input_path, output_path, rename_map, primary_uic, excluded_ids, supplements=None):
    supplements_by_id = {
        str(item["sncf_id"]): item
        for item in (supplements or [])
    }
    written_ids = set()
    output_path = Path(output_path)
    temporary_output = output_path.with_suffix(output_path.suffix + ".tmp")
    errors = []
    with open(input_path, 'r', encoding='utf-8') as infile, open(temporary_output, 'w', encoding='utf-8') as outfile:
        data = json.load(infile)
        for feature in data:
            try:
                codes_uic = [code.strip() for code in feature.get("codes_uic", "").split(";") if code.strip()]
                if not codes_uic or any(code in excluded_ids for code in codes_uic):
                    continue
                geo = feature.get("position_geographique", {})
                if not geo:
                    print(f"Skipping feature with missing geographic data: {feature}")
                    continue
                nom = feature.get("nom", "")
                if not nom:
                    print(f"Skipping feature with missing name: {feature}")
                    continue
                if nom in rename_map:
                    nom = rename_map[nom]

                primary_id = str(primary_uic.get(nom, codes_uic[0]))
                if primary_id not in codes_uic:
                    raise ValueError(f"Primary UIC {primary_id} is not listed for {nom}")
                further_ids = [code for code in codes_uic if code != primary_id]
                tags = {
                    "name": nom,
                    "further_ids": further_ids,
                    "libellecourt": feature.get("libellecourt", ""),
                    "segment_drg": feature.get("segment_drg", ""),
                    "codeinsee": feature.get("codeinsee", ""),
                }
                reviewed = next((supplements_by_id[code] for code in codes_uic
                                 if code in supplements_by_id), None)
                if reviewed:
                    tags["rfi_fallback_id"] = str(reviewed["rfi_fallback_id"])
                    tags["source_review"] = "cuneo-ventimiglia"

                node = {
                    "type": "node",
                    "id": int(primary_id),
                    "lat": float(geo["lat"]),
                    "lon": float(geo["lon"]),
                    "tags": tags,
                    "category": "france_sncf",
                }
                outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
                written_ids.add(primary_id)
            except Exception as e:
                print(f"Error processing feature: {e}")
                errors.append(str(e))

        # `gares-de-voyageurs` currently omits the reviewed French passenger
        # stops on Cuneo–Ventimiglia. If a future export gains one of them,
        # the branch above wins and merely attaches the RFI fallback tag.
        for station_id, station in supplements_by_id.items():
            if station_id in written_ids or station_id in excluded_ids:
                continue
            node = {
                "type": "node",
                "id": int(station_id),
                "lat": float(station["lat"]),
                "lon": float(station["lon"]),
                "tags": {
                    "name": str(station["name"]),
                    "rfi_fallback_id": str(station["rfi_fallback_id"]),
                    "source": "reviewed-cuneo-ventimiglia-supplement",
                },
                "category": "france_sncf",
            }
            outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
            written_ids.add(station_id)
    if errors:
        temporary_output.unlink(missing_ok=True)
        raise ValueError(f"SNCF conversion failed for {len(errors)} records")
    os.replace(temporary_output, output_path)


                    # 
  #  {
  #      "nom": "Narbonne",
  #      "libellecourt": "NBN",
  #      "segment_drg": "A",
  #      "position_geographique": {
  #          "lon": 3.00591,
  #          "lat": 43.190387
  #      },
  #      "codeinsee": "11262",
  #      "codes_uic": "87781104"
  #  },


if __name__ == "__main__":
    import argparse
    import requests

    parser = argparse.ArgumentParser(description="Generate French SNCF stations")
    parser.add_argument("--refresh", action="store_true", help="download SNCF data even if the cache is fresh")
    parser.add_argument("--max-cache-age-days", type=int, default=7)
    args = parser.parse_args()

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    age_days = None
    if CACHE.exists():
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(CACHE.stat().st_mtime, timezone.utc)
        age_days = int(age.total_seconds() // 86400)
    if args.refresh or age_days is None or age_days > args.max_cache_age_days:
        response = requests.get(SOURCE_URL, timeout=60)
        response.raise_for_status()
        temporary_cache = CACHE.with_suffix(".json.tmp")
        temporary_cache.write_text(response.text, encoding="utf-8")
        json.loads(temporary_cache.read_text(encoding="utf-8"))
        os.replace(temporary_cache, CACHE)
        print("Downloaded current SNCF station data")
    else:
        print(f"Using cached SNCF data (age: {age_days} days)")

    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_map("france")
    config = load_country_config("france")
    primary_uic = config.get("primary_uic", {})
    excluded_ids = load_excluded_ids("france")
    print(f"Loaded {len(rename_map)} rename rules")

    with SUPPLEMENTS.open(encoding="utf-8") as handle:
        supplements = json.load(handle)
    convert_from_json(CACHE, OUTPUT, rename_map, primary_uic, excluded_ids, supplements)
    print(f"Conversion complete. Output written to {OUTPUT}")
