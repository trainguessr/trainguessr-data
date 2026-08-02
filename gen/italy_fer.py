#!/usr/bin/env python3
from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlencode, urlparse

from common.italy import download, finish, provider_cache, write_catalog


BASE_URL = "https://cedfc3.tsf.it/FER_PittiInfo/Linee/Linea"
LINES = {
    "BOPOR": "BOLOGNA-PORTOMAGGIORE",
    "BOVIGN": "BOLOGNA-VIGNOLA",
    "FECODN": "FERRARA-CODIGORO",
    "MOSAS": "MODENA-SASSUOLO",
    "PRSUZ": "PARMA-SUZZARA",
    "RECIA": "REGGIO EMILIA-CIANO D'ENZA",
    "REGUAST": "REGGIO EMILIA-GUASTALLA",
    "RESAS": "REGGIO EMILIA-SASSUOLO",
    "SUZFE": "SUZZARA-FERRARA",
}


def main() -> int:
    rows_by_id: dict[str, dict[str, str]] = {}
    for line_code, line_name in LINES.items():
        url = f"{BASE_URL}?{urlencode({'codiceLinea': line_code, 'nomeLinea': line_name})}"
        raw = provider_cache("fer", "raw", f"lines/{line_code}.html")
        text = download(url, raw).decode("utf-8", errors="replace")
        for href in re.findall(r'href=["\']([^"\']*Partenze\?[^"\']+)', text):
            query = parse_qs(urlparse(html.unescape(href)).query)
            station_id = query.get("codiceStazione", [""])[0].strip()
            name = query.get("nomeStazione", [""])[0].replace("''", "'").strip()
            if station_id and name:
                rows_by_id[station_id] = {
                    "id": station_id,
                    "name": name,
                    "line_code": line_code,
                }
    if not rows_by_id:
        raise ValueError("The FER line pages did not contain station links")
    rows = sorted(rows_by_id.values(), key=lambda row: row["id"])
    write_catalog("fer", rows, ["id", "name", "line_code"])
    finish("fer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
