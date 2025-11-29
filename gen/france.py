#!/usr/bin/env python3

import json
import csv
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
        data = json.load(infile)
        for feature in data:
            try:
                # int(feature.get("codes_uic", 0)),
                codes_uic = feature.get("codes_uic", "").split(";")
                id1 = int(codes_uic[0])
                further_ids = codes_uic[1:] if len(codes_uic) > 1 else []
                geo = feature.get("position_geographique", {})
                if not geo:
                    print(f"Skipping feature with missing geographic data: {feature}")
                    continue
                nom = feature.get("nom", "")
                if not nom or nom == "":
                    print(f"Skipping feature with missing name: {feature}")
                    continue
                
                # Apply rename mapping if needed
                if nom in rename_map:
                    nom = rename_map[nom]
                
                node = {
                    "type": "node",
                    "id": id1,
                    "lat": float(geo.get("lat", 0)),
                    "lon": float(geo.get("lon", 0)),
                    "tags": {
                        "name": nom,
                        "further_ids": further_ids,
                        "libellecourt": feature.get("libellecourt", ""),
                        "segment_drg": feature.get("segment_drg", ""),
                        "codeinsee": feature.get("codeinsee", ""),
                    },
                    "category": "france_sncf"
                }
                outfile.write(json.dumps(node,
                                         ensure_ascii=False,
                                         separators=(',', ':')
                                         ) + '\n')
            except Exception as e:
                print(f"Error processing feature: {e}")

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
    import requests

    input_file = "../cache/sncf.json"
    output_file = "../nodes/nodes-france-sncf.json"

    if not os.path.exists(os.path.dirname(input_file)):
        os.makedirs(os.path.dirname(input_file))

    if not os.path.exists(input_file):
        data = requests.get("https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe/Berlin").text
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(data)

    # Load rename mapping
    print("Loading rename mapping...")
    rename_map = load_rename_mapping("../excludes/renamed-france.txt")
    print(f"Loaded {len(rename_map)} rename rules")

    convert_from_json(input_file, output_file, rename_map)
    print(f"Conversion complete. Output written to {output_file}")