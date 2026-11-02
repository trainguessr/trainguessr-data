"""Country generation CLI orchestration for Germany."""
from __future__ import annotations

import os
import sys
import argparse
from common.config import load_rename_map
from common.io import ROOT, add_cache_flag
from countries.germany.decisions import load_board_groups, load_reconciled_stations
from countries.germany.nodes import convert_from_json
from countries.germany.sources import ensure_station_cache


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Generate German DB stations")
    add_cache_flag(parser)
    args = parser.parse_args(argv)

    input_file = ensure_station_cache(use_cache=args.cache)
    output_file = os.path.join(ROOT, "nodes", "nodes-germany.json")

    print("Loading rename mapping...")
    rename_map = load_rename_map("germany")
    print(f"Loaded {len(rename_map)} rename rules")

    board_groups = load_board_groups()
    print(f"Loaded {len(board_groups)} reviewed multi-EVA board groups")
    reconciled_stations = load_reconciled_stations()
    print(f"Loaded {len(reconciled_stations)} reviewed Germany station additions")
    convert_from_json(input_file, output_file, rename_map, board_groups, reconciled_stations)
    print(f"Conversion complete. Output written to {output_file}")
    return 0
