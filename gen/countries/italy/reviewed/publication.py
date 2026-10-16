"""Guarded publication and candidate construction for Italian providers."""
from __future__ import annotations

from pathlib import Path
from common.io import publish_nodes, write_csv
from common.validate import validate_nodes
from countries.italy.reviewed.paths import node_path, audit_report_path


def publish_reviewed_nodes(
    operator: str,
    seed_path: Path,
    output: list[dict],
) -> None:
    """Publish a reviewed rebuild through the repository node safeguards."""
    if seed_path != node_path(operator) and not seed_path.is_file():
        raise FileNotFoundError(seed_path)
    publish_nodes(node_path(operator), output)


def format_validation_issue(issue: object) -> str:
    message = getattr(issue, "message", None)
    code = getattr(issue, "code", None)
    index = getattr(issue, "index", None)

    parts = []

    if code:
        parts.append(str(code))

    if index is not None:
        parts.append(f"row {index}")

    if message:
        parts.append(str(message))

    return ": ".join(parts) if parts else str(issue)


def write_reviewed_output(operator, seed_path, output, audit, *, dry_run):
    issues = validate_nodes(output)

    errors = [
        issue
        for issue in issues
        if getattr(issue, "level", "error") == "error"
    ]

    if errors:
        formatted = "; ".join(
            format_validation_issue(issue)
            for issue in errors
        )
        raise ValueError(f"{operator}: {formatted}")

    report = audit_report_path(operator)
    report.parent.mkdir(parents=True, exist_ok=True)

    write_csv(
        report,
        audit,
        [
            "id",
            "source_name",
            "reviewed_name",
            "status",
            "details",
        ],
    )

    if not dry_run:
        publish_reviewed_nodes(operator, seed_path, output)
