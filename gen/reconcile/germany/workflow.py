"""Reviewed reconciliation orchestration and audit outcomes for Germany."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from common.io import logical_path
from reconcile.germany.candidates import _boundary_geometry, build_gtfs_candidates
from reconcile.germany.db import (
    DbProbe,
    _candidate_station_names,
    _preferred_provider_ids,
    _snapshot_indexes,
    _values,
    _verification_state,
    candidate_snapshot_matches,
    load_catalogue_index,
    load_generated_identity_index,
    load_station_snapshot,
)
from reconcile.germany.decisions import load_reviewed_gap_notes, load_reviewed_station_overrides
from reconcile.germany.io import _read_json, sha256
from reconcile.germany.matching import _normalise, build_node_grid, nearby_nodes
from reconcile.germany.settings import (
    BOUNDARY_CACHE,
    BOUNDARY_URL,
    CATALOGUE,
    DB_PLAN_URL,
    DB_SNAPSHOT,
    DB_STATION_URL,
    DB_WILDCARD_URL,
    GTFS_ARCHIVE,
    GTFS_FEED_PAGE,
    GTFS_URL,
    NODES,
    OSM_BATCH_SIZE,
    OSM_ENDPOINTS,
    SEPARATE_PROVIDER_MARKERS,
    STALE_OSM_CACHE,
)
from reconcile.germany.stale import _stale_osm_evidence, _stale_records


def _provider_group(agency_names: Iterable[str]) -> str:
    text = _normalise(" ".join(agency_names))
    if any(marker in text for marker in SEPARATE_PROVIDER_MARKERS):
        return "separate_heritage_or_tourist_rail"
    return "regional_or_mainline_rail"


def _station_summaries(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        result.append(
            {
                key: record.get(key)
                for key in ("eva", "meta", "ids", "name", "ds100", "db")
                if record.get(key) not in (None, "", [])
            }
        )
    return result


def _probe_summary(probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "station_checks": [
            {
                key: row.get(key)
                for key in (
                    "requested_eva",
                    "url",
                    "http_status",
                    "response_bytes",
                    "eva",
                    "meta",
                    "name",
                    "name_match",
                    "ds100",
                    "db",
                    "verification_state",
                    "error",
                )
                if row.get(key) not in (None, "")
            }
            for row in probe.get("station_checks", [])
        ],
        "plan_checks": [
            {
                key: row.get(key)
                for key in (
                    "requested_eva",
                    "slot",
                    "url",
                    "http_status",
                    "response_bytes",
                    "verification_state",
                    "error",
                )
                if row.get(key) not in (None, "")
            }
            for row in probe.get("plan_checks", [])
        ],
        "selected_eva": probe.get("selected_eva"),
        "station_http_status": probe.get("station_http_status"),
        "plan_http_status": probe.get("plan_http_status"),
    }


def _node_match_summary(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        tags = row.get("tags") if isinstance(row.get("tags"), dict) else {}
        result.append(
            {
                "node_id": str(row.get("id") or ""),
                "name": tags.get("name", ""),
                "provider_place_ids": list(_values(tags.get("provider_place_ids"))),
                "further_ids": list(_values(tags.get("further_ids"))),
                "latitude": row.get("lat"),
                "longitude": row.get("lon"),
            }
        )
    return result


def _outcome(
    candidate: dict[str, Any],
    *,
    status: str,
    reason: str,
    provider_group: str,
    evidence: dict[str, Any],
    provider_id: str | None = None,
) -> dict[str, Any]:
    row = {
        "gtfs_parent_station": candidate["gtfs_parent_station"],
        "gtfs_stop_ids": candidate["gtfs_stop_ids"],
        "gtfs_stop_names": candidate["gtfs_stop_names"],
        "name": candidate["name"],
        "latitude": candidate["latitude"],
        "longitude": candidate["longitude"],
        "agency_ids": candidate["agency_ids"],
        "agency_names": candidate["agency_names"],
        "route_ids": candidate["route_ids"],
        "route_names": candidate["route_names"],
        "rail_stop_time_count": candidate["rail_stop_time_count"],
        "status": status,
        "provider_group": provider_group,
        "reason": reason,
        "evidence": evidence,
    }
    if provider_id:
        row["eva_id"] = provider_id
        row["db"] = "true"
        row["source"] = "reviewed-germany-current-provider"
        for station in evidence.get("db_probe", {}).get("station_checks", []):
            if str(station.get("requested_eva") or "") == provider_id:
                if station.get("ds100"):
                    row["ds100"] = station["ds100"]
                break
    return row


def _preserved_rows(previous_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    preserved: dict[str, dict[str, Any]] = {}
    for row in previous_audit.get("outcomes", []) if isinstance(previous_audit, dict) else []:
        if not isinstance(row, dict):
            continue
        if (
            row.get("status") == "added_existing_provider"
            and row.get("source") == "reviewed-germany-current-provider"
        ):
            parent = str(row.get("gtfs_parent_station") or "").strip()
            if parent:
                preserved[parent] = row
            continue
        # Keep reviewed additions stable after they have been integrated into
        # the generated catalogue. The first Germany pass predates the full
        # ledger and has no explicit source field, so its AKN prefix is also
        # kept for compatibility.
        if row.get("source") not in ("reviewed-germany-akn-supplement", None):
            continue
        if row.get("source") is None and (
            "agency_names" in row or "provider_group" in row
        ):
            continue
        parent = str(row.get("gtfs_parent_station") or "").strip()
        if parent:
            preserved[parent] = row
    return preserved


def reconcile(
    *,
    archive_path: Path = GTFS_ARCHIVE,
    boundary_path: Path = BOUNDARY_CACHE,
    station_snapshot_path: Path = DB_SNAPSHOT,
    catalogue_path: Path = CATALOGUE,
    nodes_path: Path = NODES,
    previous_audit: dict[str, Any] | None = None,
    db_probe: DbProbe | None = None,
    probe_stale_osm: dict[str, Any] | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    boundary = _boundary_geometry(_read_json(boundary_path))
    gtfs_metadata, candidates, out_of_scope = build_gtfs_candidates(archive_path, boundary)
    station_records, namespace = load_station_snapshot(station_snapshot_path)
    snapshot_indexes = _snapshot_indexes(station_records)
    generated = load_generated_identity_index(nodes_path)
    catalogue = load_catalogue_index(catalogue_path)
    reviewed_station_overrides = load_reviewed_station_overrides()
    reviewed_gap_notes = load_reviewed_gap_notes()
    node_grid = build_node_grid(generated["rows"])
    previous = previous_audit or {}
    preserved = _preserved_rows(previous)
    candidate_parent_ids = {row["gtfs_parent_station"] for row in candidates}
    preserved_rows = [
        preserved[parent] for parent in preserved if parent in candidate_parent_ids
    ]
    preserved_parent_ids = {str(row.get("gtfs_parent_station")) for row in preserved_rows}
    probe = db_probe or DbProbe()
    outcomes: list[dict[str, Any]] = []
    added_provider_ids: set[str] = set(generated["by_id"])
    feed_hash = sha256(archive_path)

    # Keep the manually verified AKN prefix byte-for-byte compatible with the
    # existing generator order while replacing the rest with the full audit.
    outcomes.extend(preserved_rows)
    for index, candidate in enumerate(
        (row for row in candidates if row["gtfs_parent_station"] not in preserved_parent_ids),
        1,
    ):
        matches, strong_matches, matched_alias = candidate_snapshot_matches(
            candidate, snapshot_indexes, station_records
        )
        reviewed_override = reviewed_station_overrides.get(
            str(candidate["gtfs_parent_station"])
        )
        if reviewed_override:
            override_ids = set(reviewed_override["provider_ids"])
            override_matches = [
                record
                for record in station_records
                if override_ids.intersection(str(value) for value in record.get("ids", []))
            ]
            if not override_matches:
                raise ValueError(
                    "Reviewed Germany station override is absent from the current DB namespace: "
                    f"{candidate['gtfs_parent_station']} -> {sorted(override_ids)}"
                )
            matches = [
                *override_matches,
                *[
                    record
                    for record in matches
                    if record not in override_matches
                ],
            ]
            strong_matches = override_matches
            matched_alias = str(reviewed_override.get("name_alias") or candidate["name"])
        probe_matches = strong_matches
        provider_ids = _preferred_provider_ids(probe_matches)
        node_matches = nearby_nodes(candidate, node_grid)
        evidence: dict[str, Any] = {
            "gtfs": {
                "feed_url": GTFS_URL,
                "feed_sha256": feed_hash,
                "route_type": "2",
                "rail_stop_time_count": candidate["rail_stop_time_count"],
                "parent_location_type": candidate["location_type"],
            },
            "db_namespace_matches": _station_summaries(matches),
            "generated_node_matches": _node_match_summary(node_matches),
            "cached_catalogue_matches": [
                station_id
                for record in matches
                for station_id in record.get("ids", [])
                if station_id in catalogue["by_id"]
            ],
        }
        if matched_alias:
            evidence["db_namespace_match_alias"] = matched_alias
        if reviewed_override:
            evidence["reviewed_station_override"] = {
                key: value
                for key, value in reviewed_override.items()
                if key != "provider_ids"
            }
        provider_group = _provider_group(
            [
                *candidate["agency_names"],
                *candidate["route_names"],
                candidate["name"],
            ]
        )
        reviewed_gap_note = reviewed_gap_notes.get(
            str(candidate["gtfs_parent_station"])
        )
        if node_matches:
            canonical_id = str(node_matches[0].get("id"))
            outcomes.append(
                _outcome(
                    candidate,
                    status="already_represented",
                    reason=(
                        "The GTFS passenger stop place matches an existing generated station by name and physical coordinates; no duplicate node is created."
                    ),
                    provider_group=provider_group,
                    evidence={**evidence, "canonical_node_id": canonical_id},
                )
            )
        elif not provider_ids:
            status = (
                "new_provider_needed"
                if provider_group == "separate_heritage_or_tourist_rail"
                else "provider_gap"
            )
            reason = (
                "The current DB namespace has no name candidate; the GTFS agency identifies a separate railway system."
                if status == "new_provider_needed"
                else "The current DB namespace has no candidate for this current German GTFS rail stop place."
            )
            if reviewed_gap_note:
                reason = reviewed_gap_note["reason"]
                evidence["reviewed_gap_note"] = reviewed_gap_note
            outcomes.append(
                _outcome(
                    candidate,
                    status=status,
                    reason=reason,
                    provider_group=provider_group,
                    evidence=evidence,
                )
            )
        else:
            probe_aliases = list(_candidate_station_names(candidate))
            probe_aliases.extend(
                str(match.get("name") or "").strip()
                for match in strong_matches
                if str(match.get("name") or "").strip()
            )
            probe_result = probe.resolve(
                provider_ids,
                expected_name=candidate["name"],
                expected_name_aliases=list(dict.fromkeys(probe_aliases)),
            )
            evidence["db_probe"] = _probe_summary(probe_result)
            selected_eva = str(probe_result.get("selected_eva") or "").strip()
            blocked_states = {
                _verification_state(row)
                for row in [
                    *probe_result.get("station_checks", []),
                    *probe_result.get("plan_checks", []),
                ]
                if _verification_state(row).startswith("provider_verification_blocked_")
            }
            if selected_eva:
                if selected_eva in added_provider_ids:
                    status = "alias_member_existing_station_complex"
                    reason = "The verified DB EVA is already represented by a generated station or earlier candidate outcome."
                else:
                    status = "added_existing_provider"
                    reason = "The direct DB station response returned db=true and at least one sampled DB plan response returned HTTP 200."
                    added_provider_ids.add(selected_eva)
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=reason,
                        provider_group=provider_group,
                        evidence=evidence,
                        provider_id=selected_eva if status == "added_existing_provider" else None,
                    )
                )
            elif blocked_states:
                status = sorted(blocked_states)[0]
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=(
                            "Direct DB identity verification was blocked; the audit keeps the GTFS passenger candidate without a guessed ID."
                        ),
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
            elif any(
                row.get("http_status") == 200 and row.get("db") is True
                for row in probe_result.get("station_checks", [])
            ):
                outcomes.append(
                    _outcome(
                        candidate,
                        status="unresolved",
                        reason=(
                            "A direct DB station identity was accepted, but none of the sampled plan hours returned a plan document; the native ID is not promoted without stronger current evidence."
                        ),
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
            else:
                status = (
                    "new_provider_needed"
                    if provider_group == "separate_heritage_or_tourist_rail"
                    else "provider_gap"
                )
                reason = (
                    "The candidate is part of a separate railway system and no verified DB runtime identity was found."
                    if status == "new_provider_needed"
                    else "DB namespace candidates were tested, but no current db=true station with a sampled plan response was verified."
                )
                if reviewed_gap_note:
                    reason = reviewed_gap_note["reason"]
                    evidence["reviewed_gap_note"] = reviewed_gap_note
                outcomes.append(
                    _outcome(
                        candidate,
                        status=status,
                        reason=reason,
                        provider_group=provider_group,
                        evidence=evidence,
                    )
                )
        if progress and index % 25 == 0:
            print(f"Reconciled {index}/{len(candidates) - len(preserved_parent_ids)} Germany GTFS station places")

    stale = _stale_records(catalogue, generated, namespace)
    osm_elements = (probe_stale_osm or {}).get("elements", []) if isinstance(probe_stale_osm, dict) else []
    stale_outcomes: list[dict[str, Any]] = []
    for record in stale:
        direct = probe.resolve([record["cached_id"]])
        direct_summary = _probe_summary(direct)
        osm = _stale_osm_evidence(record, osm_elements)
        direct_station = next(
            (row for row in direct.get("station_checks", []) if row.get("http_status") == 200),
            None,
        )
        if direct_station and direct_station.get("db") is True:
            status = "already_represented"
            reason = "The cached ID is absent from the wildcard namespace but the direct current DB station endpoint still returns db=true."
        elif record.get("generated_canonical_id") and record.get("generated_canonical_id") != record.get("cached_id"):
            status = "alias_member_existing_station_complex"
            reason = "The stale cached identity is kept as an alias of an existing generated station; absence from the current wildcard namespace is not deletion evidence."
        elif any(row.get("lifecycle_flags") for row in osm.get("nearby_features", [])) and not osm.get("extant_passenger_feature_count"):
            status = "dismantled_exclusion"
            reason = "OSM/ORM nearby railway features carry explicit gone-lifecycle signals without an extant passenger feature; removal still requires a deliberate generator exclusion."
        elif osm.get("extant_passenger_feature_count"):
            status = "provider_gap"
            reason = "Physical passenger-rail evidence still exists near the historical DB identity, but no current direct db=true identity was verified."
        else:
            blocked_states = {
                _verification_state(row)
                for row in [*direct.get("station_checks", []), *direct.get("plan_checks", [])]
                if _verification_state(row).startswith("provider_verification_blocked_")
            }
            status = sorted(blocked_states)[0] if blocked_states else "unresolved"
            reason = (
                "Direct DB verification was blocked; no deletion decision is made."
                if blocked_states
                else "Neither current direct DB identity nor nearby OSM/ORM passenger evidence supports a safe lifecycle decision."
            )
        stale_outcomes.append(
            {
                **record,
                "status": status,
                "reason": reason,
                "evidence": {
                    "current_db_namespace_contains_id": record["cached_id"] in namespace,
                    "direct_db": direct_summary,
                    "osm": osm,
                },
            }
        )

    candidate_statuses = Counter(row.get("status") for row in outcomes)
    stale_statuses = Counter(row.get("status") for row in stale_outcomes)
    primary_stale = sum(row.get("cache_role") == "primary" for row in stale)
    alias_stale = sum(row.get("cache_role") != "primary" for row in stale)
    source_files = {
        "gtfs_archive": logical_path(archive_path),
        "cached_station_catalogue": logical_path(catalogue_path),
        "current_db_station_namespace": logical_path(station_snapshot_path),
        "germany_boundary": logical_path(boundary_path),
        "generated_nodes": logical_path(nodes_path),
    }
    if probe_stale_osm is not None:
        source_files["stale_osm_capture"] = logical_path(STALE_OSM_CACHE)
    review = {
        "db_auth_configured": probe.auth_configured,
        "db_plan_slots": list(probe.plan_slots),
        "db_probe_delay_seconds": probe.delay,
        "physical_evidence_rule": "GTFS scheduled route_type=2 usage defines current passenger candidates; stale identities additionally require OSM/ORM lifecycle review.",
    }
    if probe_stale_osm is not None:
        review["osm_capture"] = {
            "queried_records": probe_stale_osm.get("queried_records"),
            "elements": len(probe_stale_osm.get("elements", [])),
            "errors": len(probe_stale_osm.get("errors", [])),
            "batch_size": OSM_BATCH_SIZE,
            "complete": not probe_stale_osm.get("errors"),
        }
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "audit_with_explicit_unresolved",
        "scope": "German-boundary GTFS.de/DELFI route_type=2 rail parent stop places with at least one passenger boarding or alighting event",
        "source_urls": {
            "gtfs_feed_page": GTFS_FEED_PAGE,
            "gtfs_feed": GTFS_URL,
            "db_station_api": DB_STATION_URL,
            "db_plan_api": DB_PLAN_URL,
            "db_station_namespace": DB_WILDCARD_URL,
            "boundary": BOUNDARY_URL,
            "osm": OSM_ENDPOINTS[0],
        },
        "source_files": source_files,
        "source_sha256": {
            "gtfs_archive": sha256(archive_path),
            "cached_station_catalogue": sha256(catalogue_path),
            "current_db_station_namespace": sha256(station_snapshot_path),
            "germany_boundary": sha256(boundary_path),
            "generated_nodes": sha256(nodes_path),
        },
        "review": review,
        "counts": {
            **gtfs_metadata,
            "current_db_station_records": len(station_records),
            "current_db_namespace_ids": len(namespace),
            "generated_nodes_before_reconciliation": len(generated["rows"]),
            "generated_provider_ids_before_reconciliation": len(generated["by_id"]),
            "candidate_records": len(outcomes),
            "candidate_statuses": dict(sorted(candidate_statuses.items())),
            "candidate_provider_groups": dict(sorted(Counter(
                str(row.get("provider_group") or "preserved_legacy") for row in outcomes
            ).items())),
            "verified_additions": candidate_statuses.get("added_existing_provider", 0),
            "out_of_scope_records": len(out_of_scope),
            "cached_primary_ids": sum(bool(str(row.get("id") or "").strip()) for row in catalogue["rows"]),
            "cached_provider_ids": len(catalogue["by_id"]),
            "cached_primary_ids_absent_from_current_db_namespace": primary_stale,
            "cached_alias_ids_absent_from_current_db_namespace": alias_stale,
            "cached_ids_absent_from_current_db_namespace": len(stale),
            "stale_statuses": dict(sorted(stale_statuses.items())),
            "stale_records": len(stale_outcomes),
        },
        "out_of_scope": out_of_scope,
        "outcomes": outcomes,
        "stale_cached_id_outcomes": stale_outcomes,
    }
