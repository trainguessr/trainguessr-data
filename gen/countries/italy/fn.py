#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from urllib.parse import urlencode

from common.config import load_country_config, load_excluded_ids
from common.italy import current_ids, download, finish, provider_cache, write_catalog
from common.io import add_cache_flag
from common.normalize import normalize_name


URL = "https://www.trenord.it/linee-e-orari/circolazione/tempo-reale/"


# OSM limits discovery to the infrastructure owner. It never supplies Trenord IDs.
OSM_QUERY = """[out:json][timeout:60];
area["ISO3166-1"="IT"][admin_level=2]->.italy;
(nwr(area.italy)[railway~"^(station|halt)$"][operator~"^(Ferrovienord|FN)$",i];
 nwr(area.italy)[railway~"^(station|halt)$"]["operator:wikidata"="Q3736799"];
);out tags;"""


def ownership_names(payload: bytes) -> set[str]:
    elements = json.loads(payload).get("elements")
    if not isinstance(elements, list):
        raise ValueError("The OSM reply has no station list.")
    names = set()
    for element in elements:
        tags = element.get("tags", {})
        owner = tags.get("operator", "").strip().casefold()
        if tags.get("railway") not in {"station", "halt"}:
            continue
        if owner not in {"ferrovienord", "fn"} and tags.get("operator:wikidata") != "Q3736799":
            continue
        for key in ("name", "official_name", "alt_name", "short_name"):
            names.update(normalize_name(name) for name in tags.get(key, "").split(";") if name.strip())
    if not names:
        raise ValueError("OSM returned no Ferrovienord stations. The old station file was kept.")
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and check the Ferrovienord station list.")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    raw = provider_cache("fn", "raw", "stations-page.html")
    text = download(URL, raw, use_cache=args.cache).decode("utf-8", errors="replace")
    scraped = [
        {"id": station_id, "name": html.unescape(name)}
        for station_id, name in re.findall(
            r"stationDetails\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
            text,
        )
    ]
    if not scraped:
        raise ValueError("The Trenord page did not contain FN station records")
    config = load_country_config("italy")
    already_checked = {
        str(row.get("id", ""))
        for row in config.get("reviews", [])
        if row.get("operator") == "fn"
        and row.get("status") == "provider_scope_review"
        and row.get("decision") in {"confirmed_fn", "not_fn"}
    }
    accepted = current_ids("fn") | load_excluded_ids("italy", "fn") | already_checked
    by_id: dict[str, dict[str, str]] = {}
    for row in scraped:
        station_id = row["id"].strip()
        name = row["name"].strip()
        if not station_id or not name:
            continue
        previous = by_id.get(station_id)
        if previous is not None and previous["name"] != name:
            raise ValueError(f"Trenord lists station ID {station_id} with two names. Check this station ID.")
        by_id[station_id] = {"id": station_id, "name": name}
    unknown = set(by_id) - accepted
    owner_names = set()
    if unknown:
        osm = provider_cache("fn", "raw", "ferrovienord-osm.json")
        owner_names = ownership_names(download(
            "https://overpass-api.de/api/interpreter?" + urlencode({"data": OSM_QUERY}),
            osm, use_cache=args.cache,
        ))
    candidates = {
        station_id: row for station_id, row in by_id.items()
        if station_id in accepted or normalize_name(row["name"]) in owner_names
    }
    print(f"FN: filtered out {len(by_id) - len(candidates)} unrelated or unconfirmed Trenord entries.")
    rows = [
        {**row, "scope_review": "" if station_id in accepted else "check"}
        for station_id, row in sorted(candidates.items())
    ]
    write_catalog("fn", rows, ["id", "name", "scope_review"])
    return finish("fn")


if __name__ == "__main__":
    raise SystemExit(main())
