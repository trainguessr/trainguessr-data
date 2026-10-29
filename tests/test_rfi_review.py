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


def test_french_cross_border_reviews_guard_native_names_separately_from_display_names():
    import pytest
    from common.config import load_country_config
    from countries.italy.reviewed.classification import classify_reviewed

    names = {"730": "BREIL SUR ROYA", "1339": "FONTAN SAORGE", "1511": "LA BRIGUE",
             "2780": "ST.DALMAS DE TENDE", "2826": "TENDE", "3050": "VIEVOLA"}
    source = {uid: {"id": uid, "name": name} for uid, name in names.items()}
    config = load_country_config("italy")
    output, audit = classify_reviewed("rfi", source, [], config, {})
    assert output == []
    assert len(audit) == 6
    assert {row["status"] for row in audit} == {"handled_by_other_provider"}
    assert next(row for row in audit if row["id"] == "1339")["reviewed_name"] == "Fontan - Saorge"
    source["1339"]["name"] = "Different station"
    with pytest.raises(ValueError, match="stale reviewed override"):
        classify_reviewed("rfi", source, [], config, {})


def test_rfi_freight_exclusion_keeps_reviewed_display_and_guards_native_identity():
    from common.config import load_country_config, load_exclusion_rules
    from countries.italy.reviewed.classification import classify_reviewed
    config = load_country_config("italy")
    rules = load_exclusion_rules("italy", "rfi")
    source = {"2378": {"id": "2378", "name": "ROMA NOMENTANA LM"}}
    output, audit = classify_reviewed("rfi", source, [], config, rules)
    assert output == []
    assert audit[0]["status"] == "excluded"
    source["2378"]["name"] = "Roma Nomentana"
    with pytest.raises(ValueError, match="stale reviewed override"):
        classify_reviewed("rfi", source, [], config, rules)
