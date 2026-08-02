#!/usr/bin/env python3
from __future__ import annotations

import html
import re

from common.config import load_excluded_ids
from common.italy import current_ids, download, finish, provider_cache, write_catalog


URL = "https://www.trenord.it/linee-e-orari/circolazione/tempo-reale/"


def main() -> int:
    raw = provider_cache("fn", "raw", "stations-page.html")
    text = download(URL, raw).decode("utf-8", errors="replace")
    rows = [
        {"id": station_id, "name": html.unescape(name)}
        for station_id, name in re.findall(
            r"stationDetails\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
            text,
        )
    ]
    allowed = current_ids("fn") | load_excluded_ids("italy", "fn")
    rows = [row for row in rows if row["id"] in allowed]
    if not rows:
        raise ValueError("The Trenord page did not contain FN station records")
    write_catalog("fn", rows, ["id", "name"])
    finish("fn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
