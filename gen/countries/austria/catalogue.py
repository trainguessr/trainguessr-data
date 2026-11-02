"""Reviewed catalogue reconciliation for Austria."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
import requests
from typing import Any, Iterable
from common.config import require_reviewed_identity
from countries.austria.decisions import _load_mvo_overrides, load_unmapped_stations
from countries.austria.identity import _float, _normal_name, normalize_ifopt
from countries.austria.scotty import ScottyResolver, verify_scotty_station
from countries.austria.selection import mvo_rail_candidates
from countries.austria.settings import _REVIEWED_NAMES


def merge_catalogues(
    geonetz_nodes: list[dict[str, Any]],
    mvo_rows: Iterable[dict[str, Any]],
    mvo_platforms: Iterable[dict[str, Any]],
    resolver: ScottyResolver,
    rename_map: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing_by_ifopt = {
        normalize_ifopt(node.get("tags", {}).get("ifopt_id")): node
        for node in geonetz_nodes
        if normalize_ifopt(node.get("tags", {}).get("ifopt_id"))
    }
    used_ids = {str(node["id"]) for node in geonetz_nodes}
    new_nodes: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "geonetz_nodes": len(geonetz_nodes),
        "mvo_rail_candidates": 0,
        "matched_existing_ifopt": 0,
        "resolved_to_existing_eva": 0,
        "failed_board_verification": 0,
        "added": [],
        "aliases": [],
        "excluded": [],
        "unresolved": [],
    }
    mvo_excluded_ifopts, mvo_aliases, reviewed_resolutions = _load_mvo_overrides()
    unmapped = load_unmapped_stations()
    existing_by_id = {str(node["id"]): node for node in geonetz_nodes}
    candidates = sorted(
        mvo_rail_candidates(mvo_rows, mvo_platforms, reviewed_resolutions={**unmapped, **reviewed_resolutions}),
        key=lambda item: (str(item.get("hst_name")), str(item.get("hst_globid"))),
    )
    resolutions = {}
    for row in candidates:
        ifopt = normalize_ifopt(row.get("hst_globid"))
        if ifopt not in existing_by_ifopt and ifopt not in mvo_excluded_ifopts and ifopt not in mvo_aliases and ifopt not in unmapped:
            resolutions[ifopt] = resolver.resolve(row)
    verifications = {}
    native_ids = sorted({int(r["eva_id"]) for r in resolutions.values() if r and str(r["eva_id"]) not in used_ids})
    if native_ids and not resolver.offline:
        print(f"Austria: checking {len(native_ids)} SCOTTY station IDs (up to 4 at a time)...", flush=True)
        started = time.monotonic()

        def verify(eva_id):
            # Each worker owns its session; retry only failed IDs after the batch.
            with requests.Session() as session:
                return verify_scotty_station(session, eva_id, resolver.timeout, attempts=1)

        with ThreadPoolExecutor(max_workers=4) as pool:
            for count, (eva_id, result) in enumerate(zip(native_ids, pool.map(verify, native_ids)), 1):
                verifications[eva_id] = result
                if count % 50 == 0 or count == len(native_ids):
                    print(f"Austria: checked {count}/{len(native_ids)} station IDs in {time.monotonic() - started:.1f}s.", flush=True)
        failed_ids = [eva_id for eva_id, result in verifications.items() if result is None]
        if failed_ids:
            print(f"Austria: retrying {len(failed_ids)} failed station checks once...", flush=True)
            with ThreadPoolExecutor(max_workers=4) as pool:
                verifications.update(zip(failed_ids, pool.map(verify, failed_ids)))
    if native_ids and not resolver.offline:
        resolver.record_verifications(verifications)
    for row in candidates:
        audit["mvo_rail_candidates"] += 1
        ifopt = normalize_ifopt(row.get("hst_globid"))
        if ifopt in existing_by_ifopt:
            audit["matched_existing_ifopt"] += 1
            continue
        exclusion = mvo_excluded_ifopts.get(ifopt)
        if exclusion is not None:
            require_reviewed_identity(
                exclusion, row.get("hst_name"), context=f"austria:{ifopt}"
            )
            audit["excluded"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "municipality": row.get("hst_gem_name"),
                "reason": "reviewed_scope_exclusion",
            })
            continue
        alias = mvo_aliases.get(ifopt)
        if alias:
            canonical_id = str(alias["canonical_id"])
            canonical = existing_by_id.get(canonical_id)
            expected_name = str(alias.get("expected_name") or "")
            canonical_expected_name = str(alias.get("canonical_expected_name") or "")
            if canonical is None:
                raise ValueError(f"austria: stale MVO alias {ifopt}->{canonical_id}: canonical node is missing")
            if _normal_name(str(row.get("hst_name") or "")) != _normal_name(expected_name):
                raise ValueError(
                    f"austria: stale MVO alias {ifopt}: expected {expected_name!r}, got {row.get('hst_name')!r}"
                )
            actual_canonical_name = str(canonical.get("tags", {}).get("name") or "")
            if _normal_name(actual_canonical_name) != _normal_name(canonical_expected_name):
                raise ValueError(
                    f"austria: stale MVO alias target {canonical_id}: expected "
                    f"{canonical_expected_name!r}, got {actual_canonical_name!r}"
                )
            audit["resolved_to_existing_eva"] += 1
            audit["aliases"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "canonical_id": int(canonical_id),
                "reason": alias.get("reason", "reviewed_provider_alias"),
            })
            continue
        if ifopt in unmapped:
            audit["unresolved"].append({
                "ifopt_id": ifopt, "name": row.get("hst_name"),
                "reason": "provider_identity_missing", **unmapped[ifopt],
            })
            continue
        resolution = resolutions.get(ifopt)
        if not resolution:
            audit["unresolved"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "municipality": row.get("hst_gem_name"),
                "reason": "no_unique_scotty_match",
            })
            continue
        eva_id = str(resolution["eva_id"])
        if eva_id in used_ids:
            audit["resolved_to_existing_eva"] += 1
            continue
        if resolver.offline:
            verification = resolver.verifications.get(eva_id)
            if not verification:
                audit["unresolved"].append({
                    "ifopt_id": ifopt, "name": row.get("hst_name"),
                    "reason": "missing_cached_verification",
                })
                continue
            verification = {**verification, "journey_count": None}
            board_status = "offline_cached_verification"
        else:
            verification = verifications.get(int(eva_id))
            if not verification:
                audit["failed_board_verification"] += 1
                audit["unresolved"].append({
                    "ifopt_id": ifopt,
                    "name": row.get("hst_name"),
                    "reason": "scotty_station_verification_failed",
                })
                continue
            board_status = "board_available" if verification["journey_count"] else "valid_eva_empty_board"
        expected_provider_name = resolution.get("expected_provider_name")
        if expected_provider_name and _normal_name(verification["station_name"]) != _normal_name(str(expected_provider_name)):
            audit["failed_board_verification"] += 1
            audit["unresolved"].append({
                "ifopt_id": ifopt,
                "name": row.get("hst_name"),
                "reason": "scotty_station_name_mismatch",
            })
            continue
        reviewed_names = _REVIEWED_NAMES.get(ifopt, ())
        source_name = str(row["hst_name"])
        name = reviewed_names[0] if reviewed_names else re.sub(
            r"\s+(?:Bahnhof|Bahnhst)$", "", source_name, flags=re.I
        )
        name = rename_map.get(source_name, name)
        node = {
            "type": "node",
            "id": int(eva_id),
            "lat": _float(row.get("rail_lat", row["hst_y"])),
            "lon": _float(row.get("rail_lon", row["hst_x"])),
            "tags": {
                "name": name,
                "ifopt_id": ifopt,
                "stp_type": "railStation",
                "mvo_hst_id": str(row.get("hst_id") or ""),
                "mvo_municipality": str(row.get("hst_gem_name") or ""),
                "mvo_mode_mask": str(row.get("umst_agg_vm") or ""),
                "mvo_source_name": source_name,
                "mvo_rail_lines": ",".join(row.get("rail_lines") or []),
                "mvo_rail_platform_ifopts": ",".join(row.get("rail_platform_ifopts") or []),
                "source": "MVO Österreichweite Haltestellen",
                "scotty_name": verification["station_name"],
                "scotty_resolution": resolution.get("method", "platform_eva_confirmed"),
                "scotty_board_status": board_status,
            },
            "category": "austria_oebb",
        }
        used_ids.add(eva_id)
        new_nodes.append(node)
        audit["added"].append({
            "id": int(eva_id),
            "ifopt_id": ifopt,
            "name": name,
            "resolved_name": resolution.get("name"),
            "distance_m": resolution.get("distance_m"),
            "similarity": resolution.get("similarity"),
            "board_journeys": verification["journey_count"],
        })
    audit["added_count"] = len(new_nodes)
    audit["alias_count"] = len(audit["aliases"])
    audit["excluded_count"] = len(audit["excluded"])
    audit["unresolved_count"] = len(audit["unresolved"])
    audit["output_nodes"] = len(geonetz_nodes) + len(new_nodes)
    return geonetz_nodes + new_nodes, audit


def preserve_sta_tags(nodes, previous):
    """STA owns these two fields; a GeoNetz/MVO refresh must not erase them."""
    by_id = {str(row["id"]): row for row in previous}
    for row in nodes:
        old = by_id.get(str(row["id"]))
        if old is None or not old.get("tags", {}).get("sta_station_id"):
            continue
        before = normalize_ifopt(old["tags"].get("ifopt_id"))
        after = normalize_ifopt(row.get("tags", {}).get("ifopt_id"))
        if not before or before != after:
            raise ValueError(f"Check the STA mapping for Austrian station {row['id']}: its IFOPT changed.")
        for field in ("sta_station_id", "sta_station_name"):
            if field in old["tags"]:
                row.setdefault("tags", {})[field] = old["tags"][field]
    return nodes
