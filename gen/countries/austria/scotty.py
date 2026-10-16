"""SCOTTY resolution and board verification for Austria."""
from __future__ import annotations

import html
import json
import logging as log
from datetime import datetime
from pathlib import Path
from typing import Any
import requests
from countries.austria.decisions import _load_mvo_overrides
from countries.austria.identity import _float, normalize_ifopt
from countries.austria.selection import parse_scotty_suggestions, select_scotty_suggestion
from countries.austria.settings import (
    DEFAULT_RESOLUTION_CACHE,
    SCOTTY_BOARD_URL,
    SCOTTY_STOP_URL,
    _REVIEWED_NAMES,
    _VIENNA,
)


class ScottyResolver:
    def __init__(
        self,
        session: requests.Session,
        cache_path: Path = DEFAULT_RESOLUTION_CACHE,
        *,
        offline: bool = False,
        timeout: int = 20,
    ) -> None:
        self.session = session
        self.cache_path = cache_path
        self.offline = offline
        self.timeout = timeout
        self.cache: dict[str, Any] = {}
        self.reviewed_evas = _load_mvo_overrides()[2]
        if cache_path.is_file():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("version") == 2:
                    self.cache = dict(payload.get("entries") or {})
            except (OSError, ValueError):
                self.cache = {}

    def resolve(self, row: dict[str, Any]) -> dict[str, Any] | None:
        key = normalize_ifopt(row.get("hst_globid"))
        expected_eva = row.get("platform_eva_id")
        if expected_eva:
            return {
                "eva_id": int(expected_eva),
                "name": str(row.get("hst_name") or ""),
                "lat": _float(row.get("rail_lat", row["hst_y"])),
                "lon": _float(row.get("rail_lon", row["hst_x"])),
                "distance_m": 0.0,
                "similarity": 1.0,
                "method": "platform_eva",
            }
        reviewed = self.reviewed_evas.get(key)
        if reviewed:
            return {
                "eva_id": int(reviewed["provider_id"]),
                "name": reviewed["expected_name"],
                "lat": _float(row.get("rail_lat", row["hst_y"])),
                "lon": _float(row.get("rail_lon", row["hst_x"])),
                "distance_m": reviewed.get("distance_m"),
                "similarity": 1.0,
                "method": "reviewed_provider_id",
                "expected_provider_name": reviewed["expected_name"],
            }
        cached = self.cache.get(key)
        if isinstance(cached, dict):
            if cached.get("eva_id"):
                return cached
        if self.offline:
            return None
        name = str(row.get("hst_name") or "").strip()
        aliases = _REVIEWED_NAMES.get(key, ())
        search_name = aliases[1] if len(aliases) > 1 else name
        try:
            response = self.session.get(
                SCOTTY_STOP_URL,
                params={
                    "getstop": "1",
                    "REQ0JourneyStopsS0A": "255",
                    "REQ0JourneyStopsS0G": f"{search_name}?",
                    "REQ0JourneyStopsB": "20",
                    "js": "true",
                },
                headers={"User-Agent": "TrainGuessr station data generator"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            selected = select_scotty_suggestion(
                parse_scotty_suggestions(response.text),
                name=name,
                lat=_float(row.get("rail_lat", row["hst_y"])),
                lon=_float(row.get("rail_lon", row["hst_x"])),
                expected_eva=int(expected_eva) if expected_eva else None,
                aliases=aliases,
            )
        except (requests.RequestException, ValueError) as exc:
            log.warning("Could not resolve Austrian stop %s (%s): %s", name, key, exc)
            return None
        if selected:
            self.cache[key] = selected
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"version": 2, "entries": self.cache}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return selected


def verify_scotty_station(
    session: requests.Session,
    eva_id: int,
    timeout: int = 20,
    attempts: int = 3,
) -> dict[str, Any] | None:
    now = datetime.now(_VIENNA)
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                SCOTTY_BOARD_URL,
                params={
                    "L": "vs_scotty.vs_liveticker",
                    "evaId": str(eva_id),
                    "boardType": "dep",
                    "time": now.strftime("%H:%M"),
                    "productsFilter": "1111111111111",
                    "additionalTime": "12",
                    "disableEquivs": "yes",
                    "maxJourneys": "3",
                    "outputMode": "tickerDataOnly",
                    "start": "yes",
                    "selectDate": "today",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            text = response.text.replace("journeysObj = ", "", 1).strip()
            payload = json.loads(text)
            if str(payload.get("stationEvaId")) != str(eva_id):
                return None
            return {
                "station_name": html.unescape(str(payload.get("stationName") or "")),
                "journey_count": len(payload.get("journey") or []),
            }
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError) as exc:
            if attempt == attempts:
                log.warning("Could not verify SCOTTY station %s after %s attempts: %s", eva_id, attempts, exc)
    return None
