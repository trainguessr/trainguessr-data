"""Interactive provider review for Italian providers."""
from __future__ import annotations

import argparse
import os
import sys
from common.config import load_country_config, load_excluded_ids
from reconcile.italy.decisions import remember, review_key, save_config, saved_review_keys
from reconcile.italy.nodes import add_coordinates, exclude_station, load_review_rows, update_node_name
from reconcile.italy.settings import OPERATORS


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


def review_operator(operator: str) -> int:
    config = load_country_config("italy")
    saved = saved_review_keys(config)
    rows = [
        row for row in load_review_rows(operator)
        if review_key(operator, row) not in saved
    ]
    excluded = load_excluded_ids("italy", operator)
    rows = [row for row in rows if row["id"] not in excluded]
    if not rows:
        print(f"{operator.upper()}: no new review items")
        return 0

    priority = {
        "missing_coordinates": 0,
        "manual_reviewed": 1,
        "reviewed_only_retained": 2,
        "gtfs_name_missing": 3,
        "matched_name_difference": 4,
    }
    rows.sort(key=lambda row: (priority[row["status"]], row["id"]))
    print(f"{operator.upper()}: {len(rows)} new review items")

    for index, row in enumerate(rows):
        name = row["source_name"] or row["reviewed_name"]
        print(f"\n[{row['status']}] {row['id']} {name}")
        if row["source_name"] and row["reviewed_name"] and row["source_name"] != row["reviewed_name"]:
            print(f"Source:   {row['source_name']}")
            print(f"Reviewed: {row['reviewed_name']}")
        if row["details"]:
            print(row["details"])

        if row["status"] == "missing_coordinates":
            choice = input("[c]oordinates, [e]xclude, [d]efer, [q]uit: ").strip().lower()
            if choice == "c":
                coordinates = prompt_coordinates()
                if coordinates is not None:
                    add_coordinates(config, operator, row, *coordinates)
                    remember(config, operator, row, "added_coordinates")
            elif choice == "e":
                exclude_station(config, operator, row)
                remember(config, operator, row, "excluded")
            elif choice == "q":
                return 1
            continue

        if row["status"] == "matched_name_difference":
            choice = input("[k]eep reviewed, use [s]ource, keep [a]ll names, [d]efer, [q]uit: ").strip().lower()
            if choice == "k":
                remember(config, operator, row, "keep_reviewed_name")
            elif choice == "s":
                update_node_name(operator, row["id"], row["source_name"])
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
                return 0
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
    return 0


def review_after_generation(operator: str) -> None:
    if not sys.stdin.isatty() or os.environ.get("TRAINGUESSR_SKIP_REVIEW") == "1":
        return
    review_operator(operator)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review new Italian provider records")
    parser.add_argument("operator", choices=[*OPERATORS, "all"])
    args = parser.parse_args(argv)
    operators = OPERATORS if args.operator == "all" else (args.operator,)
    for operator in operators:
        if review_operator(operator):
            return 1
    return 0
