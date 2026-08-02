#!/usr/bin/env python3
from __future__ import annotations

import json
import re

from common.italy import download, finish, provider_cache, write_catalog


URL = "https://orariotreni.eavsrl.it/"


def main() -> int:
    raw = provider_cache("eav", "raw", "stations-page.html")
    text = download(URL, raw).decode("utf-8", errors="replace")
    match = re.search(r"\bvar\s+xml\s*=\s*(\{.*?\});", text, re.DOTALL)
    if match is None:
        raise ValueError("The EAV page did not contain its station data")
    data = json.loads(match.group(1))
    rows = [
        {"id": str(row["id"]), "name": str(row["descrizione"])}
        for row in data.get("impianto", [])
        if row.get("id") and row.get("descrizione")
    ]
    if not rows:
        raise ValueError("The EAV page did not contain station options")
    write_catalog("eav", rows, ["id", "name"])
    finish("eav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
