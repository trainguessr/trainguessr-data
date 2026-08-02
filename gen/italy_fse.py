#!/usr/bin/env python3

import argparse
import hashlib
import json
import time
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from common.config import load_country_config
from common.io import ROOT, load_ndjson, write_csv, write_ndjson
from common.validate import validate_nodes


BASE_DIR = Path(__file__).resolve().parent
ITALY_CONFIG = load_country_config("italy")
MANUAL_STATIONS = [row for row in ITALY_CONFIG.get("manual_stations", []) if row.get("operator") == "fse"]
MANUAL_NAMES = {str(row["name"]) for row in MANUAL_STATIONS}
OVERPASS_URLS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
VIAGGIATRENO_SEARCH_URL = (
    "http://www.viaggiatreno.it/infomobilitamobile/resteasy/"
    "viaggiatreno/cercaStazione/"
)
VIAGGIATRENO_ELenco_URL = (
    "http://www.viaggiatreno.it/infomobilitamobile/resteasy/"
    "viaggiatreno/elencoStazioni/0"
)
BOUNDING_BOX = "(39.0,14.5,42.5,19.5)"
OUTPUT_FILE = ROOT / "nodes" / "nodes-italy-fse.json"
FSE_CACHE = ROOT / "cache" / "italy" / "fse"
REQUEST_CACHE = FSE_CACHE / "raw" / "requests"
UNRESOLVED_OUTPUT_FILE = FSE_CACHE / "reports" / "unresolved.json"
AUDIT_FILE = FSE_CACHE / "reports" / "audit.csv"

HEADERS = {
    "User-Agent": "trainguessr-data"
}

# These names exist as rail-mapped FSE stations in OSM but do not currently
# resolve to a stable ViaggiaTreno station identifier, so they are emitted in
# the unresolved/manual-followup file rather than the main playable dataset.
EXCLUDED_OSM_NAMES = {
    str(row.get("name"))
    for row in ITALY_CONFIG.get("excluded", [])
    if row.get("operator") == "fse" and row.get("name") and row.get("name") not in MANUAL_NAMES
}

EXCLUDED_REASON_BY_OSM_NAME = {
    str(row.get("name")): str(row.get("reason", "excluded_by_country_config"))
    for row in ITALY_CONFIG.get("excluded", [])
    if row.get("operator") == "fse" and row.get("name")
}

# Known non-S13 ViaggiaTreno IDs that belong to FSE.
KNOWN_NON_S13_FSE_IDS = {
    "S11672",  # Gallipoli
}

# OSM and ViaggiaTreno often disagree on punctuation/abbreviations.
VIAGGIATRENO_ALIASES = {
    "Adelfia": ["Adelfia"],
    "Alberobello": ["Alberobello"],
    "Alessano-Corsano": ["ALESSANO CORSANO", "Alessano"],
    "Alezio": ["Alezio"],
    "Andrano-Castiglione": ["Andrano-Castiglione"],
    "Bagnolo del Salento": ["Bagnolo del Salento"],
    "Bari Ceglie-Carbonara": ["Bari Ceglie-Carbonara"],
    "Bari Centrale (FSE)": ["Bari Centrale (FC)", "Bari Centrale FC"],
    "Bari La Fitta": ["Bari La Fitta"],
    "Bari Sud-Est": ["Bari Sud Est"],
    "Campi Salentina": ["Campi Salentina"],
    "Cannole": ["Cannole"],
    "Capece": ["Capece"],
    "Capurso": ["Capurso"],
    "Carmiano-Magliano": ["Carmiano-Magliano"],
    "Casamassima": ["Casamassima"],
    "Casarano": ["Casarano"],
    "Castellana Grotte": ["Castellana Grotte"],
    "Ceglie Messapica": ["Ceglie Messapica"],
    "Cisternino Citta": ["CISTERNINO (FSC)", "Cisternino"],
    "Conversano": ["Conversano"],
    "Copertino": ["Copertino"],
    "Corigliano d'Otranto": ["Corigliano d'Otranto"],
    "Crispiano": ["Crispiano"],
    "Crispiano San Raffaele": ["CRISPIANO S.RAFFAELE", "Crispiano"],
    "Erchie-Torre Santa Susanna": ["Erchie-Torre Santa Susanna"],
    "Gagliano-Leuca": ["GAGLIANO L.", "Gagliano"],
    "Galatina": ["Galatina"],
    "Galatone": ["GALATONE CITTA'", "Galatone"],
    "Gallipoli": ["Gallipoli"],
    "Gallipoli Baia Verde": ["Gallipoli Baia Verde"],
    "Gallipoli Via Salento": ["Gallipoli Via Salento"],
    "Gallipoli via Agrigento": ["Gallipoli via Agrigento"],
    "Galugnano": ["Galugnano"],
    "Giurdignano": ["Giurdignano"],
    "Grotte di Castellana": ["Grotte di Castellana"],
    "Guagnano": ["Guagnano"],
    "Locorotondo": ["Locorotondo"],
    "Maglie": ["Maglie"],
    "Manduria": ["Manduria"],
    "Martina Franca": ["Martina Franca"],
    "Martina Franca-Colonne Grassi": ["MARTINA FRANCA-COLONNE GRASSI"],
    "Matino": ["Matino"],
    "Melissano": ["Melissano"],
    "Melpignano": ["Melpignano"],
    "Miggiano-Montesano": ["MIGGIANO", "Miggiano"],
    "Monteroni di Lecce": ["Monteroni di Lecce"],
    "Morciano-Barbarano-Castrignano-Giuliano": ["MORCIANO B.C.G.", "Morciano"],
    "Mungivacca": ["Mungivacca"],
    "Muro Leccese": ["Muro Leccese"],
    "Nardò Centrale": ["NARDO' CENTRALE", "Nardo"],
    "Nardò Città": ["NARDO' CITTA'", "Nardo"],
    "Noci": ["Noci"],
    "Noicattaro": ["Noicattaro"],
    "Novoli": ["Novoli"],
    "Otranto": ["Otranto"],
    "Parabita": ["Parabita"],
    "Pascarosa": ["Pascarosa"],
    "Poggiardo": ["Poggiardo"],
    "Presicce-Acquarica": ["Presicce-Acquarica"],
    "Putignano": ["Putignano"],
    "Putignano in Monte Laureto": ["Putignano in Monte Laureto"],
    "Putignano San Pietro Piturno": ["PUTIGNANO S.PIETRO PITURNO"],
    "Racale-Alliste": ["Racale-Alliste"],
    "Rutigliano": ["Rutigliano"],
    "Salice-Veglie": ["Salice-Veglie"],
    "Salve-Ruggiano": ["Salve-Ruggiano"],
    "Sammichele": ["Sammichele"],
    "San Cesario di Lecce": ["San Cesario di Lecce"],
    "San Donato di Lecce": ["San Donato di Lecce"],
    "San Pancrazio Salentino": ["San Pancrazio Salentino"],
    "San Paolo": ["S.PAOLO (FSC)", "S.Paolo"],
    "Sanarica": ["Sanarica"],
    "Sannicola": ["Sannicola"],
    "Seclì-Neviano-Aradeo": ["SECLI'-NEVIANO-ARADEO", "Secli"],
    "Soleto": ["Soleto"],
    "Spongano": ["Spongano"],
    "Statte": ["Statte"],
    "Sternatia": ["Sternatia"],
    "Taranto Galese": ["Taranto Galese"],
    "Taviano": ["Taviano"],
    "Tiggiano": ["Tiggiano"],
    "Tricase": ["Tricase"],
    "Triggiano": ["Triggiano"],
    "Tuglie": ["Tuglie"],
    "Turi": ["Turi"],
    "Ugento-Taurisano": ["Ugento-Taurisano"],
    "Valenzano": ["Valenzano"],
    "Valenzano Lamie": ["Valenzano Lamie"],
    "Zollino": ["Zollino"],
}


def fetch_json(url: str, data: bytes | None = None) -> Any:
    req = Request(url, headers=HEADERS, data=data)
    with urlopen(req, timeout=180) as response:
        payload = response.read()
    key = hashlib.sha256(url.encode("utf-8") + (data or b"")).hexdigest()
    cache_file = REQUEST_CACHE / f"{key}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(payload)
    return json.loads(payload.decode("utf-8"))


def fetch_overpass_json(query: str) -> Any:
    encoded = urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None

    for url in OVERPASS_URLS:
        try:
            return fetch_json(url, encoded)
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    if last_error is not None:
        raise last_error

    raise RuntimeError("No Overpass endpoint configured")


def normalize_name(name: str) -> str:
    name = name.upper()
    name = name.replace("'", " ")
    name = name.replace("`", " ")
    name = name.replace("(", " ").replace(")", " ")
    name = name.replace(".", " ")
    name = name.replace("-", " ")
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def overpass_station_query(name: str | None = None) -> str:
    if name is not None:
        return (
            "[out:json][timeout:60];"
            f'(node[railway~"station|halt|stop"][name="{name}"]{BOUNDING_BOX};'
            f'way[railway~"station|halt|stop"][name="{name}"]{BOUNDING_BOX};'
            f'relation[railway~"station|halt|stop"][name="{name}"]{BOUNDING_BOX};);'
            "out center tags;"
        )

    return (
        "[out:json][timeout:120];"
        f'(node[operator~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};'
        f'way[operator~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};'
        f'relation[operator~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};'
        f'node[network~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};'
        f'way[network~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};'
        f'relation[network~"Ferrovie del Sud Est|FSE"][railway~"station|halt|stop"]{BOUNDING_BOX};);'
        "out center tags;"
    )


def station_score(station: dict[str, Any]) -> tuple[int, int, int, int]:
    tags = station.get("tags", {})
    return (
        0 if tags.get("railway") == "station" else 1,
        0 if station.get("type") == "node" else 1,
        0 if tags.get("public_transport") == "station" else 1,
        0 if tags.get("operator") == "Ferrovie del Sud Est" else 1,
    )


def choose_best_station(stations: list[dict[str, Any]]) -> dict[str, Any]:
    return min(stations, key=station_score)


def fetch_osm_stations() -> dict[str, dict[str, Any]]:
    data = fetch_overpass_json(overpass_station_query())
    grouped: dict[str, list[dict[str, Any]]] = {}

    for station in data["elements"]:
        name = station.get("tags", {}).get("name")
        if not name:
            continue
        grouped.setdefault(name, []).append(station)

    result = {name: choose_best_station(stations) for name, stations in grouped.items()}

    # Some FSE stations are mapped in OSM but not consistently tagged with the
    # operator/network fields, so query them explicitly by railway name.
    for name in [
        "Erchie-Torre Santa Susanna",
        "Salice-Veglie",
        "San Cesario di Lecce",
        "San Donato di Lecce",
        "San Pancrazio Salentino",
    ]:
        if name in result:
            continue
        data = fetch_overpass_json(overpass_station_query(name))
        if data["elements"]:
            result[name] = choose_best_station(data["elements"])

    return result


def resolve_viaggiatreno_station(name: str) -> dict[str, Any] | None:
    aliases = VIAGGIATRENO_ALIASES.get(name, [name])
    normalized_target = normalize_name(name)

    for alias in aliases:
        normalized_alias = normalize_name(alias)
        rows = fetch_json(VIAGGIATRENO_SEARCH_URL + quote(alias))
        if not isinstance(rows, list):
            continue
        for row in rows:
            fields = [row.get("nomeLungo", ""), row.get("nomeBreve", ""), row.get("label", "")]
            normalized_fields = [normalize_name(field) for field in fields if field]

            if normalized_target in normalized_fields or normalized_alias in normalized_fields:
                return row

            if name == "Bari Centrale (FSE)" and row.get("id") == "S13201":
                return row
            if name == "Galatone" and row.get("id") == "S13152":
                return row
            if name == "Miggiano-Montesano" and row.get("id") == "S13189":
                return row

    return None


def station_coordinates(station: dict[str, Any]) -> tuple[float, float]:
    if station.get("type") == "node":
        return float(station["lat"]), float(station["lon"])

    center = station.get("center", {})
    return float(center["lat"]), float(center["lon"])


def build_node(station_name: str, osm_station: dict[str, Any], vt_station: dict[str, Any]) -> dict[str, Any]:
    lat, lon = station_coordinates(osm_station)
    tags = dict(osm_station.get("tags", {}))
    tags["name"] = station_name
    tags["operator"] = "Ferrovie del Sud Est"
    tags["ref"] = vt_station["id"]
    tags["vt_name"] = vt_station.get("nomeLungo", station_name)
    tags["osm_id"] = str(osm_station["id"])

    return {
        "type": "node",
        "id": vt_station["id"],
        "lat": lat,
        "lon": lon,
        "tags": tags,
        "category": "italy_fse"
    }


def build_unresolved_node(
    station_name: str,
    vt_station: dict[str, Any] | None,
    reason: str,
    osm_station: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tags: dict[str, Any] = {
        "name": station_name,
        "operator": "Ferrovie del Sud Est",
        "match_status": "unresolved",
        "match_reason": reason,
    }

    if vt_station is not None:
        tags["ref"] = vt_station["id"]
        tags["vt_name"] = vt_station.get("nomeLungo", station_name)
        if vt_station.get("nomeBreve"):
            tags["vt_short_name"] = vt_station["nomeBreve"]
        if vt_station.get("label"):
            tags["vt_label"] = vt_station["label"]

    if osm_station is not None:
        tags["osm_name"] = osm_station.get("tags", {}).get("name", station_name)
        tags["osm_id"] = str(osm_station["id"])

    lat, lon = "", ""
    if osm_station is not None:
        lat, lon = station_coordinates(osm_station)

    node_id = vt_station["id"] if vt_station is not None else f"OSM_{osm_station['id']}" if osm_station is not None else "UNKNOWN"

    return {
        "type": "node",
        "id": node_id,
        "lat": lat,
        "lon": lon,
        "tags": tags,
        "category": "italy_fse"
    }


def fetch_viaggiatreno_station(name: str) -> dict[str, Any] | None:
    aliases = VIAGGIATRENO_ALIASES.get(name, [name])
    normalized_target = normalize_name(name)

    for alias in aliases:
        rows = fetch_json(VIAGGIATRENO_SEARCH_URL + quote(alias))
        if not isinstance(rows, list):
            continue
        for row in rows:
            fields = [row.get("nomeLungo", ""), row.get("nomeBreve", ""), row.get("label", "")]
            normalized_fields = [normalize_name(field) for field in fields if field]
            if normalized_target in normalized_fields or row.get("id"):
                if normalized_target in normalized_fields:
                    return row

        # If the alias is itself the exact ViaggiaTreno spelling, keep the first hit.
        if rows and isinstance(rows[0], dict) and rows[0].get("id"):
            return rows[0]

    return None


def is_fse_vt_candidate(station: dict[str, Any]) -> bool:
    """Heuristic to decide whether a VT elencoStazioni entry is an FSE station."""
    sid = station.get("codiceStazione", "")
    if sid in KNOWN_NON_S13_FSE_IDS:
        return True
    if not sid.startswith("S13"):
        return False
    lat = station.get("lat", 0.0)
    lon = station.get("lon", 0.0)
    # Exclude Swiss stations (Mendrisio ~ lat 45.88, lon 8.96)
    if lat > 40 and lon < 10:
        return False
    return True


def fetch_vt_only_stations(matched_ids: set[str]) -> list[dict[str, Any]]:
    """Return VT stations that look like FSE but are not in the matched set."""
    try:
        all_stations = fetch_json(VIAGGIATRENO_ELenco_URL)
    except Exception:
        return []

    if not isinstance(all_stations, list):
        return []

    unmatched: list[dict[str, Any]] = []
    for station in all_stations:
        if not is_fse_vt_candidate(station):
            continue
        sid = station.get("codiceStazione", "")
        if sid and sid not in matched_ids:
            unmatched.append(station)

    return unmatched


def manual_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "node",
        "id": str(row["id"]),
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "tags": {
            "name": str(row["name"]),
            "operator": "Ferrovie del Sud Est",
            "ref": str(row["id"]),
            "match_status": "manual_reviewed",
            "match_reason": str(row.get("reason", "manual_review")),
        },
        "category": "italy_fse",
    }


def apply_manual_stations(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manual_ids = {str(row["id"]) for row in MANUAL_STATIONS}
    manual_names = {normalize_name(str(row["name"])) for row in MANUAL_STATIONS}
    kept = [
        node for node in nodes
        if str(node.get("id")) not in manual_ids
        and normalize_name(str(node.get("tags", {}).get("name", ""))) not in manual_names
    ]
    kept.extend(manual_node(row) for row in MANUAL_STATIONS)
    return sorted(kept, key=lambda node: str(node["id"]))


def write_audit(nodes: list[dict[str, Any]], unresolved: list[dict[str, Any]]) -> None:
    rows = []
    for node in nodes:
        tags = node.get("tags", {})
        rows.append({
            "id": node.get("id", ""),
            "name": tags.get("name", ""),
            "lat": node.get("lat", ""),
            "lon": node.get("lon", ""),
            "status": tags.get("match_status", "automatic_match"),
            "reason": tags.get("match_reason", ""),
        })
    for node in unresolved:
        tags = node.get("tags", {})
        if str(node.get("id")) in {str(row["id"]) for row in MANUAL_STATIONS}:
            continue
        rows.append({
            "id": node.get("id", ""),
            "name": tags.get("name", ""),
            "lat": node.get("lat", ""),
            "lon": node.get("lon", ""),
            "status": "excluded_or_unresolved",
            "reason": tags.get("match_reason", ""),
        })
    write_csv(AUDIT_FILE, rows, ["id", "name", "lat", "lon", "status", "reason"])


def generate_live() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    osm_stations = fetch_osm_stations()
    nodes: list[dict[str, Any]] = []
    unresolved_nodes: list[dict[str, Any]] = []
    matched_vt_ids: set[str] = set()

    for station_name in sorted(osm_stations):
        if station_name in MANUAL_NAMES:
            continue
        if station_name in EXCLUDED_OSM_NAMES:
            vt_station = fetch_viaggiatreno_station(station_name)
            reason = EXCLUDED_REASON_BY_OSM_NAME.get(station_name, "excluded_by_country_config")
            if vt_station is not None:
                matched_vt_ids.add(vt_station["id"])
            unresolved_nodes.append(build_unresolved_node(
                station_name, vt_station, reason, osm_stations[station_name]
            ))
            continue

        vt_station = resolve_viaggiatreno_station(station_name)
        if vt_station is None:
            fallback = fetch_viaggiatreno_station(station_name)
            if fallback is not None:
                matched_vt_ids.add(fallback["id"])
            unresolved_nodes.append(build_unresolved_node(
                station_name,
                fallback,
                "missing_safe_osm_to_viaggiatreno_name_match" if fallback else "missing_viaggiatreno_id",
                osm_stations[station_name],
            ))
            continue
        matched_vt_ids.add(vt_station["id"])
        nodes.append(build_node(station_name, osm_stations[station_name], vt_station))

    for vt_station in fetch_vt_only_stations(matched_vt_ids):
        localita = vt_station.get("localita", {})
        name = localita.get("nomeLungo") or localita.get("nomeBreve") or vt_station.get("codiceStazione", "")
        unresolved_nodes.append(build_unresolved_node(
            name,
            {
                "id": vt_station.get("codiceStazione", ""),
                "nomeLungo": localita.get("nomeLungo", ""),
                "nomeBreve": localita.get("nomeBreve", ""),
                "label": localita.get("label", ""),
            },
            "missing_osm_coordinates",
        ))
    return apply_manual_stations(nodes), sorted(unresolved_nodes, key=lambda node: str(node["id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and audit the FSE station dataset")
    parser.add_argument("--offline", action="store_true", help="apply reviewed manual stations to the current JSON without network access")
    args = parser.parse_args()

    if args.offline:
        nodes = apply_manual_stations(load_ndjson(OUTPUT_FILE))
        unresolved: list[dict[str, Any]] = []
    else:
        nodes, unresolved = generate_live()

    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    write_ndjson(OUTPUT_FILE, nodes)
    write_ndjson(UNRESOLVED_OUTPUT_FILE, unresolved)
    write_audit(nodes, unresolved)
    print(f"Wrote {len(nodes)} FSE stations to {OUTPUT_FILE}")
    print(f"Wrote {len(unresolved)} unresolved/excluded records to {UNRESOLVED_OUTPUT_FILE}")
    from italy_review import review_after_generation
    review_after_generation("fse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
