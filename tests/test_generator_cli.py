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
    module = load("italy_dispatch_test", GEN / "italy.py")
    seen = []
    monkeypatch.setitem(module.PROVIDERS, "fse", lambda argv=None: seen.append(argv) or 0)
    assert module.main(["generate", "fse"]) == 0
    assert seen == [[]]


def test_freshness_aligns_long_timetable_rows(capsys):
    module = load("freshness_test", GEN / "maintenance" / "freshness.py")
    module.print_table([
        ("austria", "heuristic", "24", "current", "python3 gen/austria.py"),
        ("spain/renfe timetable", "automated", "-", "index-missing/unreadable", "python3 gen/spain.py"),
    ])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert lines[1].index("python3") == lines[2].index("python3") == lines[0].index("command")
    assert lines[1].index("current") == lines[2].index("index-missing") == lines[0].index("status")
    assert "\t" not in "\n".join(lines)


def test_sweden_streams_and_aggregates_nonrail_stops(tmp_path, monkeypatch, capsys):
    module = load("sweden_generator_test", GEN / "sweden.py")
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


def test_old_country_converters_reject_malformed_source_rows(tmp_path):
    netherlands = load("netherlands_generator_test", GEN / "netherlands.py")
    nl_source = tmp_path / "nl.csv"
    nl_source.write_text("code,name_long,geo_lat,geo_lng\nABC,Alpha,,4.0\n")
    with pytest.raises(ValueError, match="missing station identity, name, or coordinates"):
        netherlands.build_nodes(nl_source)

    uk = load("uk_generator_test", GEN / "uk.py")
    uk_source = tmp_path / "uk.json"
    uk_source.write_text(json.dumps([{"crsCode": "ABC", "stationName": "Alpha"}]))
    with pytest.raises(ValueError, match="lacks identity, name, or coordinates"):
        uk.build_nodes(uk_source, {})

    germany = load("germany_generator_test", GEN / "germany.py")
    de_source = tmp_path / "de.json"
    de_source.write_text(json.dumps([{"id": "1", "name": "Alpha", "location": {}}]))
    with pytest.raises(ValueError, match="missing coordinates"):
        germany.convert_from_json(de_source, tmp_path / "de-out.json", {}, {}, [])

    switzerland = load("switzerland_generator_test", GEN / "switzerland.py")
    with pytest.raises(ValueError, match="lacks meansoftransport"):
        switzerland.build_nodes({"features": [{
            "type": "Feature",
            "geometry": {"coordinates": [8.0, 47.0]},
            "properties": {},
        }]}, {})
