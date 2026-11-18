#!/usr/bin/env python3
"""Write lookup-only stations: foreign stations a provider knows by its own ID.

These rows are never playable. They let the app see that two providers name
the same station, so a train can be followed across a border. Every link comes
from one Trainline row; nothing is matched by name or position.
"""
from __future__ import annotations

import argparse
import json

from common.io import ROOT, load_ndjson, publish_nodes
from common.trainline import load_rows, unique_station_rows

# Trainline field -> (category, home country, file name, own nodes file).
PROVIDERS = {
    "db_id": ("germany_all", "DE", "lookup-germany.json", "nodes-germany.json"),
    "obb_id": ("austria_oebb", "AT", "lookup-austria-oebb.json", "nodes-austria-oebb.json"),
    "trenitalia_rtvt_id": ("italy_rfi", "IT", "lookup-italy-rfi.json", None),
}
# Other provider IDs on the same row, under the tags the app already reads.
LINK_TAGS = {"db_id": "db_station_id", "obb_id": "oebb_station_id",
             "trenitalia_rtvt_id": "viaggiatreno_station_id"}


# Categories whose node IDs are the same IDs as a Trainline link field.
OWN_ID_CATEGORIES = {"germany_all", "austria_oebb"}


def known_ids(nodes_dir=ROOT / "nodes"):
    """Known identities from playable nodes and independently sourced lookups.

    Trainline-derived lookups cannot support themselves or each other.
    """
    uics, links, tagged = set(), set(), {tag: set() for tag in LINK_TAGS.values()}
    derived = {spec[2] for spec in PROVIDERS.values()}
    native_lookups = [path for path in (nodes_dir.parent / "lookup").glob("lookup-*.json")
                      if path.name not in derived]
    for path in sorted([*nodes_dir.glob("nodes-*.json"), *native_lookups]):
        for row in load_ndjson(path):
            tags = row.get("tags") or {}
            for tag in ("uic_ref", "uic", "trainline_uic_ref"):
                uics.update(value for value in str(tags.get(tag) or "").split(";") if value)
            for tag in LINK_TAGS.values():
                if tags.get(tag):
                    links.add(str(tags[tag]))
                    if path.parent == nodes_dir:
                        tagged[tag].add(str(tags[tag]))
            if row.get("category") in OWN_ID_CATEGORIES:
                links.add(str(row["id"]))
            # These providers' own IDs are UIC codes (France adds a check digit).
            if row.get("category") == "switzerland_all":
                uics.add(str(row["id"]))
            elif row.get("category") == "france_sncf":
                uics.add(str(row["id"])[:7])
    return uics, links, tagged


def build_lookup(rows, revision, field, owned_ids=frozenset(), known=None):
    category, country, _, _ = PROVIDERS[field]
    others = tuple(name for name in LINK_TAGS if name != field)
    index = unique_station_rows(rows, country=country, key=field, id_fields=("uic", *others), foreign=True)
    out = []
    for native_id, row in sorted(index.items()):
        # Skip IDs a playable node already owns or already carries as a tag.
        if native_id in owned_ids or (known is not None and native_id in known[2][LINK_TAGS[field]]):
            continue
        # Keep a row only if an independent dataset knows the station identity.
        if known is not None and row.get("uic") not in known[0] and not any(
                row.get(name) in known[1] for name in others):
            continue
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError):
            continue
        source = f"trainline-stations:{revision}:{row['id']}"
        tags = {"name": row["name"], "country": row["country"],
                "trainline_station_id": row["id"], "station_identity_source": source}
        tags.update({LINK_TAGS[name]: row[name] for name in others if row.get(name)})
        if row.get("uic"):
            tags.update(uic_ref=row["uic"], uic_granularity="stop", uic_crosswalk_source=source)
        out.append({"type": "node", "id": native_id, "lat": lat, "lon": lon,
                    "tags": tags, "category": category})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    rows, revision = load_rows()
    if not rows:
        raise ValueError("Trainline snapshot missing: run python3 -m gen.countries italy generate rfi first")
    (ROOT / "lookup").mkdir(exist_ok=True)
    known = known_ids()
    for field, (_, _, filename, nodes_file) in PROVIDERS.items():
        owned = set()
        if nodes_file:
            owned = {str(row["id"]) for row in load_ndjson(ROOT / "nodes" / nodes_file)}
        out = build_lookup(rows, revision, field, owned, known)
        publish_nodes(ROOT / "lookup" / filename, out)
        print(f"Wrote {len(out)} lookup-only stations to lookup/{filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
