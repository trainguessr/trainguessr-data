"""Reviewed VT decisions preserve identity and isolated publication candidates."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from reconcile.italy.viaggiatreno.publication import apply_decisions


def test_vt_review_applies_explicit_ids_without_mutating_source_or_decisions():
    nodes = [{
        "type": "node", "id": 1, "lat": 45.0, "lon": 9.0,
        "tags": {"name": "Central", "viaggiatreno_station_id": "S00001", "nested": {"values": [1]}},
    }, {
        "type": "node", "id": 2, "lat": 45.1, "lon": 9.1,
        "tags": {"name": "East", "viaggiatreno_station_id": "S00002"},
    }]
    decisions = {"1": {"action": "accept", "vt_station_id": "S12345", "vt_name": "VT Central"},
                 "2": {"action": "reject"}}
    original = json.dumps([nodes, decisions], sort_keys=True)
    candidate = apply_decisions(nodes, decisions)
    assert candidate[0]["tags"]["viaggiatreno_station_id"] == "S12345"
    assert candidate[0]["tags"]["viaggiatreno_name"] == "VT Central"
    assert "viaggiatreno_station_id" not in candidate[1]["tags"]
    candidate[0]["tags"]["nested"]["values"].append(2)
    assert json.dumps([nodes, decisions], sort_keys=True) == original


def test_invalid_accepted_vt_identity_is_rejected():
    with pytest.raises(SystemExit, match="Invalid accepted VT ID"):
        apply_decisions([{"id": 1, "tags": {"name": "Central"}}], {
            "1": {"action": "accept", "vt_station_id": "12345"},
        })
