from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from denmark import (
    build_nodes as build_denmark_nodes,
    download_gtfs,
    validate_live_access,
)
from spain import (
    _apply_station_corrections, _clean_row, _download_official_feed,
    build as build_spain, load_feed, write_index
)


def write_gtfs(path: Path, tables: dict[str, list[dict[str, str]]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for filename, rows in tables.items():
            if not rows:
                continue
            fieldnames = list(rows[0])
            import io
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(filename, stream.getvalue())


class NewCountryGeneratorTests(unittest.TestCase):
    def test_denmark_normalizes_zero_padded_rejseplanen_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dk.zip"
            write_gtfs(path, {
                "stops.txt": [{
                    "stop_id": "000008600001", "stop_name": "Rail",
                    "stop_lat": "55", "stop_lon": "12", "parent_station": "",
                }],
                "routes.txt": [{"route_id": "r", "route_type": "2"}],
                "trips.txt": [{"route_id": "r", "trip_id": "tr"}],
                "stop_times.txt": [{"trip_id": "tr", "stop_id": "000008600001"}],
            })
            nodes = build_denmark_nodes(path)
        self.assertEqual(["8600001"], [node["id"] for node in nodes])

    def test_denmark_download_is_written_under_cache(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("stops.txt", "stop_id,stop_name\n8600001,Rail\n")
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [archive_bytes.getvalue()]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        session = Mock()
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache" / "denmark"
            archive_path = cache_dir / "rejseplanen-gtfs.zip"
            with patch("denmark.CACHE_DIR", cache_dir), patch("denmark.GTFS_ARCHIVE", archive_path):
                result = download_gtfs(session=session)
            self.assertEqual(archive_path, result)
            self.assertTrue(archive_path.is_file())
        self.assertEqual("https://www.rejseplanen.info/labs/GTFS.zip", session.get.call_args.args[0])

    def test_denmark_live_validation_checks_both_board_directions(self):
        departure = Mock()
        departure.raise_for_status.return_value = None
        departure.json.return_value = {"Departure": []}
        arrival = Mock()
        arrival.raise_for_status.return_value = None
        arrival.json.return_value = {"Arrival": []}
        session = Mock()
        session.get.side_effect = [departure, arrival]
        with patch.dict(os.environ, {"REJSEPLANEN_API_KEY": "test-key"}):
            validate_live_access("8600001", session=session)
        self.assertEqual(2, session.get.call_count)
        self.assertEqual(
            "test-key",
            session.get.call_args_list[0].kwargs["params"]["accessId"],
        )
        self.assertIn("arrivalBoard", session.get.call_args_list[1].args[0])

    def test_spain_downloads_and_extracts_official_gtfs_into_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_bytes = __import__("io").BytesIO()
            with zipfile.ZipFile(archive_bytes, "w") as archive:
                archive.writestr("stops.txt", "stop_id,stop_name\\nA,Alpha\\n")
            metadata = Mock()
            metadata.raise_for_status.return_value = None
            metadata.json.return_value = {"success": True, "result": {"url": "https://example.test/gtfs.zip"}}
            download = Mock()
            download.raise_for_status.return_value = None
            download.iter_content.return_value = [archive_bytes.getvalue()]
            download.__enter__ = Mock(return_value=download)
            download.__exit__ = Mock(return_value=False)
            session = Mock()
            session.get.side_effect = [metadata, download]
            with patch("spain.CACHE_ROOT", Path(tmp)):
                result = _download_official_feed("cercanias", session=session)
                self.assertEqual(Path(tmp) / "cercanias" / "gtfs.zip", result)
                self.assertTrue((Path(tmp) / "cercanias" / "gtfs" / "stops.txt").is_file())
            self.assertEqual(2, session.get.call_count)

    def test_spain_strips_padded_renfe_headers_and_values(self):
        self.assertEqual(
            {"end_date": "20260817", "exception_type": "2"},
            _clean_row({"end_date   ": "20260817   ", "exception_type ": "2 "}),
        )

    def test_spain_guarded_alias_merges_stop_ids_and_requires_explicit_exclusion(self):
        nodes = {
            "A": {
                "type": "node", "id": "A", "lat": 40.0, "lon": -3.0,
                "tags": {"name": "Alias", "stop_ids": ["A"], "feeds": ["cercanias"]},
                "category": "spain_renfe",
            },
            "B": {
                "type": "node", "id": "B", "lat": 40.1, "lon": -3.1,
                "tags": {"name": "Canonical", "stop_ids": ["B"], "feeds": ["ld"]},
                "category": "spain_renfe",
            },
        }
        index = {
            "stations": {
                "A": {"name": "Alias", "stop_ids": ["A"], "feeds": ["cercanias"]},
                "B": {"name": "Canonical", "stop_ids": ["B"], "feeds": ["ld"]},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            corrections = Path(tmp) / "corrections.json"
            exclusions = Path(tmp) / "excludes.json"
            corrections.write_text(json.dumps({
                "coordinate_overrides": [],
                "aliases": [{
                    "id": "A", "expected_name": "Alias",
                    "canonical_id": "B", "canonical_expected_name": "Canonical",
                }],
            }), encoding="utf-8")
            exclusions.write_text(json.dumps({
                "excluded": [{"id": "A"}], "renamed": [],
            }), encoding="utf-8")
            with patch("spain.STATION_CORRECTIONS", corrections), patch("spain.EXCLUSIONS", exclusions):
                self.assertEqual({"A"}, _apply_station_corrections(nodes, index))
        self.assertEqual(["A", "B"], nodes["B"]["tags"]["stop_ids"])
        self.assertEqual(["cercanias", "ld"], nodes["B"]["tags"]["feeds"])
        self.assertEqual(["A"], nodes["B"]["tags"]["renfe_alias_ids"])
        self.assertEqual(["A", "B"], index["stations"]["B"]["stop_ids"])

    def test_spain_guarded_alias_fails_on_renamed_source_station(self):
        nodes = {
            "A": {
                "type": "node", "id": "A", "lat": 40.0, "lon": -3.0,
                "tags": {"name": "Renamed alias", "stop_ids": ["A"], "feeds": ["cercanias"]},
                "category": "spain_renfe",
            },
            "B": {
                "type": "node", "id": "B", "lat": 40.1, "lon": -3.1,
                "tags": {"name": "Canonical", "stop_ids": ["B"], "feeds": ["ld"]},
                "category": "spain_renfe",
            },
        }
        index = {"stations": {
            "A": {"name": "Renamed alias", "stop_ids": ["A"], "feeds": ["cercanias"]},
            "B": {"name": "Canonical", "stop_ids": ["B"], "feeds": ["ld"]},
        }}
        with tempfile.TemporaryDirectory() as tmp:
            corrections = Path(tmp) / "corrections.json"
            exclusions = Path(tmp) / "excludes.json"
            corrections.write_text(json.dumps({
                "coordinate_overrides": [],
                "aliases": [{
                    "id": "A", "expected_name": "Old alias",
                    "canonical_id": "B", "canonical_expected_name": "Canonical",
                }],
            }), encoding="utf-8")
            exclusions.write_text(json.dumps({
                "excluded": [{"id": "A"}], "renamed": [],
            }), encoding="utf-8")
            with patch("spain.STATION_CORRECTIONS", corrections), patch("spain.EXCLUSIONS", exclusions):
                with self.assertRaisesRegex(ValueError, "stale alias"):
                    _apply_station_corrections(nodes, index)

    def test_denmark_keeps_only_stops_served_by_rail_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dk.zip"
            write_gtfs(path, {
                "stops.txt": [
                    {"stop_id":"8600001","stop_name":"Rail","stop_lat":"55","stop_lon":"12","parent_station":""},
                    {"stop_id":"bus","stop_name":"Bus","stop_lat":"55.1","stop_lon":"12.1","parent_station":""},
                ],
                "routes.txt": [
                    {"route_id":"r","route_type":"2"},
                    {"route_id":"b","route_type":"3"},
                ],
                "trips.txt": [
                    {"route_id":"r","trip_id":"tr"},
                    {"route_id":"b","trip_id":"tb"},
                ],
                "stop_times.txt": [
                    {"trip_id":"tr","stop_id":"8600001"},
                    {"trip_id":"tb","stop_id":"bus"},
                ],
            })
            nodes = build_denmark_nodes(path)
            self.assertEqual(["8600001"], [node["id"] for node in nodes])

    def test_spain_namespaces_trips_but_uses_stable_renfe_station_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "es.zip"
            write_gtfs(path, {
                "agency.txt": [{"agency_id":"a","agency_name":"Renfe"}],
                "stops.txt": [
                    {"stop_id":"A","stop_name":"Alpha","stop_lat":"40","stop_lon":"-3","parent_station":"","location_type":"1"},
                    {"stop_id":"B","stop_name":"Beta","stop_lat":"41","stop_lon":"-2","parent_station":"","location_type":"1"},
                ],
                "routes.txt": [{"route_id":"R","agency_id":"a","route_short_name":"C1","route_long_name":"","route_type":"2"}],
                "trips.txt": [{"route_id":"R","service_id":"S","trip_id":"T","trip_headsign":"Beta","trip_short_name":"123"}],
                "stop_times.txt": [
                    {"trip_id":"T","arrival_time":"12:00:00","departure_time":"12:00:00","stop_id":"A","stop_sequence":"1"},
                    {"trip_id":"T","arrival_time":"12:30:00","departure_time":"12:30:00","stop_id":"B","stop_sequence":"2"},
                ],
                "calendar.txt": [{
                    "service_id":"S","monday":"1","tuesday":"1","wednesday":"1","thursday":"1",
                    "friday":"1","saturday":"1","sunday":"1","start_date":"20260101","end_date":"20261231",
                }],
            })
            nodes, index = build_spain([("cercanias", load_feed(path))])
            self.assertEqual({"A", "B"}, {node["id"] for node in nodes})
            trip = index["trips"]["cercanias:T"]
            self.assertEqual("T", trip["source_trip_id"])
            self.assertEqual("A", trip["stops"][0]["stop_id"])
            self.assertEqual("A", trip["stops"][0]["station_id"])

    def test_spain_merges_shared_stations_and_excludes_bus_routes(self):
        feed = {
            "agency": [{"agency_id": "a", "agency_name": "Renfe"}],
            "stops": [{"stop_id": "A", "stop_name": "Alpha", "stop_lat": "40",
                       "stop_lon": "-3", "parent_station": ""}],
            "routes": [
                {"route_id": "rail", "agency_id": "a", "route_type": "2"},
                {"route_id": "bus", "agency_id": "a", "route_type": "3"},
            ],
            "trips": [
                {"route_id": "rail", "service_id": "S", "trip_id": "T"},
                {"route_id": "bus", "service_id": "S", "trip_id": "B"},
            ],
            "stop_times": [
                {"trip_id": "T", "stop_id": "A", "stop_sequence": "1"},
                {"trip_id": "B", "stop_id": "A", "stop_sequence": "1"},
            ],
            "calendar": [],
            "calendar_dates": [],
        }
        nodes, index = build_spain([("cercanias", feed), ("ld", feed)])
        self.assertEqual(["A"], [node["id"] for node in nodes])
        self.assertEqual(["cercanias", "ld"], nodes[0]["tags"]["feeds"])
        self.assertEqual({"cercanias:T", "ld:T"}, set(index["trips"]))

    def test_spain_index_writer_outputs_direct_sqlite(self):
        feed = {
            "stops": [
                {"stop_id": "A", "stop_name": "A", "stop_lat": "40.0", "stop_lon": "-3.0"},
                {"stop_id": "B", "stop_name": "B", "stop_lat": "41.0", "stop_lon": "-2.0"},
            ],
            "routes": [{"route_id": "R", "agency_id": "a", "route_type": "2"}],
            "agency": [{"agency_id": "a", "agency_name": "Renfe"}],
            "trips": [{"route_id": "R", "service_id": "S", "trip_id": "T", "trip_headsign": "B"}],
            "stop_times": [
                {"trip_id": "T", "stop_id": "A", "arrival_time": "12:00:00",
                 "departure_time": "12:01:00", "stop_sequence": "1"},
                {"trip_id": "T", "stop_id": "B", "arrival_time": "13:00:00",
                 "departure_time": "13:01:00", "stop_sequence": "2"},
            ],
            "calendar": [{
                "service_id": "S", "monday": "1", "tuesday": "1", "wednesday": "1",
                "thursday": "1", "friday": "1", "saturday": "1", "sunday": "1",
                "start_date": "20260101", "end_date": "20261231",
            }],
            "calendar_dates": [],
        }
        _, index = build_spain([("ld", feed)])
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "cache" / "spain.sqlite"
            write_index(index, database)
            self.assertTrue(database.is_file())
            self.assertEqual(b"SQLite format 3\x00", database.read_bytes()[:16])
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    ("1",),
                    connection.execute("SELECT value FROM metadata WHERE key='version'").fetchone(),
                )
                self.assertEqual(2, connection.execute("SELECT count(*) FROM stop_times").fetchone()[0])
            finally:
                connection.close()

    def test_generated_spain_database_is_queryable_and_matches_nodes(self):
        database = ROOT / "cache" / "spain.sqlite"
        if not database.is_file():
            self.skipTest("generated Spain GTFS index is not committed; run gen/spain.py with official GTFS inputs")
        connection = sqlite3.connect(database)
        try:
            version = connection.execute(
                "SELECT value FROM metadata WHERE key='version'"
            ).fetchone()
            station_count = connection.execute("SELECT count(*) FROM stations").fetchone()[0]
            rail_route_types = {
                json.loads(row[0]).get("route_type")
                for row in connection.execute("SELECT data FROM routes")
            }
        finally:
            connection.close()
        with (ROOT / "nodes" / "nodes-spain-renfe.json").open() as node_file:
            node_count = sum(1 for _ in node_file)
        self.assertEqual(("1",), version)
        self.assertLessEqual(node_count, station_count)
        excluded = json.loads((ROOT / "excludes" / "spain.json").read_text(encoding="utf-8"))
        excluded_ids = {str(row["id"]) for row in excluded["excluded"]}
        self.assertEqual(len(excluded_ids), station_count - node_count)
        self.assertTrue(rail_route_types <= {"2", *map(str, range(100, 200))})

    def test_spain_reviewed_foreign_stations_are_not_playable(self):
        nodes = [
            json.loads(line)
            for line in (ROOT / "nodes" / "nodes-spain-renfe.json").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        names = {str(row.get("tags", {}).get("name") or "") for row in nodes}
        for foreign_name in {
            "Narbonne", "Marseille St Charles", "Montpellier Saint-Roch", "Nimes",
            "Lyon Part Dieu", "Perpignan", "Valence TGV", "Avignon TGV",
            "Aix en Provence TGV",
        }:
            self.assertNotIn(foreign_name, names)


class CuneoVentimigliaTests(unittest.TestCase):
    def test_reviewed_french_stations_are_in_france_output_with_rfi_fallbacks(self):
        expected = {
            "Breil-sur-Roya": "730",
            "Fontan - Saorge": "1339",
            "Saint-Dalmas-de-Tende": "2780",
            "La Brigue": "1511",
            "Tende": "2826",
            "Vievola": "3050",
        }
        found = {}
        for line in (ROOT / "nodes" / "nodes-france-sncf.json").read_text(encoding="utf-8").splitlines():
            import json
            row = json.loads(line)
            name = row.get("tags", {}).get("name")
            if name in expected:
                found[name] = str(row["tags"].get("rfi_fallback_id"))
        self.assertEqual(expected, found)


if __name__ == "__main__":
    unittest.main()
