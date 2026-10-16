"""Source downloads and cache I/O for Germany."""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any
import requests
from reconcile.germany.settings import BOUNDARY_CACHE, BOUNDARY_URL, GTFS_ARCHIVE, GTFS_URL, REQUEST_HEADERS


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_bytes(
    session: requests.Session,
    url: str,
    path: Path,
    *,
    headers: dict[str, str] | None = None,
    timeout: tuple[float, float] = (10.0, 180.0),
) -> Path:
    response = session.get(url, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    _write_bytes(path, response.content)
    return path


def ensure_gtfs_archive(
    path: Path = GTFS_ARCHIVE,
    *,
    session: requests.Session | None = None,
    refresh: bool = False,
) -> Path:
    if path.is_file() and zipfile.is_zipfile(path) and not refresh:
        return path
    client = session or requests.Session()
    close_client = session is None
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with client.get(
            GTFS_URL,
            stream=True,
            timeout=(10.0, 180.0),
            headers={"User-Agent": REQUEST_HEADERS["User-Agent"]},
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if not zipfile.is_zipfile(temporary):
            raise ValueError(f"GTFS source is not a ZIP archive: {GTFS_URL}")
        os.replace(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)
        if close_client:
            client.close()


def ensure_boundary(
    path: Path = BOUNDARY_CACHE,
    *,
    session: requests.Session | None = None,
    refresh: bool = False,
) -> Path:
    if path.is_file() and not refresh:
        return path
    client = session or requests.Session()
    close_client = session is None
    try:
        return _download_bytes(client, BOUNDARY_URL, path, timeout=(10.0, 60.0))
    finally:
        if close_client:
            client.close()
