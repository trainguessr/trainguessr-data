"""Native DB identity acquisition and candidate verification for Germany."""
from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree
import requests
from common.io import load_ndjson
from reconcile.germany.io import _read_json, _write_bytes, _write_json
from reconcile.germany.matching import _is_strong_name_match, name_key, name_score, name_tokens
from reconcile.germany.settings import (
    CATALOGUE,
    DB_PLAN_URL,
    DB_STATION_URL,
    DEFAULT_PLAN_SLOT,
    GERMANY_CACHE,
    NODES,
    REQUEST_HEADERS,
)


def _local_tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _numeric_ids(value: Any) -> list[str]:
    result: list[str] = []
    for part in re.split(r"[|,; ]+", str(value or "")):
        part = part.strip()
        if part.isdigit() and part not in result:
            result.append(part)
    return result


def parse_station_xml(xml: bytes | str) -> list[dict[str, Any]]:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = ElementTree.fromstring(xml)
    records: list[dict[str, Any]] = []
    for element in root.iter():
        if _local_tag(element) != "station":
            continue
        attributes = dict(element.attrib)
        ids = []
        ids.extend(_numeric_ids(attributes.get("eva")))
        ids.extend(_numeric_ids(attributes.get("meta")))
        records.append(
            {
                "eva": str(attributes.get("eva") or "").strip(),
                "meta": str(attributes.get("meta") or "").strip(),
                "ids": list(dict.fromkeys(ids)),
                "name": str(attributes.get("name") or "").strip(),
                "ds100": str(attributes.get("ds100") or "").strip(),
                "db": str(attributes.get("db") or "").casefold() == "true",
                "attributes": attributes,
            }
        )
    return records


def load_station_snapshot(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    records = parse_station_xml(path.read_bytes())
    namespace = {station_id for record in records for station_id in record["ids"]}
    return records, namespace


def _snapshot_indexes(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = name_key(record.get("name"))
        if key:
            by_name[key].append(record)
        for token in name_tokens(record.get("name")):
            if len(token) >= 3:
                by_token[token].append(record)
    return {"by_name": by_name, "by_token": by_token}


def snapshot_matches(
    name: str,
    indexes: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exact = list(indexes["by_name"].get(name_key(name), []))
    tokens = name_tokens(name)
    possible: dict[tuple[str, str, str], dict[str, Any]] = {}
    for token in tokens:
        for record in indexes["by_token"].get(token, []):
            key = (
                str(record.get("eva") or ""),
                str(record.get("meta") or ""),
                str(record.get("name") or ""),
            )
            possible[key] = record
    scored = [
        (name_score(name, record.get("name")), record)
        for record in possible.values()
        if name_score(name, record.get("name")) >= 0.45
    ]
    scored.sort(key=lambda item: (-item[0], not item[1].get("db"), item[1].get("name", "")))
    ordered: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in [
        *sorted(exact, key=lambda row: (not row.get("db"), row.get("name", ""))),
        *(record for _, record in scored),
    ]:
        key = (
            str(record.get("eva") or ""),
            str(record.get("meta") or ""),
            str(record.get("name") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        ordered.append(record)
    return ordered[:20]


def _best_snapshot_matches(name: str, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [
        (name_score(name, record.get("name")), record)
        for record in records
    ]
    strong = [(score, record) for score, record in scored if score >= 0.72]
    if not strong:
        return []
    best_score = max(score for score, _ in strong)
    best = [record for score, record in strong if abs(score - best_score) < 1e-9]
    best_exact_token_count = max(
        len(name_tokens(name) & name_tokens(record.get("name")))
        for record in best
    )
    best = [
        record
        for record in best
        if len(name_tokens(name) & name_tokens(record.get("name")))
        == best_exact_token_count
    ]
    exact = [record for record in best if name_key(name) == name_key(record.get("name"))]
    if exact:
        return exact

    groups: list[set[str]] = []
    for record in best:
        identifiers = set(str(value) for value in record.get("ids", []) if str(value))
        overlapping = [group for group in groups if group & identifiers]
        if not overlapping:
            groups.append(identifiers)
            continue
        merged = set(identifiers)
        for group in overlapping:
            merged.update(group)
            groups.remove(group)
        groups.append(merged)
    if len(groups) != 1:
        return []
    return best


def _candidate_station_names(candidate: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for value in [candidate.get("name"), *(candidate.get("gtfs_stop_names") or [])]:
        name = str(value or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def candidate_snapshot_matches(
    candidate: dict[str, Any],
    indexes: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Match a GTFS stop place using every name carried by its stop hierarchy.

    GTFS parent display names are often generic ("... Bahnhof") while a child
    stop carries the exact DB spelling ("...(Württ)").  Restricting namespace
    lookup to the chosen parent name creates false provider gaps.
    """
    all_matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    best_matches: list[dict[str, Any]] = []
    best_alias: str | None = None
    best_rank: tuple[int, int, float, int] | None = None

    for alias_index, alias in enumerate(_candidate_station_names(candidate)):
        alias_matches = snapshot_matches(alias, indexes, records)
        for record in alias_matches:
            key = (
                str(record.get("eva") or ""),
                str(record.get("meta") or ""),
                str(record.get("name") or ""),
            )
            if key not in seen:
                seen.add(key)
                all_matches.append(record)

        strong = _best_snapshot_matches(alias, alias_matches)
        if not strong:
            continue
        score = max(name_score(alias, record.get("name")) for record in strong)
        exact = int(
            any(name_key(alias) == name_key(record.get("name")) for record in strong)
        )
        has_db_identity = int(any(record.get("db") is True for record in strong))
        rank = (exact, has_db_identity, score, -alias_index)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_matches = strong
            best_alias = alias

    # Put the selected matches first so the persisted evidence clearly shows
    # which namespace identity drove provider probing.
    ordered: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str]] = set()
    for record in [*best_matches, *all_matches]:
        key = (
            str(record.get("eva") or ""),
            str(record.get("meta") or ""),
            str(record.get("name") or ""),
        )
        if key in selected_keys:
            continue
        selected_keys.add(key)
        ordered.append(record)
    return ordered[:20], best_matches, best_alias


def _values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _values(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _values(child)
    elif value not in (None, ""):
        yield str(value)


def load_generated_identity_index(path: Path = NODES) -> dict[str, Any]:
    rows = load_ndjson(path)
    by_id: dict[str, str] = {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        canonical_id = str(row.get("id") or "").strip()
        if not canonical_id:
            continue
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        ids = [canonical_id]
        for key in ("provider_place_ids", "further_ids", "provider_ids"):
            ids.extend(_values(tags.get(key)))
        for station_id in ids:
            if station_id:
                by_id[station_id] = canonical_id
        by_name[name_key(tags.get("name"))].append(row)
    return {"rows": rows, "by_id": by_id, "by_name": by_name}


def load_catalogue_index(path: Path = CATALOGUE) -> dict[str, Any]:
    rows = _read_json(path) if path.is_file() else []
    if not isinstance(rows, list):
        raise ValueError(f"Germany station catalogue must be an array: {path}")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        station_id = str(row.get("id") or "").strip()
        if station_id:
            by_id[station_id] = row
        for alias in row.get("additionalIds") or []:
            alias = str(alias).strip()
            if alias:
                by_id[alias] = row
    return {"rows": rows, "by_id": by_id}


def _preferred_provider_ids(records: Iterable[dict[str, Any]], limit: int = 8) -> list[str]:
    ids: list[str] = []
    for record in records:
        values = list(record.get("ids") or [])
        values.sort(key=lambda value: (not (len(value) == 7 and value.startswith("80")), len(value), value))
        for value in values:
            if value not in ids:
                ids.append(value)
    return ids[:limit]


def _verification_state(result: dict[str, Any]) -> str:
    status = result.get("http_status")
    if result.get("verification_state"):
        return str(result["verification_state"])
    if status in (401, 403):
        return "provider_verification_blocked_auth"
    if status in (429, 500, 502, 503, 504) or status is None:
        return "provider_verification_blocked_access"
    if status == 200 and result.get("db") is True:
        return "verified"
    if status == 404:
        return "provider_incompatible"
    return "provider_incompatible"


class DbProbe:
    def __init__(
        self,
        *,
        cache_dir: Path = GERMANY_CACHE / "db-probes",
        session: requests.Session | None = None,
        delay: float = 0.15,
        refresh: bool = False,
        plan_slots: Iterable[str] = (DEFAULT_PLAN_SLOT,),
    ) -> None:
        self.cache_dir = cache_dir
        self.session = session or requests.Session()
        self.delay = max(0.0, delay)
        self.refresh = refresh
        self.plan_slots = list(dict.fromkeys(str(slot) for slot in plan_slots if str(slot).strip()))
        self.client_id = (
            os.getenv("DB_API_TIMETABLES_CLIENTID")
            or os.getenv("DB_API_RISBOARDS_CLIENTID", "")
        )
        self.secret = (
            os.getenv("DB_API_TIMETABLES_SECRET")
            or os.getenv("DB_API_RISBOARDS_CLIENTSECRET", "")
        )
        self.headers = {
            **REQUEST_HEADERS,
            "DB-Client-ID": self.client_id,
            "DB-Api-Key": self.secret,
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def auth_configured(self) -> bool:
        return bool(self.client_id and self.secret)

    def _blocked(self, url: str, reason: str) -> dict[str, Any]:
        return {
            "url": url,
            "http_status": None,
            "verification_state": reason,
        }

    def _pause(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    def station(self, eva: str) -> dict[str, Any]:
        eva = str(eva).strip()
        path = self.cache_dir / f"station-{eva}.json"
        url = DB_STATION_URL.format(eva=eva)
        if path.is_file() and not self.refresh:
            return _read_json(path)
        if not self.auth_configured:
            result = self._blocked(url, "provider_verification_blocked_auth")
            _write_json(path, result)
            return result
        result: dict[str, Any] = {"url": url, "requested_eva": eva}
        try:
            response = self.session.get(url, headers=self.headers, timeout=(5.0, 30.0))
            result["http_status"] = response.status_code
            result["response_bytes"] = len(response.content)
            if response.status_code == 200:
                records = parse_station_xml(response.content)
                if not records:
                    result["verification_state"] = "provider_incompatible"
                    result["error"] = "successful response contained no station element"
                else:
                    station = records[0]
                    result.update(
                        {
                            "eva": station.get("eva"),
                            "meta": station.get("meta"),
                            "name": station.get("name"),
                            "ds100": station.get("ds100"),
                            "db": station.get("db"),
                            "verification_state": _verification_state(
                                {"http_status": 200, "db": station.get("db")}
                            ),
                        }
                    )
                    _write_bytes(self.cache_dir / f"station-{eva}.xml", response.content)
            elif response.status_code in (401, 403):
                result["verification_state"] = "provider_verification_blocked_auth"
            elif response.status_code in (429, 500, 502, 503, 504):
                result["verification_state"] = "provider_verification_blocked_access"
            elif response.status_code == 404:
                result["verification_state"] = "provider_incompatible"
            else:
                result["verification_state"] = "provider_verification_blocked_access"
        except (requests.RequestException, ValueError, ElementTree.ParseError) as exc:
            result["http_status"] = None
            result["verification_state"] = "provider_verification_blocked_access"
            result["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(path, result)
        self._pause()
        return result

    def plan(self, eva: str, slot: str) -> dict[str, Any]:
        eva = str(eva).strip()
        slot = str(slot).strip()
        safe_slot = slot.replace("/", "-")
        path = self.cache_dir / f"plan-{eva}-{safe_slot}.json"
        url = DB_PLAN_URL.format(eva=eva, slot=slot)
        if path.is_file() and not self.refresh:
            return _read_json(path)
        if not self.auth_configured:
            result = self._blocked(url, "provider_verification_blocked_auth")
            result["slot"] = slot
            _write_json(path, result)
            return result
        result: dict[str, Any] = {"url": url, "slot": slot, "requested_eva": eva}
        try:
            response = self.session.get(url, headers=self.headers, timeout=(5.0, 30.0))
            result["http_status"] = response.status_code
            result["response_bytes"] = len(response.content)
            if response.status_code == 200:
                try:
                    ElementTree.fromstring(response.content)
                except ElementTree.ParseError as exc:
                    result["verification_state"] = "provider_verification_blocked_access"
                    result["error"] = f"invalid XML: {exc}"
                else:
                    result["verification_state"] = "verified"
                    _write_bytes(self.cache_dir / f"plan-{eva}-{safe_slot}.xml", response.content)
            elif response.status_code in (401, 403):
                result["verification_state"] = "provider_verification_blocked_auth"
            elif response.status_code in (429, 500, 502, 503, 504):
                result["verification_state"] = "provider_verification_blocked_access"
            elif response.status_code == 404:
                result["verification_state"] = "provider_incompatible"
            else:
                result["verification_state"] = "provider_verification_blocked_access"
        except (requests.RequestException, ValueError) as exc:
            result["http_status"] = None
            result["verification_state"] = "provider_verification_blocked_access"
            result["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(path, result)
        self._pause()
        return result

    def resolve(
        self,
        provider_ids: Iterable[str],
        *,
        expected_name: str | None = None,
        expected_name_aliases: Iterable[str] = (),
    ) -> dict[str, Any]:
        station_checks: list[dict[str, Any]] = []
        plan_checks: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        aliases = [str(value).strip() for value in expected_name_aliases if str(value or "").strip()]
        expected_names = [str(expected_name).strip()] if str(expected_name or "").strip() else []
        expected_names.extend(aliases)
        for provider_id in list(dict.fromkeys(str(value) for value in provider_ids)):
            station = self.station(provider_id)
            station_checks.append(station)
            if station.get("http_status") != 200 or station.get("db") is not True:
                continue
            if expected_names and not any(
                _is_strong_name_match(name, station.get("name"))
                for name in expected_names
            ) and not any(
                _is_strong_name_match(station.get("name"), alias)
                for alias in aliases
            ):
                station["name_match"] = False
                station["verification_state"] = "provider_incompatible"
                continue
            station["name_match"] = True if expected_name else None
            plans = [self.plan(provider_id, slot) for slot in self.plan_slots]
            plan_checks.extend(plans)
            if any(plan.get("http_status") == 200 for plan in plans):
                selected = station
                break
        return {
            "station_checks": station_checks,
            "plan_checks": plan_checks,
            "selected_station": selected,
            "selected_eva": selected.get("eva") if selected else None,
            "station_http_status": selected.get("http_status") if selected else None,
            "plan_http_status": 200 if any(row.get("http_status") == 200 for row in plan_checks) else None,
        }
