from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.request import Request, urlopen

from .io import ROOT, load_ndjson, write_csv
from .validate import validate_file


USER_AGENT = "trainguessr-data/1.0"


def provider_cache(operator: str, section: str, filename: str) -> Path:
    return ROOT / "cache" / "italy" / operator / section / filename


def download(url: str, target: Path) -> bytes:
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


def finish(operator: str) -> None:
    from italy_legacy import rebuild
    from italy_review import review_after_generation

    output, audit = rebuild(operator)
    path = ROOT / "nodes" / f"nodes-italy-{operator}.json"
    errors = validate_file(path)
    if errors:
        raise ValueError(f"{operator}: {'; '.join(errors)}")
    review_count = sum(row["status"] != "matched" for row in audit)
    print(f"Wrote {len(output)} stations to {path.relative_to(ROOT)}")
    print(f"Review items: {review_count}")
    review_after_generation(operator)
