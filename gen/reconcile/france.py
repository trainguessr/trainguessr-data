#!/usr/bin/env python3
"""Audit French OSM railway features against the current SNCF catalogue.

The SNCF export is the runtime identity source. OSM finds
physical and separate-provider candidates; an unmatched OSM UIC stem is never
written to the playable SNCF nodes without independent provider evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from common.io import ROOT, load_ndjson, logical_path


SNCF_EXPORT_URL = (
    "https://data.sncf.com/api/explore/v2.1/catalog/datasets/"
    "gares-de-voyageurs/exports/json?lang=fr&timezone=Europe/Berlin"
)
INFRASTRUCTURE_URL = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/liste-des-gares/exports/json"
FREQUENTATION_URL = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/frequentation-gares/exports/json"
IDFM_STATIONS_URL = "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/emplacement-des-gares-idf/records"
IDFM_STOPS_URL = "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/arrets-lignes/records"
INFRASTRUCTURE_SOURCE_DATE = "2024-03-28"
BOUNDARY_URL = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/FRA.geo.json"
SNCF_EXPORT = ROOT / "cache" / "sncf.json"
INFRASTRUCTURE_EXPORT = ROOT / "cache" / "france" / "liste-des-gares.json"
FREQUENTATION_EXPORT = ROOT / "cache" / "france" / "frequentation-gares.json"
SNCF_NODES = ROOT / "nodes" / "nodes-france-sncf.json"
AUDIT_FILE = ROOT / "docs" / "review" / "france-reconciliation.json"
CUNEO_SUPPLEMENTS = ROOT / "docs" / "review" / "france" / "cuneo-ventimiglia.json"
DEFAULT_OSM_DIR = ROOT / "cache" / "france" / "audit"
DEFAULT_OSM_GLOB = "cache/france/audit/trainguessr-france-osm-*.json"

# These OSM features omit operator tags, so use the reviewed IDFM crosswalk
# rather than treating their old SNCF UIC stems as runtime identities.
IDFM_RER_CROSSWALKS: dict[str, dict[str, Any]] = {
    "8775808": {
        "station_id": 439,
        "station_name": "Le V\u00e9sinet-Le Pecq",
        "line": "A",
        "network": "RER A",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:43237",
    },
    "8775834": {
        "station_id": 597,
        "station_name": "Noisy-Champs",
        "line": "A",
        "network": "RER A",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:58937",
    },
    "8775870": {
        "station_id": 790,
        "station_name": "Sceaux",
        "line": "B",
        "network": "RER B",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:59206",
    },
    "8775871": {
        "station_id": 287,
        "station_name": "Fontenay-aux-Roses",
        "line": "B",
        "network": "RER B",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:43125",
    },
    "8775883": {
        "station_id": 429,
        "station_name": "Le Guichet",
        "line": "B",
        "network": "RER B",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:43232",
    },
    "8775886": {
        "station_id": 401,
        "station_name": "La Hacquini\u00e8re",
        "line": "B",
        "network": "RER B",
        "operator": "RATP",
        "stop_id": "IDFM:monomodalStopPlace:47046",
    },
}

# Metropolitan France and Corsica from the FRA GeoJSON boundary.  This is a
# selection boundary only; it is not used as station or provider evidence.
FRANCE_POLYGONS: tuple[tuple[tuple[float, float], ...], ...] = (
    (
        (9.560016, 42.152492),
        (9.229752, 41.380007),
        (8.775723, 41.583612),
        (8.544213, 42.256517),
        (8.746009, 42.628122),
        (9.390001, 43.009985),
        (9.560016, 42.152492),
    ),
    (
        (3.588184, 50.378992),
        (4.286023, 49.907497),
        (4.799222, 49.985373),
        (5.674052, 49.529484),
        (5.897759, 49.442667),
        (6.18632, 49.463803),
        (6.65823, 49.201958),
        (8.099279, 49.017784),
        (7.593676, 48.333019),
        (7.466759, 47.620582),
        (7.192202, 47.449766),
        (6.736571, 47.541801),
        (6.768714, 47.287708),
        (6.037389, 46.725779),
        (6.022609, 46.27299),
        (6.5001, 46.429673),
        (6.843593, 45.991147),
        (6.802355, 45.70858),
        (7.096652, 45.333099),
        (6.749955, 45.028518),
        (7.007562, 44.254767),
        (7.549596, 44.127901),
        (7.435185, 43.693845),
        (6.529245, 43.128892),
        (4.556963, 43.399651),
        (3.100411, 43.075201),
        (2.985999, 42.473015),
        (1.826793, 42.343385),
        (0.701591, 42.795734),
        (0.338047, 42.579546),
        (-1.502771, 43.034014),
        (-1.901351, 43.422802),
        (-1.384225, 44.02261),
        (-1.193798, 46.014918),
        (-2.225724, 47.064363),
        (-2.963276, 47.570327),
        (-4.491555, 47.954954),
        (-4.59235, 48.68416),
        (-3.295814, 48.901692),
        (-1.616511, 48.644421),
        (-1.933494, 49.776342),
        (-0.989469, 49.347376),
        (1.338761, 50.127173),
        (1.639001, 50.946606),
        (2.513573, 51.148506),
        (2.658422, 50.796848),
        (3.123252, 50.780363),
        (3.588184, 50.378992),
    ),
)

IDENTITY_TAGS = (
    "name",
    "official_name",
    "railway",
    "train",
    "public_transport",
    "uic_ref",
    "railway:ref",
    "ref:FR:sncf:resarail",
    "operator",
    "network",
    "note",
    "description",
    "source",
    "disused",
    "railway:disused",
    "abandoned:railway",
    "demolished:railway",
    "razed:railway",
)
UIC_PATTERN = re.compile(r"(?<!\d)87\d{5,}(?!\d)")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _values(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _values(item)
    elif value not in (None, ""):
        yield str(value)


def uic_stems(value: Any) -> set[str]:
    """Return seven-digit French UIC stems from scalar or structured tags."""
    stems: set[str] = set()
    for text in _values(value):
        stems.update(match.group(0)[:7] for match in UIC_PATTERN.finditer(text))
    return stems


def _location(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    geometry = element.get("geometry")
    if not isinstance(geometry, list):
        return None
    points = [
        (float(point["lat"]), float(point["lon"]))
        for point in geometry
        if isinstance(point, dict) and point.get("lat") is not None and point.get("lon") is not None
    ]
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude = math.radians((first[0] + second[0]) / 2.0)
    x = math.radians(second[1] - first[1]) * math.cos(latitude)
    y = math.radians(second[0] - first[0])
    return 6_371_000.0 * math.hypot(x, y)


def _inside(point: tuple[float, float], ring: tuple[tuple[float, float], ...]) -> bool:
    x, y = point
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index - 1]
        x2, y2 = ring[index]
        if ((y1 > y) != (y2 > y)) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _in_france(location: tuple[float, float]) -> bool:
    lat, lon = location
    return any(_inside((lon, lat), polygon) for polygon in FRANCE_POLYGONS)


def load_osm_elements(paths: Iterable[Path]) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        payload = _read_json(path)
        source = payload.get("elements") if isinstance(payload, dict) else payload
        if not isinstance(source, list):
            raise ValueError(f"OSM input must contain an elements array: {path}")
        for element in source:
            if not isinstance(element, dict):
                continue
            key = (str(element.get("type", "")), str(element.get("id", "")))
            if key in seen:
                continue
            seen.add(key)
            elements.append(element)
    return elements


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _infrastructure_summary(record: dict[str, Any]) -> dict[str, Any]:
    location = record.get("c_geo") or record.get("geo_point_2d") or {}
    summary = {
        "source_url": INFRASTRUCTURE_URL,
        "source_date": INFRASTRUCTURE_SOURCE_DATE,
        "code_uic": str(record.get("code_uic") or ""),
        "name": record.get("libelle", ""),
        "voyageurs": record.get("voyageurs", ""),
        "fret": record.get("fret", ""),
        "code_ligne": record.get("code_ligne", ""),
        "commune": record.get("commune", ""),
        "coordinates": {
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
    }
    return {
        key: value
        for key, value in summary.items()
        if value not in ("", None, {}, {"lat": None, "lon": None})
    }


def _infrastructure_by_stem(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        for stem in uic_stems(record.get("code_uic")):
            by_stem[stem].append(record)
    return by_stem


def _frequency_by_stem(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        for stem in uic_stems(record.get("code_uic_complet")):
            by_stem[stem].append(record)
    return by_stem


def _frequency_summary(record: dict[str, Any]) -> dict[str, Any]:
    year_keys = (
        "total_voyageurs_2015",
        "total_voyageurs_2016",
        "totalvoyageurs2017",
        "total_voyageurs_2018",
        "total_voyageurs_2019",
        "total_voyageurs_2020",
        "total_voyageurs_2021",
        "total_voyageurs_2022",
        "total_voyageurs_2023",
        "total_voyageurs_2024",
    )
    counts = {
        key[-4:]: record.get(key)
        for key in year_keys
        if record.get(key) not in (None, "")
    }
    return {
        "source_url": FREQUENTATION_URL,
        "code_uic_complet": str(record.get("code_uic_complet") or ""),
        "name": record.get("nom_gare", ""),
        "segmentation_marketing": record.get("segmentation_marketing", ""),
        "annual_passenger_counts": counts,
    }


def _has_historical_passenger_count(record: dict[str, Any]) -> bool:
    summary = _frequency_summary(record)
    return any(float(value or 0) > 0 for value in summary["annual_passenger_counts"].values())


def _normalised_names(tags: dict[str, Any]) -> set[str]:
    return {
        _normalise(tags.get(key))
        for key in ("name", "official_name", "railway:name")
        if tags.get(key)
    }


def _infrastructure_uic_conflicts(
    stem: str,
    features: Iterable[dict[str, Any]],
    infrastructure_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    feature_names = set()
    feature_locations: list[tuple[float, float]] = []
    for feature in features:
        tags = feature.get("tags") if isinstance(feature.get("tags"), dict) else {}
        feature_names.update(_normalised_names(tags))
        location = _location(feature)
        if location is not None:
            feature_locations.append(location)
    conflicts: list[dict[str, Any]] = []
    for record in infrastructure_records:
        record_stems = uic_stems(record.get("code_uic"))
        if not record_stems or stem in record_stems:
            continue
        name = _normalise(record.get("libelle"))
        location = record.get("c_geo") or record.get("geo_point_2d") or {}
        if not name or location.get("lat") is None or location.get("lon") is None:
            continue
        if name not in feature_names:
            continue
        record_location = (float(location["lat"]), float(location["lon"]))
        if not any(_distance_m(record_location, feature_location) <= 1_000.0 for feature_location in feature_locations):
            continue
        conflicts.append(_infrastructure_summary(record))
    return conflicts


def _candidate_features(elements: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    selected: list[dict[str, Any]] = []
    by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for element in elements:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        location = _location(element)
        if tags.get("railway") not in {"station", "halt"} or tags.get("train") != "yes":
            continue
        if location is None or not _in_france(location):
            continue
        selected.append(element)
        for stem in uic_stems(tags.get("uic_ref")):
            by_stem[stem].append(element)
    return selected, by_stem


def _output_stems(path: Path) -> set[str]:
    stems: set[str] = set()
    for row in load_ndjson(path):
        stems.update(uic_stems(row.get("id")))
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        stems.update(uic_stems(tags.get("further_ids")))
    return stems


def _baseline_sncf_stems(export_records: Iterable[dict[str, Any]]) -> set[str]:
    """Return SNCF identities before the reviewed infrastructure supplements."""
    represented: set[str] = set()
    for record in export_records:
        represented.update(uic_stems(record.get("codes_uic")))
    if CUNEO_SUPPLEMENTS.is_file():
        for record in _read_json(CUNEO_SUPPLEMENTS):
            if isinstance(record, dict):
                represented.update(uic_stems(record.get("sncf_id")))
    exclusions = _read_json(ROOT / "overrides" / "exclusions" / "france.json")
    for record in exclusions.get("excluded", []) if isinstance(exclusions, dict) else []:
        if isinstance(record, dict):
            represented.difference_update(uic_stems(record.get("id")))
    return represented


def _lifecycle_signals(features: Iterable[dict[str, Any]]) -> list[str]:
    signals: set[str] = set()
    for element in features:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        for key, value in tags.items():
            text = _normalise(f"{key} {value}")
            if any(marker in text for marker in ("disused", "abandoned", "closed", "desaffect", "ferme", "heritage", "tourist")):
                signals.add(f"{key}={value}")
            if any(marker in _normalise(key) for marker in ("demolished", "razed", "removed", "destroyed")):
                signals.add(f"{key}={value}")
    return sorted(signals)


def _dismantled(features: Iterable[dict[str, Any]]) -> bool:
    for element in features:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        for key, value in tags.items():
            key_text = _normalise(key)
            if any(marker in key_text for marker in ("demolished", "razed", "removed", "destroyed")):
                return True
            if key_text == "railway" and _normalise(value) in {"demolished", "razed", "removed"}:
                return True
    return False


def _feature_summary(element: dict[str, Any]) -> dict[str, Any]:
    location = _location(element)
    tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
    summary: dict[str, Any] = {
        "url": f"https://www.openstreetmap.org/{element.get('type', 'node')}/{element.get('id')}",
        "osm_type": element.get("type"),
        "osm_id": element.get("id"),
        "tags": {key: tags[key] for key in IDENTITY_TAGS if key in tags},
    }
    if location is not None:
        summary["latitude"] = round(location[0], 7)
        summary["longitude"] = round(location[1], 7)
    return summary


def _provider_group(features: Iterable[dict[str, Any]], stem: str | None = None) -> str:
    if stem in IDFM_RER_CROSSWALKS:
        return "ratp_rer"
    values: list[str] = []
    for element in features:
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        values.extend(str(tags.get(key) or "") for key in ("name", "operator", "network", "description"))
    text = _normalise(" ".join(values))
    if "ratp" in text or "rer" in text:
        return "ratp_rer"
    if "caminu di ferru" in text or "chemin de fer de la corse" in text:
        return "cfc"
    if "chemins de fer de provence" in text or "regie regionale des transports" in text:
        return "chemins_de_fer_de_provence"
    if "ttda" in text:
        return "ttda"
    if "attcv" in text:
        return "attcv"
    if "haute auvergne" in text or "cfha" in text:
        return "cfha"
    if "monaco" in text:
        return "monaco"
    if "region occitanie" in text:
        return "region_occitanie"
    return "sncf_or_unspecified"


def _decision(
    provider_group: str,
    features: list[dict[str, Any]],
    infrastructure: list[dict[str, Any]],
    frequency: list[dict[str, Any]],
    infrastructure_conflicts: list[dict[str, Any]],
) -> tuple[str, str]:
    if _dismantled(features):
        return (
            "dismantled_exclusion",
            "OSM contains an explicit demolished, razed, removed, or destroyed lifecycle tag.",
        )
    if provider_group == "ratp_rer":
        return (
            "deferred_secondary_mode",
            "The unmatched feature is tagged for RATP/RER urban rail, not the SNCF heavy-rail namespace.",
        )
    if provider_group in {
        "cfc",
        "chemins_de_fer_de_provence",
        "ttda",
        "attcv",
        "cfha",
    }:
        return (
            "new_provider_needed",
            "The feature identifies a separate railway operator without a verified SNCF runtime identity.",
        )
    if provider_group in {"sncf_or_unspecified", "region_occitanie"} and any(
        str(record.get("voyageurs") or "").upper() == "O" for record in infrastructure
    ):
        return (
            "added_existing_provider",
            "The official SNCF Reseau infrastructure register marks the exact UIC as a passenger railway point, and OSM supplies the physical station feature.",
        )
    current_conflicts = [
        record
        for record in infrastructure_conflicts
        if str(record.get("voyageurs") or "").upper() == "O"
    ]
    if current_conflicts and provider_group in {"sncf_or_unspecified", "region_occitanie"}:
        return (
            "added_existing_provider",
            "The OSM UIC conflicts with an older frequency UIC, but the current SNCF Reseau register provides an exact passenger UIC for the same named and located feature.",
        )
    if infrastructure_conflicts:
        return (
            "unresolved",
            "The historical passenger record conflicts with a different current SNCF Reseau UIC for the same named and located feature; the historical ID is not promoted.",
        )
    if provider_group in {"sncf_or_unspecified", "region_occitanie"} and any(
        _has_historical_passenger_count(record) for record in frequency
    ):
        return (
            "added_existing_provider",
            "The official SNCF Gares & Connexions frequency register contains historical passenger counts for the exact UIC, and OSM supplies the current physical station feature.",
        )
    if provider_group == "monaco":
        return (
            "provider_gap",
            "The feature is in Monaco and is outside the current France SNCF catalogue scope; its provider namespace needs an explicit scope decision.",
        )
    return (
        "unresolved",
        "The current SNCF export has no matching UIC stem. OSM evidence alone is insufficient to add a runtime ID or assert the physical lifecycle.",
    )


def reconcile(
    export_records: list[dict[str, Any]],
    osm_elements: list[dict[str, Any]],
    output_path: Path = SNCF_NODES,
    infrastructure_records: list[dict[str, Any]] | None = None,
    frequency_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected, by_stem = _candidate_features(osm_elements)
    represented = _baseline_sncf_stems(export_records)
    infrastructure_by_stem = _infrastructure_by_stem(infrastructure_records or [])
    frequency_by_stem = _frequency_by_stem(frequency_records or [])
    candidate_stems = sorted(stem for stem in by_stem if stem not in represented)
    outcomes: list[dict[str, Any]] = []
    for stem in candidate_stems:
        features = sorted(by_stem[stem], key=lambda element: (str(element.get("type")), str(element.get("id"))))
        group = _provider_group(features, stem)
        infrastructure = infrastructure_by_stem.get(stem, [])
        frequency = frequency_by_stem.get(stem, [])
        infrastructure_conflicts = _infrastructure_uic_conflicts(
            stem, features, infrastructure_records or []
        )
        status, reason = _decision(
            group, features, infrastructure, frequency, infrastructure_conflicts
        )
        operators = sorted({
            str((element.get("tags") or {}).get("operator"))
            for element in features
            if (element.get("tags") or {}).get("operator")
        })
        networks = sorted({
            str((element.get("tags") or {}).get("network"))
            for element in features
            if (element.get("tags") or {}).get("network")
        })
        idfm_crosswalk = IDFM_RER_CROSSWALKS.get(stem)
        evidence = {
            "osm_feature_count": len(features),
            "osm_features": [_feature_summary(element) for element in features],
            "current_sncf_export_match": False,
            "official_sncf_infrastructure": [
                _infrastructure_summary(record) for record in infrastructure
            ],
            "official_sncf_frequency": [
                _frequency_summary(record) for record in frequency
            ],
            "official_sncf_uic_conflicts": infrastructure_conflicts,
        }
        if idfm_crosswalk is not None:
            evidence["official_idfm_rer"] = {
                **idfm_crosswalk,
                "source_urls": [IDFM_STATIONS_URL, IDFM_STOPS_URL],
                "reviewed_at": "2026-08-28",
            }
        outcomes.append({
            "uic_stem": stem,
            "status": status,
            "provider_group": group,
            "reason": reason,
            "lifecycle_signals": _lifecycle_signals(features),
            "operator_values": operators,
            "network_values": networks,
            "evidence": evidence,
        })

    export_uics: list[str] = []
    missing_fields = 0
    multi_uic = 0
    for record in export_records:
        if not isinstance(record, dict):
            continue
        codes = uic_stems(record.get("codes_uic"))
        export_uics.extend(sorted(codes))
        if len(codes) > 1:
            multi_uic += 1
        if not record.get("nom") or not record.get("position_geographique") or not codes:
            missing_fields += 1

    statuses = Counter(row["status"] for row in outcomes)
    groups = Counter(row["provider_group"] for row in outcomes)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "audit_with_explicit_unresolved",
        "scope": "Metropolitan France and Corsica railway=station|halt features with train=yes",
        "source_urls": {
            "sncf_export": SNCF_EXPORT_URL,
            "sncf_infrastructure": INFRASTRUCTURE_URL,
            "idfm_rer_stations": IDFM_STATIONS_URL,
            "idfm_rer_stops": IDFM_STOPS_URL,
            "boundary": BOUNDARY_URL,
            "osm": "https://overpass-api.de/",
        },
        "counts": {
            "captured_osm_elements": len(osm_elements),
            "france_station_halt_elements": len(selected),
            "france_uic_stems": len(by_stem),
            "represented_sncf_stems": len(by_stem.keys() & represented),
            "candidate_stems": len(candidate_stems),
            "candidate_statuses": dict(sorted(statuses.items())),
            "candidate_provider_groups": dict(sorted(groups.items())),
            "official_sncf_export_records": len(export_records),
            "official_sncf_export_uic_stems": len(set(export_uics)),
            "official_sncf_records_with_missing_identity_fields": missing_fields,
            "official_sncf_records_with_multiple_uic": multi_uic,
            "generated_sncf_nodes": len(load_ndjson(output_path)),
            "official_sncf_infrastructure_records": len(infrastructure_records or []),
            "candidate_official_passenger_records": sum(
                any(
                    str(record.get("voyageurs") or "").upper() == "O"
                    for record in infrastructure_by_stem.get(row["uic_stem"], [])
                )
                for row in outcomes
            ),
            "candidate_official_uic_correction_records": sum(
                bool(row["evidence"]["official_sncf_uic_conflicts"])
                and row["status"] == "added_existing_provider"
                for row in outcomes
            ),
            "candidate_historical_passenger_records": sum(
                not any(
                    str(record.get("voyageurs") or "").upper() == "O"
                    for record in infrastructure_by_stem.get(row["uic_stem"], [])
                )
                and any(
                    _has_historical_passenger_count(record)
                    for record in frequency_by_stem.get(row["uic_stem"], [])
                )
                for row in outcomes
            ),
            "candidate_historical_passenger_additions": sum(
                row["status"] == "added_existing_provider"
                and not any(
                    str(record.get("voyageurs") or "").upper() == "O"
                    for record in infrastructure_by_stem.get(row["uic_stem"], [])
                )
                and not row["evidence"]["official_sncf_uic_conflicts"]
                and any(
                    _has_historical_passenger_count(record)
                    for record in frequency_by_stem.get(row["uic_stem"], [])
                )
                for row in outcomes
            ),
        },
        "source_files": {
            "sncf_export": logical_path(SNCF_EXPORT),
            "sncf_nodes": logical_path(output_path),
        },
        "outcomes": outcomes,
    }


def build_passenger_supplements(
    audit: dict[str, Any],
    infrastructure_records: list[dict[str, Any]],
    frequency_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build reviewed runtime supplements from exact SNCF infrastructure UICs."""
    by_stem = _infrastructure_by_stem(infrastructure_records)
    frequency_by_stem = _frequency_by_stem(frequency_records or [])
    supplements: list[dict[str, Any]] = []
    for outcome in audit.get("outcomes", []):
        if outcome.get("status") != "added_existing_provider":
            continue
        records = by_stem.get(str(outcome.get("uic_stem")), [])
        passenger_records = [
            record
            for record in records
            if str(record.get("voyageurs") or "").upper() == "O"
        ]
        frequency = next(
            (
                record
                for record in frequency_by_stem.get(str(outcome.get("uic_stem")), [])
                if _has_historical_passenger_count(record)
            ),
            None,
        )
        conflict_records = [
            record
            for record in outcome.get("evidence", {}).get("official_sncf_uic_conflicts", [])
            if str(record.get("voyageurs") or "").upper() == "O"
        ]
        if not passenger_records and not conflict_records and frequency is None:
            continue
        record = sorted(
            passenger_records or records,
            key=lambda row: str(row.get("code_uic") or ""),
        )[0] if passenger_records or records else {}
        conflict = sorted(conflict_records, key=lambda row: str(row.get("code_uic") or ""))[0] if conflict_records else {}
        code = str(conflict.get("code_uic") or record.get("code_uic") or (frequency or {}).get("code_uic_complet") or "")
        location = conflict.get("coordinates") or record.get("c_geo") or record.get("geo_point_2d") or {}
        if not location and outcome.get("evidence", {}).get("osm_features"):
            osm = outcome["evidence"]["osm_features"][0]
            location = {"lat": osm.get("latitude"), "lon": osm.get("longitude")}
        if not code or location.get("lat") is None or location.get("lon") is None:
            continue
        source = "SNCF Reseau liste-des-gares" if passenger_records or conflict_records else "SNCF Gares & Connexions frequentation-gares"
        source_url = INFRASTRUCTURE_URL if passenger_records or conflict_records else FREQUENTATION_URL
        source_date = INFRASTRUCTURE_SOURCE_DATE if passenger_records or conflict_records else "2015-2024"
        supplements.append({
            "sncf_id": code,
            "uic_stem": code[:7],
            "name": str(conflict.get("name") or record.get("libelle") or (frequency or {}).get("nom_gare") or "").strip(),
            "lat": float(location["lat"]),
            "lon": float(location["lon"]),
            "source": source,
            "source_url": source_url,
            "source_date": source_date,
            "voyageurs": str(conflict.get("voyageurs") or record.get("voyageurs") or ""),
            "fret": str(conflict.get("fret") or record.get("fret") or ""),
            "code_ligne": str(conflict.get("code_ligne") or record.get("code_ligne") or ""),
        })
        if frequency is not None and not passenger_records and not conflict_records:
            supplements[-1]["historical_passenger_counts"] = _frequency_summary(frequency)["annual_passenger_counts"]
    return sorted(supplements, key=lambda row: row["sncf_id"])


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sncf-input", type=Path, default=SNCF_EXPORT)
    parser.add_argument("--infrastructure-input", type=Path, default=INFRASTRUCTURE_EXPORT)
    parser.add_argument("--frequentation-input", type=Path, default=FREQUENTATION_EXPORT)
    parser.add_argument("--nodes-input", type=Path, default=SNCF_NODES)
    parser.add_argument("--osm-input", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=AUDIT_FILE)
    parser.add_argument("--supplements-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    osm_paths = args.osm_input or sorted(DEFAULT_OSM_DIR.glob("trainguessr-france-osm-*.json"))
    if not osm_paths:
        raise SystemExit(f"No OSM captures supplied; use --osm-input or {DEFAULT_OSM_GLOB}")
    export = _read_json(args.sncf_input)
    if not isinstance(export, list):
        raise ValueError("SNCF export must be a JSON array")
    infrastructure: list[dict[str, Any]] = []
    if args.infrastructure_input.is_file():
        payload = _read_json(args.infrastructure_input)
        if not isinstance(payload, list):
            raise ValueError("SNCF infrastructure export must be a JSON array")
        infrastructure = payload
    frequency: list[dict[str, Any]] = []
    if args.frequentation_input.is_file():
        payload = _read_json(args.frequentation_input)
        if not isinstance(payload, list):
            raise ValueError("SNCF frequentation export must be a JSON array")
        frequency = payload
    elements = load_osm_elements(osm_paths)
    audit = reconcile(export, elements, args.nodes_input, infrastructure, frequency)
    audit["source_files"]["sncf_export"] = logical_path(args.sncf_input)
    audit["source_files"]["infrastructure"] = logical_path(args.infrastructure_input)
    audit["source_files"]["frequentation"] = logical_path(args.frequentation_input)
    audit["source_files"]["osm"] = [logical_path(path) for path in osm_paths]
    if args.supplements_output is not None:
        audit["source_files"]["passenger_supplements"] = logical_path(args.supplements_output)
    _write_json(args.output, audit)
    if args.supplements_output is not None:
        _write_json(
            args.supplements_output,
            build_passenger_supplements(audit, infrastructure, frequency),
        )
    print(
        f"France reconciliation: {audit['counts']['candidate_stems']} candidates; "
        f"{audit['counts']['candidate_statuses']}"
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
