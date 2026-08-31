#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

from common.italy import download, extract_options, finish, provider_cache, write_catalog


URL = "https://iechub.rfi.it/ArriviPartenze/ArrivalsDepartures/Home"


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
    finish("rfi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
