"""Review evidence and persisted decisions for Italian providers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any
from reconcile.italy.viaggiatreno.settings import DEFERRED_SEED, VALID_VT_ID


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}")
            if not isinstance(row, dict):
                raise SystemExit(f"{path}:{lineno}: expected JSON object")
            rows.append(row)
    return rows


def load_review(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Review file must contain a JSON object")

    by_id: dict[str, dict[str, Any]] = {}
    for bucket in ("safe_to_promote", "manual_review", "unresolved"):
        rows = data.get(bucket) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("rfi_place_id") or "").strip()
            if not pid:
                continue
            item = dict(row)
            item["_bucket"] = bucket
            by_id[pid] = item
    return by_id


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 2, "review_pass": 1, "decisions": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid progress file: {path}")
    # Schema 2 adds pass-aware temporary deferrals. Old progress files remain valid.
    data["schema_version"] = max(int(data.get("schema_version") or 1), 2)
    data.setdefault("review_pass", 1)
    data.setdefault("decisions", {})
    return data


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def bootstrap_progress(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Build durable review state from committed runtime mappings + defer seeds."""
    progress: dict[str, Any] = {
        "schema_version": 2,
        "review_pass": 1,
        "decisions": {},
    }
    decisions = progress["decisions"]
    for node in nodes:
        pid = str(node.get("id") or "")
        tags = node.get("tags") if isinstance(node.get("tags"), dict) else {}
        sid = str(tags.get("viaggiatreno_station_id") or "").strip()
        if VALID_VT_ID.fullmatch(sid):
            decisions[pid] = {
                "action": "accept",
                "vt_station_id": sid,
                "vt_name": str(tags.get("viaggiatreno_name") or "").strip() or None,
                "region": tags.get("viaggiatreno_region"),
                "method": "bootstrap_from_committed_nodes",
                "note": "existing reviewed runtime mapping",
            }

    if DEFERRED_SEED.is_file():
        seed = json.loads(DEFERRED_SEED.read_text(encoding="utf-8"))
        for row in seed.get("stations", []):
            pid = str(row.get("rfi_place_id") or "")
            if not pid or pid in decisions:
                continue
            decisions[pid] = {
                "action": "defer",
                "deferred_pass": 1,
                "note": str(row.get("reason") or "deferred_for_now"),
                "source_bucket": "tracked_deferred_seed",
            }
    return progress


def choose_deferred(
    nodes: list[dict[str, Any]],
    decisions: dict[str, Any],
) -> set[str]:
    """Interactively choose which previous deferrals should be retried now."""
    by_id = {str(n.get("id") or ""): n for n in nodes}
    rows = [
        (pid, d) for pid, d in decisions.items()
        if isinstance(d, dict) and d.get("action") == "defer" and pid in by_id
    ]
    if not rows or not sys.stdin.isatty():
        return set()

    rows.sort(key=lambda item: (by_id[item[0]].get("tags", {}).get("name", ""), item[0]))
    print(f"\n{len(rows)} station(s) were deferred in an earlier review.")
    answer = input("Recheck deferred stations now? [n]one / [a]ll / [l]ist-select > ").strip().lower()
    if answer in ("a", "all"):
        return {pid for pid, _ in rows}
    if answer not in ("l", "list"):
        return set()

    print()
    for idx, (pid, decision) in enumerate(rows, 1):
        name = by_id[pid].get("tags", {}).get("name", "")
        print(f"{idx:>3}. {name} ({pid})")
        print(f"     Last time: {decision.get('note') or 'no reason recorded'}")
    raw = input("Numbers to recheck (comma-separated; ranges like 2-5; blank=none): ").strip()
    chosen: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a, b = int(left), int(right)
            except ValueError:
                continue
            chosen.update(range(min(a, b), max(a, b) + 1))
        else:
            try:
                chosen.add(int(part))
            except ValueError:
                continue
    return {pid for idx, (pid, _) in enumerate(rows, 1) if idx in chosen}
