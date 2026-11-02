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
    "missing_native_id",
    "missing_coordinates",
    "provider_scope_review",
    "reviewed_only_retained",
    "matched_name_difference",
    "manual_reviewed",
    "gtfs_name_missing",
    "excluded_or_unresolved",
}

AUDIT_STATUS_LABELS = {
    "missing_native_id": "Provider ID needed",
    "missing_coordinates": "Coordinates needed",
    "provider_scope_review": "Check railway owner",
    "reviewed_only_retained": "Not found in the new download. Kept the old station.",
    "matched_name_difference": "Provider name changed",
    "manual_reviewed": "ID checked",
    "gtfs_name_missing": "Name not in current timetable",
    "excluded_or_unresolved": "Check this station",
    "excluded": "Excluded after review",
    "handled_by_other_provider": "Listed in another station file",
    "matched": "Provider ID checked",
}
AUDIT_STATUS_CODES = {label: code for code, label in AUDIT_STATUS_LABELS.items()}
AUDIT_STATUS_CODES["Not in download; kept old station"] = "reviewed_only_retained"
