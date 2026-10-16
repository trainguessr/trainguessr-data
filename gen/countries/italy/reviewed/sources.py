"""Source acquisition and parsing for Italian providers."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable
from countries.italy.reviewed.paths import cache_path, require_file
from countries.italy.reviewed.settings import ITALY_CACHE


def parse_catalog_csv(
    path: Path,
    *,
    required_columns: Iterable[str] = ("id", "name"),
) -> list[dict[str, str]]:
    """Read a normalized provider catalog CSV."""

    require_file(path, "normalized station catalog")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")

        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"{path}: missing required columns: {', '.join(sorted(missing))}"
            )

        rows: list[dict[str, str]] = []

        for line_number, row in enumerate(reader, 2):
            station_id = str(row.get("id", "")).strip()
            name = str(row.get("name", "")).strip()

            if not station_id or not name:
                raise ValueError(
                    f"{path}:{line_number}: station id and name are required"
                )

            normalized = {
                key: str(value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            normalized["id"] = station_id
            normalized["name"] = name
            rows.append(normalized)

    return rows


def parse_fn() -> list[dict[str, str]]:
    return parse_catalog_csv(
        cache_path("fn", "derived", "stations.csv")
    )


def parse_tt() -> list[dict[str, str]]:
    path = require_file(
        cache_path("tt", "raw", "legacy-station-map.html"),
        "TT legacy station-ID map",
    )

    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(r"\s+", " ", name).strip(),
        }
        for name, station_id in re.findall(
            r'([^<\n]+)<div\s+id=["\']St(\d+)["\']',
            text,
            flags=re.IGNORECASE,
        )
    ]

    if not rows:
        raise ValueError(
            f"{path}: no TT station records were found; "
            "the provider page format may have changed"
        )

    return rows


def parse_fer() -> list[dict[str, str]]:
    path = cache_path("fer", "derived", "stations.csv")
    require_file(path, "normalized station catalog")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        first_row = next(csv.reader(handle), [])

    if first_row[:2] == ["id", "name"]:
        return parse_catalog_csv(path)

    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), 1):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                raise ValueError(f"{path}:{line_number}: expected id,name,line_code")
            rows.append({
                "id": row[0].strip(),
                "name": row[1].strip(),
                "line_code": row[2].strip() if len(row) > 2 else "",
            })
    return rows


def parse_eav() -> list[dict[str, str]]:
    catalog = cache_path("eav", "derived", "stations.csv")
    if catalog.is_file():
        return parse_catalog_csv(catalog)

    path = require_file(
        cache_path("eav", "raw", "stations-page.html"),
        "EAV station selector page",
    )

    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(
                r"\s+",
                " ",
                re.sub(r"<.*?>", "", name, flags=re.DOTALL),
            ).strip(),
        }
        for station_id, name in re.findall(
            r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if station_id.strip()
        and re.sub(r"<.*?>", "", name, flags=re.DOTALL).strip()
    ]

    if not rows:
        raise ValueError(
            f"{path}: no EAV station records were found; "
            "the provider page format may have changed"
        )

    return rows


def find_rfi_station_page() -> Path:
    """Use the canonical RFI page or the newest saved snapshot."""

    canonical = cache_path("rfi", "raw", "stations-page.html")
    if canonical.is_file():
        return canonical

    snapshots = sorted(
        (ITALY_CACHE / "rfi" / "raw" / "snapshots").glob("*.html")
    )

    if snapshots:
        return snapshots[-1]

    raise FileNotFoundError(
        "Missing RFI station page. Expected either:\n"
        f"  {canonical}\n"
        "or at least one HTML file under:\n"
        f"  {ITALY_CACHE / 'rfi' / 'raw' / 'snapshots'}"
    )


def parse_rfi() -> list[dict[str, str]]:
    path = find_rfi_station_page()
    text = path.read_text(encoding="utf-8", errors="replace")

    rows = [
        {
            "id": station_id.strip(),
            "name": re.sub(
                r"\s+",
                " ",
                re.sub(r"<.*?>", "", name, flags=re.DOTALL),
            ).strip(),
        }
        for station_id, name in re.findall(
            r"<option[^>]*value=[\"']?([^\"' >]+)[\"']?[^>]*>"
            r"(.*?)</option>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if station_id.strip()
        and re.sub(r"<.*?>", "", name, flags=re.DOTALL).strip()
    ]

    if not rows:
        raise ValueError(
            f"{path}: no RFI station records were found; "
            "the provider page format may have changed"
        )

    return rows
