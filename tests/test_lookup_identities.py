"""Foreign IDs are kept from exact source rows, never from names or positions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gen"))
from countries.belgium.generate import published_uic
from countries.germany.nodes import apply_station_identifiers
from countries.lookup.generate import build_lookup
from common.trainline import unique_station_rows


def row(**changes):
    values = dict(id="7604", country="DE", is_city="f", same_as="", name="Frankfurt (Main) Hbf",
                  latitude="50.1", longitude="8.6", uic="8011068", db_id="8000105", obb_id="8000105",
                  trenitalia_rtvt_id="")
    values.update(changes)
    return values


def test_irail_uic_needs_matching_uri_and_id():
    assert published_uic({"id": "BE.NMBS.008011068",
                          "@id": "http://irail.be/stations/NMBS/008011068"}) == "8011068"
    assert published_uic({"id": "BE.NMBS.008011068",
                          "@id": "http://irail.be/stations/NMBS/008011069"}) is None
    assert published_uic({"id": "BE.NMBS.8814217", "@id": ""}) is None


def test_db_station_gets_uic_only_from_a_unique_trainline_row():
    index = unique_station_rows([row()], country="DE", key="db_id", id_fields=("uic", "obb_id"))
    nodes = [{"id": 8000105, "tags": {"name": "Other label"}}, {"id": 8000207, "tags": {}}]
    assert apply_station_identifiers(nodes, index, "rev") == 1
    assert nodes[0]["tags"]["uic_ref"] == "8011068"
    assert nodes[1]["tags"] == {}
    duplicate = [row(), row(id="9999", db_id="8000999")]  # same UIC on two rows
    assert unique_station_rows(duplicate, country="DE", key="db_id", id_fields=("uic", "obb_id")) == {}


def test_lookup_keeps_foreign_rows_that_link_a_known_station():
    rows = [row(id="1", country="AT", name="Salzburg Hbf", uic="8100002", db_id="8100002", obb_id="8100002"),
            row(id="2", country="AT", name="Nowhere", uic="8199999", db_id="8199998", obb_id="8199998")]
    out = build_lookup(rows, "rev", "db_id", known=({"8100002"}, set(), {"db_station_id": set()}))
    assert [(item["id"], item["tags"]["oebb_station_id"]) for item in out] == [("8100002", "8100002")]
    assert build_lookup(rows, "rev", "db_id", owned_ids={"8100002"}, known=({"8100002"}, set(), {"db_station_id": set()})) == []
    assert build_lookup(rows, "rev", "db_id", known=({"8100002"}, set(), {"db_station_id": {"8100002"}})) == []


def test_renfe_and_crs_ids_use_their_own_formats():
    renfe = row(id="1", country="ES", name="Marchena", uic="7101005", renfe_id="01005")
    crs = row(id="2", country="GB", name="London St Pancras", uic="7015400", atoc_id="STP")
    bad = row(id="3", country="ES", name="Bad", uic="7100001", renfe_id="1")
    assert set(unique_station_rows([renfe, bad], country="ES", key="renfe_id", id_fields=("uic",))) == {"01005"}
    assert set(unique_station_rows([crs], country="GB", key="atoc_id", id_fields=("uic",))) == {"STP"}
    # Two rows naming one UIC are ambiguous: neither is linked.
    twin = row(id="4", country="ES", name="Twin", uic="7101005", renfe_id="01006")
    assert unique_station_rows([renfe, twin], country="ES", key="renfe_id", id_fields=("uic",)) == {}
