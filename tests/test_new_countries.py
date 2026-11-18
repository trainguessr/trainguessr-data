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

from countries.denmark.generate import (
    build_nodes as build_denmark_nodes,
    download_gtfs,
    validate_live_access,
)
from countries.spain.generate import (
    _apply_station_corrections, _clean_row, _download_official_feed,
    _load_station_corrections,
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
    def test_spain_station_corrections_are_editable_csv_rows(self):
        config = _load_station_corrections()
        self.assertEqual(2, len(config["coordinate_overrides"]))
        self.assertEqual(4, len(config["aliases"]))
        self.assertEqual(2, len(config["name_overrides"]))
        padron = next(row for row in config["coordinate_overrides"] if row["id"] == "23021")
        self.assertEqual(42.7812443, padron["lat"])
        self.assertTrue(padron["source_url"].startswith("https://"))

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

    def test_denmark_includes_provider_supported_light_rail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dk.zip"
            write_gtfs(path, {
                "stops.txt": [{
                    "stop_id": "00000860005300", "stop_name": "Aarhus H (Letbane)",
                    "stop_lat": "56.15", "stop_lon": "10.20", "parent_station": "",
                }],
                "routes.txt": [{"route_id": "l1", "route_type": "0"}],
                "trips.txt": [{"route_id": "l1", "trip_id": "trip-l1"}],
                "stop_times.txt": [{"trip_id": "trip-l1", "stop_id": "00000860005300"}],
            })
            nodes = build_denmark_nodes(path)
        self.assertEqual(["860005300"], [node["id"] for node in nodes])

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
            with patch("countries.denmark.generate.CACHE_DIR", cache_dir), patch("countries.denmark.generate.GTFS_ARCHIVE", archive_path):
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
            with patch("countries.spain.generate.CACHE_ROOT", Path(tmp)):
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
            corrections = Path(tmp) / "corrections.csv"
            exclusions = Path(tmp) / "excludes.json"
            with corrections.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "record", "id", "expected_name", "name", "canonical_id",
                    "canonical_expected_name", "lat", "lon", "source", "source_url", "reason",
                ])
                writer.writeheader()
                writer.writerow({
                    "record": "alias", "id": "A", "expected_name": "Alias",
                    "canonical_id": "B", "canonical_expected_name": "Canonical",
                })
            exclusions.write_text(json.dumps({
                "excluded": [{"id": "A"}], "renamed": [],
            }), encoding="utf-8")
            with patch("countries.spain.generate.STATION_CORRECTIONS", corrections), patch("countries.spain.generate.EXCLUSIONS", exclusions):
                self.assertEqual({"A"}, _apply_station_corrections(nodes, index))
        self.assertEqual(["A", "B"], nodes["B"]["tags"]["stop_ids"])
        self.assertEqual(["cercanias", "ld"], nodes["B"]["tags"]["feeds"])
        self.assertEqual(["A"], nodes["B"]["tags"]["renfe_alias_ids"])
        self.assertEqual(["A", "B"], index["stations"]["B"]["stop_ids"])

    def test_spain_absent_alias_keeps_only_checked_canonical_identity(self):
        config = {"aliases": [{"id": "A", "expected_name": "Alias",
                              "canonical_id": "B", "canonical_expected_name": "Canonical"}]}
        nodes = {"B": {"id": "B", "tags": {"name": "Canonical", "stop_ids": ["B"]}}}
        index = {"stations": {"B": {"stop_ids": ["B"]}}}
        with patch("countries.spain.generate._load_station_corrections", return_value=config), \
             patch("countries.spain.generate._excluded_station_ids", return_value={"A"}):
            self.assertEqual(set(), _apply_station_corrections(nodes, index))
            self.assertEqual(["B"], nodes["B"]["tags"]["stop_ids"])
            self.assertNotIn("A", index["stations"])
            nodes["B"]["tags"]["name"] = "Different station"
            with self.assertRaises(ValueError):
                _apply_station_corrections(nodes, index)
            with self.assertRaises(ValueError):
                _apply_station_corrections({}, index)

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
            corrections = Path(tmp) / "corrections.csv"
            exclusions = Path(tmp) / "excludes.json"
            with corrections.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "record", "id", "expected_name", "name", "canonical_id",
                    "canonical_expected_name", "lat", "lon", "source", "source_url", "reason",
                ])
                writer.writeheader()
                writer.writerow({
                    "record": "alias", "id": "A", "expected_name": "Old alias",
                    "canonical_id": "B", "canonical_expected_name": "Canonical",
                })
            exclusions.write_text(json.dumps({
                "excluded": [{"id": "A"}], "renamed": [],
            }), encoding="utf-8")
            with patch("countries.spain.generate.STATION_CORRECTIONS", corrections), patch("countries.spain.generate.EXCLUSIONS", exclusions):
                with self.assertRaisesRegex(ValueError, "Check station ID"):
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

    def test_spain_keeps_explicit_station_without_current_trip(self):
        feed = {
            "agency": [{"agency_id": "a", "agency_name": "Renfe"}],
            "stops": [
                {"stop_id": "A", "stop_name": "Alpha", "stop_lat": "40",
                 "stop_lon": "-3", "parent_station": "", "location_type": "1"},
                {"stop_id": "C", "stop_name": "Dormant", "stop_lat": "41",
                 "stop_lon": "-4", "parent_station": "", "location_type": "1"},
                {"stop_id": "BUS", "stop_name": "Replacement bus", "stop_lat": "42",
                 "stop_lon": "-5", "parent_station": "", "location_type": "0"},
            ],
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
                {"trip_id": "B", "stop_id": "BUS", "stop_sequence": "1"},
            ],
            "calendar": [],
            "calendar_dates": [],
        }
        nodes, index = build_spain([("cercanias", feed)])
        self.assertEqual({"A", "C"}, {node["id"] for node in nodes})
        self.assertIn("C", index["stations"])
        self.assertNotIn("BUS", index["stations"])
        self.assertNotIn("C", index["station_trips"])

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
            self.skipTest("generated Spain GTFS index is not committed; run python3 -m gen.countries spain with official GTFS inputs")
        connection = sqlite3.connect(database)
        try:
            version = connection.execute(
                "SELECT value FROM metadata WHERE key='version'"
            ).fetchone()
            station_ids = {row[0] for row in connection.execute("SELECT id FROM stations")}
            station_count = len(station_ids)
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
        excluded = json.loads((ROOT / "overrides" / "exclusions" / "spain.json").read_text(encoding="utf-8"))
        excluded_ids = {str(row["id"]) for row in excluded["excluded"]}
        with (ROOT / "lookup" / "lookup-spain-renfe.json").open() as lookup_file:
            abroad_count = sum(1 for _ in lookup_file)
        self.assertEqual(len(excluded_ids & station_ids) + abroad_count, station_count - node_count)
        self.assertTrue(rail_route_types <= {"2", *map(str, range(100, 200))})

    def test_spain_reviewed_foreign_stations_are_outside_the_dataset(self):
        nodes = [
            json.loads(line)
            for line in (ROOT / "nodes" / "nodes-spain-renfe.json").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        names = {str(row.get("tags", {}).get("name") or "") for row in nodes}
        for foreign_name in {
            "Narbonne", "Marseille St Charles", "Montpellier Saint-Roch", "Nimes",
            "Lyon Part Dieu", "Perpignan", "Valence TGV", "Avignon TGV",
            "Aix en Provence TGV", "Cerbère",
        }:
            self.assertNotIn(foreign_name, names)


class CuneoVentimigliaTests(unittest.TestCase):
    def test_reviewed_french_stations_are_in_france_output_with_rfi_fallbacks(self):
        expected = {
            "87756833": "730",  # Breil-sur-Roya
            "87756858": "1339",  # Fontan - Saorge
            "87756866": "2780",  # Saint-Dalmas-de-Tende
            "87756874": "1511",  # La Brigue
            "87756882": "2826",  # Tende
            "87756890": "3050",  # Vievola
        }
        found = {}
        for line in (ROOT / "nodes" / "nodes-france-sncf.json").read_text(encoding="utf-8").splitlines():
            import json
            row = json.loads(line)
            station_id = str(row["id"])
            if station_id in expected:
                found[station_id] = str(row["tags"].get("rfi_fallback_id"))
        self.assertEqual(expected, found)


if __name__ == "__main__":
    unittest.main()


def test_official_exclusions_use_native_ids_after_source_name_changes(tmp_path):
    from countries.belgium.generate import build_nodes as belgium
    from countries.norway.generate import build_nodes as norway
    from countries.sweden.generate import convert_from_xml
    from common.io import load_ndjson
    assert belgium({'station': [{'id': 'BE.NMBS.008400058', 'standardname': 'Amsterdam Centraal', 'locationX': '4.9', 'locationY': '52.4'}]}) == []
    assert norway([{'id': 'NSR:StopPlace:63244', 'name': 'Brussels Central', 'transportMode': 'RAIL'}]) == []
    def stop(station_id, name):
        return f'<StopPlace><Name>{name}</Name><TransportMode>rail</TransportMode><Centroid><Location><Longitude>16</Longitude><Latitude>60</Latitude></Location></Centroid><keyList><KeyValue><Key>rikshallplats</Key><Value>{station_id}</Value></KeyValue></keyList></StopPlace>'
    source = tmp_path / 'stops.xml'
    source.write_text('<root>' + stop('740069608', 'Fors') + stop('740000704', 'Fors') + stop('740999999', 'Fors') + '</root>')
    output = tmp_path / 'nodes.json'
    convert_from_xml(source, output, {})
    rows = load_ndjson(output)
    assert [r['id'] for r in rows] == [740000704, 740999999]
    assert [r['tags']['name'] for r in rows] == ['Fors', 'Fors']


def test_austria_reviewed_id_wins_over_stale_mvo_platform_id(tmp_path):
    from countries.austria.scotty import ScottyResolver
    resolver = ScottyResolver(None, tmp_path / 'absent.json', offline=True)
    result = resolver.resolve({'hst_globid': 'at:44:46263', 'hst_name': 'Weidach (Vorchdorf) Lokalbahn', 'hst_x': 13.908346, 'hst_y': 47.9897634, 'platform_eva_id': 1240712})
    assert result['eva_id'] == 8101751
    assert result['expected_provider_name'] == 'Vorchdorf Weidach Bahnhst'


def test_austria_retries_only_failed_native_checks(monkeypatch):
    from types import SimpleNamespace
    from countries.austria import catalogue
    from unittest.mock import Mock
    monkeypatch.setattr(catalogue, '_load_mvo_overrides', lambda: ({}, {}, {}))
    verify = Mock(side_effect=[None, {'station_name': 'Example', 'journey_count': 0}])
    monkeypatch.setattr(catalogue, 'verify_scotty_station', verify)
    resolver = SimpleNamespace(offline=False, timeout=1, record_verifications=lambda results: None, resolve=lambda row: {'eva_id': 1234567, 'name': 'Example'})
    rows = [{'hst_id': '1', 'hst_globid': 'at:43:99999', 'hst_name': 'Example', 'hst_x': 15, 'hst_y': 48}]
    platforms = [{'hst_id': '1', 'stg_x': 15, 'stg_y': 48, 'umst_vm': '10000000000000', 'linien': 'R1'}]
    result, audit = catalogue.merge_catalogues([], rows, platforms, resolver, {})
    assert [node['id'] for node in result] == [1234567]
    assert audit['unresolved'] == []
    assert verify.call_count == 2
    assert all(call.kwargs == {'attempts': 1} for call in verify.call_args_list)


def test_austria_offline_never_invents_a_successful_board_check(tmp_path):
    from countries.austria.scotty import ScottyResolver
    from countries.austria.catalogue import merge_catalogues
    resolver = ScottyResolver(None, tmp_path / 'cache.json', offline=True)
    rows = [{'hst_id': '1', 'hst_globid': 'at:43:99999', 'hst_name': 'Example', 'hst_x': 15, 'hst_y': 48}]
    platforms = [{'hst_id': '1', 'stg_x': 15, 'stg_y': 48, 'umst_vm': '10000000000000', 'linien': 'R1', 'extids_obb': '1234567'}]
    result, audit = merge_catalogues([], rows, platforms, resolver, {})
    assert result == []
    assert audit['unresolved'][0]['reason'] == 'missing_cached_verification'
    resolver.record_verifications({1234567: {'station_name': 'Example', 'journey_count': 2}})
    resolver = ScottyResolver(None, tmp_path / 'cache.json', offline=True)
    result, audit = merge_catalogues([], rows, platforms, resolver, {})
    assert [row['id'] for row in result] == [1234567]
    assert result[0]['tags']['scotty_board_status'] == 'offline_cached_verification'
    assert audit['added'][0]['board_journeys'] is None


def test_austria_unmapped_railway_stops_have_a_permanent_home(tmp_path):
    from countries.austria.decisions import load_unmapped_stations, _load_mvo_overrides
    from countries.austria.catalogue import merge_catalogues
    from countries.austria.scotty import ScottyResolver
    stops = load_unmapped_stations()
    assert set(stops) == {'at:43:70106', 'at:43:70107', 'at:43:70108', 'at:43:20834'}
    assert not set(stops).intersection(_load_mvo_overrides()[2])
    rows = [{'hst_id': str(i), 'hst_globid': key, 'hst_name': row['name'], 'hst_x': row['lon'], 'hst_y': row['lat']} for i, (key, row) in enumerate(stops.items())]
    result, audit = merge_catalogues([], rows, [], ScottyResolver(None, tmp_path / 'none', offline=True), {})
    assert result == []
    assert {row['ifopt_id'] for row in audit['unresolved']} == set(stops)
    assert all(row['source_url'].startswith('https://') and row['operator'] for row in audit['unresolved'])


def test_austria_refresh_preserves_sta_ids_on_the_same_native_station():
    import pytest
    from countries.austria.catalogue import preserve_sta_tags
    previous = [{'id': 8100106, 'tags': {'ifopt_id': 'at:47:1', 'sta_station_id': '66001375', 'sta_station_name': 'Matrei'}}]
    current = [{'id': 8100106, 'tags': {'ifopt_id': 'at:47:1', 'name': 'Updated label'}}]
    preserve_sta_tags(current, previous)
    assert current[0]['tags']['sta_station_id'] == '66001375'
    assert current[0]['tags']['sta_station_name'] == 'Matrei'
    assert current[0]['tags']['name'] == 'Updated label'
    with pytest.raises(ValueError, match='IFOPT changed'):
        preserve_sta_tags([{'id': 8100106, 'tags': {'ifopt_id': 'at:47:2'}}], previous)


def test_sweden_and_finland_keep_stations_abroad_as_lookup_rows(tmp_path):
    from countries.finland.generate import build_nodes as finland
    from countries.sweden.generate import convert_from_xml
    from common.io import load_ndjson
    stop = ('<StopPlace><Name>{1}</Name><TransportMode>rail</TransportMode><Centroid><Location>'
            '<Longitude>11</Longitude><Latitude>60</Latitude></Location></Centroid><keyList><KeyValue>'
            '<Key>rikshallplats</Key><Value>{0}</Value></KeyValue></keyList></StopPlace>')
    source = tmp_path / 'stops.xml'
    source.write_text('<root>' + stop.format('740000001', 'Stockholm') + stop.format('760000100', 'Oslo S') + '</root>')
    convert_from_xml(source, tmp_path / 'nodes.json', {}, lookup_path=tmp_path / 'lookup.json')
    assert [r['id'] for r in load_ndjson(tmp_path / 'nodes.json')] == [740000001]
    assert [r['id'] for r in load_ndjson(tmp_path / 'lookup.json')] == [760000100]

    lookup = []
    rows = [{'countryCode': code, 'type': 'STATION', 'stationShortCode': short, 'stationName': short,
             'latitude': 60, 'longitude': 25, 'stationUICCode': 1} for code, short in (('FI', 'HKI'), ('RU', 'VYB'))]
    assert [r['id'] for r in finland(rows, {}, lookup)] == ['HKI']
    assert [(r['id'], r['tags']['country']) for r in lookup] == [('VYB', 'RU')]


def test_belgian_stations_abroad_go_to_lookup_by_published_uic():
    from countries.belgium.generate import build_nodes as belgium
    stations = [{'id': f'BE.NMBS.00{uic}', 'standardname': name, 'locationX': '6', 'locationY': '49.6',
                 '@id': f'http://irail.be/stations/NMBS/00{uic}'} for uic, name in
                (('8814001', 'Bruxelles-Midi'), ('8200100', 'Lëtzebuerg'))]
    lookup = []
    assert [n['tags']['name'] for n in belgium({'station': stations}, lookup)] == ['Bruxelles-Midi']
    assert [n['tags']['name'] for n in lookup] == ['Lëtzebuerg']
