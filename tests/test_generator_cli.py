from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

GEN = Path(__file__).parents[1] / "gen"
if str(GEN) not in sys.path:
    sys.path.insert(0, str(GEN))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_italy_dispatcher_does_not_leak_its_args_to_fse(monkeypatch):
    module = load("italy_dispatch_test", GEN / "countries" / "italy" / "generate.py")
    seen = []
    monkeypatch.setitem(module.PROVIDERS, "fse", lambda argv=None: seen.append(argv) or 0)
    assert module.main(["generate", "fse"]) == 0
    assert seen == [[]]


def test_country_entrypoint_shows_source_errors_without_a_traceback(monkeypatch, capsys):
    import importlib
    import countries.__main__ as entrypoint

    class Generator:
        @staticmethod
        def main(_argv):
            raise FileNotFoundError("Saved station data is missing. Run again without --cache to download it.")

    monkeypatch.setattr(importlib, "import_module", lambda _name: Generator)
    assert entrypoint.main(["denmark", "--cache"]) == 1
    captured = capsys.readouterr()
    assert "Error: Saved station data is missing" in captured.err
    assert "Traceback" not in captured.err


def test_freshness_aligns_long_timetable_rows(capsys):
    module = load("freshness_test", GEN / "maintenance" / "freshness.py")
    module.print_table([
        ("austria", "reviewed", "24", "current", "python3 -m gen.countries austria"),
        ("spain/renfe timetable", "official", "-", "index-missing/unreadable", "python3 -m gen.countries spain"),
    ])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert lines[1].index("python3") == lines[2].index("python3") == lines[0].index("command")
    assert lines[1].index("current") == lines[2].index("index-missing") == lines[0].index("status")
    assert "\t" not in "\n".join(lines)


def test_freshness_uses_actual_spanish_calendar_schema(tmp_path):
    import sqlite3
    module = load("freshness_calendar_test", GEN / "maintenance" / "freshness.py")
    db_path = tmp_path / "timetable.sqlite"
    with sqlite3.connect(db_path) as db:
        # Both Renfe and FGC writers name the JSON column `data`.
        db.executescript("""
            CREATE TABLE calendar(service_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE calendar_dates(service_id TEXT, date TEXT, exception_type TEXT);
        """)
        db.execute("INSERT INTO calendar VALUES (?, ?)",
                   ("weekday", '{"end_date":"20271231"}'))
        db.execute("INSERT INTO calendar_dates VALUES (?, ?, ?)",
                   ("weekday", "20271101", "1"))
    assert module.sqlite_calendar_end(db_path) == "20271231"
    with sqlite3.connect(db_path) as db:
        db.execute("DELETE FROM calendar")
    assert module.sqlite_calendar_end(db_path) == "20271101"


def test_sta_freshness_limit_is_ninety_days():
    module = load("freshness_sta_age_test", GEN / "maintenance" / "freshness.py")
    assert module.AGE_LIMITS["italy/sta"] == 90


def test_denmark_cache_mode_uses_saved_source_without_calling_live_api(tmp_path, monkeypatch, capsys):
    module = load("denmark_cache_test", GEN / "countries" / "denmark" / "generate.py")
    calls = []
    station = {
        "type": "node", "id": "8600001", "lat": 55.0, "lon": 12.0,
        "tags": {"name": "Station"}, "category": "denmark_all",
    }
    monkeypatch.setattr(module, "download_gtfs", lambda *, use_cache=False: calls.append(("source", use_cache)) or tmp_path / "saved.zip")
    monkeypatch.setattr(module, "build_nodes", lambda _path, _lookup=None: [station])
    monkeypatch.setattr(module, "validate_live_access", lambda *_args: calls.append(("api", True)))
    monkeypatch.setattr(module, "publish_nodes", lambda *_args: calls.append(("publish", True)))
    assert module.main(["--cache"]) == 0
    assert calls == [("source", True), ("publish", True), ("publish", True)]
    assert "saved Rejseplanen source" in capsys.readouterr().out


def test_denmark_cache_mode_fails_clearly_when_saved_source_is_missing(tmp_path, monkeypatch):
    module = load("denmark_missing_cache_test", GEN / "countries" / "denmark" / "generate.py")
    monkeypatch.setattr(module, "GTFS_ARCHIVE", tmp_path / "missing.zip")
    with pytest.raises(FileNotFoundError, match="Saved Rejseplanen GTFS archive is missing"):
        module.main(["--cache"])


def test_sweden_streams_and_aggregates_nonrail_stops(tmp_path, monkeypatch, capsys):
    module = load("sweden_generator_test", GEN / "countries" / "sweden" / "generate.py")
    monkeypatch.setattr(module, "load_exclusion_rules", lambda country: {})
    monkeypatch.setattr(module, "load_rename_id_rules", lambda country: {})
    source = tmp_path / "_stops.xml"
    source.write_text("""<PublicationDelivery xmlns="urn:test">
      <StopPlace><Name>Rail A</Name><Centroid><Location><Longitude>18.1</Longitude><Latitude>59.3</Latitude></Location></Centroid><TransportMode>rail</TransportMode><keyList><KeyValue><Key>rikshallplats</Key><Value>740000001</Value></KeyValue></keyList></StopPlace>
      <StopPlace><Name>Bus B</Name><Centroid><Location><Longitude>18.2</Longitude><Latitude>59.4</Latitude></Location></Centroid><TransportMode>bus</TransportMode><keyList><KeyValue><Key>rikshallplats</Key><Value>740000002</Value></KeyValue></keyList></StopPlace>
    </PublicationDelivery>""")
    output = tmp_path / "nodes.json"
    module.convert_from_xml(source, output, {})
    assert len(output.read_text().splitlines()) == 1
    captured = capsys.readouterr().out
    assert "Parsed 2 stop places; wrote 1 railway/metro stations" in captured
    assert "mode:bus=1" in captured
    assert "Skipping feature" not in captured


def test_switzerland_preserves_native_sloid_for_ojp_identity():
    switzerland = load("switzerland_sloid_test", GEN / "countries" / "switzerland" / "generate.py")
    nodes = switzerland.build_nodes({"features": [{
        "type": "Feature",
        "geometry": {"coordinates": [7.987, 46.319]},
        "properties": {
            "meansoftransport": "TRAIN",
            "designationofficial": "Brig",
            "number": "8501609",
            "sloid": "ch:1:sloid:1609",
        },
    }]}, {})
    assert nodes[0]["tags"]["sloid"] == "ch:1:sloid:1609"


def test_country_converters_reject_malformed_source_rows(tmp_path):
    netherlands = load("netherlands_generator_test", GEN / "countries" / "netherlands" / "generate.py")
    nl_source = tmp_path / "nl.csv"
    nl_source.write_text("code,name_long,geo_lat,geo_lng\nABC,Alpha,,4.0\n")
    with pytest.raises(ValueError, match="missing station ID, name, or coordinates"):
        netherlands.build_nodes(nl_source)

    uk = load("uk_generator_test", GEN / "countries" / "uk" / "generate.py")
    uk_source = tmp_path / "uk.json"
    uk_source.write_text(json.dumps([{"crsCode": "ABC", "stationName": "Alpha"}]))
    with pytest.raises(ValueError, match="is missing its ID, name, or coordinates"):
        uk.build_nodes(uk_source, {})

    from countries.germany.nodes import convert_from_json
    de_source = tmp_path / "de.json"
    de_source.write_text(json.dumps([{"id": "1", "name": "Alpha", "location": {}}]))
    with pytest.raises(ValueError, match="missing coordinates"):
        convert_from_json(de_source, tmp_path / "de-out.json", {}, {}, [])

    switzerland = load("switzerland_generator_test", GEN / "countries" / "switzerland" / "generate.py")
    with pytest.raises(ValueError, match="lacks meansoftransport"):
        switzerland.build_nodes({"features": [{
            "type": "Feature",
            "geometry": {"coordinates": [8.0, 47.0]},
            "properties": {},
        }]}, {})


def test_switzerland_includes_mixed_train_modes_without_nonrail_false_positives():
    switzerland = load("switzerland_mixed_modes_test", GEN / "countries" / "switzerland" / "generate.py")
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [8.802636, 46.172645]},
                 "properties": {"number": 8505470 + index, "designationofficial": "Locarno FART",
                                "meansoftransport": mode, "sloid": "ch:1:sloid:5470"}}
                for index, mode in enumerate(["BUS|TRAIN", "TRAIN|BUS", "BUS", "TRAINING", None])]
    nodes = switzerland.build_nodes({"features": features}, {})
    assert [node["id"] for node in nodes] == [8505470, 8505471]
    assert nodes[0]["tags"]["sloid"] == "ch:1:sloid:5470"


def test_italy_dispatches_rebuild_to_owning_module_with_dry_run(monkeypatch):
    module = load("italy_rebuild_dispatch_test", GEN / "countries" / "italy" / "generate.py")
    seen = []
    monkeypatch.setattr(module.reviewed_rebuild, "main", lambda argv: seen.append(argv) or 0)
    assert module.main(["rebuild", "rfi", "--dry-run"]) == 0
    assert seen == [["rfi", "--dry-run"]]


def test_reviewed_rebuild_cli_reports_dry_run_without_publishing(monkeypatch, capsys):
    from countries.italy.reviewed import rebuild as workflow
    calls = []
    def dry_rebuild(operator, *, dry_run):
        calls.append((operator, dry_run))
        return [{}], [{"status": "matched_name_difference"}]
    monkeypatch.setattr(workflow, "rebuild", dry_rebuild)
    monkeypatch.setattr("countries.italy.review.pending_review_rows", lambda _operator: [])
    assert workflow.main(["rfi", "--dry-run"]) == 0
    assert calls == [("rfi", True)]
    text = capsys.readouterr().out
    assert "RFI: would write 1 stations; 1 review items" in text
    assert "cache/italy/rfi/reports/audit.csv" in text


def test_austria_failed_refresh_preserves_mvo_and_station_output(tmp_path, monkeypatch):
    import requests
    from countries.austria import generate
    from countries.austria import sources
    paths = {
        name: tmp_path / name
        for name in ("DEFAULT_MVO_CACHE", "GEONETZ_FILTERED", "GEONETZ_ARCHIVE", "DEFAULT_RESOLUTION_CACHE")
    }
    for name, path in paths.items():
        path.write_text("old")
        owner = sources if name in {"GEONETZ_FILTERED", "GEONETZ_ARCHIVE"} else generate
        monkeypatch.setattr(owner, name, path)
    monkeypatch.setattr(generate,'_download_geonetz',lambda session, **kwargs:tmp_path/'geo')
    monkeypatch.setattr(generate,'load_geonetz_nodes',lambda *args:[])
    monkeypatch.setattr(generate,'download_mvo_snapshot',lambda *args, **kwargs:(_ for _ in ()).throw(requests.ConnectTimeout()))
    output=tmp_path/'nodes.json';output.write_text('original')
    with pytest.raises(SystemExit,match='Austria MVO source unavailable'):
        generate.main(['--output',str(output)])
    assert paths['DEFAULT_MVO_CACHE'].read_text()=='old'
    assert output.read_text()=='original'


def test_rfi_delta_reports_new_unreviewed_provider_rows(tmp_path,monkeypatch):
    from countries.italy import rfi
    (tmp_path/'nodes').mkdir()
    (tmp_path/'nodes/nodes-italy-rfi.json').write_text('')
    monkeypatch.setattr(rfi,'ROOT',tmp_path)
    monkeypatch.setattr(rfi,'provider_cache',lambda *args:tmp_path/'report.json')
    rfi.write_catalog_diff([{'id':'1339','name':'FONTAN SAORGE'},
                            {'id':'2378','name':'ROMA NOMENTANA LM'},
                            {'id':'99999','name':'New station'}])
    report=json.loads((tmp_path/'report.json').read_text())
    assert {row['id'] for row in report['added']}=={'2378','99999'}
    assert {row['id'] for row in report['known_outside_dataset']}=={'1339'}


def test_austria_cache_explicitly_reuses_validated_mvo(tmp_path, monkeypatch):
    from countries.austria import generate, sources
    cached = tmp_path / "mvo.zip"
    cached.write_bytes(b"cached")
    monkeypatch.setattr(generate, "DEFAULT_MVO_CACHE", cached)
    monkeypatch.setattr(generate, "_download_geonetz", lambda session, **kwargs: tmp_path / "geo")
    monkeypatch.setattr(generate, "load_geonetz_nodes", lambda *args: [])
    validated = []
    monkeypatch.setattr(sources, "_validate_mvo_archive", lambda path: validated.append(path))
    monkeypatch.setattr(generate, "download_mvo_snapshot", lambda *args: pytest.fail("cache must not download MVO"))
    monkeypatch.setattr(generate, "load_mvo_snapshot", lambda path: ([], []))
    monkeypatch.setattr(generate, "validate_mvo_wgs84", lambda rows: None)
    monkeypatch.setattr(generate, "ScottyResolver", lambda *args, **kwargs: None)
    monkeypatch.setattr(generate, "merge_catalogues", lambda *args: ([], {"added_count": 0, "unresolved_count": 0, "unresolved": []}))
    monkeypatch.setattr(generate, "publish_nodes", lambda *args: None)
    generate.main(["--cache", "--output", str(tmp_path / "out"), "--audit", str(tmp_path / "audit")])
    assert validated == [cached]


def test_italy_checked_rebuild_blocks_publication_with_new_review(tmp_path, monkeypatch, capsys):
    from countries.italy.reviewed import rebuild as module
    from countries.italy import review
    from common.io import ROOT
    original = ROOT / "nodes" / "nodes-italy-rfi.json"
    stamp = original.stat().st_mtime_ns
    monkeypatch.setattr(module, "rebuild", lambda operator, dry_run: ([{"id": 1}], [{}]))
    monkeypatch.setattr(review, "pending_review_rows", lambda operator: [
        {"id": "1429", "status": "matched_name_difference"}
    ])
    output, audit, rc = module.checked_rebuild("rfi")
    assert rc == 2
    assert original.stat().st_mtime_ns == stamp
    assert "The station file is unchanged" in capsys.readouterr().out


def test_italy_checked_rebuild_publishes_when_reviewed(tmp_path, monkeypatch):
    from countries.italy.reviewed import rebuild as module
    from countries.italy import review
    from common.io import ROOT
    calls = []
    monkeypatch.setattr(module, "rebuild", lambda operator, dry_run: ([{"id": 1}], [{}]))
    monkeypatch.setattr(review, "pending_review_rows", lambda operator: [])
    import common.io as io
    monkeypatch.setattr(io, "publish_nodes", lambda path, rows: calls.append((path, rows)))
    _, _, rc = module.checked_rebuild("rfi")
    assert rc == 0 and calls == [(ROOT / "nodes/nodes-italy-rfi.json", [{"id": 1}])]


def test_mvo_authenticated_catalogue_calls_use_bearer_and_current_query(tmp_path, monkeypatch):
    import requests
    from countries.austria import sources, settings
    from countries.austria.settings import MVO_DATASETS_URL, MVO_METADATA_URL
    assert "tagFilterModeInclusive=true" in MVO_DATASETS_URL
    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    class Session:
        def __init__(self): self.calls = []
        def post(self, url, **kw): return Response({"access_token": "test-token"})
        def get(self, url, **kw):
            self.calls.append((url, kw.get("headers", {})))
            if url == MVO_DATASETS_URL: return Response([{"id": 42, "nameDe": "Haltestellen (CSV)"}])
            if url == MVO_METADATA_URL.format(dataset_id="42"):
                return Response({"activeVersions": [{"year": "2026"}]})
            raise AssertionError(url)
    session = Session()
    monkeypatch.setenv("MVO_USERNAME", "dummy")
    monkeypatch.setenv("MVO_PASSWORD", "dummy")
    monkeypatch.setattr(sources, "_download_to_cache", lambda *args, **kw: tmp_path / "mvo.zip")
    monkeypatch.setattr(sources, "_cache_age", lambda path: "0 days")
    sources.download_mvo_snapshot(session)
    assert session.calls == [
        (MVO_DATASETS_URL, {"Authorization": "Bearer test-token"}),
        (MVO_METADATA_URL.format(dataset_id="42"), {"Authorization": "Bearer test-token"}),
    ]


def test_source_terms_manifest_covers_every_generated_category():
    from common.io import load_ndjson, ROOT
    import json
    payload = json.loads((ROOT / "docs/source-terms.json").read_text(encoding="utf-8"))
    categories = {row["category"] for path in (ROOT / "nodes").glob("nodes-*.json") for row in load_ndjson(path)}
    assert set(payload["datasets"]) == categories


def test_mvo_missing_credentials_fail_before_public_sample_request(monkeypatch):
    from countries.austria import sources
    monkeypatch.delenv("MVO_USERNAME", raising=False)
    monkeypatch.delenv("MVO_PASSWORD", raising=False)
    class Session:
        def get(self, *args, **kwargs): raise AssertionError("must not query sample")
    with pytest.raises(ValueError, match="registered account"):
        sources.download_mvo_snapshot(Session())


def test_mvo_partial_credentials_fail_closed(monkeypatch):
    from countries.austria import sources
    monkeypatch.setenv("MVO_USERNAME", "user")
    monkeypatch.delenv("MVO_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="must both be set"):
        sources.download_mvo_snapshot(None)


def test_geonetz_filtered_cache_is_atomic_and_reads_only_expected_members(tmp_path, monkeypatch):
    import io
    import zipfile
    from countries.austria import sources
    cache = tmp_path / 'austria'
    cache.mkdir()
    archive = cache / 'geonetz.zip'
    filtered = cache / 'filtered.json'
    monkeypatch.setattr(sources, 'AUSTRIA_CACHE', cache)
    monkeypatch.setattr(sources, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(sources, 'GEONETZ_ARCHIVE', archive)
    monkeypatch.setattr(sources, 'GEONETZ_FILTERED', filtered)
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, 'w') as z:
        z.writestr('any/OEBB_NETWORK.json', json.dumps({'features': [
            {'properties': {'STP_TYPE': 'railStation', 'EVA_NR': '8100001'}},
            {'properties': {'STP_TYPE': 'busStop', 'EVA_NR': '8100002'}},
        ]}))
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('nested/OEBB_NETWORK_GeoJSON.zip', inner_buffer.getvalue())
        z.writestr('../outside', 'should never extract')
    class NoNetwork:
        def get(self, *args, **kwargs):
            raise AssertionError('cache already exists')
    output = sources._download_geonetz(NoNetwork())
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row['EVA_NR'] for row in rows] == ['8100001']
    assert not (tmp_path / 'outside').exists()
    filtered.unlink()
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('something-else.txt', b'broken')
    with pytest.raises(ValueError, match='inner GeoJSON ZIP'):
        sources._download_geonetz(NoNetwork())
    assert not filtered.exists()


def test_austrian_unverified_mvo_rail_stops_show_names_and_action(capsys):
    from countries.austria.generate import report_unverified_mvo_stops
    report_unverified_mvo_stops({"unresolved": [
        {"ifopt_id": "at:42:123", "name": "Example Bahnhof", "reason": "no_unique_scotty_match"},
        {"ifopt_id": "at:42:124", "name": "Example Halt", "reason": "scotty_station_verification_failed"},
    ]})
    out = capsys.readouterr().out
    assert "2 MVO station records" in out
    assert "Example Bahnhof [at:42:123]" in out
    assert "Example Halt [at:42:124]" in out
    assert "no unique SCOTTY" in out
    assert "SCOTTY board verification failed" in out
    assert "They are not exclusions" in out
    assert "overrides/austria-unmapped-stations.csv" in out
    assert "review:" not in out
    assert ".json (" not in out


def test_austrian_no_unverified_candidates_no_extra_output(capsys):
    from countries.austria.generate import report_unverified_mvo_stops
    report_unverified_mvo_stops({"unresolved": []})
    assert capsys.readouterr().out == ""
