#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json

from common.italy import download, extract_options, finish, provider_cache, write_catalog
from common.io import ROOT, load_ndjson


URL = "https://iechub.rfi.it/ArriviPartenze/ArrivalsDepartures/Home"


def write_catalog_diff(rows: list[dict[str, str]]) -> None:
    """Persist the provider-ID delta before the reviewed rebuild runs."""
    nodes_path = ROOT / "nodes" / "nodes-italy-rfi.json"
    previous = {
        str(row["id"]): str(row.get("tags", {}).get("name", ""))
        for row in load_ndjson(nodes_path)
    }
    current = {str(row["id"]): str(row["name"]) for row in rows}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
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

    print(f"RFI catalog delta: +{len(report['added'])} / -{len(report['removed'])}")
    if report["added"]:
        print("  Added: " + ", ".join(f"{r['name']} ({r['id']})" for r in report["added"]))
    if report["removed"]:
        print("  Removed: " + ", ".join(f"{r['name']} ({r['id']})" for r in report["removed"]))


def main() -> int:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    snapshot = provider_cache("rfi", "raw", f"snapshots/stations-{date}.html")
    data = download(URL, snapshot)
    canonical = provider_cache("rfi", "raw", "stations-page.html")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_bytes(data)
    rows = extract_options(data.decode("utf-8", errors="replace"))
    if not rows:
        raise ValueError("The RFI page did not contain station options")
    write_catalog("rfi", rows, ["id", "name"])
    write_catalog_diff(rows)
    finish("rfi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
