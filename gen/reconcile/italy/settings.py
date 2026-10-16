"""Source locations and reviewed policy constants for Italian providers."""
from __future__ import annotations


OPERATORS = ("fn", "tt", "fer", "eav", "rfi", "fse")


OPERATOR_NAMES = {
    "fn": "Ferrovienord",
    "tt": "Trentino Trasporti",
    "fer": "Ferrovie Emilia Romagna",
    "eav": "Ente Autonomo Volturno",
    "rfi": "RFI",
    "fse": "Ferrovie del Sud Est",
}


REVIEW_STATUSES = {
    "missing_coordinates",
    "reviewed_only_retained",
    "matched_name_difference",
    "manual_reviewed",
    "gtfs_name_missing",
    "excluded_or_unresolved",
}
