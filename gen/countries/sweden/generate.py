#!/usr/bin/env python3

import os
import argparse
import shutil
from pathlib import Path
from common.io import ROOT, add_cache_flag, publish_nodes, require_cached_file, save_source_file
from common.config import (
    load_exclusion_rules, load_rename_id_rules, load_rename_map,
    require_reviewed_identity,
)


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


ERA_ENDPOINT = "https://graph.data.era.europa.eu/repositories/rinf-plus"
ERA_QUERY = """PREFIX era: <http://data.europa.eu/949/>
SELECT ?uopid ?location WHERE {
  ?op a era:OperationalPoint ;
      era:inCountry <http://publications.europa.eu/resource/authority/country/SWE> ;
      era:uopid ?uopid ; era:primaryLocation ?location .
}"""


def load_era_locations(path, *, use_cache):
    """ERA RINF operational points: Trafikverket signature -> TAP primary location."""
    import json
    import requests

    if use_cache:
        require_cached_file(path, "ERA RINF Swedish primary locations")
    else:
        response = requests.post(ERA_ENDPOINT, data={"query": ERA_QUERY}, timeout=240,
                                 headers={"Accept": "application/sparql-results+json",
                                          "User-Agent": "TrainGuessr-data/1.0"})
        response.raise_for_status()
        save_source_file(path, response.content)
    return json.loads(Path(path).read_text())["results"]["bindings"]


def uic_by_signature(bindings):
    """Map each signature to a UIC only when RINF gives it exactly one location.

    RINF's UOPID is "SE" + signature and its primary location "SE" + five digits;
    the Swedish UIC station number is the country code 74 + those digits.
    """
    import re
    from collections import defaultdict

    found = defaultdict(set)
    for row in bindings:
        uopid = row["uopid"]["value"]
        location = row["location"]["value"].rsplit("/", 1)[-1]
        if uopid.startswith("SE") and re.fullmatch(r"SE\d{5}", location):
            found[uopid[2:].upper()].add("74" + location[2:])
    return {signature: codes.pop() for signature, codes in found.items() if len(codes) == 1}


def convert_from_xml(input_path, output_path, rename_map, uic_codes=None, lookup_path=None):
    """Stream NeTEx StopPlace records instead of materialising the 70k-stop tree."""
    import xml.etree.ElementTree as ET
    from collections import Counter

    exclusions = load_exclusion_rules("sweden")
    rename_id_rules = load_rename_id_rules("sweden")
    rename_id_map = {station_id: str(rule["to"]) for station_id, rule in rename_id_rules.items()}
    print(f"Loaded {len(exclusions)} excluded station IDs")
    seen, nodes, abroad = set(), [], []
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
            # Samtrafiken national stop IDs start with 740; others are stops abroad.
            foreign = not station_id.startswith("740")
            rule = exclusions.get(station_id)
            if rule is not None and not foreign:
                skipped["excluded station ID"] += 1; continue
            if station_id in rename_id_rules and not foreign:
                require_reviewed_identity(
                    {"expected_name": rename_id_rules[station_id]["from"]},
                    name,
                    context=f"sweden rename:{station_id}",
                )

            tags = {
                "name": name if foreign else rename_id_map.get(station_id, rename_map.get(name, name)),
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
            # Only the Trafikverket signature; alternative-name abbreviations are other codes.
            signature_text = key_values.get("trafikverket-signatures", "")
            signatures = {part.strip().upper() for part in signature_text.replace("|", ",").split(",")
                          if part.strip()}
            codes = {(uic_codes or {}).get(signature) for signature in signatures} - {None}
            if len(codes) == 1:
                tags.update(uic_ref=codes.pop(), uic_granularity="stop",
                            uic_crosswalk_source="ERA RINF primaryLocation by Trafikverket signature")

            seen.add(station_id)
            (abroad if foreign else nodes).append({
                "type": "node", "id": int(station_id),
                "lat": float(lat), "lon": float(lon),
                "tags": tags, "category": "sweden_all",
            })
        except (TypeError, ValueError) as exc:
            station_label = element.attrib.get("id", "unknown")
            raise ValueError(f"Malformed Swedish StopPlace {station_label}: {exc}") from exc
        finally:
            element.clear()

    # A UIC claimed by two stop places identifies neither.
    claims = Counter(node["tags"].get("uic_ref") for node in nodes)
    for node in nodes:
        if node["tags"].get("uic_ref") and claims[node["tags"]["uic_ref"]] > 1:
            for key in ("uic_ref", "uic_granularity", "uic_crosswalk_source"):
                del node["tags"][key]
    nodes.sort(key=lambda node: node["id"])
    publish_nodes(Path(output_path), nodes)
    if lookup_path is not None:
        abroad.sort(key=lambda node: node["id"])
        Path(lookup_path).parent.mkdir(exist_ok=True)
        publish_nodes(Path(lookup_path), abroad)
        print(f"Wrote {len(abroad)} stop places abroad to {lookup_path}")
    print(f"Parsed {sum(modes.values())} stop places; wrote {len(nodes)} railway/metro stations")
    print("Modes: " + ", ".join(f"{name}={count}" for name, count in sorted(modes.items())))
    if skipped:
        print("Filtered: " + ", ".join(f"{name}={count}" for name, count in sorted(skipped.items())))



def main(argv=None):
    import requests
    import zipfile
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate Swedish railway stations")
    add_cache_flag(parser)
    args = parser.parse_args(argv)

    cache_dir = str(ROOT / "cache" / "sweden")
    zip_file = os.path.join(cache_dir, "stops.zip")
    xml_file = os.path.join(cache_dir, "_stops.xml")
    output_file = ROOT / "nodes" / "nodes-sweden.json"

    if args.cache:
        require_cached_file(Path(zip_file), "Swedish NeTEx source")
    elif not os.path.exists(cache_dir):
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
            return 1
        
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
            return 1
        
        if response.status_code != 200:
            print(f"Failed to download data: {response.status_code}")
            return 1
        
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
    
    era_file = Path(cache_dir) / "era-primary-locations.json"
    uic_codes = uic_by_signature(load_era_locations(era_file, use_cache=args.cache))
    convert_from_xml(xml_file, output_file, rename_map, uic_codes, ROOT / "lookup" / "lookup-sweden.json")
    print(f"Done! Output written to {output_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
