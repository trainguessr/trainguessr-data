from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


def test_sweden_streams_and_aggregates_nonrail_stops(tmp_path, monkeypatch, capsys):
    module = load("sweden_generator_test", GEN / "sweden.py")
    monkeypatch.setattr(module, "load_excluded_ids", lambda country: set())
    monkeypatch.setattr(module, "load_rename_id_map", lambda country: {})
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
