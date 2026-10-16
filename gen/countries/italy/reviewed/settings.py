"""Source locations and reviewed policy constants for Italian providers."""
from __future__ import annotations

from common.io import ROOT


ITALY_CACHE = ROOT / "cache" / "italy"


COORDINATE_OVERRIDES = ROOT / "overrides" / "italy-coordinate-corrections.json"


HANDLED_OUTSIDE_PROVIDER_DECISIONS = {
    "handled_by_france_with_rfi_fallback",
}


OPERATOR_NAMES = {
    "fn": "Ferrovienord",
    "tt": "Trentino Trasporti",
    "fer": "Ferrovie Emilia Romagna",
    "eav": "Ente Autonomo Volturno",
    "rfi": "RFI",
}
