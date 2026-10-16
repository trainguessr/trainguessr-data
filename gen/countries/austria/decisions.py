"""Explicit reviewed decision lookup for Austria."""
from __future__ import annotations

from typing import Any
from common.config import load_country_config, load_exclusion_rules
from countries.austria.identity import normalize_ifopt


def _load_mvo_overrides() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    excluded = {
        normalize_ifopt(station_id): row
        for station_id, row in load_exclusion_rules("austria", "mvo").items()
    }
    aliases: dict[str, dict[str, Any]] = {}
    for row in load_country_config("austria").get("mvo_aliases", []):
        if not isinstance(row, dict):
            raise ValueError("austria: every mvo_aliases entry must be an object")
        ifopt = normalize_ifopt(row.get("id"))
        canonical_id = str(row.get("canonical_id") or "").strip()
        if not ifopt.startswith("at:") or not canonical_id:
            raise ValueError(f"austria: invalid MVO alias {row!r}")
        aliases[ifopt] = row
    resolutions: dict[str, dict[str, Any]] = {}
    for row in load_country_config("austria").get("mvo_resolutions", []):
        if not isinstance(row, dict):
            raise ValueError("austria: every mvo_resolutions entry must be an object")
        ifopt = normalize_ifopt(row.get("id"))
        provider_id = str(row.get("provider_id") or "").strip()
        expected_name = str(row.get("expected_name") or "").strip()
        if not ifopt.startswith("at:") or not provider_id.isdigit() or not expected_name:
            raise ValueError(f"austria: invalid MVO resolution {row!r}")
        resolutions[ifopt] = row
    return excluded, aliases, resolutions
