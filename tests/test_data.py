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
    _feature_type_from_capabilities,
    download_mvo_wfs,
    load_geonetz_nodes,
    load_mvo_csv,
    merge_catalogues,
    mvo_rail_candidates,
    parse_scotty_suggestions,
    ScottyResolver,
    select_scotty_suggestion,
    validate_mvo_wgs84,
)
from finland import build_nodes, load_stations  # noqa: E402
from norway import build_nodes as build_norway_nodes, load_stop_places  # noqa: E402
from italy_fse import MANUAL_STATIONS, apply_manual_stations  # noqa: E402
from italy_legacy import rebuild  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_all_node_files_are_valid(self) -> None:
        for path in sorted((ROOT / "nodes").glob("nodes-*.json")):
            self.assertEqual([], validate_file(path), path.name)

    def test_one_exclude_file_per_country(self) -> None:
        expected = {
            "austria", "belgium", "finland", "france", "germany",
            "italy", "netherlands", "norway", "sweden", "switzerland", "uk",
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


    def test_austria_mvo_filters_to_austrian_rail_and_sbahn_stops(self) -> None:
        rows = load_mvo_csv(ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv")
        candidates = mvo_rail_candidates(rows)
        self.assertEqual({"Bregenz", "Mariazell", "Tschagguns"}, {row["hst_name"] for row in candidates})

    def test_austria_mvo_offline_input_requires_wgs84_coordinates(self) -> None:
        rows = load_mvo_csv(ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv")
        validate_mvo_wgs84(rows)
        projected = [
            {"hst_x": "600000", "hst_y": "480000", "hst_name": "Projected one"},
            {"hst_x": "610000", "hst_y": "490000", "hst_name": "Projected two"},
        ]
        with self.assertRaisesRegex(ValueError, "WGS84"):
            validate_mvo_wgs84(projected)

    def test_austria_mvo_zip_input_finds_haltestellen_csv(self) -> None:
        fixture = (ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "mvo.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("2026/haltestellen.csv", fixture)
                handle.writestr("2026/steige.csv", b"ignored")
            rows = load_mvo_csv(archive)
        self.assertEqual(5, len(rows))
        self.assertEqual("Bregenz", rows[0]["hst_name"])

    def test_austria_wfs_feature_type_discovery_prefers_haltestellen(self) -> None:
        xml = """<?xml version="1.0"?><WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0"><FeatureTypeList><FeatureType><Name>pub:steige</Name><Title>Steige</Title></FeatureType><FeatureType><Name>pub:haltestellen_2026</Name><Title>Haltestellen</Title></FeatureType></FeatureTypeList></WFS_Capabilities>"""
        self.assertEqual("pub:haltestellen_2026", _feature_type_from_capabilities(xml))

    def test_austria_wfs_paginates_and_uses_requested_wgs84_geometry(self) -> None:
        capabilities = """<?xml version="1.0"?><WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0"><FeatureTypeList><FeatureType><Name>pub:haltestellen</Name><Title>Haltestellen</Title></FeatureType></FeatureTypeList></WFS_Capabilities>"""

        class Response:
            def __init__(self, *, text="", payload=None):
                self.text = text
                self._payload = payload
            def raise_for_status(self):
                return None
            def json(self):
                return self._payload

        class Session:
            def __init__(self):
                self.calls = []
            def get(self, url, params, timeout):
                self.calls.append(dict(params))
                if params["request"] == "GetCapabilities":
                    return Response(text=capabilities)
                start = params["startIndex"]
                if start == 0:
                    return Response(payload={
                        "numberMatched": 2, "features": [{
                            "properties": {"hst_name": "One", "hst_x": 999, "hst_y": 999},
                            "geometry": {"coordinates": [14.0, 47.0]},
                        }]
                    })
                return Response(payload={
                    "numberMatched": 2, "features": [{
                        "properties": {"hst_name": "Two"},
                        "geometry": {"coordinates": [15.0, 48.0]},
                    }]
                })

        # A first page shorter than the server-advertised total must still be followed.
        session = Session()
        rows = download_mvo_wfs(session)
        self.assertEqual(["One", "Two"], [row["hst_name"] for row in rows])
        self.assertEqual((14.0, 47.0), (rows[0]["hst_x"], rows[0]["hst_y"]))
        self.assertEqual(3, len(session.calls))
        self.assertEqual("EPSG:4326", session.calls[1]["srsName"])
        self.assertEqual(1, session.calls[2]["startIndex"])

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

    def test_austria_merge_preserves_existing_nodes_and_adds_only_resolved_gaps(self) -> None:
        old_nodes = load_ndjson(ROOT / "nodes" / "nodes-austria-oebb.json")
        mvo = load_mvo_csv(ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv")

        class FixtureResolver:
            def resolve(self, row):
                if row["hst_name"] == "Mariazell":
                    return {"eva_id": 1234567, "name": "Mariazell", "distance_m": 0.0, "similarity": 1.0}
                return None

        merged, audit = merge_catalogues(old_nodes, mvo, FixtureResolver(), {})
        self.assertEqual(old_nodes, merged[:len(old_nodes)])
        self.assertEqual(len(old_nodes) + 1, len(merged))
        self.assertEqual("Mariazell", merged[-1]["tags"]["name"])
        self.assertEqual("at:31:9991", merged[-1]["tags"]["ifopt_id"])
        self.assertEqual(1, audit["added_count"])
        self.assertEqual(1, audit["matched_existing_ifopt"])
        self.assertEqual(1, audit["unresolved_count"])

    def test_austria_merge_does_not_duplicate_existing_eva_from_new_ifopt(self) -> None:
        old_nodes = load_ndjson(ROOT / "nodes" / "nodes-austria-oebb.json")
        existing_eva = int(old_nodes[0]["id"])
        row = {
            "hst_id": "900", "hst_name": "Synthetic alias", "hst_globid": "at:99:999",
            "hst_x": "16.370", "hst_y": "48.210", "hst_gem_name": "Wien",
            "umst_agg_vm": "10000000000000",
        }
        class ExistingResolver:
            def resolve(self, item):
                return {"eva_id": existing_eva, "name": item["hst_name"], "distance_m": 1.0, "similarity": 1.0}
        merged, audit = merge_catalogues(old_nodes, [row], ExistingResolver(), {})
        self.assertEqual(old_nodes, merged)
        self.assertEqual(1, audit["resolved_to_existing_eva"])
        self.assertEqual(0, audit["added_count"])

    def test_austria_existing_catalogue_rebuild_preserves_current_ids_and_names(self) -> None:
        source = ROOT / "cache" / "austria_stations_filtered.json"
        if not source.is_file():
            self.skipTest("GeoNetz cache not available")
        rebuilt = load_geonetz_nodes(source, {
            row["from"]: row["to"]
            for row in json.loads((ROOT / "excludes" / "austria.json").read_text(encoding="utf-8"))["renamed"]
        })
        current = load_ndjson(ROOT / "nodes" / "nodes-austria-oebb.json")
        self.assertEqual(
            [(str(row["id"]), row["tags"]["name"]) for row in current],
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


if __name__ == "__main__":
    unittest.main()
