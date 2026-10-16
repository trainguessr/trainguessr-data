"""Explicit reviewed decision lookup for Italian providers."""
from __future__ import annotations

from countries.italy.reviewed.settings import HANDLED_OUTSIDE_PROVIDER_DECISIONS


def index_source_rows(
    operator: str,
    rows: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Index source rows without silently accepting duplicate provider IDs."""

    indexed: dict[str, dict[str, str]] = {}

    for row in rows:
        station_id = str(row.get("id", "")).strip()

        if not station_id:
            raise ValueError(f"{operator}: source catalog contains an empty ID")

        previous = indexed.get(station_id)

        if previous is not None and previous != row:
            raise ValueError(
                f"{operator}: duplicate source ID {station_id!r} has "
                f"conflicting records: {previous!r} and {row!r}"
            )

        indexed[station_id] = row

    return indexed


def handled_outside_provider_review(
    config: dict,
    operator: str,
    station_id: str,
) -> dict | None:
    """Return an explicit decision that keeps a source ID out of this dataset."""
    for review in config.get("reviews", []):
        if (
            str(review.get("operator", "")) == operator
            and str(review.get("id", "")) == station_id
            and review.get("decision") in HANDLED_OUTSIDE_PROVIDER_DECISIONS
        ):
            return review
    return None
