#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile

from common.io import ROOT, add_cache_flag, load_ndjson, write_csv
from common.italy import download, finish, provider_cache, write_catalog
from common.normalize import normalize_name


URL = "https://www.trentinotrasporti.it/opendata/google_transit_extraurbano_tte.zip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and check the Trentino Trasporti station list.")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    archive = provider_cache("tt", "raw", "google-transit-extraurbano.zip")
    data = download(URL, archive, use_cache=args.cache)
    extract_dir = provider_cache("tt", "raw", "google-transit-extraurbano")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        source.extractall(extract_dir)

    stops_path = extract_dir / "stops.txt"
    with stops_path.open(encoding="utf-8-sig", newline="") as handle:
        gtfs_names = {row["stop_name"].strip() for row in csv.DictReader(handle)}
    if not gtfs_names:
        raise ValueError("The TT GTFS archive did not contain stops")

    native = download(
        "https://trainview.algorab.net/",
        provider_cache("tt", "raw", "trainview-stations.html"), use_cache=args.cache,
    ).decode("utf-8", errors="replace")
    native_ids = {station_id for _, station_id, _ in re.findall(
        r"Stazioni\.push\(\[(\d+),(\d+),'([^']*)'\]\)", native,
    )}
    if not native_ids:
        raise ValueError("TT returned no native station IDs. The station file was kept.")
    nodes = load_ndjson(ROOT / "nodes" / "nodes-italy-tt.json")
    rows = [
        {"id": str(node["id"]), "name": str(node["tags"]["name"])}
        for node in nodes
    ]
    write_catalog("tt", rows, ["id", "name"])
    normalized_gtfs = {normalize_name(name): name for name in gtfs_names}
    gtfs_audit = [
        {
            "id": row["id"],
            "reviewed_name": row["name"],
            "native_id_status": "Checked" if row["id"] in native_ids else "Not found",
            "gtfs_name": normalized_gtfs.get(normalize_name(row["name"]), ""),
            "status": (
                "Found in timetable"
                if normalize_name(row["name"]) in normalized_gtfs
                else "Native ID checked; GTFS label differs" if row["id"] in native_ids
                else "Name not in timetable"
            ),
        }
        for row in rows
    ]
    write_csv(
        provider_cache("tt", "reports", "gtfs.csv"),
        gtfs_audit,
        ["id", "reviewed_name", "gtfs_name", "status", "native_id_status"],
    )

    compatibility = provider_cache("tt", "raw", "legacy-station-map.html")
    compatibility.write_text(
        "".join(f'{row["name"]}<div id="St{row["id"]}"></div>\n' for row in rows),
        encoding="utf-8",
    )
    return finish("tt")


if __name__ == "__main__":
    raise SystemExit(main())
