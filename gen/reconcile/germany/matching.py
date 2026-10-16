"""Pure name and spatial matching for Germany."""
from __future__ import annotations

import difflib
from functools import lru_cache
import math
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable
from reconcile.germany.settings import GENERIC_NAME_TOKENS, NODE_MATCH_RADIUS_METRES, TOKEN_EXPANSIONS


def _float_pair(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        latitude = float(row.get("stop_lat") or "")
        longitude = float(row.get("stop_lon") or "")
    except (TypeError, ValueError):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


def _normalise(value: Any) -> str:
    text = str(value or "").replace("ß", "ss").replace("ø", "oe").replace("Ø", "Oe")
    text = re.sub(r"\bb\.s[- ]", "bad salzuflen ", text, flags=re.IGNORECASE)
    text = re.sub(r"\ba\.?\s+k\.?\b", "am Kaiserstuhl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.?\s+k\.?\b", "im Kaiserstuhl", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b([^\W\d_]+)str\.?(?=\s|$|[(),/+:-])",
        r"\1strasse",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bstr\.?\b", "strasse", text, flags=re.IGNORECASE)
    text = re.sub(r"\brh\.?\b", "rhein", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.?\s+s\.?\b", "im", text, flags=re.IGNORECASE)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def name_tokens(value: Any) -> frozenset[str]:
    # Cache only immutable normalized text, preserving support for arbitrary
    # input values without retaining mutable candidate records.
    return _name_tokens(str(value or ""))


@lru_cache(maxsize=16384)
def _name_tokens(value: str) -> frozenset[str]:
    tokens = _normalise(value).split()
    filtered = [token for token in tokens if token not in GENERIC_NAME_TOKENS]
    if len(filtered) > 1:
        filtered = [token for token in filtered if token != "s"]
    expanded: list[str] = []
    for token in filtered:
        expanded.extend(TOKEN_EXPANSIONS.get(token, (token,)))
    return frozenset(expanded)


def name_key(value: Any) -> str:
    return " ".join(sorted(name_tokens(value)))


def name_score(first: Any, second: Any) -> float:
    first_tokens = name_tokens(first)
    second_tokens = name_tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    if first_tokens == second_tokens:
        return 1.0
    pairs: list[tuple[float, str, str]] = []
    for first_token in first_tokens:
        for second_token in second_tokens:
            if first_token == second_token:
                similarity = 1.0
            elif min(len(first_token), len(second_token)) >= 4:
                similarity = difflib.SequenceMatcher(
                    None, first_token, second_token
                ).ratio()
                if first_token.startswith(second_token) or second_token.startswith(first_token):
                    similarity = max(similarity, 0.82)
            else:
                similarity = 0.0
            if similarity >= 0.72:
                pairs.append((similarity, first_token, second_token))
    pairs.sort(reverse=True)
    matched_first: set[str] = set()
    matched_second: set[str] = set()
    similarities: list[float] = []
    for similarity, first_token, second_token in pairs:
        if first_token in matched_first or second_token in matched_second:
            continue
        matched_first.add(first_token)
        matched_second.add(second_token)
        similarities.append(similarity)
    if not similarities:
        return 0.0
    score = sum(similarities) / len(first_tokens | second_tokens)
    shared_tokens = first_tokens & second_tokens
    if len(shared_tokens) >= 3 or (
        len(shared_tokens) >= 2
        and max(len(first_tokens), len(second_tokens)) <= 3
    ):
        score = max(score, 0.72)
    if len(matched_first) == len(first_tokens):
        score = max(
            score,
            0.72 if min(len(first_tokens), len(second_tokens)) == 1 else 0.86,
        )
    return score


def _is_strong_name_match(first: Any, second: Any, *, score: float | None = None) -> bool:
    first_key = name_key(first)
    second_key = name_key(second)
    if not first_key or not second_key:
        return False
    if first_key == second_key:
        return True
    if (score if score is not None else name_score(first, second)) < 0.72:
        return False
    shared = name_tokens(first) & name_tokens(second)
    if len(shared) >= 2:
        return True
    return (
        len(shared) == 1
        and len(next(iter(shared))) >= 5
        and min(len(name_tokens(first)), len(name_tokens(second))) == 1
    )


def distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude = math.radians((first[0] + second[0]) / 2.0)
    x = math.radians(second[1] - first[1]) * math.cos(latitude)
    y = math.radians(second[0] - first[0])
    return 6_371_000.0 * math.hypot(x, y)


def _grid_key(latitude: float, longitude: float) -> tuple[int, int]:
    return int(math.floor(latitude * 10)), int(math.floor(longitude * 10))


def build_node_grid(rows: Iterable[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    grid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        try:
            location = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        grid[_grid_key(*location)].append(row)
    return grid


def nearby_nodes(
    candidate: dict[str, Any],
    grid: dict[tuple[int, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if candidate.get("latitude") is None or candidate.get("longitude") is None:
        return []
    location = float(candidate["latitude"]), float(candidate["longitude"])
    latitude_key, longitude_key = _grid_key(*location)
    matches: list[tuple[float, float, dict[str, Any]]] = []
    for latitude_delta in (-1, 0, 1):
        for longitude_delta in (-1, 0, 1):
            for row in grid.get((latitude_key + latitude_delta, longitude_key + longitude_delta), []):
                try:
                    row_location = float(row["lat"]), float(row["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                distance = distance_m(location, row_location)
                score = name_score(candidate.get("name"), (row.get("tags") or {}).get("name"))
                strong_name = score >= 0.72 and distance <= NODE_MATCH_RADIUS_METRES
                close_name = score >= 0.33 and distance <= 300.0
                shared_tokens = name_tokens(candidate.get("name")) & name_tokens(
                    (row.get("tags") or {}).get("name")
                )
                coordinate_name = (
                    distance <= 100.0
                    and any(len(token) >= 5 for token in shared_tokens)
                )
                if strong_name or close_name or coordinate_name:
                    matches.append((score, distance, row))
    matches.sort(key=lambda item: (-item[0], item[1], str(item[2].get("id"))))
    return [row for _, _, row in matches[:8]]
