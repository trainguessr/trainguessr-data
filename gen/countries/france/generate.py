#!/usr/bin/env python3

import json
import csv
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

from common.config import (
    load_country_config, load_exclusion_rules, load_rename_map,
    require_reviewed_identity,
)
from common.io import (
    ROOT, add_cache_flag, load_ndjson, publish_nodes, require_cached_file,
    save_source_file,
)

SOURCE_URL = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?lang=fr&timezone=Europe/Berlin"
CACHE = ROOT / "cache" / "france" / "sncf.json"
LEGACY_CACHE = ROOT / "cache" / "sncf.json"
OUTPUT = ROOT / "nodes" / "nodes-france-sncf.json"
SUPPLEMENTS = ROOT / "overrides" / "france" / "cuneo-ventimiglia.csv"
PASSENGER_SUPPLEMENTS = ROOT / "overrides" / "france" / "station-supplements.json"

def convert_from_json(
    input_path,
    output_path,
    rename_map,
    split_uic_names,
    exclusion_rules,
    supplements=None,
    passenger_supplements=None,
    *,
    guard_publication=False,
):
    excluded_ids = set(exclusion_rules)
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
                if not codes_uic:
                    continue
                nom = feature.get("nom", "")
                if nom in rename_map:
                    nom = rename_map[nom]

                split_names = split_uic_names.get(nom)
                for station_id in codes_uic:
                    rule = exclusion_rules.get(station_id)
                    if rule is not None:
                        reviewed_name = (
                            split_names.get(station_id)
                            if isinstance(split_names, dict)
                            else nom
                        )
                        require_reviewed_identity(
                            rule, reviewed_name, context=f"france:{station_id}"
                        )
                if not isinstance(split_names, dict) and any(code in excluded_ids for code in codes_uic):
                    # Historical exclusions such as Mareil-Marly represent an
                    # entire source complex with no reviewed SNCF identities.
                    # Reviewed split complexes instead exclude each UIC below.
                    continue
                if len(codes_uic) > 1:
                    if not isinstance(split_names, dict):
                        raise ValueError(
                            f"Multi-UIC station {nom} requires a reviewed split_uic_names mapping"
                        )
                    reviewed_ids = {str(code) for code in split_names}
                    source_ids = set(codes_uic)
                    if reviewed_ids != source_ids:
                        raise ValueError(
                            f"Reviewed UIC split for {nom} does not match source: "
                            f"reviewed={sorted(reviewed_ids)} source={sorted(source_ids)}"
                        )
                else:
                    split_names = {codes_uic[0]: nom}

                if all(code in excluded_ids for code in codes_uic):
                    continue
                geo = feature.get("position_geographique", {})
                if not geo:
                    print(f"Skipping feature with missing geographic data: {feature}")
                    continue
                if not nom:
                    print(f"Skipping feature with missing name: {feature}")
                    continue

                # The SNCF source supplies one geometry for the aggregate public
                # station record.  Preserve that source geometry for each reviewed
                # operational UIC instead of collapsing distinct live boards into
                # one TrainGuessr station.
                for station_id in codes_uic:
                    if station_id in excluded_ids:
                        continue
                    station_name = str(split_names.get(station_id) or "").strip()
                    if not station_name:
                        raise ValueError(f"Missing reviewed display name for UIC {station_id} ({nom})")
                    tags = {
                        "name": station_name,
                        "further_ids": [],
                        "libellecourt": feature.get("libellecourt", ""),
                        "segment_drg": feature.get("segment_drg", ""),
                        "codeinsee": feature.get("codeinsee", ""),
                    }
                    reviewed = supplements_by_id.get(station_id)
                    if reviewed:
                        tags["rfi_fallback_id"] = str(reviewed["rfi_fallback_id"])
                        tags["source_review"] = "cuneo-ventimiglia"

                    node = {
                        "type": "node",
                        "id": int(station_id),
                        "lat": float(geo["lat"]),
                        "lon": float(geo["lon"]),
                        "tags": tags,
                        "category": "france_sncf",
                    }
                    outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
                    written_ids.add(station_id)
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

        for station in passenger_supplements or []:
            station_id = str(station.get("sncf_id") or "").strip()
            if not station_id or station_id in written_ids or station_id in excluded_ids:
                continue
            tags = {
                "name": str(station.get("name") or "").strip(),
                "further_ids": [],
            }
            for key in (
                "uic_stem",
                "source",
                "source_url",
                "source_date",
                "voyageurs",
                "fret",
                "code_ligne",
            ):
                value = station.get(key)
                if value not in (None, ""):
                    tags[key] = str(value)
            node = {
                "type": "node",
                "id": int(station_id),
                "lat": float(station["lat"]),
                "lon": float(station["lon"]),
                "tags": tags,
                "category": "france_sncf",
            }
            outfile.write(json.dumps(node, ensure_ascii=False, separators=(',', ':')) + '\n')
            written_ids.add(station_id)
    if errors:
        temporary_output.unlink(missing_ok=True)
        raise ValueError(f"SNCF conversion failed for {len(errors)} records")
    if guard_publication:
        try:
            publish_nodes(output_path, load_ndjson(temporary_output))
        finally:
            temporary_output.unlink(missing_ok=True)
    else:
        os.replace(temporary_output, output_path)

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    import argparse
    import requests

    parser = argparse.ArgumentParser(description="Generate French SNCF stations")
    add_cache_flag(parser)
    args = parser.parse_args(argv)

    if args.cache:
        source_file = require_cached_file(CACHE, "SNCF station data")
        print("Using the saved SNCF station data.")
    else:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(SOURCE_URL, timeout=60)
        response.raise_for_status()
        json.loads(response.text)
        save_source_file(CACHE, response.content)
        source_file = CACHE
        print("Downloaded current SNCF station data")

    print("Loading rename mapping...")
    rename_map = load_rename_map("france")
    config = load_country_config("france")
    split_uic_names = config.get("split_uic_names", {})
    exclusion_rules = load_exclusion_rules("france")
    print(f"Loaded {len(rename_map)} rename rules")

    with SUPPLEMENTS.open(encoding="utf-8-sig", newline="") as handle:
        supplements = list(csv.DictReader(handle))
    with PASSENGER_SUPPLEMENTS.open(encoding="utf-8") as handle:
        passenger_supplements = json.load(handle)
    convert_from_json(
        source_file,
        OUTPUT,
        rename_map,
        split_uic_names,
        exclusion_rules,
        supplements,
        passenger_supplements,
        guard_publication=True,
    )
    print(f"Conversion complete. Output written to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
