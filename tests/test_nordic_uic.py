from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))
from countries.norway import generate as norway
from countries.sweden import generate as sweden


def _stop(number: int, uic: str) -> dict:
    return {"id": f"NSR:StopPlace:{number}", "topographicPlaceRef": {"ref": "KVE:TopographicPlace:0301"}, "name": f"Stop {number}", "transportMode": "RAIL",
            "centroid": {"location": {"latitude": 60.0, "longitude": 10.0 + number}},
            "keyList": {"keyValue": [{"key": "uicCode", "value": uic}]}}


def test_norway_keeps_only_unique_published_uic_codes() -> None:
    nodes = {node["id"]: node["tags"] for node in norway.build_nodes(
        [_stop(1, "7600100"), _stop(2, "7600200"), _stop(3, "7600200"), _stop(4, "76x")])}

    assert nodes["NSR:StopPlace:1"]["uic_ref"] == "7600100"
    assert not any("uic_ref" in nodes[f"NSR:StopPlace:{n}"] for n in (2, 3, 4))


def _binding(uopid: str, location: str) -> dict:
    return {"uopid": {"value": uopid},
            "location": {"value": f"http://data.europa.eu/949/primaryLocation/{location}"}}


def test_sweden_maps_signatures_to_one_rinf_location() -> None:
    codes = sweden.uic_by_signature([
        _binding("SEMc", "SE02611"), _binding("SEAb", "SE00001"), _binding("SEAB", "SE00002"),
        _binding("SEX", "EU00239"),
    ])

    assert codes == {"MC": "7402611"}


def test_norway_sends_stops_abroad_to_lookup_by_entur_municipality() -> None:
    home = {**_stop(1, "7600100"), "topographicPlaceRef": {"ref": "KVE:TopographicPlace:0301"}}
    abroad = {**_stop(2, "7401318"), "topographicPlaceRef": {"ref": "LAN:TopographicPlace:1480"}}
    lookup: list = []
    nodes = norway.build_nodes([home, abroad], lookup)

    assert [node["id"] for node in nodes] == ["NSR:StopPlace:1"]
    assert [row["id"] for row in lookup] == ["NSR:StopPlace:2"]
    assert lookup[0]["tags"]["uic_ref"] == "7401318"
