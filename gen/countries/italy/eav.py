#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re

from common.italy import download, finish, provider_cache, write_catalog


URL = "https://orariotreni.eavsrl.it/"


def parse_station_catalog(text: str) -> list[dict[str, str]]:
    """Extract the same visible station catalogue consumed by EAV's index.js."""
    match = re.search(
        r'<script\b[^>]*\bid=["\']data-localita["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError("The EAV page did not contain data-localita station data")

    try:
        data = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        raise ValueError("The EAV data-localita station data was not valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError("The EAV data-localita station data was not a list")

    stations: dict[str, str] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        if str(row.get("visualizzato", "")).lower() != "true":
            continue
        station_id = str(row.get("id") or "").strip()
        name = re.sub(r"\s+", " ", str(row.get("descrizione") or "")).strip()
        if not station_id or not name:
            continue
        previous = stations.get(station_id)
        if previous is not None and previous != name:
            raise ValueError(
                f"EAV station {station_id} has conflicting names: "
                f"{previous!r} and {name!r}"
            )
        stations.setdefault(station_id, name)

    if not stations:
        raise ValueError("The EAV page did not contain visible station records")
    return [{"id": station_id, "name": name} for station_id, name in stations.items()]


def main() -> int:
    raw = provider_cache("eav", "raw", "stations-page.html")
    text = download(URL, raw).decode("utf-8", errors="replace")
    rows = parse_station_catalog(text)
    write_catalog("eav", rows, ["id", "name"])
    finish("eav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
