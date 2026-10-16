"""Source and output locations for Italian providers."""
from __future__ import annotations

from pathlib import Path
from common.io import ROOT
from countries.italy.reviewed.settings import ITALY_CACHE


def cache_path(operator: str, section: str, filename: str) -> Path:
    return ITALY_CACHE / operator / section / filename


def node_path(operator: str) -> Path:
    return ROOT / "nodes" / f"nodes-italy-{operator}.json"


def reviewed_nodes_path(operator: str) -> Path:
    """Use the tracked reviewed dataset, with cache as a bootstrap fallback."""
    committed = node_path(operator)
    if committed.exists():
        return committed

    cached = cache_path(operator, "reviewed", "nodes.json")
    if cached.exists():
        return cached

    raise FileNotFoundError(
        f"No reviewed seed exists for {operator}. Expected either:\n"
        f"  {cached}\n"
        f"or:\n"
        f"  {committed}"
    )


def audit_report_path(operator: str) -> Path:
    return cache_path(operator, "reports", "audit.csv")


def require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {description}:\n"
            f"  {path}\n\n"
            "Populate cache/italy first using the documented download or "
            "migration procedure."
        )
    return path
