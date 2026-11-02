from __future__ import annotations

from contextlib import contextmanager

import csv
import filecmp
import json
import os
import shutil
from math import ceil
from pathlib import Path
import tempfile
import argparse
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]


def add_cache_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Use saved source files. Do not download.",
    )


def require_cached_file(path: Path, source_name: str) -> Path:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Saved {source_name} is missing: {logical_path(path)}. "
            "Run again without --cache to download it."
        )
    return path


def save_source_file(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def logical_path(path: Path | str) -> str:
    """Return a stable repository-relative label for durable evidence."""
    candidate = Path(path).absolute()
    try:
        return candidate.relative_to(ROOT.absolute()).as_posix()
    except ValueError:
        return f"external/{candidate.name}"


def load_ndjson(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            rows.append(row)
    return rows


def write_ndjson(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def publish_nodes(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    max_shrink_fraction: float = 0.20,
) -> None:
    """Validate and publish a generated node dataset.

    The size comparison is a maintenance guard, not a statement about an
    upstream catalogue's exact size. Remove or move the existing output when a
    deliberately larger reduction has already been reviewed.
    """
    from .validate import validate_nodes

    materialized = [dict(row) for row in rows]
    errors = validate_nodes(materialized)
    if not materialized:
        errors.insert(0, "dataset is empty")
    if errors:
        raise ValueError(f"{path}: node validation failed: " + "; ".join(errors[:20]))

    if not 0 <= max_shrink_fraction < 1:
        raise ValueError("max_shrink_fraction must be between 0 (inclusive) and 1")
    output_mode = path.stat().st_mode & 0o777 if path.is_file() else 0o644
    if path.is_file():
        previous = load_ndjson(path)
        # Keep the established order; upstream ordering is not station data.
        key = lambda row: (str(row.get("category", "")), str(row["id"]))
        by_key = {key(row): row for row in materialized}
        old_keys = {key(row) for row in previous}
        materialized = [row if row == by_key[key(row)] else by_key[key(row)] for row in previous if key(row) in by_key]
        materialized.extend(sorted((row for k, row in by_key.items() if k not in old_keys), key=key))
        if materialized == previous:
            print(f"OK | nodes | {logical_path(path)} | {len(materialized)} stations | unchanged")
            return
        previous_count = len(previous)
        minimum = ceil(previous_count * (1 - max_shrink_fraction))
        if previous_count and len(materialized) < minimum:
            raise ValueError(
                f"{path}: refusing to replace {previous_count} nodes with "
                f"{len(materialized)} (more than {max_shrink_fraction:.0%} shrink); "
                "review the source and move the existing output before an intentional rebuild"
            )

    if not path.is_file():
        materialized.sort(key=lambda row: (str(row.get("category", "")), str(row["id"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        write_ndjson(temporary, materialized)
        os.chmod(temporary, output_mode)
        if path.is_file() and filecmp.cmp(temporary, path, shallow=False):
            print(f"OK | nodes | {logical_path(path)} | {len(materialized)} stations | unchanged")
            return
        os.replace(temporary, path)
        print(f"OK | nodes | {logical_path(path)} | {len(materialized)} stations | published")
    finally:
        temporary.unlink(missing_ok=True)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@contextmanager
def preserve_outputs_on_failure(*paths: Path):
    """Roll back a multi-file build on handled exceptions.

    Individual outputs are atomic, but no filesystem guarantees cross-file
    crash atomicity. Deploy a station/index pair from one completed build.
    """
    backups: list[tuple[Path, Path | None]] = []
    try:
        for target in paths:
            target = Path(target)
            if not target.is_file():
                backups.append((target, None))
                continue
            fd, name = tempfile.mkstemp(prefix=f".{target.name}.backup-", dir=target.parent)
            os.close(fd)
            backup = Path(name)
            shutil.copy2(target, backup)
            backups.append((target, backup))
        yield
    except Exception:
        for target, backup in backups:
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                os.replace(backup, target)
        raise
    finally:
        for _target, backup in backups:
            if backup is not None:
                backup.unlink(missing_ok=True)
