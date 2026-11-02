#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import csv
import json

from common.italy import download, extract_options, finish, provider_cache, write_catalog
from common.io import ROOT, add_cache_flag, load_ndjson
from common.config import load_country_config, load_exclusion_rules, require_reviewed_identity
from countries.italy.reviewed.decisions import handled_outside_provider_review


URL = "https://iechub.rfi.it/ArriviPartenze/ArrivalsDepartures/Home"


def write_catalog_diff(rows: list[dict[str, str]], previous_source: dict[str, str] | None = None) -> None:
    """Distinguish source-to-source changes from source-vs-reviewed coverage."""
    nodes_path = ROOT / "nodes" / "nodes-italy-rfi.json"
    previous = {
        str(row["id"]): str(row.get("tags", {}).get("name", ""))
        for row in load_ndjson(nodes_path)
    }
    current = {str(row["id"]): str(row["name"]) for row in rows}
    full_source = dict(current)
    config = load_country_config("italy")
    exclusions = load_exclusion_rules("italy", "rfi")
    outside_dataset = []
    for uid in list(current.keys() - previous.keys()):
        rule = exclusions.get(uid)
        outside = handled_outside_provider_review(config, "rfi", uid)
        if rule or outside:
            expected = rule or {"expected_name": outside.get("source_name") or outside.get("reviewed_name")}
            require_reviewed_identity(expected, current[uid], context=f"rfi catalogue:{uid}")
            outside_dataset.append({"id": uid, "name": current.pop(uid),
                                    "reason": "Excluded after review." if rule else "Listed in another station file."})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "known_outside_dataset": sorted(outside_dataset, key=lambda row: row["id"]),
        "comparison": "RFI download compared with the current station file",
        "source_change": None if previous_source is None else {
            "added": [{"id": k, "name": full_source[k]} for k in sorted(full_source.keys() - previous_source.keys())],
            "removed": [{"id": k, "name": previous_source[k]} for k in sorted(previous_source.keys() - full_source.keys())],
        },
        "added": [
            {"id": station_id, "name": current[station_id]}
            for station_id in sorted(current.keys() - previous.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
        ],
        "removed": [
            {"id": station_id, "name": previous[station_id]}
            for station_id in sorted(previous.keys() - current.keys(), key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
        ],
    }
    target = provider_cache("rfi", "reports", "catalog-diff.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    changes = report["source_change"]
    if changes is None:
        print("RFI download change: there is no earlier saved station list to compare.")
    else:
        print(f"RFI station list changed: {len(changes['added'])} added, {len(changes['removed'])} removed.")
    print(f"RFI download check: {len(report['added'])} new stations, "
          f"{len(report['removed'])} old stations not found.")
    if outside_dataset:
        print(f"  Excluded or covered by another provider: {len(outside_dataset)}")
    if report["added"]:
        print("  Check these station IDs: " + ", ".join(f"{r['name']} ({r['id']})" for r in report["added"]))
    if report["removed"]:
        print("  Not found in the new download; kept the old station: " + ", ".join(
            f"{r['name']} ({r['id']})" for r in report["removed"]
        ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and check the RFI station list.")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    snapshot = provider_cache("rfi", "raw", f"snapshots/stations-{date}.html")
    canonical = provider_cache("rfi", "raw", "stations-page.html")
    data = download(URL, canonical, use_cache=args.cache)
    if not args.cache:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(data)
    rows = extract_options(data.decode("utf-8", errors="replace"))
    if not rows:
        raise ValueError("The RFI page did not contain station options")
    saved_catalog = provider_cache("rfi", "derived", "stations.csv")
    previous_source = None
    if saved_catalog.is_file():
        with saved_catalog.open(encoding="utf-8-sig", newline="") as handle:
            previous_source = {row["id"]: row["name"] for row in csv.DictReader(handle)}
    write_catalog_diff(rows, previous_source)
    write_catalog("rfi", rows, ["id", "name"])
    return finish("rfi")


if __name__ == "__main__":
    raise SystemExit(main())
