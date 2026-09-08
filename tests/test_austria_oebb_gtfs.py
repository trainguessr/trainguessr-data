import csv
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))
from austria import build_oebb_operator_index as build_index, load_oebb_gtfs as load_gtfs, main as austria_main


def _csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class OebbGtfsOperatorIndexTests(unittest.TestCase):
    def _feed(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "gtfs.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("agency.txt", _csv([
                {"agency_id": "oebb", "agency_name": "ÖBB Personenverkehr AG"},
                {"agency_id": "mbs", "agency_name": "Montafonerbahn AG"},
            ]))
            z.writestr("routes.txt", _csv([
                {"route_id": "r1", "agency_id": "oebb", "route_short_name": "S3", "route_type": "2"},
                {"route_id": "r2", "agency_id": "mbs", "route_short_name": "S4", "route_type": "2"},
                {"route_id": "bus", "agency_id": "oebb", "route_short_name": "B1", "route_type": "3"},
            ]))
            z.writestr("trips.txt", _csv([
                {"route_id": "r1", "service_id": "daily", "trip_id": "t1", "trip_short_name": "1"},
                {"route_id": "r2", "service_id": "daily", "trip_id": "t2", "trip_short_name": "2"},
                {"route_id": "bus", "service_id": "daily", "trip_id": "t3", "trip_short_name": "B1"},
            ]))
            z.writestr("stops.txt", _csv([
                {"stop_id": "Pat:47:1187", "parent_station": "", "stop_code": ""},
                {"stop_id": "at:47:1187:0:1", "parent_station": "Pat:47:1187", "stop_code": ""},
            ]))
            z.writestr("stop_times.txt", _csv([
                {"trip_id": "t1", "stop_id": "at:47:1187:0:1"},
                {"trip_id": "t2", "stop_id": "at:47:1187:0:1"},
                {"trip_id": "t3", "stop_id": "at:47:1187:0:1"},
            ]))
            z.writestr("calendar.txt", _csv([
                {"service_id": "daily", "monday": "1", "tuesday": "1", "wednesday": "1",
                 "thursday": "1", "friday": "1", "saturday": "1", "sunday": "1",
                 "start_date": "20260101", "end_date": "20261231"},
            ]))
            z.writestr("calendar_dates.txt", _csv([
                {"service_id": "daily", "date": "20260908", "exception_type": "2"},
            ]))
            z.writestr("feed_info.txt", _csv([
                {"feed_publisher_name": "ÖBB", "feed_start_date": "20251214", "feed_end_date": "20261212"},
            ]))
        return path

    def test_builds_rail_only_operator_index(self):
        source = self._feed()
        output = source.parent / "operators.sqlite"
        stats = build_index(load_gtfs(source), output)
        self.assertEqual(2, stats["agencies"])
        self.assertEqual(2, stats["rail_routes"])
        self.assertEqual(2, stats["rail_trips"])
        self.assertEqual("20261212", stats["feed_end_date"])
        with sqlite3.connect(output) as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM trips WHERE short_name='B1'").fetchone()[0])
            self.assertEqual("ÖBB Personenverkehr AG", db.execute(
                "SELECT agency_name FROM agencies WHERE agency_id='oebb'"
            ).fetchone()[0])
            self.assertEqual(("S3", "S3"), db.execute(
                "SELECT short_name, line_key FROM routes WHERE route_id='r1'"
            ).fetchone())
            self.assertEqual("at:47:1187", db.execute(
                "SELECT station_ifopt FROM stops WHERE stop_id='at:47:1187:0:1'"
            ).fetchone()[0])
            self.assertEqual("2", dict(db.execute("SELECT key,value FROM metadata"))["version"])

    def test_loads_gtfs_under_wrapper_directory(self):
        source = self._feed()
        wrapped = source.parent / "wrapped.zip"
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(wrapped, "w") as output:
            for name in original.namelist():
                output.writestr("GTFS_Fahrplan_2026/" + name, original.read(name))
        self.assertEqual(2, len(load_gtfs(wrapped)["agency"]))

    def test_loads_one_nested_gtfs_zip(self):
        source = self._feed()
        outer = source.parent / "outer.zip"
        with zipfile.ZipFile(outer, "w") as output:
            output.writestr("downloads/readme.txt", "official bundle")
            output.writestr("downloads/GTFS.zip", source.read_bytes())
        self.assertEqual(2, len(load_gtfs(outer)["agency"]))

    def test_single_austria_entrypoint_can_build_index_only(self):
        source = self._feed()
        output = source.parent / "operators.sqlite"
        audit = source.parent / "audit.json"
        result = austria_main([
            "--oebb-gtfs", str(source),
            "--oebb-operator-index", str(output),
            "--oebb-operator-audit", str(audit),
            "--oebb-operator-index-only",
        ])
        self.assertEqual(0, result)
        self.assertTrue(output.is_file())
        self.assertEqual(2, json.loads(audit.read_text())["rail_routes"])

    def test_rejects_non_gtfs_zip(self):
        bad = Path(tempfile.mkstemp(suffix=".zip")[1])
        self.addCleanup(lambda: bad.unlink(missing_ok=True))
        bad.write_text("nope")
        with self.assertRaises(ValueError):
            load_gtfs(bad)


if __name__ == "__main__":
    unittest.main()
