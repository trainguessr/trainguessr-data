"""Interactive provider review for Italian providers."""
from __future__ import annotations

import argparse
import os
import sys
from common.config import load_country_config, load_excluded_ids
from countries.italy.review_decisions import remember, review_key, save_config, saved_review_keys
from countries.italy.review_nodes import (
    add_coordinates, add_native_id, exclude_station, load_review_rows,
)
from countries.italy.review_settings import OPERATORS

REVIEW_MESSAGES = {
    "missing_native_id": "This station has no provider ID yet. Check the ID.",
    "missing_coordinates": "New station. Add coordinates or exclude it with a reason.",
    "provider_scope_review": "Check which railway runs this station.",
    "matched_name_difference": "The provider name changed. Check the station name.",
    "reviewed_only_retained": "Not found in the new download. Kept the old station.",
    "gtfs_name_missing": "The station name is missing from the current timetable file.",
    "manual_reviewed": "Check this station ID.",
}


def prompt_coordinates() -> tuple[float, float] | None:
    value = input("Coordinates as latitude,longitude or d to defer: ").strip()
    if value.lower() == "d":
        return None
    try:
        lat_text, lon_text = value.split(",", 1)
        return float(lat_text.strip()), float(lon_text.strip())
    except ValueError:
        print("Enter two numbers separated by a comma.")
        return prompt_coordinates()


def pending_review_rows(operator: str) -> list[dict[str, str]]:
    """Only actionable, unsaved decisions from the last candidate audit."""
    config = load_country_config("italy")
    saved = saved_review_keys(config)
    excluded = load_excluded_ids("italy", operator)
    return [
        row for row in load_review_rows(operator)
        if row["id"] not in excluded and review_key(operator, row) not in saved
    ]


def review_operator(operator: str) -> int:
    config = load_country_config("italy")
    rows = pending_review_rows(operator)
    if not rows:
        print(f"{operator.upper()}: no new review items")
        return 0

    priority = {
        "missing_native_id": 0,
        "missing_coordinates": 0,
        "provider_scope_review": 0,
        "manual_reviewed": 1,
        "reviewed_only_retained": 2,
        "gtfs_name_missing": 3,
        "matched_name_difference": 4,
    }
    rows.sort(key=lambda row: (priority[row["status"]], row["id"]))
    print(f"{operator.upper()}: {len(rows)} new review items")

    for index, row in enumerate(rows):
        name = row["source_name"] or row["reviewed_name"]
        print(f"\n{REVIEW_MESSAGES.get(row['status'], 'Check this station ID.')} {row['id']} {name}")
        if row["source_name"] and row["reviewed_name"] and row["source_name"] != row["reviewed_name"]:
            print(f"Source:   {row['source_name']}")
            print(f"Reviewed: {row['reviewed_name']}")
        if row["status"] == "provider_scope_review":
            print("Trenord lists this ID, but it has not been checked as an FN station.")
            choice = input("[y]es, it is FN; [n]o, it is not FN; [d]efer; [q]uit: ").strip().lower()
            if choice == "y":
                coordinates = prompt_coordinates()
                if coordinates is not None:
                    try:
                        add_coordinates(config, operator, row, *coordinates)
                    except ValueError as exc:
                        print(exc)
                        continue
                    remember(config, operator, row, "confirmed_fn")
            elif choice == "n":
                remember(config, operator, row, "not_fn")
            elif choice == "q":
                return 1
            continue

        if row["status"] == "missing_coordinates":
            choice = input("[c]oordinates, [e]xclude, [d]efer, [q]uit: ").strip().lower()
            if choice == "c":
                coordinates = prompt_coordinates()
                if coordinates is not None:
                    try:
                        add_coordinates(config, operator, row, *coordinates)
                    except ValueError as exc:
                        print(exc)
                        continue
                    remember(config, operator, row, "added_coordinates")
            elif choice == "e":
                exclude_station(config, operator, row)
                remember(config, operator, row, "excluded")
            elif choice == "q":
                return 1
            continue

        if row["status"] == "missing_native_id":
            choice = input("Enter the exact provider ID [i], defer [d], or quit [q]: ").strip().lower()
            if choice == "i":
                station_id = input("Exact ViaggiaTreno ID (S followed by five digits): ").strip()
                try:
                    add_native_id(config, operator, row, station_id)
                except ValueError as exc:
                    print(exc)
                    continue
                remember(config, operator, row, "added_native_id")
            elif choice == "q":
                return 1
            continue

        if row["status"] == "matched_name_difference":
            choice = input("[k]eep reviewed, use [s]ource, keep [a]ll names, [d]efer, [q]uit: ").strip().lower()
            if choice == "k":
                remember(config, operator, row, "keep_reviewed_name")
            elif choice == "s":
                remember(config, operator, row, "use_source_name")
            elif choice == "a":
                for remaining in rows[index:]:
                    if remaining["status"] == "matched_name_difference":
                        remember(
                            config,
                            operator,
                            remaining,
                            "keep_reviewed_name",
                            save=False,
                        )
                save_config(config)
                print("Saved all pending name confirmations.")
                return 1 if pending_review_rows(operator) else 0
            elif choice == "q":
                return 1
            continue

        if row["status"] == "reviewed_only_retained":
            choice = input("[k]eep, [e]xclude, [d]efer, [q]uit: ").strip().lower()
            if choice == "k":
                remember(config, operator, row, "keep_reviewed_station")
            elif choice == "e":
                exclude_station(config, operator, row)
                remember(config, operator, row, "excluded")
            elif choice == "q":
                return 1
            continue

        choice = input("[c]onfirm, [d]efer, [q]uit: ").strip().lower()
        if choice == "c":
            remember(config, operator, row, "confirmed")
        elif choice == "q":
            return 1
    remaining = pending_review_rows(operator)
    if remaining:
        print(f"Check these {len(remaining)} station details for {operator.upper()}, then run "
              f"python3 -m gen.countries italy generate {operator} again.")
        return 1
    print(f"OK | italy/{operator} | all review decisions recorded")
    return 0


def review_after_generation(operator: str) -> int | None:
    if not sys.stdin.isatty() or os.environ.get("TRAINGUESSR_SKIP_REVIEW") == "1":
        return None
    return review_operator(operator)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review new Italian provider records")
    parser.add_argument("operator", choices=[*OPERATORS, "all"])
    args = parser.parse_args(argv)
    operators = OPERATORS if args.operator == "all" else (args.operator,)
    if not sys.stdin.isatty():
        print("Run this command in a terminal so you can choose what to keep.")
        return 2
    for operator in operators:
        if review_operator(operator):
            return 1
    return 0
