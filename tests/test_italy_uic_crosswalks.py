from __future__ import annotations

import copy
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson  # noqa: E402
from countries.italy.reviewed.crosswalks import (  # noqa: E402
    apply_station_uic_crosswalks,
    load_station_uic_crosswalks,
)


EXPECTED = {
    ("fn", "S01146"): ("", "8320005"),
    ("fn", "S01139"): ("", "8325635"),
    ("fn", "S01138"): ("", "8319371"),
    ("fn", "S01137"): ("", "8325631"),
    ("rfi", "766"): ("S01031", "8301031"),
    ("rfi", "1393"): ("S01030", "8301030"),
    ("rfi", "2994"): ("S01205", "8301205"),
    ("rfi", "1492"): ("S01204", "8301204"),
    ("rfi", "451"): ("S01203", "8301203"),
    ("rfi", "2974"): ("S01206", "8301206"),
    ("rfi", "2912"): ("S02038", "8302038"),
    ("rfi", "2440"): ("S02044", "8302044"),
    ("rfi", "3025"): ("S02430", "8302061"),
    ("rfi", "683"): ("S05043", "8305043"),
    ("rfi", "685"): ("S02026", "8302026"),
    ("rfi", "1356"): ("S02011", "8302011"),
}


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _nodes(operator: str) -> list[dict]:
    return load_ndjson(ROOT / "nodes" / f"nodes-italy-{operator}.json")


def test_reviewed_csv_keeps_exact_provider_ids_and_accepted_stop_pairs():
    rows = load_station_uic_crosswalks()
    actual = {}
    for row in rows:
        provider_id = row["fn_station_id"] if row["operator"] == "fn" else row["rfi_station_id"]
        actual[(row["operator"], provider_id)] = (row["viaggiatreno_station_id"], row["uic_ref"])
    assert actual == EXPECTED
    assert len(rows) == 16

    # Busto Arsizio Nord and Busto Arsizio FS are distinct provider records.
    assert actual[("fn", "S01137")][1] != actual[("rfi", "766")][1]
    # Varese FS is mapped; nearby Varese Nord remains a separate FN record.
    assert actual[("rfi", "2994")][1] == "8301205"
    assert all(row["granularity"] == "stop" for row in rows)


def test_register_preserves_stop_level_source_evidence():
    rows = load_station_uic_crosswalks()
    for row in rows:
        assert row["uic_location_type"] == 0
        assert row["uic_ref"] == row["uic_original_stop_id"] == row["uic_didok"]
        assert row["uic_parent_station"] == f"Parent{row['uic_ref']}"
        assert row["uic_platform_code"] == ""
        assert not row["uic_ref"].startswith("Parent")
        if row["oebb_station_id"]:
            expected_source = (
                "rfi-vt+oebb-hafas+reviewed-station-register:RJ83:2026-11-02"
                if row["previous_uic_ref"] else "rfi-vt+oebb-hafas:RJ83:2026-11-02"
            )
            assert row["source_tag"] == expected_source
            assert row["hafas_gid"] == f"U×{row['uic_ref']}"
            assert int(row["hafas_crd_x"]) > 0
            assert int(row["hafas_crd_y"]) > 0
            assert row["regione_stop_lat_raw"] == row["regione_stop_lon_raw"] == ""
        else:
            assert row["source_tag"] == "regione:j5jz-kvqn+sbb-otd-gtfs:20261024"


@pytest.mark.parametrize("operator", ["fn", "rfi"])
def test_crosswalks_add_unchanged_runtime_tags_to_the_exact_node(operator):
    rows = load_station_uic_crosswalks()
    nodes = _nodes(operator)
    before = copy.deepcopy(nodes)
    applied = apply_station_uic_crosswalks(operator, nodes, rows)
    expected_ids = {provider_id for (kind, provider_id) in EXPECTED if kind == operator}
    assert applied == expected_ids
    for row in rows:
        if row["operator"] != operator:
            continue
        node_id = row["fn_station_id"] if operator == "fn" else row["rfi_station_id"]
        target = [node for node in nodes if str(node["id"]) == node_id]
        assert len(target) == 1
        tags = target[0]["tags"]
        assert tags["uic_ref"] == row["uic_ref"]
        assert tags["uic_name"] == row["uic_name"]
        assert tags["uic_granularity"] == "stop"
        assert tags["uic_crosswalk_source"] == row["source_tag"]
        original = next(node for node in before if str(node["id"]) == node_id)
        previous_uic = row["previous_uic_ref"]
        if previous_uic:
            if original["tags"].get("uic_ref") == previous_uic:
                assert original["tags"].get("uic_crosswalk_previous_ref") is None
            else:
                assert original["tags"].get("uic_ref") == row["uic_ref"]
                assert original["tags"].get("uic_crosswalk_previous_ref") == previous_uic
            assert tags["uic_crosswalk_previous_ref"] == previous_uic
            assert tags["uic_crosswalk_previous_name"] == row["previous_uic_name"]
            assert tags["uic_crosswalk_previous_source"] == row["previous_uic_source"]
        else:
            assert original["tags"].get("uic_ref") in {None, row["uic_ref"]}


def test_an_additional_reviewed_mapping_is_accepted(tmp_path):
    rows = load_station_uic_crosswalks()
    extra = dict(rows[0])
    extra.update({
        "fn_station_id": "S99999",
        "expected_node_name": "Example Station",
        "regione_stop_id": "S99999",
        "regione_stop_name": "Example Station",
        "uic_ref": "8999999",
        "uic_name": "Example Station",
        "uic_stop_lat": "45.0",
        "uic_stop_lon": "9.0",
        "uic_parent_station": "Parent8999999",
        "uic_original_stop_id": "8999999",
        "uic_didok": "8999999",
    })
    rows.append(extra)
    path = tmp_path / "crosswalks.csv"
    _write_csv(path, rows)
    assert len(load_station_uic_crosswalks(path)) == 17


@pytest.mark.parametrize("field,value", [
    ("rfi_station_id", ""),
    ("viaggiatreno_station_id", ""),
    ("viaggiatreno_station_id", "S99999"),
])
def test_rfi_mapping_requires_both_exact_ids_and_the_region_id(field, value, tmp_path):
    rows = load_station_uic_crosswalks()
    target = next(row for row in rows if row["operator"] == "rfi")
    target[field] = value
    path = tmp_path / "crosswalks.csv"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="exact RFI and ViaggiaTreno IDs|ViaggiaTreno ID must match"):
        load_station_uic_crosswalks(path)


@pytest.mark.parametrize("operator", ["fn", "rfi"])
def test_duplicate_provider_nodes_block_mapping(operator):
    rows = load_station_uic_crosswalks()
    nodes = _nodes(operator)
    row = next(row for row in rows if row["operator"] == operator)
    node_id = row["fn_station_id"] if operator == "fn" else row["rfi_station_id"]
    nodes.append(copy.deepcopy(next(node for node in nodes if str(node["id"]) == node_id)))
    with pytest.raises(ValueError, match="found 2 matching records"):
        apply_station_uic_crosswalks(operator, nodes, rows)


def test_rfi_mapping_needs_exact_rfi_and_viaggiatreno_ids_on_one_node():
    rows = load_station_uic_crosswalks()
    nodes = _nodes("rfi")
    target = next(node for node in nodes if str(node["id"]) == "766")
    target["tags"].pop("viaggiatreno_station_id")
    with pytest.raises(ValueError, match="check station ID 766"):
        apply_station_uic_crosswalks("rfi", nodes, rows)


def test_rj83_crosswalks_are_finite_exact_stop_pairs_with_source_gid_and_coordinates():
    rows = [row for row in load_station_uic_crosswalks() if row["oebb_station_id"]]
    assert {
        (row["rfi_station_id"], row["viaggiatreno_station_id"], row["oebb_station_id"], row["hafas_gid"])
        for row in rows
    } == {
        ("2912", "S02038", "8300101", "U×8302038"),
        ("2440", "S02044", "8300113", "U×8302044"),
        ("3025", "S02430", "8300120", "U×8302061"),
        ("683", "S05043", "8300217", "U×8305043"),
        ("685", "S02026", "8300084", "U×8302026"),
        ("1356", "S02011", "8300089", "U×8302011"),
    }
    assert all(row["granularity"] == "stop" for row in rows)
    assert all("platform" in row["review_note"].casefold() for row in rows)


def test_rj83_reviewed_mappings_preserve_conflicting_osm_uic_observations():
    rows = load_station_uic_crosswalks()
    nodes = _nodes("rfi")
    previous = {
        "685": ("8300084", "Bolzano/Bozen"),
        "1356": ("8300089", "Fortezza/Franzensfeste"),
    }
    for station_id, (old_uic, old_name) in previous.items():
        tags = next(row for row in nodes if str(row["id"]) == station_id)["tags"]
        tags["uic_ref"] = old_uic
        tags["uic_name"] = old_name
        for key in ("uic_crosswalk_previous_ref", "uic_crosswalk_previous_name", "uic_crosswalk_previous_source"):
            tags.pop(key, None)
    apply_station_uic_crosswalks("rfi", nodes, rows)
    expected = {
        "685": ("8302026", "8300084", "Bolzano/Bozen"),
        "1356": ("8302011", "8300089", "Fortezza/Franzensfeste"),
    }
    for station_id, (expected_uic, old_uic, old_name) in expected.items():
        node = next(row for row in nodes if str(row["id"]) == station_id)
        tags = node["tags"]
        assert tags["uic_ref"] == expected_uic
        assert tags["uic_crosswalk_previous_ref"] == old_uic
        assert tags["uic_crosswalk_previous_name"] == old_name
        assert tags["uic_crosswalk_previous_source"] == "osm-node-tags:uic_ref"
    apply_station_uic_crosswalks("rfi", nodes, rows)


def test_rj83_reviewed_aliases_do_not_collapse_neighboring_stations():
    rows = load_station_uic_crosswalks()
    by_rfi = {row["rfi_station_id"]: row for row in rows if row["operator"] == "rfi"}
    assert by_rfi["685"]["uic_ref"] == "8302026"
    assert "Bolzano Sud" in by_rfi["685"]["review_note"]
    assert by_rfi["683"]["uic_ref"] == "8305043"
    assert "8305046" in by_rfi["683"]["review_note"]
    nodes = _nodes("rfi")
    bolzano_sud = next(row for row in nodes if str(row["id"]) == "687")
    bologna_av = next(row for row in nodes if str(row["id"]) == "942")
    assert bolzano_sud["tags"]["uic_ref"] == "8302226"
    assert bologna_av["tags"].get("uic_ref") is None


def test_rj83_crosswalk_rejects_modified_native_gid(tmp_path):
    rows = load_station_uic_crosswalks()
    target = next(row for row in rows if row["rfi_station_id"] == "2912")
    target["hafas_gid"] = "U×8300101"
    path = tmp_path / "crosswalks.csv"
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="HAFAS must publish this exact UIC alias"):
        load_station_uic_crosswalks(path)


def test_existing_uic_conflict_blocks_mapping():
    rows = load_station_uic_crosswalks()
    nodes = _nodes("fn")
    target = next(node for node in nodes if str(node["id"]) == "S01146")
    target["tags"]["uic_ref"] = "8325635"
    with pytest.raises(ValueError, match="already has a different UIC ID"):
        apply_station_uic_crosswalks("fn", nodes, rows)


def test_changed_station_name_blocks_mapping():
    rows = load_station_uic_crosswalks()
    nodes = _nodes("fn")
    target = next(node for node in nodes if str(node["id"]) == "S01146")
    target["tags"]["name"] = "Different Station"
    with pytest.raises(ValueError, match="check the name for station ID S01146"):
        apply_station_uic_crosswalks("fn", nodes, rows)
