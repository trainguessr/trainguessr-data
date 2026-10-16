"""Reviewed catalogue reconciliation for Austria."""
from __future__ import annotations

import re
from typing import Any, Iterable
from common.config import require_reviewed_identity
from countries.austria.decisions import _load_mvo_overrides
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
    existing_by_id = {str(node["id"]): node for node in geonetz_nodes}
    for row in sorted(mvo_rail_candidates(mvo_rows, mvo_platforms, reviewed_resolutions=reviewed_resolutions), key=lambda item: (str(item.get("hst_name")), str(item.get("hst_globid")))):
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
        resolution = resolver.resolve(row)
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
            verification = {
                "station_name": str(
                    resolution.get("expected_provider_name")
                    or resolution.get("name")
                    or row.get("hst_name")
                    or ""
                ),
                "journey_count": 0,
            }
            board_status = "offline_cached_resolution"
        else:
            verification = verify_scotty_station(resolver.session, int(eva_id), resolver.timeout)
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
