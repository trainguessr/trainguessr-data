"""Pure rail eligibility and SCOTTY candidate selection for Austria."""
from __future__ import annotations

import json
import re
import statistics
from difflib import SequenceMatcher
from typing import Any, Iterable
from countries.austria.decisions import _load_mvo_overrides
from countries.austria.identity import _float, _haversine_m, _normal_name, normalize_ifopt
from countries.austria.settings import (
    _EVA_RE,
    _RAIL_LINE_RE,
    _RAIL_MASK_POSITIONS,
    _REPLACEMENT_LINE_RE,
    _REVIEWED_LIGHT_RAIL_IFOPTS,
    _SUGGESTION_RE,
)


def _rail_mask(value: Any) -> bool:
    mask = re.sub(r"\s+", "", str(value or ""))
    return len(mask) >= 2 and all(char in "01" for char in mask) and any(mask[pos] == "1" for pos in _RAIL_MASK_POSITIONS)


def _line_tokens(value: Any) -> list[str]:
    return [token.strip() for token in str(value or "").split(",") if token.strip()]


def _real_rail_platform(platform: dict[str, Any], *, allow_light_rail: bool = False) -> bool:
    tokens = _line_tokens(platform.get("linien"))
    conventional_rail = _rail_mask(platform.get("umst_vm"))
    reviewed_light_rail = allow_light_rail and "STB" in {token.upper() for token in tokens}
    if not conventional_rail and not reviewed_light_rail:
        return False
    return any(
        not _REPLACEMENT_LINE_RE.fullmatch(token) and _RAIL_LINE_RE.fullmatch(token)
        for token in tokens
    )


def _platform_eva(platform: dict[str, Any]) -> int | None:
    value = re.sub(r"\D", "", str(platform.get("extids_obb") or ""))
    if len(value) == 7 and not value.startswith("0"):
        return int(value)
    return None


def mvo_rail_candidates(
    rows: Iterable[dict[str, Any]],
    platforms: Iterable[dict[str, Any]],
    *, reviewed_resolutions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if reviewed_resolutions is None:
        reviewed_resolutions = _load_mvo_overrides()[2]
    platforms_by_stop: dict[str, list[dict[str, Any]]] = {}
    if platforms is not None:
        for platform in platforms:
            platforms_by_stop.setdefault(str(platform.get("hst_id") or ""), []).append(platform)

    result: list[dict[str, Any]] = []
    for row in rows:
        ifopt = normalize_ifopt(row.get("hst_globid"))
        name = str(row.get("hst_name") or "").strip()
        if not ifopt.startswith("at:") or not name:
            continue
        qualifying_platforms = [
            platform for platform in platforms_by_stop.get(str(row.get("hst_id") or ""), [])
            if _real_rail_platform(
                platform,
                allow_light_rail=ifopt in _REVIEWED_LIGHT_RAIL_IFOPTS,
            )
        ]
        if not qualifying_platforms and ifopt not in reviewed_resolutions:
            continue
        try:
            lon = _float(row.get("hst_x"))
            lat = _float(row.get("hst_y"))
        except (TypeError, ValueError):
            continue
        if not (45.0 <= lat <= 50.0 and 8.0 <= lon <= 18.0):
            continue
        item = dict(row)
        item["hst_globid"] = ifopt
        item["hst_x"] = lon
        item["hst_y"] = lat
        if qualifying_platforms:
            evas = {_platform_eva(platform) for platform in qualifying_platforms}
            evas.discard(None)
            if len(evas) > 1:
                continue
            if evas:
                item["platform_eva_id"] = evas.pop()
            item["rail_lines"] = sorted({
                token for platform in qualifying_platforms for token in _line_tokens(platform.get("linien"))
                if _RAIL_LINE_RE.fullmatch(token) and not _REPLACEMENT_LINE_RE.fullmatch(token)
            })
            item["rail_platform_ifopts"] = sorted({
                str(platform.get("stg_globid") or "") for platform in qualifying_platforms
                if platform.get("stg_globid")
            })
            platform_lats = [_float(platform["stg_y"]) for platform in qualifying_platforms]
            platform_lons = [_float(platform["stg_x"]) for platform in qualifying_platforms]
            item["rail_lat"] = statistics.median(platform_lats)
            item["rail_lon"] = statistics.median(platform_lons)
        else:
            # A reviewed physical station may be temporarily represented only by
            # replacement-service, bus-only, or unclassified MVO platforms.
            item["reviewed_rail_override"] = True
        result.append(item)
    return result


def parse_scotty_suggestions(text: str) -> list[dict[str, Any]]:
    match = _SUGGESTION_RE.search(text)
    if not match:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("SCOTTY stop response has no suggestion object")
        raw = text[start:end + 1]
    else:
        raw = match.group(1)
    payload = json.loads(raw)
    suggestions = payload.get("suggestions") if isinstance(payload, dict) else None
    if not isinstance(suggestions, list):
        raise ValueError("SCOTTY stop response has no suggestions list")
    return [row for row in suggestions if isinstance(row, dict)]


def _suggestion_coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lon = _float(row.get("xcoord"))
        lat = _float(row.get("ycoord"))
    except (TypeError, ValueError):
        return None
    if abs(lon) > 180:
        lon /= 1_000_000
    if abs(lat) > 90:
        lat /= 1_000_000
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lat, lon


def select_scotty_suggestion(
    suggestions: Iterable[dict[str, Any]],
    *,
    name: str,
    lat: float,
    lon: float,
    expected_eva: int | None = None,
    aliases: Iterable[str] = (),
) -> dict[str, Any] | None:
    wanted_names = {_normal_name(name), *(_normal_name(alias) for alias in aliases)}
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for row in suggestions:
        if str(row.get("type", "1")) not in {"1", "station", "stop"}:
            continue
        match = _EVA_RE.search(str(row.get("id") or ""))
        coords = _suggestion_coordinates(row)
        candidate_name = str(row.get("value") or row.get("name") or "").strip()
        if not match or not coords or not candidate_name:
            continue
        eva_id = int(match.group(1))
        if expected_eva is not None and eva_id != expected_eva:
            continue
        distance = _haversine_m(lat, lon, *coords)
        normalized_candidate = _normal_name(candidate_name)
        similarity = max(SequenceMatcher(None, wanted, normalized_candidate).ratio() for wanted in wanted_names)
        if normalized_candidate in wanted_names:
            similarity = 1.0
        if distance > 2_000 or similarity < 0.72:
            continue
        ranked.append((similarity, distance, {
            "eva_id": eva_id,
            "name": candidate_name,
            "lat": coords[0],
            "lon": coords[1],
            "distance_m": round(distance, 1),
            "similarity": round(similarity, 4),
        }))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    best_similarity, best_distance, best = ranked[0]
    if best_similarity < 0.86 and best_distance > 750:
        return None
    if len(ranked) > 1:
        second_similarity, second_distance, _ = ranked[1]
        if abs(best_similarity - second_similarity) < 0.03 and abs(best_distance - second_distance) < 250:
            return None
    return best
