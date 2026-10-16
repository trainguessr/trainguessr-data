"""Pure reviewed-coordinate reconciliation for Italian providers."""
import copy
from common.config import require_reviewed_identity
from common.normalize import normalize_name
from common.manual_overrides import apply_coordinate_overrides
from countries.italy.reviewed.decisions import handled_outside_provider_review
from countries.italy.reviewed.settings import OPERATOR_NAMES


def prepare_reviewed_seed(operator, seed_rows, italy_config):
    seed_rows = list(seed_rows)
    seed_ids = {str(row["id"]) for row in seed_rows}
    for manual in italy_config.get("manual_stations", []):
        if manual.get("operator") != operator or str(manual.get("id")) in seed_ids:
            continue
        station_id: str | int = str(manual["id"])
        if operator in {"eav", "rfi"} and station_id.isdigit():
            station_id = int(station_id)
        seed_rows.append({
            "type": "node",
            "id": station_id,
            "lat": float(manual["lat"]),
            "lon": float(manual["lon"]),
            "tags": {
                "name": str(manual["name"]),
                "operator": OPERATOR_NAMES[operator],
            },
            "category": f"italy_{operator}",
        })
        seed_ids.add(str(station_id))

    return seed_rows


def classify_reviewed(operator, source, seed_rows, italy_config, exclusion_rules):
    seed_ids = {str(row["id"]) for row in seed_rows}
    review_exclusions = {
        str(review.get("id")): {
            "expected_name": review.get("source_name") or review.get("reviewed_name")
        }
        for review in italy_config.get("reviews", [])
        if review.get("operator") == operator
        and review.get("decision") == "excluded"
        and review.get("id") not in (None, "")
    }
    excluded = set(exclusion_rules) | set(review_exclusions)

    output: list[dict] = []
    audit: list[dict] = []

    expected_category = f"italy_{operator}"
    accepted_source_names = {
        (
            str(review.get("id", "")),
            str(review.get("source_name", "")),
            str(review.get("reviewed_name", "")),
        )
        for review in italy_config.get("reviews", [])
        if review.get("operator") == operator
        and review.get("status") == "matched_name_difference"
        and review.get("decision") == "use_source_name"
    }

    # Keep reviewed order, coordinates and metadata. Provider data is
    # currently used only to verify identifiers and report name differences.
    for reviewed in seed_rows:
        station_id = str(reviewed["id"])

        if station_id in excluded:
            source_name = source.get(station_id, {}).get("name", "")
            reviewed_name = reviewed.get("tags", {}).get("name", "")
            require_reviewed_identity(
                exclusion_rules.get(station_id) or review_exclusions[station_id],
                source_name if station_id in source else reviewed_name,
                context=f"italy/{operator}:{station_id}",
            )
            audit.append(
                {
                    "id": station_id,
                    "source_name": source_name,
                    "reviewed_name": reviewed_name,
                    "status": "excluded",
                    "details": "listed in overrides/exclusions/italy.json",
                }
            )
            continue

        node = copy.deepcopy(reviewed)

        if node.get("category") != expected_category:
            previous_category = node.get("category", "")
            node["category"] = expected_category

            if operator == "rfi":
                node.setdefault("tags", {})["operator"] = "RFI"

            category_detail = (
                f"category corrected from {previous_category!r} "
                f"to {expected_category!r}"
            )
        else:
            category_detail = ""

        output.append(node)

        source_row = source.get(station_id)
        reviewed_name = str(node.get("tags", {}).get("name", ""))

        if source_row is None:
            audit.append(
                {
                    "id": station_id,
                    "source_name": "",
                    "reviewed_name": reviewed_name,
                    "status": "reviewed_only_retained",
                    "details": (
                        "absent from current provider snapshot"
                        + (f"; {category_detail}" if category_detail else "")
                    ),
                }
            )
            continue

        source_name = str(source_row.get("name", ""))

        if (station_id, source_name, reviewed_name) in accepted_source_names:
            node.setdefault("tags", {})["name"] = source_name
            reviewed_name = source_name

        if normalize_name(source_name) == normalize_name(reviewed_name):
            status = "matched"
        else:
            status = "matched_name_difference"

        details = "provider ID match"

        if category_detail:
            details += f"; {category_detail}"

        audit.append(
            {
                "id": station_id,
                "source_name": source_name,
                "reviewed_name": reviewed_name,
                "status": status,
                "details": details,
            }
        )

    # Provider records not represented in the reviewed coordinate seed cannot
    # be added safely. Record them for manual coordinate review.
    for station_id, source_row in sorted(source.items()):
        if station_id in seed_ids:
            continue

        is_excluded = station_id in excluded
        if is_excluded:
            require_reviewed_identity(
                exclusion_rules.get(station_id) or review_exclusions[station_id],
                source_row.get("name", ""),
                context=f"italy/{operator}:{station_id}",
            )
        outside_provider = handled_outside_provider_review(
            italy_config,
            operator,
            station_id,
        )

        if outside_provider is not None:
            require_reviewed_identity(
                {"expected_name": outside_provider.get("source_name") or outside_provider.get("reviewed_name")},
                source_row.get("name", ""),
                context=f"italy/{operator} cross-provider:{station_id}",
            )
            audit.append(
                {
                    "id": station_id,
                    "source_name": source_row.get("name", ""),
                    "reviewed_name": str(outside_provider.get("reviewed_name", "")),
                    "status": "handled_by_other_provider",
                    "details": str(
                        outside_provider.get("details")
                        or "handled by another provider"
                    ),
                }
            )
            continue

        audit.append(
            {
                "id": station_id,
                "source_name": source_row.get("name", ""),
                "reviewed_name": "",
                "status": "excluded" if is_excluded else "missing_coordinates",
                "details": (
                    "listed in overrides/exclusions/italy.json"
                    if is_excluded
                    else "provider record has no reviewed coordinate match"
                ),
            }
        )

    return output, audit


def apply_reviewed_coordinates(operator, output, audit, coordinate_overrides):
    overridden_ids = apply_coordinate_overrides(
        output,
        coordinate_overrides,
        context=f"italy/{operator}",
    )
    if overridden_ids:
        for row in audit:
            if str(row.get("id")) in overridden_ids:
                details = str(row.get("details") or "")
                row["details"] = (
                    f"{details}; guarded coordinate override applied"
                    if details else "guarded coordinate override applied"
                )
