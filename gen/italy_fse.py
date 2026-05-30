#!/usr/bin/env python3

import json
import time
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
OVERPASS_URLS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
VIAGGIATRENO_SEARCH_URL = (
    "http://www.viaggiatreno.it/infomobilitamobile/resteasy/"
    "viaggiatreno/cercaStazione/"
)
BOUNDING_BOX = "(39.0,14.5,42.5,19.5)"
OUTPUT_FILE = BASE_DIR.parent / "nodes" / "nodes-italy-fse.json"
UNRESOLVED_OUTPUT_FILE = "nodes-italy-fse-unresolved.json"

HEADERS = {
    "User-Agent": "trainguessr-data"
}

# These names exist as rail-mapped FSE stations in OSM but do not currently
# resolve to a stable ViaggiaTreno station identifier, so they are emitted in
# the unresolved/manual-followup file rather than the main playable dataset.
EXCLUDED_OSM_NAMES = {
    "Erchie-Torre Santa Susanna",
    "Gallipoli Porto",
    "Salice-Veglie",
    "San Cesario di Lecce",
    "San Donato di Lecce",
    "San Pancrazio Salentino",
    "Sava",
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
        return json.loads(response.read().decode("utf-8"))


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
            f"(node[railway~\"station|halt|stop\"][name=\"{name}\"]{BOUNDING_BOX};"
            f"way[railway~\"station|halt|stop\"][name=\"{name}\"]{BOUNDING_BOX};"
            f"relation[railway~\"station|halt|stop\"][name=\"{name}\"]{BOUNDING_BOX};);"
            "out center tags;"
        )

    return (
        "[out:json][timeout:120];"
        f"(node[operator~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};"
        f"way[operator~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};"
        f"relation[operator~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};"
        f"node[network~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};"
        f"way[network~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};"
        f"relation[network~\"Ferrovie del Sud Est|FSE\"][railway~\"station|halt|stop\"]{BOUNDING_BOX};);"
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


def build_unresolved_node(station_name: str, vt_station: dict[str, Any],
                          reason: str, osm_station: dict[str, Any] | None = None) -> dict[str, Any]:
    tags = {
        "name": station_name,
        "operator": "Ferrovie del Sud Est",
        "ref": vt_station["id"],
        "vt_name": vt_station.get("nomeLungo", station_name),
        "match_status": "unresolved",
        "match_reason": reason,
    }

    if vt_station.get("nomeBreve"):
        tags["vt_short_name"] = vt_station["nomeBreve"]
    if vt_station.get("label"):
        tags["vt_label"] = vt_station["label"]
    if osm_station is not None:
        tags["osm_name"] = osm_station.get("tags", {}).get("name", station_name)
        tags["osm_id"] = str(osm_station["id"])

    return {
        "type": "node",
        "id": vt_station["id"],
        "lat": "",
        "lon": "",
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


def main() -> None:
    osm_stations = fetch_osm_stations()
    nodes: list[dict[str, Any]] = []
    unresolved_nodes: list[dict[str, Any]] = []
    unresolved_names: list[str] = []

    for station_name in sorted(osm_stations):
        if station_name in EXCLUDED_OSM_NAMES:
            vt_station = fetch_viaggiatreno_station(station_name)
            if vt_station is not None:
                unresolved_nodes.append(build_unresolved_node(
                    station_name,
                    vt_station,
                    "missing_safe_osm_to_viaggiatreno_coordinate_match",
                    osm_stations[station_name]
                ))
            continue

        vt_station = resolve_viaggiatreno_station(station_name)
        if vt_station is None:
            fallback_station = fetch_viaggiatreno_station(station_name)
            if fallback_station is not None:
                unresolved_nodes.append(build_unresolved_node(
                    station_name,
                    fallback_station,
                    "missing_safe_osm_to_viaggiatreno_name_match",
                    osm_stations[station_name]
                ))
            else:
                unresolved_names.append(station_name)
            continue

        nodes.append(build_node(station_name, osm_stations[station_name], vt_station))

    if unresolved_names:
        raise RuntimeError(
            "Failed to resolve ViaggiaTreno IDs for: " + ", ".join(unresolved_names)
        )

    nodes.sort(key=lambda node: node["id"])
    unresolved_nodes.sort(key=lambda node: node["id"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as output_file:
        for node in nodes:
            output_file.write(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n")

    with open(UNRESOLVED_OUTPUT_FILE, "w", encoding="utf-8") as output_file:
        for node in unresolved_nodes:
            output_file.write(json.dumps(node, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"Generated {len(nodes)} FSE stations into {OUTPUT_FILE}")
    print(f"Generated {len(unresolved_nodes)} unresolved FSE stations into {UNRESOLVED_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
