"""Source acquisition and parsing for Germany."""
from __future__ import annotations

import json
import io
import os
import tarfile
from datetime import datetime, timezone
import requests
from countries.germany.settings import GERMANY_CACHE, NPM_REGISTRY_URL


def _cache_age(path):
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(
        os.path.getmtime(path), timezone.utc
    )
    seconds = max(0, int(age.total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def ensure_station_cache(cache_dir=GERMANY_CACHE, session=None, use_cache=False):
    """Ensure db-stations data exists, downloading the current npm package if needed."""
    os.makedirs(cache_dir, exist_ok=True)
    full_path = os.path.join(cache_dir, "full.json")
    data_path = os.path.join(cache_dir, "data.json")
    if use_cache and os.path.exists(full_path) and os.path.exists(data_path):
        print(f"Using cached Germany station data (full.json age: {_cache_age(full_path)})")
        return full_path

    session = session or requests.Session()
    metadata_response = session.get(NPM_REGISTRY_URL, timeout=30)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    version = metadata.get("version", "unknown")
    tarball_url = metadata.get("dist", {}).get("tarball")
    if not tarball_url:
        raise ValueError("npm metadata for db-stations contains no package tarball")

    print(f"Downloading db-stations {version} from npm...")
    package_response = session.get(tarball_url, timeout=120)
    package_response.raise_for_status()
    with tarfile.open(fileobj=io.BytesIO(package_response.content), mode="r:gz") as archive:
        members = {}
        for name in ("package/full.json", "package/data.json"):
            member = archive.getmember(name)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"db-stations package is missing {name}")
            payload = extracted.read()
            json.loads(payload)
            members[name.rsplit("/", 1)[-1]] = payload

    for filename, payload in members.items():
        temporary = os.path.join(cache_dir, f".{filename}.tmp")
        with open(temporary, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, os.path.join(cache_dir, filename))
    print(f"Cached db-stations {version} (full.json age: {_cache_age(full_path)})")
    return full_path
