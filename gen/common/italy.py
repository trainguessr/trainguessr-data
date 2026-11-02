from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.request import Request, urlopen

from .io import ROOT, load_ndjson, require_cached_file, write_csv
from .validate import validate_file


USER_AGENT = "trainguessr-data/1.0"


def provider_cache(operator: str, section: str, filename: str) -> Path:
    return ROOT / "cache" / "italy" / operator / section / filename


def download(url: str, target: Path, *, use_cache: bool = False) -> bytes:
    if use_cache:
        return require_cached_file(target, "Italian provider source").read_bytes()
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=180) as response:
        data = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def extract_options(text: str) -> list[dict[str, str]]:
    rows = []
    for station_id, name in re.findall(
        r'<option[^>]*value=["\']?([^"\' >]*)["\']?[^>]*>(.*?)</option>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        clean_name = re.sub(r"<.*?>", "", html.unescape(name), flags=re.DOTALL)
        clean_name = re.sub(r"\s+", " ", clean_name).strip()
        if station_id.strip() and clean_name:
            rows.append({"id": station_id.strip(), "name": clean_name})
    return rows


def current_ids(operator: str) -> set[str]:
    path = ROOT / "nodes" / f"nodes-italy-{operator}.json"
    return {str(row["id"]) for row in load_ndjson(path)}


def write_catalog(operator: str, rows: list[dict[str, str]], fields: list[str]) -> Path:
    path = provider_cache(operator, "derived", "stations.csv")
    write_csv(path, rows, fields)
    return path


def finish(operator: str) -> int:
    from countries.italy.reviewed.rebuild import checked_rebuild
    from countries.italy.reviewed.paths import audit_report_path

    output, _audit, status = checked_rebuild(operator)
    if status:
        from countries.italy.review import review_after_generation
        reviewed = review_after_generation(operator)
        if reviewed is None or reviewed:
            return status
        output, _audit, status = checked_rebuild(operator)
        if status:
            return status
    path = ROOT / "nodes" / f"nodes-italy-{operator}.json"
    errors = validate_file(path)
    if errors:
        raise ValueError(f"{operator}: {'; '.join(errors)}")
    print(f"OK | italy/{operator} | {len(output)} checked stations; "
          f"report: {audit_report_path(operator).relative_to(ROOT)}")
    return 0
