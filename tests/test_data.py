from __future__ import annotations

import csv
import json
import tempfile
import zipfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson  # noqa: E402
from common.validate import validate_file  # noqa: E402
from austria import (  # noqa: E402
    load_geonetz_nodes,
    load_mvo_csv,
    load_mvo_snapshot,
    mvo_rail_candidates,
    parse_scotty_suggestions,
    ScottyResolver,
    select_scotty_suggestion,
    validate_mvo_wgs84,
)
from finland import build_nodes, load_stations  # noqa: E402
from germany import load_board_groups  # noqa: E402
from norway import build_nodes as build_norway_nodes, load_stop_places  # noqa: E402
from italy_fse import MANUAL_STATIONS, apply_manual_stations  # noqa: E402
from italy_legacy import rebuild  # noqa: E402
from common.manual_overrides import apply_coordinate_overrides  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_all_node_files_are_valid(self) -> None:
        for path in sorted((ROOT / "nodes").glob("nodes-*.json")):
            self.assertEqual([], validate_file(path), path.name)


    def test_germany_reviewed_board_groups_are_in_generated_nodes(self) -> None:
        groups = load_board_groups()
        self.assertGreaterEqual(len(groups), 10)
        rows = load_ndjson(ROOT / "nodes" / "nodes-germany.json")
        by_id = {str(row["id"]): row for row in rows}
        for station_id, group in groups.items():
            self.assertIn(station_id, by_id)
            self.assertEqual(
                group["provider_ids"],
                by_id[station_id]["tags"].get("provider_place_ids"),
                station_id,
            )
        self.assertEqual(
            ["8011160", "8098160", "8089021"],
            by_id["8011160"]["tags"]["provider_place_ids"],
        )
        self.assertEqual(
            ["8000261", "8098261", "8098262", "8098263"],
            by_id["8000261"]["tags"]["provider_place_ids"],
        )


    def test_split_station_complex_audit_matches_current_nodes(self) -> None:
        audit = json.loads(
            (ROOT / "audits" / "europe-split-station-complexes-2026.json").read_text(
                encoding="utf-8"
            )
        )
        for group in audit["merge_via_provider_aliases"]:
            category = group["category"]
            self.assertEqual("germany_all", category)
            rows = load_ndjson(ROOT / "nodes" / "nodes-germany.json")
            by_id = {str(row["id"]): row for row in rows}
            node = by_id[group["canonical_id"]]
            self.assertEqual(
                group["provider_ids"],
                node["tags"]["provider_place_ids"],
            )

        filename_by_category = {
            "italy_rfi": "nodes-italy-rfi.json",
            "spain_renfe": "nodes-spain-renfe.json",
            "switzerland_all": "nodes-switzerland.json",
            "france_sncf": "nodes-france-sncf.json",
        }
        for group in audit["keep_separate_examples"]:
            rows = load_ndjson(ROOT / "nodes" / filename_by_category[group["category"]])
            ids = {str(row["id"]) for row in rows}
            expected = {str(station["id"]) for station in group["stations"]}
            self.assertTrue(expected.issubset(ids), group)
            self.assertEqual(len(expected), len(group["stations"]))

    def test_one_exclude_file_per_country(self) -> None:
        expected = {
            "austria", "belgium", "finland", "france", "germany",
            "italy", "netherlands", "norway", "spain", "sweden", "switzerland", "uk",
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
        self.assertTrue(all(str(row["id"]).startswith("740") for row in rows))
        names = [str(row["tags"]["name"]) for row in rows]
        self.assertEqual(len(names), len(set(names)))

    def test_reviewed_non_station_records_are_excluded(self) -> None:
        expected_absent = {
            "nodes-sweden.json": {
                "740000622", "740001552", "740011647", "740012918",
                "740013971", "740015886", "740020483", "740020490",
                "740032989", "740053481", "740055861", "740062322",
                "740069608", "740073734",
            },
            "nodes-italy-eav.json": {"101", "102"},
            "nodes-italy-rfi.json": {"2378"},
        }
        for filename, excluded_ids in expected_absent.items():
            rows = load_ndjson(ROOT / "nodes" / filename)
            active_ids = {str(row["id"]) for row in rows}
            self.assertTrue(excluded_ids.isdisjoint(active_ids), filename)

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


    def test_austria_mvo_requires_physical_non_replacement_rail_platform(self) -> None:
        stops = [
            {"hst_id": "1", "hst_name": "Mariazell (Stmk) Bahnhof", "hst_globid": "at:46:6625", "hst_x": "15.3078", "hst_y": "47.7832", "umst_agg_vm": "10000000000000"},
            {"hst_id": "2", "hst_name": "Übelbach Am Steinbühel", "hst_globid": "at:46:30055", "hst_x": "15.25", "hst_y": "47.22", "umst_agg_vm": "10000000000000"},
        ]
        platforms = [
            {"hst_id": "1", "stg_globid": "at:46:6625:0:2", "extids_obb": "1260202", "stg_x": "15.3075", "stg_y": "47.7833", "umst_vm": "10000000000000", "linien": "R56,REX56"},
            {"hst_id": "2", "stg_globid": "at:46:30055:0:3", "extids_obb": "0696895", "stg_x": "15.25", "stg_y": "47.22", "umst_vm": "10000000000000", "linien": "SEV"},
        ]
        candidates = mvo_rail_candidates(stops, platforms)
        self.assertEqual(["Mariazell (Stmk) Bahnhof"], [row["hst_name"] for row in candidates])
        self.assertEqual(1260202, candidates[0]["platform_eva_id"])

    def test_austria_mvo_offline_input_requires_wgs84_coordinates(self) -> None:
        rows = load_mvo_csv(ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv")
        validate_mvo_wgs84(rows)
        projected = [
            {"hst_x": "600000", "hst_y": "480000", "hst_name": "Projected one"},
            {"hst_x": "610000", "hst_y": "490000", "hst_name": "Projected two"},
        ]
        with self.assertRaisesRegex(ValueError, "WGS84"):
            validate_mvo_wgs84(projected)

    def test_austria_mvo_zip_input_requires_stops_and_platforms(self) -> None:
        fixture = (ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv").read_bytes()
        platforms = b"hst_id,stg_globid,extids_obb,stg_x,stg_y,umst_vm,linien\n1,at:48:452:0:1,8100090,9.7,47.5,10000000000000,S1\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "mvo.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("2026/haltestellen.csv", fixture)
                handle.writestr("2026/steige.csv", platforms)
            rows, platform_rows = load_mvo_snapshot(archive)
        self.assertEqual(5, len(rows))
        self.assertEqual(1, len(platform_rows))

    def test_austria_scotty_suggestion_selection_uses_name_and_coordinates(self) -> None:
        suggestions = parse_scotty_suggestions(
            (ROOT / "tests" / "fixtures" / "austria-scotty-suggestions.js").read_text(encoding="utf-8")
        )
        match = select_scotty_suggestion(
            suggestions, name="Mariazell", lat=47.7732, lon=15.3167
        )
        self.assertIsNotNone(match)
        self.assertEqual(1234567, match["eva_id"])
        self.assertLess(match["distance_m"], 10)

    def test_austria_scotty_suggestion_rejects_ambiguous_or_distant_matches(self) -> None:
        ambiguous = [
            {"type": "1", "value": "Testdorf", "id": "A=1@L=111@", "xcoord": 14000000, "ycoord": 47000000},
            {"type": "1", "value": "Testdorf Bahnhof", "id": "A=1@L=222@", "xcoord": 14000100, "ycoord": 47000100},
        ]
        self.assertIsNone(select_scotty_suggestion(ambiguous, name="Testdorf", lat=47.00005, lon=14.00005))
        distant = [
            {"type": "1", "value": "Mariazell", "id": "A=1@L=333@", "xcoord": 16000000, "ycoord": 48000000},
        ]
        self.assertIsNone(select_scotty_suggestion(distant, name="Mariazell", lat=47.7732, lon=15.3167))

    def test_austria_scotty_resolution_failure_does_not_abort_migration(self) -> None:
        class FailingSession:
            def get(self, *args, **kwargs):
                import requests
                raise requests.Timeout("temporary outage")

        row = {
            "hst_globid": "at:31:9991",
            "hst_name": "Mariazell",
            "hst_x": "15.3167",
            "hst_y": "47.7732",
        }
        with tempfile.TemporaryDirectory() as tmp:
            resolver = ScottyResolver(FailingSession(), Path(tmp) / "resolutions.json")
            self.assertIsNone(resolver.resolve(row))
            self.assertFalse((Path(tmp) / "resolutions.json").exists())

    def test_austria_existing_catalogue_rebuild_preserves_current_ids_and_names(self) -> None:
        source = ROOT / "cache" / "austria_stations_filtered.json"
        if not source.is_file():
            self.skipTest("GeoNetz cache not available")
        rebuilt = load_geonetz_nodes(source, {
            row["from"]: row["to"]
            for row in json.loads((ROOT / "excludes" / "austria.json").read_text(encoding="utf-8"))["renamed"]
        })
        current = load_ndjson(ROOT / "nodes" / "nodes-austria-oebb.json")
        self.assertGreaterEqual(len(current), len(rebuilt))
        self.assertEqual(
            [(str(row["id"]), row["tags"]["name"]) for row in current[:len(rebuilt)]],
            [(str(row["id"]), row["tags"]["name"]) for row in rebuilt],
        )

    def test_finland_fixture_filters_non_playable_stations(self) -> None:
        stations = load_stations(ROOT / "tests" / "fixtures" / "finland-stations.json")
        nodes = build_nodes(stations)
        self.assertEqual(1, len(nodes))
        self.assertEqual("HKI", nodes[0]["id"])
        self.assertEqual("finland_all", nodes[0]["category"])

    def test_norway_fixture_keeps_active_rail_stop_places_only(self) -> None:
        stops = load_stop_places(ROOT / "tests" / "fixtures" / "norway-stop-places.json")
        nodes = build_norway_nodes(stops)
        self.assertEqual(1, len(nodes))
        self.assertEqual("NSR:StopPlace:59872", nodes[0]["id"])
        self.assertEqual("Oslo S", nodes[0]["tags"]["name"])
        self.assertEqual("norway_all", nodes[0]["category"])


    def test_reviewed_norway_cross_provider_ids_are_excluded(self) -> None:
        config = json.loads((ROOT / "excludes" / "norway.json").read_text(encoding="utf-8"))
        excluded = {str(row["id"]) for row in config["excluded"]}
        active = {
            str(row["id"])
            for row in load_ndjson(ROOT / "nodes" / "nodes-norway.json")
        }
        self.assertGreaterEqual(len(excluded), 154)
        self.assertTrue(excluded.isdisjoint(active))

    def test_spain_vallecas_feed_alias_is_not_a_second_playable_station(self) -> None:
        rows = {
            str(row["id"]): row
            for row in load_ndjson(ROOT / "nodes" / "nodes-spain-renfe.json")
        }
        self.assertNotIn("70001", rows)
        self.assertIn("70005", rows)
        self.assertIn("70001", rows["70005"]["tags"]["stop_ids"])
        self.assertIn("70001", rows["70005"]["tags"]["renfe_alias_ids"])

    def test_reviewed_coordinate_corrections_are_present(self) -> None:
        expected = {
            ("nodes-italy-fer.json", "S05995"): (44.50343, 11.47214),
            ("nodes-italy-fer.json", "S05931"): (44.699327, 10.523291),
            ("nodes-italy-fer.json", "S05971"): (44.49252, 11.21811),
            ("nodes-italy-eav.json", "32"): (40.80206, 14.36150),
            ("nodes-italy-eav.json", "62"): (40.62585, 14.37979),
            ("nodes-italy-eav.json", "41"): (40.75970, 14.45100),
            ("nodes-spain-renfe.json", "23021"): (42.7812443, -8.656552),
            ("nodes-spain-renfe.json", "05403"): (43.527123, -5.690694),
        }
        for (filename, station_id), coordinates in expected.items():
            rows = {
                str(row["id"]): row
                for row in load_ndjson(ROOT / "nodes" / filename)
            }
            self.assertEqual(coordinates, (rows[station_id]["lat"], rows[station_id]["lon"]))
            self.assertTrue(rows[station_id]["tags"].get("coordinate_override"))

    def test_guarded_coordinate_override_fails_when_station_name_changes(self) -> None:
        rows = [{
            "type": "node", "id": "X", "lat": 1.0, "lon": 2.0,
            "tags": {"name": "Renamed station"}, "category": "test",
        }]
        with self.assertRaisesRegex(ValueError, "stale coordinate override"):
            apply_coordinate_overrides(
                rows,
                [{"id": "X", "expected_name": "Old station", "lat": 3.0, "lon": 4.0}],
                context="test",
            )

    def test_museum_railway_stops_remain_playable(self) -> None:
        rows = {
            str(row["id"]): row
            for row in load_ndjson(ROOT / "nodes" / "nodes-norway.json")
        }
        for station_id in {
            "NSR:StopPlace:57940",
            "NSR:StopPlace:57941",
            "NSR:StopPlace:57942",
        }:
            self.assertIn(station_id, rows)
            self.assertEqual("tourist_railway", rows[station_id]["tags"].get("rail_submode"))



if __name__ == "__main__":
    unittest.main()
