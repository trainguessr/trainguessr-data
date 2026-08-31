from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from reconcile.germany import (  # noqa: E402
    _boundary_geometry,
    _read_json,
    build_node_grid,
    build_gtfs_candidates,
    load_reviewed_station_overrides,
    load_reviewed_gap_notes,
    nearby_nodes,
    name_score,
    parse_station_xml,
    reconcile,
)


def write_gtfs(path: Path, tables: dict[str, list[dict[str, str]]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for filename, rows in tables.items():
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(filename, stream.getvalue())


class GermanyReconciliationTests(unittest.TestCase):
    def test_reviewed_station_override_is_well_formed(self) -> None:
        overrides = load_reviewed_station_overrides()
        self.assertEqual(["8011002"], overrides["394215"]["provider_ids"])

    def test_reviewed_gap_notes_are_well_formed(self) -> None:
        notes = load_reviewed_gap_notes()
        self.assertEqual(
            "separate_provider_gap",
            notes["14907"]["classification"],
        )

    def test_gtfs_candidates_use_rail_trip_hierarchy_and_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "feed.zip"
            write_gtfs(
                archive,
                {
                    "agency.txt": [
                        {"agency_id": "rail", "agency_name": "Regional Rail"},
                        {"agency_id": "bus", "agency_name": "City Bus"},
                    ],
                    "routes.txt": [
                        {"route_id": "r", "agency_id": "rail", "route_type": "2"},
                        {"route_id": "b", "agency_id": "bus", "route_type": "3"},
                    ],
                    "trips.txt": [
                        {"route_id": "r", "trip_id": "rail-trip"},
                        {"route_id": "b", "trip_id": "bus-trip"},
                    ],
                    "stops.txt": [
                        {
                            "stop_id": "parent",
                            "stop_name": "Rail Place",
                            "parent_station": "",
                            "stop_lat": "50.0",
                            "stop_lon": "10.0",
                            "location_type": "1",
                            "platform_code": "",
                        },
                        {
                            "stop_id": "child",
                            "stop_name": "Rail Place platform",
                            "parent_station": "parent",
                            "stop_lat": "50.0",
                            "stop_lon": "10.0",
                            "location_type": "",
                            "platform_code": "1",
                        },
                        {
                            "stop_id": "bus-stop",
                            "stop_name": "Bus Place",
                            "parent_station": "",
                            "stop_lat": "50.1",
                            "stop_lon": "10.1",
                            "location_type": "1",
                            "platform_code": "",
                        },
                    ],
                    "stop_times.txt": [
                        {"trip_id": "rail-trip", "stop_id": "child"},
                        {"trip_id": "bus-trip", "stop_id": "bus-stop"},
                    ],
                },
            )
            boundary = root / "DEU.geo.json"
            boundary.write_text(
                json.dumps(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[5, 45], [15, 45], [15, 55], [5, 55], [5, 45]]],
                        },
                    }
                ),
                encoding="utf-8",
            )
            metadata, candidates, out_of_scope = build_gtfs_candidates(
                archive, _boundary_geometry(_read_json(boundary))
            )

        self.assertEqual({"2": 1, "3": 1}, metadata["route_type_counts"])
        self.assertEqual(1, metadata["rail_routes"])
        self.assertEqual(["parent"], [row["gtfs_parent_station"] for row in candidates])
        self.assertEqual(["rail"], candidates[0]["agency_ids"])
        self.assertEqual([], out_of_scope)

    def test_gtfs_candidates_exclude_non_boarding_rail_points(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "feed.zip"
            write_gtfs(
                archive,
                {
                    "agency.txt": [{"agency_id": "rail", "agency_name": "Regional Rail"}],
                    "routes.txt": [{"route_id": "r", "agency_id": "rail", "route_type": "2"}],
                    "trips.txt": [
                        {"route_id": "r", "trip_id": "passenger"},
                        {"route_id": "r", "trip_id": "through"},
                    ],
                    "stops.txt": [
                        {"stop_id": "passenger-stop", "stop_name": "Passenger Place", "parent_station": "", "stop_lat": "50.0", "stop_lon": "10.0", "location_type": "1"},
                        {"stop_id": "through-stop", "stop_name": "Through Point", "parent_station": "", "stop_lat": "50.1", "stop_lon": "10.1", "location_type": "1"},
                    ],
                    "stop_times.txt": [
                        {"trip_id": "passenger", "stop_id": "passenger-stop", "pickup_type": "0", "drop_off_type": "0"},
                        {"trip_id": "through", "stop_id": "through-stop", "pickup_type": "1", "drop_off_type": "1"},
                    ],
                },
            )
            boundary = root / "boundary.json"
            boundary.write_text(
                json.dumps({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[5, 45], [15, 45], [15, 55], [5, 55], [5, 45]]]}}),
                encoding="utf-8",
            )
            metadata, candidates, out_of_scope = build_gtfs_candidates(
                archive, _boundary_geometry(_read_json(boundary))
            )

        self.assertEqual(1, metadata["non_passenger_parent_stop_places"])
        self.assertEqual(["passenger-stop"], [row["gtfs_parent_station"] for row in candidates])
        self.assertEqual("not_passenger_station", out_of_scope[0]["scope_reason"])

    def test_station_xml_preserves_eva_and_meta_identity(self) -> None:
        records = parse_station_xml(
            b'<stations><station meta="8000001|8000002" name="Place" '
            b'eva="8000001" ds100="PLC" db="true"/></stations>'
        )
        self.assertEqual(["8000001", "8000002"], records[0]["ids"])
        self.assertTrue(records[0]["db"])
        self.assertEqual("PLC", records[0]["ds100"])

    def test_name_score_accepts_common_db_station_abbreviations(self) -> None:
        for gtfs_name, db_name in (
            (
                "Lichtenstein, Hp Hartensteiner Str",
                "Lichtenstein Hartensteiner Straße",
            ),
            ("Wörth/Rh, Bienwaldhalle", "Wörth(Rhein) Bienwaldhalle"),
            ("Weil i. S. Untere Halde", "Weil im Schönbuch Untere Halde"),
            (
                "Durlach Untermühlstraße",
                "Durlach Untermühlstraße, Karlsruhe",
            ),
            ("S+U Wittenau (Berlin)", "Berlin Wittenau (Wilhelmsruher Damm)"),
            ("S+U Hermannstr. (Berlin)", "Berlin Hermannstraße"),
            (
                "S+U Yorckstr. (Großgörschenstr.) (Berlin)",
                "Berlin Yorckstr.(S1)",
            ),
            ("Böblingen Südbahnhof", "Böblingen Südbf"),
            ("Lößnitz, oberer Bahnhof", "Lößnitz ob Bf"),
            ("Lößnitz, unterer Bahnhof", "Lößnitz unt Bf"),
            ("Aue, Stadion", "Aue(Sachs) Erzgebirgsstadion"),
            ("Apach(fr)", "Apach(Moselle)"),
            (
                "Friedrichstal St-Riquier-Platz",
                "Friedrichstal Saint-Riquier-Platz, Stutensee",
            ),
            ("Karlsruhe Einfahrt über Gl. 21", "Einfahrt über Gleis 21, Karlsruhe"),
        ):
            self.assertGreaterEqual(name_score(gtfs_name, db_name), 0.72)
        self.assertGreaterEqual(
            name_score(
                "Untermühlstraße, Karlsruhe",
                "Durlach Untermühlstraße, Karlsruhe",
            ),
            0.72,
        )
        self.assertGreaterEqual(name_score("Apach(fr)", "Apach(Moselle)"), 0.72)

    def test_nearby_nodes_accept_exact_place_name_at_same_coordinates(self) -> None:
        candidate = {
            "name": "Immenhausen Bahnhof, Bereich Gleis 1",
            "latitude": 51.42708,
            "longitude": 9.464436,
        }
        node = {
            "id": 8003062,
            "lat": 51.426902,
            "lon": 9.464397,
            "tags": {"name": "Immenhausen (Hess)"},
        }
        self.assertEqual([node], nearby_nodes(candidate, build_node_grid([node])))

    def test_reconcile_uses_child_stop_name_alias_for_db_namespace_match(self) -> None:
        class Probe:
            auth_configured = True
            plan_slots = ["260828/13"]
            delay = 0

            def resolve(self, provider_ids, *, expected_name=None, expected_name_aliases=()):
                self.provider_ids = list(provider_ids)
                self.aliases = list(expected_name_aliases)
                if "8006145" not in self.provider_ids:
                    return {
                        "station_checks": [],
                        "plan_checks": [],
                        "selected_station": None,
                        "selected_eva": None,
                        "station_http_status": None,
                        "plan_http_status": None,
                    }
                return {
                    "station_checks": [{
                        "requested_eva": "8006145",
                        "url": "https://example.test/station/8006145",
                        "http_status": 200,
                        "response_bytes": 100,
                        "eva": "8006145",
                        "name": "Wallhausen(Württ)",
                        "ds100": "TWAL",
                        "db": True,
                        "verification_state": "verified",
                    }],
                    "plan_checks": [{
                        "requested_eva": "8006145",
                        "slot": "260828/13",
                        "url": "https://example.test/plan/8006145/260828/13",
                        "http_status": 200,
                        "response_bytes": 100,
                        "verification_state": "verified",
                    }],
                    "selected_station": {"eva": "8006145"},
                    "selected_eva": "8006145",
                    "station_http_status": 200,
                    "plan_http_status": 200,
                }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "feed.zip"
            write_gtfs(
                archive,
                {
                    "agency.txt": [{"agency_id": "a", "agency_name": "Regional Rail"}],
                    "routes.txt": [{"route_id": "r", "agency_id": "a", "route_type": "2"}],
                    "trips.txt": [{"route_id": "r", "trip_id": "t"}],
                    "stops.txt": [
                        {"stop_id": "parent", "stop_name": "Wallhausen Bahnhof", "parent_station": "", "stop_lat": "49.209305", "stop_lon": "10.063045", "location_type": "1"},
                        {"stop_id": "child", "stop_name": "Wallhausen(Württ)", "parent_station": "parent", "stop_lat": "49.209305", "stop_lon": "10.063045", "location_type": ""},
                    ],
                    "stop_times.txt": [{"trip_id": "t", "stop_id": "child"}],
                },
            )
            boundary = root / "boundary.json"
            boundary.write_text(
                json.dumps({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[5, 45], [15, 45], [15, 55], [5, 55], [5, 45]]]}}),
                encoding="utf-8",
            )
            snapshot = root / "stations.xml"
            snapshot.write_text(
                '<stations><station name="Wallhausen(Württ)" eva="8006145" ds100="TWAL" db="true"/></stations>',
                encoding="utf-8",
            )
            catalogue = root / "full.json"
            catalogue.write_text("[]", encoding="utf-8")
            nodes = root / "nodes.json"
            nodes.write_text("", encoding="utf-8")
            probe = Probe()
            audit = reconcile(
                archive_path=archive,
                boundary_path=boundary,
                station_snapshot_path=snapshot,
                catalogue_path=catalogue,
                nodes_path=nodes,
                previous_audit={},
                db_probe=probe,
                probe_stale_osm={"elements": []},
            )

        outcome = audit["outcomes"][0]
        self.assertEqual("added_existing_provider", outcome["status"])
        self.assertEqual("8006145", outcome["eva_id"])
        self.assertEqual(
            "Wallhausen(Württ)",
            outcome["evidence"]["db_namespace_match_alias"],
        )
        self.assertIn("Wallhausen(Württ)", probe.aliases)

    def test_reconcile_preserves_akn_prefix_and_requires_probe_for_addition(self) -> None:
        class Probe:
            auth_configured = True
            plan_slots = ["260828/13"]
            delay = 0

            def resolve(self, provider_ids, *, expected_name=None, expected_name_aliases=()):
                if "8000002" not in provider_ids:
                    return {
                        "station_checks": [],
                        "plan_checks": [],
                        "selected_station": None,
                        "selected_eva": None,
                        "station_http_status": None,
                        "plan_http_status": None,
                    }
                return {
                    "station_checks": [{
                        "requested_eva": "8000002",
                        "url": "https://example.test/station/8000002",
                        "http_status": 200,
                        "response_bytes": 100,
                        "eva": "8000002",
                        "name": "New Place",
                        "ds100": "NEW",
                        "db": True,
                        "verification_state": "verified",
                    }],
                    "plan_checks": [{
                        "requested_eva": "8000002",
                        "slot": "260828/13",
                        "url": "https://example.test/plan/8000002/260828/13",
                        "http_status": 200,
                        "response_bytes": 100,
                        "verification_state": "verified",
                    }],
                    "selected_station": {"eva": "8000002"},
                    "selected_eva": "8000002",
                    "station_http_status": 200,
                    "plan_http_status": 200,
                }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "feed.zip"
            write_gtfs(
                archive,
                {
                    "agency.txt": [{"agency_id": "a", "agency_name": "Regional Rail"}],
                    "routes.txt": [{"route_id": "r", "agency_id": "a", "route_type": "2"}],
                    "trips.txt": [{"route_id": "r", "trip_id": "t"}],
                    "stops.txt": [
                        {"stop_id": "p1", "stop_name": "AKN Place", "parent_station": "", "stop_lat": "50", "stop_lon": "10", "location_type": "1"},
                        {"stop_id": "p2", "stop_name": "New Place", "parent_station": "", "stop_lat": "51", "stop_lon": "10", "location_type": "1"},
                    ],
                    "stop_times.txt": [
                        {"trip_id": "t", "stop_id": "p1"},
                        {"trip_id": "t", "stop_id": "p2"},
                    ],
                },
            )
            boundary = root / "boundary.json"
            boundary.write_text(
                json.dumps({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[5, 45], [15, 45], [15, 55], [5, 55], [5, 45]]]}}),
                encoding="utf-8",
            )
            snapshot = root / "stations.xml"
            snapshot.write_text(
                '<stations><station meta="8000002" name="New Place" eva="8000002" ds100="NEW" db="true"/></stations>',
                encoding="utf-8",
            )
            catalogue = root / "full.json"
            catalogue.write_text("[]", encoding="utf-8")
            nodes = root / "nodes.json"
            nodes.write_text("", encoding="utf-8")
            previous = {
                "outcomes": [{
                    "gtfs_parent_station": "p1",
                    "gtfs_stop_ids": ["p1"],
                    "name": "AKN Place",
                    "latitude": 50.0,
                    "longitude": 10.0,
                    "status": "added_existing_provider",
                    "eva_id": "8000001",
                    "db": "true",
                    "evidence": {"station_http_status": 200, "plan_http_status": 200},
                }],
            }
            audit = reconcile(
                archive_path=archive,
                boundary_path=boundary,
                station_snapshot_path=snapshot,
                catalogue_path=catalogue,
                nodes_path=nodes,
                previous_audit=previous,
                db_probe=Probe(),
                probe_stale_osm={"elements": []},
            )

        self.assertEqual(2, audit["counts"]["candidate_records"])
        self.assertEqual("8000001", audit["outcomes"][0]["eva_id"])
        self.assertEqual("added_existing_provider", audit["outcomes"][1]["status"])
        self.assertEqual("8000002", audit["outcomes"][1]["eva_id"])
        self.assertEqual(2, audit["counts"]["candidate_statuses"]["added_existing_provider"])


if __name__ == "__main__":
    unittest.main()
