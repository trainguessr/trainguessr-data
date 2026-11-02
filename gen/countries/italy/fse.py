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
from common.io import ROOT, publish_nodes, write_ndjson, write_csv
from common.io import add_cache_flag
from common.validate import validate_nodes


BASE_DIR = Path(__file__).resolve().parent
# These station decisions are refreshed before each source build so choices
# made by the shared review tool take effect on the same run.
ITALY_CONFIG: dict[str, Any] = {}
MANUAL_STATIONS: list[dict[str, Any]] = []
MANUAL_NAMES: set[str] = set()
EXCLUDED_OSM_NAMES: set[str] = set()
EXCLUDED_REASON_BY_OSM_NAME: dict[str, str] = {}
EXCLUDED_REASON_BY_ID: dict[str, str] = {}


def refresh_review_config() -> None:
    global ITALY_CONFIG, MANUAL_STATIONS, MANUAL_NAMES
    global EXCLUDED_OSM_NAMES, EXCLUDED_REASON_BY_OSM_NAME, EXCLUDED_REASON_BY_ID
    ITALY_CONFIG = load_country_config("italy")
    MANUAL_STATIONS = [
        row for row in ITALY_CONFIG.get("manual_stations", [])
        if row.get("operator") == "fse"
    ]
    MANUAL_NAMES = {str(row["name"]) for row in MANUAL_STATIONS}
    fse_exclusions = [
        row for row in ITALY_CONFIG.get("excluded", [])
        if row.get("operator") == "fse"
    ]
    EXCLUDED_OSM_NAMES = {
        str(row["name"])
        for row in fse_exclusions
        if row.get("name") and row.get("name") not in MANUAL_NAMES
    }
    EXCLUDED_REASON_BY_OSM_NAME = {
        str(row["name"]): str(row.get("reason", "excluded_by_country_config"))
        for row in fse_exclusions if row.get("name")
    }
    EXCLUDED_REASON_BY_ID = {
        str(row["id"]): str(row.get("reason", "excluded_by_country_config"))
        for row in fse_exclusions if row.get("id")
    }


refresh_review_config()
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
EXCLUDED_OUTPUT_FILE = FSE_CACHE / "reports" / "excluded.json"
AUDIT_FILE = FSE_CACHE / "reports" / "audit.csv"

HEADERS = {
    "User-Agent": "trainguessr-data"
}
CACHE_ONLY = False

# Known non-S13 ViaggiaTreno IDs used by FSE.
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
    key = hashlib.sha256(url.encode("utf-8") + (data or b"")).hexdigest()
    cache_file = REQUEST_CACHE / f"{key}.json"
    if CACHE_ONLY:
        if not cache_file.is_file():
            raise FileNotFoundError(f"Saved FSE source response is missing: {cache_file}")
        payload = cache_file.read_bytes()
    else:
        req = Request(url, headers=HEADERS, data=data)
        with urlopen(req, timeout=180) as response:
            payload = response.read()
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
            if not CACHE_ONLY:
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
    by_id = {str(node.get("id")): node for node in nodes}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        name = normalize_name(str(node.get("tags", {}).get("name", "")))
        by_name.setdefault(name, []).append(node)
    for row in MANUAL_STATIONS:
        station_id = str(row["id"])
        expected_name = normalize_name(str(row["name"]))
        same_id = by_id.get(station_id)
        if same_id is not None:
            actual_name = normalize_name(str(same_id.get("tags", {}).get("name", "")))
            if actual_name != expected_name:
                raise ValueError(
                    f"italy/fse: Check station ID {station_id}. The saved name is "
                    f"{row['name']!r}; the downloaded name is {same_id.get('tags', {}).get('name')!r}."
                )
        conflicting_ids = {
            str(node.get("id")) for node in by_name.get(expected_name, [])
            if str(node.get("id")) != station_id
        }
        if conflicting_ids:
            raise ValueError(
                f"italy/fse: manual station {station_id} name {row['name']!r} "
                f"is now generated under {sorted(conflicting_ids)}"
            )
    kept = [
        node for node in nodes
        if str(node.get("id")) not in manual_ids
    ]
    kept.extend(manual_node(row) for row in MANUAL_STATIONS)
    return sorted(kept, key=lambda node: str(node["id"]))


def write_audit(nodes: list[dict[str, Any]], unresolved: list[dict[str, Any]]) -> None:
    rows = []
    excluded_ids = set(EXCLUDED_REASON_BY_ID)
    for node in nodes:
        tags = node.get("tags", {})
        checked_manually = tags.get("match_status") == "manual_reviewed"
        rows.append({
            "id": node.get("id", ""),
            "name": tags.get("name", ""),
            "lat": node.get("lat", ""),
            "lon": node.get("lon", ""),
            "status": "ID checked" if checked_manually else "Included",
            "reason": "Provider ID and station details were checked." if checked_manually else "Station matched to provider data.",
        })
    for node in unresolved:
        tags = node.get("tags", {})
        if str(node.get("id")) in {str(row["id"]) for row in MANUAL_STATIONS}:
            continue
        station_id = str(node.get("id"))
        excluded = station_id in excluded_ids
        reason = str(tags.get("match_reason", ""))
        if reason == "missing_viaggiatreno_id":
            status = "missing_native_id"
            reason = "No ViaggiaTreno ID was found for this station name."
        elif excluded or tags.get("name") in EXCLUDED_OSM_NAMES:
            status = "excluded"
            reason = EXCLUDED_REASON_BY_ID.get(station_id, reason) or "Excluded after station review."
        else:
            status = "excluded_or_unresolved"
            reason = "Check this station's saved details."
        rows.append({
            "id": node.get("id", ""),
            "name": tags.get("name", ""),
            "source_name": tags.get("name", ""),
            "reviewed_name": tags.get("name", ""),
            "lat": node.get("lat", ""),
            "lon": node.get("lon", ""),
            "status": {
                "missing_native_id": "Provider ID needed",
                "excluded": "Excluded after review",
                "excluded_or_unresolved": "Check this station",
            }[status],
            "reason": reason,
        })
    write_csv(
        AUDIT_FILE,
        rows,
        ["id", "name", "source_name", "reviewed_name", "lat", "lon", "status", "reason"],
    )


def generate_live() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refresh_review_config()
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
        station_id = str(vt_station.get("codiceStazione", ""))
        unresolved_nodes.append(build_unresolved_node(
            name,
            {
                "id": station_id,
                "nomeLungo": localita.get("nomeLungo", ""),
                "nomeBreve": localita.get("nomeBreve", ""),
                "label": localita.get("label", ""),
            },
            EXCLUDED_REASON_BY_ID.get(station_id, "missing_osm_coordinates"),
        ))
    manual_ids = {str(row["id"]) for row in MANUAL_STATIONS}
    unresolved_nodes = [
        node for node in unresolved_nodes
        if str(node.get("id")) not in manual_ids
    ]
    return apply_manual_stations(nodes), sorted(unresolved_nodes, key=lambda node: str(node["id"]))


def apply_saved_name_decisions(nodes: list[dict[str, Any]]) -> None:
    """Apply only name choices that still match the saved source report."""
    from countries.italy.review_decisions import review_key
    from countries.italy.review_nodes import load_review_rows

    config = load_country_config("italy")
    decisions = {
        (
            str(saved.get("operator", "")),
            str(saved.get("id", "")),
            str(saved.get("status", "")),
            str(saved.get("source_name", "")),
            str(saved.get("reviewed_name", "")),
        ): str(saved.get("decision", ""))
        for saved in config.get("reviews", [])
    }
    by_id = {str(node.get("id")): node for node in nodes}
    for row in load_review_rows("fse"):
        if row["status"] != "matched_name_difference":
            continue
        decision = decisions.get(review_key("fse", row))
        if decision == "keep_reviewed_name":
            name = row["reviewed_name"]
        elif decision == "use_source_name":
            name = row["source_name"]
        else:
            continue
        node = by_id.get(row["id"])
        if node is not None:
            node.setdefault("tags", {})["name"] = name



def write_source_reports(records):
    excluded, pending = [], []
    for record in records:
        tags = record.get("tags", {})
        target = excluded if str(record.get("id")) in EXCLUDED_REASON_BY_ID or tags.get("name") in EXCLUDED_OSM_NAMES else pending
        target.append(record)
    write_ndjson(UNRESOLVED_OUTPUT_FILE, pending)
    write_ndjson(EXCLUDED_OUTPUT_FILE, excluded)
    return pending, excluded


def main(argv: list[str] | None = None) -> int:
    global CACHE_ONLY
    parser = argparse.ArgumentParser(description="Generate and audit the FSE station dataset")
    add_cache_flag(parser)
    args = parser.parse_args(argv)
    CACHE_ONLY = args.cache

    nodes, unresolved = generate_live()
    errors = validate_nodes(nodes)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    write_source_reports(unresolved)
    write_audit(nodes, unresolved)
    from countries.italy.review import pending_review_rows, review_after_generation
    pending = pending_review_rows("fse")
    if pending:
        reviewed = review_after_generation("fse")
        if reviewed is None:
            print(f"Check these {len(pending)} FSE station details. "
                  f"Report: {AUDIT_FILE.relative_to(ROOT)}. The station file is unchanged. "
                  "Run `python3 -m gen.countries italy review fse` in a terminal.")
            return 2
        if reviewed:
            return int(reviewed)

        # The first build saved all source responses. Rebuild from those saved
        # files after the user has made decisions; do not download a second time.
        CACHE_ONLY = True
        nodes, unresolved = generate_live()
        errors = validate_nodes(nodes)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        write_source_reports(unresolved)
        write_audit(nodes, unresolved)
        apply_saved_name_decisions(nodes)
        pending = pending_review_rows("fse")
        if pending:
            print(f"Check these {len(pending)} FSE station details. "
                  f"Report: {AUDIT_FILE.relative_to(ROOT)}. The station file is unchanged.")
            return 2

    publish_nodes(OUTPUT_FILE, nodes)
    pending_records, excluded_records = write_source_reports(unresolved)
    print(f"OK | italy/fse | {len(nodes)} checked stations; "
          f"{len(pending_records)} unresolved stations; {len(excluded_records)} excluded source records")
    if pending_records:
        print(f"Check: {UNRESOLVED_OUTPUT_FILE.relative_to(ROOT)}")
    if excluded_records:
        print(f"Excluded records: {EXCLUDED_OUTPUT_FILE.relative_to(ROOT)}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
