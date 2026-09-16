from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


GEN = Path(__file__).parents[1] / "gen"
sys.path.insert(0, str(GEN))
MODULE = GEN / "countries" / "italy" / "sta.py"
SPEC = importlib.util.spec_from_file_location("italy_sta_generator", MODULE)
sta = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sta)


def test_station_code_page_extracts_both_pairs():
    raw = b"""
    <table>
      <tr><th>Station</th><th>Code</th><th>Station</th><th>Code</th></tr>
      <tr><td>Malles/Mals</td><td>54</td><td>Naturno/Naturns</td><td>43</td></tr>
    </table>
    """
    assert sta.parse_station_code_page(raw) == [
        {"name": "Malles/Mals", "ticket_code": "54"},
        {"name": "Naturno/Naturns", "ticket_code": "43"},
    ]


def test_stopfinder_preserves_provider_owned_id_and_coordinates():
    raw = b"""<?xml version="1.0"?>
    <itdRequest>
      <odvNameElem stateless="100123" objectName="Malles/Mals"
                   x="10.54123" y="46.68876"/>
    </itdRequest>"""
    assert sta.parse_stopfinder(raw) == [{
        "id": "100123",
        "name": "Malles/Mals",
        "x": "10.54123",
        "y": "46.68876",
    }]


def test_catalogue_aliases_strip_country_and_split_bilingual_names():
    assert sta._aliases("Naturno/Naturns") == ["Naturno", "Naturns"]
    assert sta._aliases("Abfaltersbach (Austria)") == ["Abfaltersbach"]


def test_resolver_accepts_exact_sta_railway_label_not_generic_station_text():
    candidates = [
        {"id": "bus", "name": "Naturno, Via Stazione"},
        {"id": "rail", "name": "Stazione di Naturno"},
    ]
    match, reason = sta._resolve_candidates("Naturno/Naturns", candidates)
    assert match["id"] == "rail"
    assert reason == "exact_railway_label"


def test_resolver_rejects_fuzzy_and_ambiguous_railway_candidates():
    assert sta._resolve_candidates(
        "Malles/Mals",
        [{"id": "1", "name": "Malles, centro"}],
    )[0] is None
    assert sta._resolve_candidates(
        "Trento/Trient",
        [
            {"id": "1", "name": "Trento, Stazione di Trento"},
            {"id": "2", "name": "Stazione di Trento"},
        ],
    )[0] is None


def test_resolver_accepts_exact_alias_without_station_word():
    match, reason = sta._resolve_candidates(
        "Ponte Adige/Sigmundskron",
        [{"id": "66003067", "name": "Ponte Adige"}],
    )
    assert match["id"] == "66003067"
    assert reason == "exact_alias"


def test_resolver_accepts_sta_compound_railway_label_with_exact_first_component():
    match, reason = sta._resolve_candidates(
        "Spondigna/Spondinig",
        [{"id": "66000075", "name": "Stazione di Spondigna - Prato"}],
    )
    assert match["id"] == "66000075"
    assert reason == "exact_railway_label"

    match, reason = sta._resolve_candidates(
        "Sluderno/Schluderns",
        [{"id": "66000047", "name": "Sluderno, Stazione di Sluderno - Glorenza"}],
    )
    assert match["id"] == "66000047"


def test_resolver_does_not_accept_alias_as_arbitrary_station_label_prefix():
    match, _ = sta._resolve_candidates(
        "Plaus",
        [{"id": "x", "name": "Stazione di Plaus Centro"}],
    )
    assert match is None


def test_write_nodes_fails_closed_when_vinschgau_identity_is_incomplete(monkeypatch):
    import pytest
    monkeypatch.setattr(sta, "_read_nodes", lambda path: [])
    with pytest.raises(ValueError, match="exact STA identity is missing"):
        sta.write_nodes([{
            "id": "66000171", "name": "Naturno, Stazione di Naturno",
            "lat": "46", "lon": "11", "ticket_code": "43",
            "source_name": "Naturno/Naturns",
        }])


def test_write_nodes_fails_closed_when_complete_vinschgau_has_missing_coordinates(monkeypatch):
    import pytest
    monkeypatch.setattr(sta, "_read_nodes", lambda path: [])
    rows = [{
        "id": f"sta-{code}", "name": f"Station {code}",
        "lat": "" if code == "43" else "46", "lon": "11",
        "ticket_code": code, "source_name": f"Station {code}",
    } for code in sorted(sta.VINSCHGAU_STA_TICKET_CODES, key=int)]
    with pytest.raises(ValueError, match="provider coordinates are missing"):
        sta.write_nodes(rows)


def _node(node_id, name):
    return {"type": "node", "id": node_id, "lat": 1.0, "lon": 2.0,
            "tags": {"name": name}, "category": "test"}


def test_classification_keeps_only_vinschgau_block_as_sta_nodes():
    rows = [
        {"id":"v","name":"Naturno, Stazione di Naturno","lat":"1","lon":"2","ticket_code":"43","source_name":"Naturno/Naturns"},
        {"id":"r","name":"Trento, Stazione di Trento","lat":"","lon":"","ticket_code":"32","source_name":"Trento/Trient"},
        {"id":"a","name":"Sillian, Stazione di Sillian","lat":"","lon":"","ticket_code":"66","source_name":"Sillian (Austria)"},
    ]
    native, mapped, unmapped = sta.classify_rows(
        rows, [_node(2912, "Trient - Trento")], [_node(8100142, "Sillian")])
    assert [x["id"] for x in native] == ["v"]
    assert [(x["id"], p, n["id"]) for x,p,n in mapped] == [
        ("r","rfi",2912), ("a","oebb",8100142)]
    assert unmapped == []


def test_crosswalk_requires_unique_exact_complete_alias_set():
    row = {"source_name":"Bolzano/Bozen"}
    assert sta._unique_existing_node(row, [_node(685,"Bozen - Bolzano")])["id"] == 685
    assert sta._unique_existing_node(row, [_node(687,"Bolzano Sud - Bozen Süd")]) is None
    assert sta._unique_existing_node(row, [_node(1,"Bozen - Bolzano"),_node(2,"Bolzano - Bozen")]) is None


def test_augmentation_adds_sta_identity_without_replacing_native_id():
    nodes=[_node(2912,"Trient - Trento")]
    row={"id":"66000662","name":"Trento, Stazione di Trento"}
    out=sta._augment_nodes(nodes,[(row,"rfi",nodes[0])],"rfi")
    assert out[0]["id"] == 2912
    assert out[0]["tags"]["sta_station_id"] == "66000662"
    assert out[0]["tags"]["sta_station_name"] == "Trento, Stazione di Trento"


def test_resolver_accepts_exact_compound_catalogue_components_from_live_sta():
    cases = [
        ("Monguelfo-Casies/Welsberg-Gsies", "66001922", "Stazione di Monguelfo - Casies"),
        ("Perca-Plan de Corones/Percha-Kronplatz", "66001891", "Stazione di Perca - Plan de Corones"),
        ("Egna-Termeno/Neumarkt-Tramin", "66000696", "Stazione di Egna - Termeno"),
        ("Terlano-Andriano/Terlan-Andrian", "66000454", "Stazione di Terlano - Andriano"),
        ("Lana-Postal/Burgstall", "66002294", "Stazione di Lana - Postal"),
        ("Valdaora-Anterselva/Olang-Antholz", "66001899", "Stazione di Valdaora - Anterselva"),
        ("Magrè-Cortaccia/Magreid-Kurtatsch", "66000679", "Stazione di Magrè - Cortaccia"),
        ("Versciaco-Elmo/Vierschach-Helm", "66002765", "Stazione di Versciaco - Elmo"),
        ("Vipiteno-Val di Vizze /Sterzing-Pfitsch", "66001393", "Stazione di Vipiteno - Val di Vizze"),
    ]
    for source, provider_id, provider_name in cases:
        match, reason = sta._resolve_candidates(
            source, [{"id": provider_id, "name": provider_name, "x": "1", "y": "2"}])
        assert match["id"] == provider_id, source
        assert reason == "exact_railway_label"


def test_resolver_selects_exact_railway_candidate_among_same_place_results():
    match, reason = sta._resolve_candidates(
        "Villa Bassa-Braies/Niederdorf-Prags",
        [
            {"id": "bus", "name": "Villabassa, Piazza Von Kurz"},
            {"id": "rail", "name": "Villabassa, Stazione di Villabassa - Braies"},
        ],
    )
    assert match["id"] == "rail"
    assert reason == "exact_railway_label"


def test_reviewed_sta_exceptions_require_exact_provider_id_and_name():
    cases = [
        ("Mittewald an der Drau (Austria)", "66002976", "Stazione di Mittewald"),
        ("Gries (Austria)", "66007139", "Gries am Brenner, Stazione di Gries a. Br."),
        ("St. Jodok (Austria)", "66007138", "St. Jodok a. Br. Bahnhaltestelle"),
        ("Steinach in Tirol (Austria)", "66000659", "Stazione di Steinach a. Br."),
        ("Matrei (Austria)", "66001375", "Stazione di Matrei a. Br."),
    ]
    for source, provider_id, provider_name in cases:
        match, reason = sta._resolve_candidates(
            source, [{"id": provider_id, "name": provider_name, "x": "1", "y": "2"}])
        assert match["id"] == provider_id
        assert reason == "reviewed_exact_provider_exception"

        match, _ = sta._resolve_candidates(
            source, [{"id": provider_id, "name": provider_name + " changed", "x": "1", "y": "2"}])
        assert match is None


def test_reviewed_exceptions_do_not_guess_bad_or_missing_live_candidates():
    for source, candidates in [
        ("Patsch (Austria)", [{"id":"66000019","name":"Patscheid"}]),
        ("Innsbruck HBF (Austria)", [{"id":"66007175","name":"Hauptbahnhof S+U"}]),
        ("Unterberg-Stefansbrücke (Austria)", []),
        ("Merano-Maia Bassa/Meran-Untermais",
         [{"id":"66000301","name":"Fermata autobus a lunga percorrenza Merano Maia Bassa"}]),
    ]:
        match, _ = sta._resolve_candidates(source, candidates)
        assert match is None


def test_query_aliases_add_railway_search_terms_without_changing_identity_aliases():
    assert sta._aliases("Bolzano/Bozen") == ["Bolzano", "Bozen"]
    queries = sta._query_aliases("Bolzano/Bozen")
    assert queries == ["Bolzano", "Bozen", "Bolzano Stazione", "Bozen Bahnhof"]
    assert sta._catalogue_aliases("Bolzano/Bozen") == {"bolzano", "bozen"}


def test_query_aliases_cover_all_six_bad_live_stopfinder_searches():
    expected = {
        "Bolzano Sud/Bozen Süd": "Bolzano Sud Stazione",
        "Patsch (Austria)": "Patsch Bahnhof",
        "Innsbruck HBF (Austria)": "Innsbruck Hauptbahnhof",
        "Unterberg-Stefansbrücke (Austria)": "Stefansbrücke Bahnhof",
        "Merano-Maia Bassa/Meran-Untermais": "Merano Maia Bassa Stazione",
    }
    for source, query in expected.items():
        assert query in sta._query_aliases(source)


def test_exact_id_coordinate_lookup_uses_native_stop_id(monkeypatch):
    seen = {}
    def fake_download(url, params):
        seen.update(params)
        return b"<itdRequest/>"
    monkeypatch.setattr(sta, "_download", fake_download)
    monkeypatch.setattr(sta, "parse_stopfinder", lambda raw: [])
    _, rows = sta.stopfinder_by_id("66000171")
    assert seen["type_sf"] == "stopID"
    assert seen["name_sf"] == "66000171"
    assert rows == []


def test_write_nodes_allows_partial_non_vinschgau_augmentation(monkeypatch, tmp_path):
    rfi = [_node(2912, "Trient - Trento")]
    oebb = []
    monkeypatch.setattr(sta, "RFI_NODES", tmp_path / "rfi.json")
    monkeypatch.setattr(sta, "OEBB_NODES", tmp_path / "oebb.json")
    monkeypatch.setattr(sta, "ROOT", tmp_path)
    monkeypatch.setattr(sta, "_read_nodes",
                        lambda path: rfi if path.name == "rfi.json" else oebb)
    written = {}
    monkeypatch.setattr(sta, "_atomic_write_ndjson",
                        lambda path, rows: written.__setitem__(path.name, rows))

    rows = [{
        "id": f"sta-{code}", "name": f"Station {code}",
        "lat": "46", "lon": "11", "ticket_code": code,
        "source_name": f"Station {code}",
    } for code in sorted(sta.VINSCHGAU_STA_TICKET_CODES, key=int)]
    rows += [
        {"id":"66000662","name":"Trento, Stazione di Trento","lat":"46","lon":"11",
         "ticket_code":"32","source_name":"Trento/Trient"},
        {"id":"unmapped","name":"Some exact STA station","lat":"46","lon":"11",
         "ticket_code":"35","source_name":"No matching RFI/OEBB node"},
    ]
    _, _, _, stats = sta.write_nodes(rows)
    assert stats == {
        "sta_nodes": 17, "rfi_augmented": 1, "oebb_augmented": 0,
        "resolved_but_unmapped": 1,
    }
    assert written["rfi.json"][0]["id"] == 2912
    assert written["rfi.json"][0]["tags"]["sta_station_id"] == "66000662"
    assert len(written["nodes-italy-sta.json"]) == 17


def test_atomic_write_ndjson_replaces_only_after_temp_write(monkeypatch, tmp_path):
    target = tmp_path / "nodes.json"
    target.write_text("old\n")
    calls = []
    def fake_write(path, rows):
        calls.append(("write", path.name))
        path.write_text("new\n")
    real_replace = sta.os.replace
    def fake_replace(src, dst):
        calls.append(("replace", src.name, dst.name))
        real_replace(src, dst)
    monkeypatch.setattr(sta, "write_ndjson", fake_write)
    monkeypatch.setattr(sta.os, "replace", fake_replace)
    sta._atomic_write_ndjson(target, [{"id": 1}])
    assert target.read_text() == "new\n"
    assert calls[0][0] == "write"
    assert calls[1][0] == "replace"


def test_native_sta_nodes_use_official_bilingual_catalogue_name(monkeypatch, tmp_path):
    monkeypatch.setattr(sta, "RFI_NODES", tmp_path / "rfi.json")
    monkeypatch.setattr(sta, "OEBB_NODES", tmp_path / "oebb.json")
    monkeypatch.setattr(sta, "ROOT", tmp_path)
    monkeypatch.setattr(sta, "_read_nodes", lambda path: [])
    written = {}
    monkeypatch.setattr(sta, "_atomic_write_ndjson",
                        lambda path, rows: written.__setitem__(path.name, rows))
    rows = [{
        "id": f"sta-{code}", "name": f"Localized provider label {code}",
        "lat": "46", "lon": "11", "ticket_code": code,
        "source_name": f"Italiano {code}/Deutsch {code}",
    } for code in sorted(sta.VINSCHGAU_STA_TICKET_CODES, key=int)]
    sta.write_nodes(rows)
    node = written["nodes-italy-sta.json"][0]
    assert "/" in node["tags"]["name"]
    assert node["tags"]["sta_station_name"].startswith("Localized provider label")
