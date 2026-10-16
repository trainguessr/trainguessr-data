"""Explicit reviewed decision lookup for Italian providers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from common.io import ROOT


def config_path() -> Path:
    return ROOT / "overrides" / "exclusions" / "italy.json"


def save_config(config: dict[str, Any]) -> None:
    config_path().write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def review_key(operator: str, row: dict[str, str]) -> tuple[str, ...]:
    return (
        operator,
        row["id"],
        row["status"],
        row["source_name"],
        row["reviewed_name"],
    )


def saved_review_keys(config: dict[str, Any]) -> set[tuple[str, ...]]:
    return {
        (
            str(row.get("operator", "")),
            str(row.get("id", "")),
            str(row.get("status", "")),
            str(row.get("source_name", "")),
            str(row.get("reviewed_name", "")),
        )
        for row in config.get("reviews", [])
    }


def remember(
    config: dict[str, Any],
    operator: str,
    row: dict[str, str],
    decision: str,
    *,
    save: bool = True,
) -> None:
    reviews = config.setdefault("reviews", [])
    key = review_key(operator, row)
    reviews[:] = [
        saved for saved in reviews
        if (
            str(saved.get("operator", "")),
            str(saved.get("id", "")),
            str(saved.get("status", "")),
            str(saved.get("source_name", "")),
            str(saved.get("reviewed_name", "")),
        ) != key
    ]
    reviews.append({
        "operator": operator,
        "id": row["id"],
        "status": row["status"],
        "source_name": row["source_name"],
        "reviewed_name": row["reviewed_name"],
        "decision": decision,
    })
    if save:
        save_config(config)
