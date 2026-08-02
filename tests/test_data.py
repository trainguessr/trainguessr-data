from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson  # noqa: E402
from common.validate import validate_file  # noqa: E402
from finland import build_nodes, load_stations  # noqa: E402
from italy_fse import MANUAL_STATIONS, apply_manual_stations  # noqa: E402
from italy_legacy import rebuild  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_all_node_files_are_valid(self) -> None:
        for path in sorted((ROOT / "nodes").glob("nodes-*.json")):
            self.assertEqual([], validate_file(path), path.name)

    def test_one_exclude_file_per_country(self) -> None:
        expected = {
            "austria", "belgium", "finland", "france", "germany",
            "italy", "netherlands", "sweden", "switzerland", "uk",
        }
        actual = {path.stem for path in (ROOT / "excludes").glob("*.json")}
        self.assertEqual(expected, actual)
        for path in (ROOT / "excludes").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("excluded", data)
            self.assertIn("renamed", data)

    def test_fse_manual_resolutions_are_in_the_output(self) -> None:
        rows = load_ndjson(ROOT / "nodes" / "nodes-italy-fse.json")
        self.assertEqual(91, len(rows))
        by_id = {str(row["id"]): row for row in rows}
        self.assertEqual(
            {"S13109", "S13111", "S13112", "S13114", "S13163", "S13164"},
            {str(row["id"]) for row in MANUAL_STATIONS},
        )
        for station in MANUAL_STATIONS:
            self.assertEqual("manual_reviewed", by_id[str(station["id"])]["tags"]["match_status"])
        self.assertEqual(91, len(apply_manual_stations(rows)))

    def test_sweden_contains_only_swedish_ids(self) -> None:
        rows = load_ndjson(ROOT / "nodes" / "nodes-sweden.json")
        self.assertEqual(850, len(rows))
        self.assertTrue(all(str(row["id"]).startswith("740") for row in rows))

    def test_legacy_parsers_rebuild_active_json(self) -> None:
        required_cache = [
            ROOT / "cache" / "italy" / "fn" / "derived" / "stations.csv",
            ROOT / "cache" / "italy" / "tt" / "raw" / "legacy-station-map.html",
            ROOT / "cache" / "italy" / "fer" / "derived" / "stations.csv",
            ROOT / "cache" / "italy" / "eav" / "derived" / "stations.csv",
            ROOT / "cache" / "italy" / "rfi" / "raw" / "stations-page.html",
        ]
        if not all(path.is_file() for path in required_cache):
            self.skipTest("run the Italian provider generators to populate cache/italy")

        for operator in ("fn", "tt", "fer", "eav", "rfi"):
            current = load_ndjson(ROOT / "nodes" / f"nodes-italy-{operator}.json")
            output, _ = rebuild(operator, dry_run=True)
            self.assertEqual(
                {str(row["id"]) for row in current},
                {str(row["id"]) for row in output},
                operator,
            )

    def test_rfi_laveno_is_not_misclassified_as_fn(self) -> None:
        rows = {str(row["id"]): row for row in load_ndjson(ROOT / "nodes" / "nodes-italy-rfi.json")}
        self.assertEqual("italy_rfi", rows["1542"]["category"])
        self.assertEqual("RFI", rows["1542"]["tags"]["operator"])

    def test_finland_fixture_filters_non_playable_stations(self) -> None:
        stations = load_stations(ROOT / "tests" / "fixtures" / "finland-stations.json")
        nodes = build_nodes(stations)
        self.assertEqual(1, len(nodes))
        self.assertEqual("HKI", nodes[0]["id"])
        self.assertEqual("finland_all", nodes[0]["category"])


if __name__ == "__main__":
    unittest.main()
