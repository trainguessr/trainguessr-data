#!/usr/bin/env python3
"""Build a reviewed STA/südtirolmobil rail-stop catalogue from official sources.

Authority chain:
1. südtirolmobil's official train-station-code page supplies the physical rail
   station names to enumerate.
2. STA's official EFA StopFinder supplies provider-native stop IDs and
   coordinates.

The generator accepts only deterministic provider-owned StopFinder evidence.
The official catalogue's bilingual names are queried as individual aliases.
A result may resolve when either its name is an exact alias, or when exactly
one candidate identifies itself as the railway station for an exact catalogue
alias (for example ``Naturno/Naturns`` -> ``Stazione di Naturno``). Ambiguous
or unmatched stations are written to review and are never guessed from
proximity, RFI IDs, ticket codes, or fuzzy similarity.

Default operation is non-destructive: it refreshes raw/derived cache files.
Pass --write-nodes only after reviewing the generated reports.
"""
from __future__ import annotations

import argparse
import csv
import sys
import html
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

# Provider modules normally run through ``gen/italy.py``. Keep this module
# directly executable as well for data-maintenance/debugging workflows.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.io import ROOT, write_csv, write_ndjson
from common.validate import validate_nodes

BASE = "https://efa.sta.bz.it/apb"
STOPFINDER = f"{BASE}/XML_STOPFINDER_REQUEST"
STATION_CODES = (
    "https://www.suedtirolmobil.info/en/tickets/"
    "ticketing-system-and-ticket-validation/station-codes-for-train-journeys"
)
USER_AGENT = "trainguessr-data/1.0 (STA EFA station catalogue)"

# Official südtirolmobil line 250 (Vinschgau / Val Venosta) non-RFI station
# block. Merano (code 13) is the RFI interchange and is augmented, not copied.
VINSCHGAU_STA_TICKET_CODES = {str(code) for code in range(38, 55)}
RFI_NODES = ROOT / "nodes" / "nodes-italy-rfi.json"
OEBB_NODES = ROOT / "nodes" / "nodes-austria-oebb.json"

# Exact reviewed exceptions from archived STA StopFinder responses.  These are
# provider-owned IDs selected only where the response itself identifies a rail
# stop but STA's label uses a documented abbreviation/short form that cannot
# satisfy the generic exact-name rules.  Keep this deliberately small and
# payload-checked: a provider response change fails closed instead of silently
# reusing an old ID.
# Search-only aliases for catalogue names whose plain StopFinder lookup is
# demonstrably polluted or empty.  These strings never establish identity:
# results must still pass the normal exact railway-label resolver (or a
# separately reviewed exact provider exception).
STOPFINDER_QUERY_ALIASES = {
    "Bolzano/Bozen": ("Bolzano Stazione", "Bozen Bahnhof"),
    "Bolzano Sud/Bozen Süd": ("Bolzano Sud Stazione", "Bozen Süd Bahnhof"),
    "Patsch (Austria)": ("Patsch Bahnhof",),
    "Innsbruck HBF (Austria)": ("Innsbruck Hauptbahnhof", "Innsbruck Hbf"),
    "Unterberg-Stefansbrücke (Austria)": ("Unterberg-Stefansbrücke Bahnhof", "Stefansbrücke Bahnhof"),
    "Merano-Maia Bassa/Meran-Untermais": ("Merano Maia Bassa Stazione", "Meran Untermais Bahnhof"),
}

REVIEWED_STOPFINDER_EXCEPTIONS = {
    "Mittewald an der Drau (Austria)": ("66002976", "Stazione di Mittewald"),
    "Gries (Austria)": ("66007139", "Gries am Brenner, Stazione di Gries a. Br."),
    "St. Jodok (Austria)": ("66007138", "St. Jodok a. Br. Bahnhaltestelle"),
    "Steinach in Tirol (Austria)": ("66000659", "Stazione di Steinach a. Br."),
    "Matrei (Austria)": ("66001375", "Stazione di Matrei a. Br."),
}
CACHE = ROOT / "cache" / "italy" / "sta"
FIELDS = ["id", "name", "lat", "lon", "ticket_code", "source_name"]


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() == "tr":
            self._row = []
        elif tag.casefold() in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            value = re.sub(r"\s+", " ", html.unescape("".join(self._cell))).strip()
            self._row.append(value)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _download(url: str, *, params: dict[str, str] | None = None) -> bytes:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/xml,text/xml,text/html;q=0.9,*/*;q=0.1",
        },
    )
    with urlopen(request, timeout=60) as response:
        return response.read()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,.;")


def parse_station_code_page(raw: bytes) -> list[dict[str, str]]:
    parser = _TableParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    stations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    # The official page lays out two station/code pairs per table row. Parse
    # pairs rather than depending on a particular number of columns.
    for row in parser.rows:
        for index in range(0, len(row) - 1, 2):
            name, code = row[index].strip(), row[index + 1].strip()
            if not name or not re.fullmatch(r"\d{2,3}", code):
                continue
            key = (_normalize(name), code)
            if key in seen:
                continue
            seen.add(key)
            stations.append({"name": name, "ticket_code": code})
    if not stations:
        raise ValueError("official südtirolmobil station-code page contained no station/code pairs")
    return stations


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_stopfinder(raw: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in root.iter():
        if _local(node.tag) != "odvNameElem":
            continue
        station_id = str(node.get("stateless") or node.get("id") or node.get("stopID") or "").strip()
        if not station_id or station_id in seen:
            continue
        seen.add(station_id)
        name = str(node.get("objectName") or "").strip()
        if not name:
            name = re.sub(r"\s+", " ", " ".join(node.itertext())).strip()

        # EFA versions differ on whether coordinates are attached to the name
        # element or a nearby ODV object. We consume only coordinates attached
        # to this exact provider result; missing coordinates stay review-only.
        x = str(node.get("x") or node.get("lon") or "").strip()
        y = str(node.get("y") or node.get("lat") or "").strip()
        rows.append({"id": station_id, "name": name, "x": x, "y": y})
    return rows


def stopfinder(name: str) -> tuple[bytes, list[dict[str, str]]]:
    raw = _download(
        STOPFINDER,
        params={
            "language": "it",
            "locationServerActive": "1",
            "stateless": "1",
            "type_sf": "stop",
            "name_sf": name,
            "anyObjFilter_sf": "2",
            "coordOutputFormat": "WGS84[DD.DDDDD]",
        },
    )
    return raw, parse_stopfinder(raw)


def stopfinder_by_id(provider_id: str) -> tuple[bytes, list[dict[str, str]]]:
    """Hydrate coordinates for an already proven exact STA stop ID."""
    raw = _download(
        STOPFINDER,
        params={
            "language": "it",
            "locationServerActive": "1",
            "stateless": "1",
            "type_sf": "stopID",
            "name_sf": provider_id,
            "anyObjFilter_sf": "2",
            "coordOutputFormat": "WGS84[DD.DDDDD]",
        },
    )
    return raw, parse_stopfinder(raw)


def _coordinate_pair(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        lon, lat = float(row["x"]), float(row["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lat, lon


def _aliases(source_name: str) -> list[str]:
    """Return exact catalogue aliases, preserving order.

    Parenthesised country qualifiers describe catalogue scope, not the stop
    name. Slash-separated bilingual names are independent authoritative names.
    """
    value = re.sub(r"\s*\([^)]*\)\s*$", "", source_name).strip()
    aliases: list[str] = []
    for part in value.split("/"):
        part = re.sub(r"\s+", " ", part).strip()
        if part and _normalize(part) not in {_normalize(v) for v in aliases}:
            aliases.append(part)
    return aliases or [value]



def _query_aliases(source_name: str) -> list[str]:
    """Authoritative catalogue aliases plus search-only railway qualifiers."""
    values = [*_aliases(source_name), *STOPFINDER_QUERY_ALIASES.get(source_name, ())]
    out = []
    seen = set()
    for value in values:
        key = _normalize(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out

def _rail_station_label(name: str) -> str | None:
    """Extract the station-name part from STA's Italian railway-stop labels.

    These are exact structural forms observed in StopFinder's own names; this
    is deliberately not a substring/fuzzy ``"stazione"`` test, so
    ``Autostazione`` and ``Via Stazione`` cannot qualify.
    """
    value = re.sub(r"\s+", " ", html.unescape(name)).strip()
    patterns = (
        r"^Stazione di (.+)$",
        r"^(.+?), Stazione di (.+)$",
        r"^(.+?), Stazione (.+)$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value, flags=re.IGNORECASE)
        if match:
            # In "Town, Stazione di Town", the provider's actual station
            # label is the text following the marker.
            return match.group(match.lastindex or 1).strip()
    return None


def _station_key(value: str) -> str:
    value = _normalize(value)
    return re.sub(r"[\s._'-]+", "", value)


def _alias_matches_station_label(alias: str, label: str) -> bool:
    """Require an exact catalogue component in STA's railway-station label.

    Compound catalogue names (``Egna-Termeno``) and provider labels
    (``Egna - Termeno``) differ only in separator typography.  Compare their
    ordered components exactly; never use substring or edit-distance matching.
    """
    alias_parts = [p.strip() for p in re.split(r"\s*-\s*", alias) if p.strip()]
    label_parts = [p.strip() for p in re.split(r"\s+-\s+", label) if p.strip()]
    if not alias_parts or len(alias_parts) > len(label_parts):
        return False
    return all(_station_key(a) == _station_key(b) for a, b in zip(alias_parts, label_parts))

def _resolve_candidates(
    source_name: str,
    candidates: list[dict[str, str]],
) -> tuple[dict[str, str] | None, str]:
    aliases = _aliases(source_name)
    wanted = {_normalize(alias) for alias in aliases}

    exact = [row for row in candidates if _normalize(row.get("name", "")) in wanted]
    exact_ids = {row["id"] for row in exact}
    if len(exact_ids) == 1:
        return exact[0], "exact_alias"

    railway = []
    for row in candidates:
        label = _rail_station_label(row.get("name", ""))
        if label and any(_alias_matches_station_label(alias, label) for alias in aliases):
            railway.append(row)
    railway_ids = {row["id"] for row in railway}
    if len(railway_ids) == 1:
        return railway[0], "exact_railway_label"
    reviewed = REVIEWED_STOPFINDER_EXCEPTIONS.get(source_name)
    if reviewed is not None:
        reviewed_id, reviewed_name = reviewed
        exact_payload = [
            row for row in candidates
            if row.get("id") == reviewed_id and row.get("name") == reviewed_name
        ]
        if len(exact_payload) == 1:
            return exact_payload[0], "reviewed_exact_provider_exception"

    return None, "no_unique_exact_stopfinder_match"


def _merge_candidates(groups: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    """Union repeated StopFinder queries by exact provider ID."""
    merged: dict[str, dict[str, str]] = {}
    for group in groups:
        for row in group:
            previous = merged.get(row["id"])
            if previous is None:
                merged[row["id"]] = row
            elif previous != row:
                # Same provider ID with different response payload is not
                # silently reconciled; retain the first and let resolution use
                # only identity/name evidence common to a single record.
                continue
    return list(merged.values())


def crawl() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    raw_page = _download(STATION_CODES)
    page_path = CACHE / "raw" / f"station-codes-{date}.html"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_bytes(raw_page)
    (CACHE / "raw" / "station-codes.html").write_bytes(raw_page)

    source = parse_station_code_page(raw_page)
    resolved: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    sf_dir = CACHE / "raw" / "stopfinder"
    sf_dir.mkdir(parents=True, exist_ok=True)

    for index, station in enumerate(source, 1):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", station["ticket_code"]).strip("-")
        groups: list[list[dict[str, str]]] = []
        for alias_index, alias in enumerate(_query_aliases(station["name"]), 1):
            raw, alias_candidates = stopfinder(alias)
            (sf_dir / f"{safe}-{alias_index}.xml").write_bytes(raw)
            groups.append(alias_candidates)
        candidates = _merge_candidates(groups)
        match, resolution = _resolve_candidates(station["name"], candidates)
        if match is None:
            review.append({
                "source_name": station["name"],
                "ticket_code": station["ticket_code"],
                "reason": resolution,
                "candidates": json.dumps(candidates, ensure_ascii=False, separators=(",", ":")),
            })
            continue

        # Identity is useful independently of coordinate availability.
        # StopFinder commonly omits x/y on otherwise exact stop records; that
        # must not turn an authoritative STA ID into an "unresolved" ID.
        coords = _coordinate_pair(match)
        if coords is None:
            id_raw, id_candidates = stopfinder_by_id(match["id"])
            (sf_dir / f"{station['ticket_code']}-id-{match['id']}.xml").write_bytes(id_raw)
            coordinate_rows = [
                row for row in id_candidates
                if row.get("id") == match["id"] and _coordinate_pair(row) is not None
            ]
            if coordinate_rows:
                distinct = {_coordinate_pair(row) for row in coordinate_rows}
                if len(distinct) != 1:
                    raise ValueError(
                        f"STA exact-ID coordinate lookup for {match['id']!r} "
                        "returned conflicting provider coordinates"
                    )
                coords = next(iter(distinct))
        lat, lon = coords if coords is not None else (None, None)
        resolved.append({
            "id": match["id"],
            "name": match["name"],
            "lat": "" if lat is None else f"{lat:.7f}".rstrip("0").rstrip("."),
            "lon": "" if lon is None else f"{lon:.7f}".rstrip("0").rstrip("."),
            "ticket_code": station["ticket_code"],
            "source_name": station["name"],
        })
        if coords is None:
            review.append({
                "source_name": station["name"],
                "ticket_code": station["ticket_code"],
                "reason": "resolved_id_missing_provider_coordinates",
                "candidates": json.dumps([match], ensure_ascii=False, separators=(",", ":")),
            })
        print(
            f"[{index}/{len(source)}] {station['name']} -> "
            f"{match['id']} ({resolution})"
        )

    ids: dict[str, dict[str, str]] = {}
    for row in resolved:
        previous = ids.get(row["id"])
        if previous is not None and previous != row:
            raise ValueError(f"STA StopFinder ID {row['id']!r} resolved to multiple station records")
        ids[row["id"]] = row

    derived = CACHE / "derived"
    reports = CACHE / "reports"
    derived.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    write_csv(derived / "stations.csv", sorted(resolved, key=lambda r: (r["name"].casefold(), r["id"])), FIELDS)
    write_csv(
        reports / "stopfinder-review.csv",
        review,
        ["source_name", "ticket_code", "reason", "candidates"],
    )
    return resolved, review


def _read_nodes(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _node_aliases(node: dict) -> set[str]:
    name = str(node.get("tags", {}).get("name", ""))
    return {_normalize(part) for part in re.split(r"\s+-\s+", name) if part.strip()}


def _catalogue_aliases(source_name: str) -> set[str]:
    return {_normalize(alias) for alias in _aliases(source_name)}


def _unique_existing_node(row: dict[str, str], nodes: list[dict]) -> dict | None:
    wanted = _catalogue_aliases(row["source_name"])
    matches = [
        node for node in nodes
        if _node_aliases(node) and _node_aliases(node).issubset(wanted)
    ]
    return matches[0] if len(matches) == 1 else None


def classify_rows(rows, rfi_nodes, oebb_nodes):
    """Keep Vinschgau native; map all other proven STA IDs to RFI/ÖBB."""
    native, mapped, unmapped = [], [], []
    for row in rows:
        if row["ticket_code"] in VINSCHGAU_STA_TICKET_CODES:
            native.append(row)
            continue
        rfi = _unique_existing_node(row, rfi_nodes)
        oebb = _unique_existing_node(row, oebb_nodes)
        if rfi is not None and oebb is None:
            mapped.append((row, "rfi", rfi))
        elif oebb is not None and rfi is None:
            mapped.append((row, "oebb", oebb))
        else:
            unmapped.append(row)
    return native, mapped, unmapped


def _augment_nodes(nodes, mappings, provider):
    by_id = {str(node["id"]): node for node in nodes}
    for row, target_provider, target in mappings:
        if target_provider != provider:
            continue
        node = by_id[str(target["id"])]
        tags = node.setdefault("tags", {})
        existing = tags.get("sta_station_id")
        if existing is not None and str(existing) != row["id"]:
            raise ValueError(
                f"STA augmentation conflict on {provider} node {node['id']}: "
                f"{existing!r} != {row['id']!r}"
            )
        tags["sta_station_id"] = row["id"]
        tags["sta_station_name"] = row["name"]
    return nodes



def _atomic_write_ndjson(path: Path, rows: list[dict]) -> None:
    """Write one NDJSON dataset by atomic same-directory replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.sta-tmp-{os.getpid()}")
    try:
        write_ndjson(tmp, rows)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass

def write_nodes(rows: list[dict[str, str]]) -> tuple[Path, Path, Path, dict[str, int]]:
    """Write complete Vinschgau nodes and best-effort exact RFI/ÖBB augmentation.

    Missing non-Vinschgau STA identities and unambiguous crosswalk gaps are
    partial coverage, not a reason to discard the independently complete
    Vinschgau dataset.
    """
    rfi_nodes, oebb_nodes = _read_nodes(RFI_NODES), _read_nodes(OEBB_NODES)
    native, mapped, unmapped = classify_rows(rows, rfi_nodes, oebb_nodes)

    expected_native = VINSCHGAU_STA_TICKET_CODES
    present_native = {row["ticket_code"] for row in native}
    missing_native = sorted(expected_native - present_native, key=int)
    if missing_native:
        raise ValueError(
            "STA Vinschgau node write blocked: exact STA identity is missing for "
            f"ticket codes {', '.join(missing_native)}"
        )

    incomplete = [row for row in native if not row.get("lat") or not row.get("lon")]
    if incomplete:
        names = ", ".join(row["source_name"] for row in incomplete[:5])
        suffix = "" if len(incomplete) <= 5 else f" (+{len(incomplete)-5} more)"
        raise ValueError(
            "STA Vinschgau node write blocked: provider coordinates are missing for "
            f"{len(incomplete)} stations: {names}{suffix}"
        )

    sta_nodes = [{
        "type": "node", "id": row["id"], "lat": float(row["lat"]), "lon": float(row["lon"]),
        "tags": {
            "name": re.sub(r"\s*\([^)]*\)\s*$", "", row["source_name"]).strip(),
            "sta_station_name": row["name"],
            "operator": "STA / südtirolmobil",
        },
        "category": "italy_sta",
    } for row in sorted(native, key=lambda r: (r["name"].casefold(), r["id"]))]
    errors = validate_nodes(sta_nodes)
    if errors:
        raise ValueError("STA: " + "; ".join(errors))

    augmented_rfi = _augment_nodes(rfi_nodes, mapped, "rfi")
    augmented_oebb = _augment_nodes(oebb_nodes, mapped, "oebb")
    # Validate all mutations before the first replacement.
    for label, nodes in (("RFI", augmented_rfi), ("ÖBB", augmented_oebb)):
        errors = validate_nodes(nodes)
        if errors:
            raise ValueError(f"{label} after STA augmentation: " + "; ".join(errors))

    sta_path = ROOT / "nodes" / "nodes-italy-sta.json"
    _atomic_write_ndjson(sta_path, sta_nodes)
    _atomic_write_ndjson(RFI_NODES, augmented_rfi)
    _atomic_write_ndjson(OEBB_NODES, augmented_oebb)
    stats = {
        "sta_nodes": len(sta_nodes),
        "rfi_augmented": sum(1 for _, provider, _ in mapped if provider == "rfi"),
        "oebb_augmented": sum(1 for _, provider, _ in mapped if provider == "oebb"),
        "resolved_but_unmapped": len(unmapped),
    }
    return sta_path, RFI_NODES, OEBB_NODES, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enumerate exact STA EFA train-stop IDs.")
    parser.add_argument(
        "--write-nodes",
        action="store_true",
        help="replace nodes-italy-sta.json with unique exact reviewed-source matches",
    )
    args = parser.parse_args(argv)
    rows, review = crawl()
    unresolved = sum(row["reason"] == "no_unique_exact_stopfinder_match" for row in review)
    missing_coords = sum(row["reason"] == "resolved_id_missing_provider_coordinates" for row in review)
    print(
        f"Resolved {len(rows)} exact STA stop IDs; "
        f"{unresolved} IDs unresolved; {missing_coords} resolved IDs lack StopFinder coordinates "
        "(does not block RFI/ÖBB augmentation)."
    )
    if args.write_nodes:
        sta_path, rfi_path, oebb_path, stats = write_nodes(rows)
        print(f"Wrote {stats['sta_nodes']} Vinschgau stations to {sta_path.relative_to(ROOT)}")
        print(f"Augmented {stats['rfi_augmented']} shared RFI stations in {rfi_path.relative_to(ROOT)}")
        print(f"Augmented {stats['oebb_augmented']} shared ÖBB stations in {oebb_path.relative_to(ROOT)}")
        if stats["resolved_but_unmapped"]:
            print(
                f"Left {stats['resolved_but_unmapped']} resolved non-Vinschgau STA IDs "
                "unmapped for review; valid node writes were not blocked."
            )
        if unresolved:
            print(
                f"Left {unresolved} unresolved STA catalogue identities in the review report; "
                "valid node writes were not blocked."
            )
    else:
        print("Node dataset unchanged; inspect cache/italy/sta/reports/stopfinder-review.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
