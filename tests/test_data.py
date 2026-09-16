from __future__ import annotations

import csv
import json
import tempfile
import zipfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson, logical_path  # noqa: E402
from common.config import load_country_config  # noqa: E402
from common.validate import validate_file  # noqa: E402
from austria import (  # noqa: E402
    load_geonetz_nodes,
    load_mvo_csv,
    load_mvo_snapshot,
    main as austria_main,
    merge_catalogues,
    mvo_rail_candidates,
    parse_scotty_suggestions,
    ScottyResolver,
    select_scotty_suggestion,
    validate_mvo_wgs84,
)
from finland import (  # noqa: E402
    build_nodes,
    load_reconciled_extant_stations,
    load_reviewed_stations,
    load_stations,
)
from france import convert_from_json  # noqa: E402
from reconcile.france import uic_stems  # noqa: E402
from germany import load_board_groups, load_reconciled_stations  # noqa: E402
from norway import build_nodes as build_norway_nodes, load_stop_places  # noqa: E402
from countries.italy.fse import MANUAL_STATIONS, apply_manual_stations  # noqa: E402
from countries.italy.legacy import rebuild  # noqa: E402
from countries.italy.review import load_review_rows, review_key, saved_review_keys  # noqa: E402
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

    def test_germany_reconciled_supplements_are_in_generated_nodes(self) -> None:
        reviewed = load_reconciled_stations()
        audit = json.loads(
            (ROOT / "docs" / "review" / "germany-reconciliation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1264, len(reviewed))
        self.assertEqual(1264, audit["counts"]["verified_additions"])
        self.assertEqual(6602, len(audit["outcomes"]))
        status_counts = {}
        for row in audit["outcomes"]:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        self.assertEqual(audit["counts"]["candidate_statuses"], status_counts)
        rows = load_ndjson(ROOT / "nodes" / "nodes-germany.json")
        by_id = {str(row["id"]): row for row in rows}
        for station in reviewed:
            station_id = str(station["id"])
            self.assertIn(station_id, by_id)
            self.assertEqual(
                station["source"],
                by_id[station_id]["tags"]["source"],
            )
        for station_id in ("8000092", "8002555", "8000271"):
            self.assertIn(station_id, by_id)


    def test_split_station_complex_audit_matches_current_nodes(self) -> None:
        audit = json.loads(
            (ROOT / "docs" / "review" / "global" / "station-complexes.json").read_text(
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

    def test_one_exclusion_override_file_per_country(self) -> None:
        expected = {
            "austria", "belgium", "denmark", "finland", "france", "germany",
            "italy", "netherlands", "norway", "spain", "sweden", "switzerland", "uk",
        }
        actual = {path.stem for path in (ROOT / "overrides" / "exclusions").glob("*.json")}
        self.assertEqual(expected, actual)
        for path in (ROOT / "overrides" / "exclusions").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("excluded", data)
            self.assertIn("renamed", data)

    def test_belgium_reviewed_physical_stations_are_in_generated_nodes(self) -> None:
        reviewed_ids = {
            "BE.NMBS.008811155", "BE.NMBS.008814472", "BE.NMBS.008821147",
            "BE.NMBS.008821337", "BE.NMBS.008822459", "BE.NMBS.008844644",
            "BE.NMBS.008863115", "BE.NMBS.008866258", "BE.NMBS.008881190",
            "BE.NMBS.008882339", "BE.NMBS.008893039", "BE.NMBS.008894821",
            "BE.NMBS.008895646", "BE.NMBS.008896412",
        }
        active_ids = {
            str(row["id"])
            for row in load_ndjson(ROOT / "nodes" / "nodes-belgium.json")
        }
        self.assertTrue(reviewed_ids.issubset(active_ids))
        self.assertNotIn("BE.NMBS.008869047", active_ids)

    def test_fse_manual_resolutions_are_in_the_output(self) -> None:
        rows = load_ndjson(ROOT / "nodes" / "nodes-italy-fse.json")
        self.assertEqual(92, len(rows))
        by_id = {str(row["id"]): row for row in rows}
        self.assertEqual(
            {"S13109", "S13111", "S13112", "S13114", "S13163", "S13164", "S13174"},
            {str(row["id"]) for row in MANUAL_STATIONS},
        )
        for station in MANUAL_STATIONS:
            self.assertEqual("manual_reviewed", by_id[str(station["id"])]["tags"]["match_status"])
        self.assertEqual(92, len(apply_manual_stations(rows)))
        saved = saved_review_keys(load_country_config("italy"))
        self.assertTrue(
            all(review_key("fse", row) in saved for row in load_review_rows("fse"))
        )

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
            "nodes-italy-fse.json": {"S13135", "S13183", "S13200"},
            "nodes-italy-fer.json": {"S05198", "S05321", "S05713", "S13199"},
            "nodes-italy-rfi.json": {"2378", "3619"},
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
        self.assertEqual("Napoli Afragola PES", rows["3611"]["tags"]["name"])
        self.assertEqual("italy_rfi", rows["3611"]["category"])

    def test_rfi_cross_border_reviews_are_not_new_coordinate_items(self) -> None:
        rfi_cache = ROOT / "cache" / "italy" / "rfi" / "raw"
        if not (rfi_cache / "stations-page.html").is_file() and not list((rfi_cache / "snapshots").glob("*.html")):
            self.skipTest("run the RFI generator to populate cache/italy/rfi")
        _, audit = rebuild("rfi", dry_run=True)
        audit_by_id = {str(row["id"]): row for row in audit}
        cross_border_ids = {"730", "1339", "1511", "2780", "2826", "3050"}

        for station_id in cross_border_ids:
            self.assertEqual(
                "handled_by_other_provider",
                audit_by_id[station_id]["status"],
                station_id,
            )

        review_ids = {row["id"] for row in load_review_rows("rfi")}
        self.assertTrue(cross_border_ids.isdisjoint(review_ids))


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

    def test_austria_mvo_keeps_rail_platform_without_eva_for_scotty_resolution(self) -> None:
        stops = [{
            "hst_id": "1", "hst_name": "Seekirchen Stadt S-Bahn", "hst_globid": "at:45:56408",
            "hst_x": "13.1200744", "hst_y": "47.8912034", "umst_agg_vm": "11000010000000",
        }]
        platforms = [{
            "hst_id": "1", "stg_globid": "at:45:56408:0:1", "extids_obb": "",
            "stg_x": "13.1201103", "stg_y": "47.8912757", "umst_vm": "11000000000000",
            "linien": "R21,S2",
        }]
        candidates = mvo_rail_candidates(stops, platforms)
        self.assertEqual(["Seekirchen Stadt S-Bahn"], [row["hst_name"] for row in candidates])
        self.assertNotIn("platform_eva_id", candidates[0])
        self.assertEqual(["R21", "S2"], candidates[0]["rail_lines"])

    def test_austria_mvo_reviewed_physical_station_can_use_nonrail_platforms(self) -> None:
        stops = [{
            "hst_id": "1", "hst_name": "Dellach im Gailtal Alter Bahnhof", "hst_globid": "at:42:3916",
            "hst_x": "13.081339", "hst_y": "46.6582926", "umst_agg_vm": "00000000000000",
        }]
        self.assertEqual(
            [{"hst_name": "Dellach im Gailtal Alter Bahnhof", "reviewed_rail_override": True}],
            [
                {
                    "hst_name": row["hst_name"],
                    "reviewed_rail_override": row["reviewed_rail_override"],
                }
                for row in mvo_rail_candidates(stops, [])
            ],
        )

    def test_austria_mvo_does_not_admit_reisach_nearby_bus_stop(self) -> None:
        stops = [{
            "hst_id": "7670", "hst_name": "Reisach (Kirchbach) Reisach im Gailtal",
            "hst_globid": "at:42:6171", "hst_x": "13.1551177", "hst_y": "46.6490558",
            "umst_agg_vm": "00000010000000",
        }]
        self.assertEqual([], mvo_rail_candidates(stops, []))

    def test_austria_mvo_reviewed_alias_and_scope_exclusion_are_guarded(self) -> None:
        geonetz = [{
            "type": "node", "id": 8100226, "lat": 47.9627, "lon": 16.4190,
            "tags": {"name": "Ebreichsdorf", "ifopt_id": "at:43:3326"},
            "category": "austria_oebb",
        }]
        stops = [
            {
                "hst_id": "9612", "hst_name": "Ebreichsdorf Bahnhof", "hst_globid": "at:43:3653",
                "hst_x": "16.4193169", "hst_y": "47.9641515", "umst_agg_vm": "11000010001000",
            },
            {
                "hst_id": "21672", "hst_name": "Gmunden Bezirkshauptmannschaft", "hst_globid": "at:44:46088",
                "hst_x": "13.7946193", "hst_y": "47.916159", "umst_agg_vm": "10000010000000",
            },
        ]
        platforms = [
            {
                "hst_id": "9612", "stg_globid": "at:43:3653:0:1", "extids_obb": "",
                "stg_x": "16.4192451", "stg_y": "47.9641816", "umst_vm": "10000000000000",
                "linien": "REX6",
            },
            {
                "hst_id": "21672", "stg_globid": "at:44:46088:0:1", "extids_obb": "0497276",
                "stg_x": "13.7946373", "stg_y": "47.9161831", "umst_vm": "10000010000000",
                "linien": "R 301",
            },
        ]

        class UnusedResolver:
            session = object()

            def resolve(self, row):
                raise AssertionError(f"unexpected provider lookup for {row['hst_globid']}")

        output, audit = merge_catalogues(geonetz, stops, platforms, UnusedResolver(), {})
        self.assertEqual([8100226], [row["id"] for row in output])
        self.assertEqual(1, audit["alias_count"])
        self.assertEqual(1, audit["excluded_count"])
        self.assertEqual(8100226, audit["aliases"][0]["canonical_id"])

        class FailingSession:
            def get(self, *args, **kwargs):
                raise AssertionError("reviewed provider ID should not query station search")

        with tempfile.TemporaryDirectory() as tmp:
            resolver = ScottyResolver(FailingSession(), Path(tmp) / "resolutions.json")
            resolution = resolver.resolve({
                "hst_globid": "at:45:54358",
                "hst_name": "Lengdorf (Niedernsill) Bahnhof",
                "hst_x": "12.6282647",
                "hst_y": "47.2815019",
                "rail_lon": "12.6282558",
                "rail_lat": "47.2814348",
            })
        self.assertIsNotNone(resolution)
        self.assertEqual(1250624, resolution["eva_id"])

    def test_austria_reviewed_mvo_resolutions_are_in_generated_output(self) -> None:
        config = json.loads((ROOT / "overrides" / "exclusions" / "austria.json").read_text(encoding="utf-8"))
        rows = {
            str(row["tags"].get("ifopt_id")): row
            for row in load_ndjson(ROOT / "nodes" / "nodes-austria-oebb.json")
        }
        for resolution in config["mvo_resolutions"]:
            row = rows[resolution["id"]]
            self.assertEqual(int(resolution["provider_id"]), row["id"])
            self.assertEqual("reviewed_provider_id", row["tags"].get("scotty_resolution"))

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

    def test_austria_offline_generation_uses_cached_resolution_without_network(self) -> None:
        class NetworkDisabledSession:
            def get(self, *args, **kwargs):
                raise AssertionError("offline Austria generation attempted a network request")

            def post(self, *args, **kwargs):
                raise AssertionError("offline Austria generation attempted a network request")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()
            (cache_dir / "austria_stations_filtered.json").write_text("", encoding="utf-8")
            resolution_cache = cache_dir / "scotty-resolutions.json"
            resolution_cache.write_text(
                json.dumps({
                    "version": 2,
                    "entries": {
                        "at:31:9991": {
                            "eva_id": 1234567,
                            "name": "Mariazell",
                            "lat": 47.7732,
                            "lon": 15.3167,
                            "method": "cached",
                        }
                    },
                }),
                encoding="utf-8",
            )
            mvo_zip = tmp_path / "mvo.zip"
            with zipfile.ZipFile(mvo_zip, "w") as archive:
                archive.writestr(
                    "2026/haltestellen.csv",
                    (ROOT / "tests" / "fixtures" / "austria-mvo-haltestellen.csv").read_text(encoding="utf-8"),
                )
                archive.writestr(
                    "2026/steige.csv",
                    "hst_id,stg_globid,extids_obb,stg_x,stg_y,umst_vm,linien\n"
                    "2,at:31:9991:0:1,,15.3167,47.7732,10000000000000,R56\n",
                )
            output = tmp_path / "nodes.json"
            audit = tmp_path / "audit.json"
            with patch("austria.requests.Session", return_value=NetworkDisabledSession()), \
                 patch("austria.CACHE_DIR", cache_dir), \
                 patch("austria.DEFAULT_RESOLUTION_CACHE", resolution_cache):
                self.assertEqual(
                    0,
                    austria_main([
                        "--offline",
                        "--mvo-input", str(mvo_zip),
                        "--output", str(output),
                        "--audit", str(audit),
                    ]),
                )
            rows = load_ndjson(output)
            self.assertEqual([1234567], [row["id"] for row in rows])
            self.assertEqual("offline_cached_resolution", rows[0]["tags"]["scotty_board_status"])

    def test_austria_online_resolution_still_verifies_scotty_board(self) -> None:
        class OnlineResolver:
            offline = False
            session = object()
            timeout = 20

            def resolve(self, row):
                return {
                    "eva_id": 1234567,
                    "name": row["hst_name"],
                    "method": "cached",
                }

        stops = [{
            "hst_id": "1",
            "hst_name": "Mariazell",
            "hst_globid": "at:31:9991",
            "hst_x": "15.3167",
            "hst_y": "47.7732",
        }]
        platforms = [{
            "hst_id": "1",
            "stg_globid": "at:31:9991:0:1",
            "extids_obb": "",
            "stg_x": "15.3167",
            "stg_y": "47.7732",
            "umst_vm": "10000000000000",
            "linien": "R56",
        }]
        with patch(
            "austria.verify_scotty_station",
            return_value={"station_name": "Mariazell", "journey_count": 1},
        ) as verify:
            resolver = OnlineResolver()
            output, _ = merge_catalogues([], stops, platforms, resolver, {})
        self.assertEqual([1234567], [row["id"] for row in output])
        verify.assert_called_once_with(resolver.session, 1234567, 20)

    def test_austria_existing_catalogue_rebuild_preserves_current_ids_and_names(self) -> None:
        source = ROOT / "cache" / "austria_stations_filtered.json"
        if not source.is_file():
            self.skipTest("GeoNetz cache not available")
        rebuilt = load_geonetz_nodes(source, {
            row["from"]: row["to"]
            for row in json.loads((ROOT / "overrides" / "exclusions" / "austria.json").read_text(encoding="utf-8"))["renamed"]
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

    def test_finland_reviewed_no_service_station_is_retained(self) -> None:
        reviewed = load_reviewed_stations()
        stations = [{
            "passengerTraffic": False,
            "type": "STATION",
            "stationName": "Pihtipudas",
            "stationShortCode": "PP",
            "stationUICCode": 258,
            "countryCode": "FI",
            "longitude": 25.556278,
            "latitude": 63.371806,
        }]
        nodes = build_nodes(stations, reviewed)
        self.assertEqual(["PP"], [node["id"] for node in nodes])
        self.assertEqual(
            "extant_no_current_passenger_traffic",
            nodes[0]["tags"]["station_status"],
        )

    def test_finland_reconciliation_covers_every_no_traffic_station(self) -> None:
        audit_path = ROOT / "docs" / "review" / "finland-reconciliation.json"
        if not audit_path.is_file():
            self.skipTest("Finland reconciliation has not been generated")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        outcomes = audit.get("outcomes", [])
        outcome_ids = [str(row["stationShortCode"]) for row in outcomes]
        self.assertEqual(299, audit["counts"]["candidate_records"])
        self.assertEqual(299, len(outcomes))
        self.assertEqual(299, len(set(outcome_ids)))
        self.assertEqual(299, sum(audit["counts"]["candidate_statuses"].values()))
        self.assertTrue(
            {
                "added_existing_provider",
                "dismantled_exclusion",
                "not_passenger_station",
                "provider_gap",
                "provider_verification_blocked_live_board",
                "unresolved",
            }.issuperset(audit["counts"]["candidate_statuses"])
        )
        self.assertTrue({"HYT", "IOA", "KOI", "LO", "PP", "UKP", "VI", "VKT"}.issubset(set(outcome_ids)))
        self.assertTrue(all(row.get("reason") and row.get("evidence") for row in outcomes))
        retained = load_reconciled_extant_stations()
        self.assertEqual(
            {str(row["stationShortCode"]) for row in audit["retained_extant_no_service"]},
            set(retained),
        )

    def test_france_configured_primary_uic_is_stable_when_source_order_changes(self) -> None:
        feature = [{
            "nom": "Paris Gare de Lyon",
            "codes_uic": "87686006;87686030",
            "position_geographique": {"lat": 48.844888, "lon": 2.37352},
            "libellecourt": "PLY",
            "segment_drg": "A;B",
            "codeinsee": "75112",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "france.json"
            output = Path(tmp) / "nodes.json"
            source.write_text(json.dumps(feature), encoding="utf-8")
            convert_from_json(
                source,
                output,
                {},
                {"Paris Gare de Lyon": "87686030"},
                set(),
                [],
            )
            rows = load_ndjson(output)
        self.assertEqual(87686030, rows[0]["id"])
        self.assertEqual(["87686006"], rows[0]["tags"]["further_ids"])

    def test_france_reconciliation_keeps_unmatched_provider_candidates_explicit(self) -> None:
        audit_path = ROOT / "docs" / "review" / "france-reconciliation.json"
        if not audit_path.is_file():
            self.skipTest("France reconciliation has not been generated")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(95, audit["counts"]["candidate_stems"])
        self.assertEqual(
            {
                "added_existing_provider": 61,
                "deferred_secondary_mode": 20,
                "new_provider_needed": 6,
                "provider_gap": 1,
                "unresolved": 7,
            },
            audit["counts"]["candidate_statuses"],
        )
        outcomes = audit["outcomes"]
        self.assertEqual(95, len(outcomes))
        self.assertEqual(95, len({row["uic_stem"] for row in outcomes}))
        self.assertTrue(all(not row["evidence"]["current_sncf_export_match"] for row in outcomes))
        self.assertTrue(all(row.get("reason") and row.get("evidence") for row in outcomes))
        self.assertEqual(51, audit["counts"]["candidate_official_passenger_records"])
        self.assertEqual(1, audit["counts"]["candidate_official_uic_correction_records"])
        self.assertEqual(11, audit["counts"]["candidate_historical_passenger_records"])
        self.assertEqual(9, audit["counts"]["candidate_historical_passenger_additions"])
        by_stem = {row["uic_stem"]: row for row in outcomes}
        for stem, station_id, stop_id in (
            ("8775808", 439, "IDFM:monomodalStopPlace:43237"),
            ("8775834", 597, "IDFM:monomodalStopPlace:58937"),
            ("8775870", 790, "IDFM:monomodalStopPlace:59206"),
            ("8775871", 287, "IDFM:monomodalStopPlace:43125"),
            ("8775883", 429, "IDFM:monomodalStopPlace:43232"),
            ("8775886", 401, "IDFM:monomodalStopPlace:47046"),
        ):
            self.assertEqual("deferred_secondary_mode", by_stem[stem]["status"])
            self.assertEqual(
                station_id,
                by_stem[stem]["evidence"]["official_idfm_rer"]["station_id"],
            )
            self.assertEqual(
                stop_id,
                by_stem[stem]["evidence"]["official_idfm_rer"]["stop_id"],
            )

    def test_france_official_infrastructure_supplements_are_in_generated_nodes(self) -> None:
        supplements = json.loads(
            (ROOT / "docs" / "review" / "france" / "liste-des-gares-supplement.json").read_text(
                encoding="utf-8"
            )
        )
        nodes = {
            str(row["id"]): row
            for row in load_ndjson(ROOT / "nodes" / "nodes-france-sncf.json")
        }
        self.assertEqual(61, len(supplements))
        self.assertTrue(
            all(
                str(row["sncf_id"]) in nodes
                and nodes[str(row["sncf_id"])]["tags"].get("source") == row["source"]
                for row in supplements
            )
        )
        self.assertIn("87561143", nodes)
        self.assertNotIn("87565143", nodes)

    def test_france_uic_parser_accepts_non_string_tag_values(self) -> None:
        self.assertEqual(
            {"8712345", "8770000"},
            uic_stems([87123456, {"uic": "87700001"}]),
        )

    def test_norway_fixture_keeps_active_rail_stop_places_only(self) -> None:
        stops = load_stop_places(ROOT / "tests" / "fixtures" / "norway-stop-places.json")
        nodes = build_norway_nodes(stops)
        self.assertEqual(1, len(nodes))
        self.assertEqual("NSR:StopPlace:59872", nodes[0]["id"])
        self.assertEqual("Oslo S", nodes[0]["tags"]["name"])
        self.assertEqual("norway_all", nodes[0]["category"])


    def test_reviewed_norway_cross_provider_ids_are_excluded(self) -> None:
        config = json.loads((ROOT / "overrides" / "exclusions" / "norway.json").read_text(encoding="utf-8"))
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
            ("nodes-italy-fer.json", "S05100"): (44.5151514, 11.2849781),
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

    def test_global_repository_layout_and_provider_identity_consistency(self) -> None:
        for legacy in ("sources", "excludes", "audits"):
            self.assertFalse((ROOT / legacy).exists(), f"legacy top-level tree still present: {legacy}")

        for required in ("cache", "docs", "gen", "nodes", "overrides", "tests"):
            path = ROOT / required
            if required == "cache":
                # cache is intentionally ignored and may not exist in a clean clone.
                continue
            self.assertTrue(path.exists(), required)

        provider_inventory = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        seen_full_ids: set[str] = set()
        categories: set[str] = set()
        for path in sorted((ROOT / "nodes").glob("nodes-*.json")):
            for row in load_ndjson(path):
                category = str(row["category"])
                station_id = str(row["id"])
                full_id = f"{category}:{station_id}"
                self.assertNotIn(full_id, seen_full_ids, full_id)
                seen_full_ids.add(full_id)
                categories.add(category)
                self.assertIn(f"`{category}`", provider_inventory)

        self.assertGreater(len(seen_full_ids), 1_000)
        self.assertTrue(categories)

    def test_reconciliation_evidence_uses_machine_independent_paths(self) -> None:
        audits = (
            ROOT / "docs" / "review" / "finland-reconciliation.json",
            ROOT / "docs" / "review" / "france-reconciliation.json",
            ROOT / "docs" / "review" / "germany-reconciliation.json",
        )
        for path in audits:
            payload = json.loads(path.read_text(encoding="utf-8"))
            source_files = payload.get("source_files", {})
            values = source_files.values()
            for value in values:
                paths = value if isinstance(value, list) else [value]
                for source_path in paths:
                    self.assertFalse(str(source_path).startswith("/"), (path, source_path))
                    self.assertNotIn("/tmp/", str(source_path), (path, source_path))

        self.assertEqual(
            "cache/france/audit/example.json",
            logical_path(ROOT / "cache" / "france" / "audit" / "example.json"),
        )
        self.assertEqual("external/example.json", logical_path("/tmp/example.json"))

    def test_country_documentation_and_public_entrypoints_are_complete(self) -> None:
        expected = {
            "austria": "austria.py",
            "belgium": "belgium.py",
            "denmark": "denmark.py",
            "finland": "finland.py",
            "france": "france.py",
            "germany": "germany.py",
            "italy": "italy.py",
            "netherlands": "netherlands.py",
            "norway": "norway.py",
            "spain": "spain.py",
            "sweden": "sweden.py",
            "switzerland": "switzerland.py",
            "uk": "uk.py",
        }
        for country, entrypoint in expected.items():
            doc = ROOT / "docs" / f"{country}.md"
            self.assertTrue(doc.is_file(), country)
            content = doc.read_text(encoding="utf-8")
            self.assertIn("## Current providers", content, country)
            self.assertIn("## Other providers", content, country)
            self.assertTrue((ROOT / "gen" / entrypoint).is_file(), country)

        self.assertTrue((ROOT / "docs" / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
