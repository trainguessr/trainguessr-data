#!/usr/bin/env python3
"""Capture the bounded Overpass inputs used by the France physical audit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import ROOT as DATA_ROOT  # noqa: E402


OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OUTPUT_DIR = DATA_ROOT / "cache" / "france" / "audit"
QUERY_TEMPLATE = (
    "[out:json][timeout:180];"
    "(nwr[\"railway\"~\"^(station|halt|stop)$\"]({bbox});"
    "nwr[\"disused:railway\"~\"^(station|halt|stop)$\"]({bbox});"
    "nwr[\"abandoned:railway\"~\"^(station|halt|stop)$\"]({bbox}););"
    "out center tags;"
)
CAPTURES = {
    "sw": {
        "filename": "trainguessr-france-osm-sw.json",
        "bbox": "41.3,-5.2,46.3,2.25",
    },
    "se": {
        "filename": "trainguessr-france-osm-se.json",
        "bbox": "41.3,2.25,46.3,9.7",
    },
    "ne": {
        "filename": "trainguessr-france-osm-ne.json",
        "bbox": "46.3,2.25,51.2,9.7",
    },
    "nw-n": {
        "filename": "trainguessr-france-osm-nw-n.json",
        "bbox": "48.75,-5.2,51.2,2.25",
    },
    "nw-s2": {
        "filename": "trainguessr-france-osm-nw-s2.json",
        "bbox": "47.5,-5.2,48.75,2.25",
    },
}


def _capture(name: str, *, endpoint: str, timeout: float, refresh: bool) -> bool:
    spec = CAPTURES[name]
    output = OUTPUT_DIR / spec["filename"]
    if output.is_file() and not refresh:
        print(f"Using existing {output}")
        return True

    query = QUERY_TEMPLATE.format(bbox=spec["bbox"])
    try:
        response = requests.get(
            endpoint,
            params={"data": query},
            headers={
                "Accept": "application/json",
                "User-Agent": "TrainGuessr France OSM capture/1.0",
            },
            timeout=(15, timeout),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
            raise ValueError("Overpass response does not contain an elements array")
    except (requests.RequestException, ValueError) as exc:
        print(f"{name}: capture failed ({type(exc).__name__}: {exc})")
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    print(f"Wrote {output} ({len(payload['elements'])} elements)")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", choices=sorted(CAPTURES), help="capture only this area; repeatable")
    parser.add_argument("--endpoint", default=OVERPASS_ENDPOINT)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    names = args.capture or list(CAPTURES)
    failed = [
        name
        for name in names
        if not _capture(name, endpoint=args.endpoint, timeout=args.timeout, refresh=args.refresh)
    ]
    if failed:
        print(f"Missing captures after this run: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
