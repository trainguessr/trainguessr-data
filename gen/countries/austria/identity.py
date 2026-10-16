"""Pure native identity and geographic helpers for Austria."""
from __future__ import annotations

import html
import math
import re
from typing import Any
from countries.austria.settings import _IFOPT_RE


def _float(value: Any) -> float:
    return float(str(value).strip().replace(",", "."))


def _normal_name(value: str) -> str:
    value = html.unescape(value).casefold().replace("ß", "ss")
    value = re.sub(r"\b(?:bahnhof|bahnhst|hbf)\b", " ", value)
    value = re.sub(r"\((?:stmk|tirol|oö|nö|sbg|ktn)\)", " ", value)
    value = re.sub(r"\[in\s+[^\]]+\]", " ", value)
    value = re.sub(r"\bst\s*\.\s*", "st ", value)
    value = re.sub(r"[^a-z0-9äöü]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_ifopt(value: Any) -> str:
    value = str(value or "").strip().casefold()
    match = _IFOPT_RE.fullmatch(value)
    if match:
        return f"at:{int(match.group(1))}:{int(match.group(2))}"
    return value


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
