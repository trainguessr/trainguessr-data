"""Provider ID joins are independent of labels, geography and train numbers."""
from copy import deepcopy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from countries.italy.reviewed.station_identifiers import index_station_identifiers, apply_station_identifiers


def source(**changes):
    return dict(id="20950", country="IT", is_city="f", same_as="", name="Different spelling",
                trenitalia_rtvt_id="S05319", uic="8305319", obb_id="8300229", db_id="8300229", **changes)


def node(vt="S05319", **tags):
    return {"id": 2516, "category": "italy_rfi", "tags": dict(name="S.GIOVANNI", viaggiatreno_station_id=vt, **tags)}


def test_exact_source_ids_enrich_any_service_without_changing_existing_alias():
    nodes = [node(uic_ref="8309999"), node("S99999")]
    assert apply_station_identifiers(nodes, index_station_identifiers([source()]), "revision") == 1
    assert nodes[0]["tags"]["oebb_station_id"] == "8300229"
    assert nodes[0]["tags"]["trainline_uic_ref"] == "8305319"
    assert nodes[0]["tags"]["uic_ref"] == "8309999"
    assert "oebb_station_id" not in nodes[1]["tags"]


def test_city_alias_duplicate_vt_or_reused_foreign_id_cannot_prove_mapping():
    row = source()
    for bad in [dict(row, is_city="t"), dict(row, same_as="another"), dict(row, country="FR")]:
        assert not index_station_identifiers([bad])
    assert not index_station_identifiers([row, deepcopy(row)])
    assert not index_station_identifiers([row, dict(row, id="20951", trenitalia_rtvt_id="S05313")])
    nodes = [node(), node()]
    assert apply_station_identifiers(nodes, index_station_identifiers([row]), "revision") == 0


def test_existing_foreign_identity_change_requires_review():
    with pytest.raises(ValueError, match="conflicting explicit oebb_station_id"):
        apply_station_identifiers([node(oebb_station_id="8300000")], index_station_identifiers([source()]), "revision")
