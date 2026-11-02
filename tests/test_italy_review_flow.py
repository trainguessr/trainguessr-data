from __future__ import annotations

import json
import pytest
import csv
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gen"))

from common.io import load_ndjson  # noqa: E402
from common import italy as italy_common  # noqa: E402
from common.config import load_country_config  # noqa: E402
from common.manual_overrides import load_override_config  # noqa: E402
from countries.italy import review_decisions  # noqa: E402
from countries.italy.reviewed.classification import classify_reviewed, prepare_reviewed_seed  # noqa: E402
from countries.italy.reviewed import rebuild as rebuild_module  # noqa: E402
from countries.italy.reviewed import publication as publication_module  # noqa: E402
from countries.italy import review  # noqa: E402
from countries.italy import review_nodes  # noqa: E402
from countries.italy import fn as fn_generator  # noqa: E402


def _node(station_id: str, name: str = "Old Station") -> dict:
    return {
        "type": "node", "id": station_id, "lat": 45.0, "lon": 9.0,
        "tags": {"name": name, "operator": "Ferrovienord"}, "category": "italy_fn",
    }


def _scope_row() -> dict[str, str]:
    return {
        "id": "S99999", "status": "provider_scope_review",
        "source_name": "New Station", "reviewed_name": "", "details": "internal test detail",
        "lat": "45.2", "lon": "9.2",
    }


def test_new_fn_source_id_is_reported_and_does_not_replace_the_reviewed_seed():
    old = _node("S00001")
    source = {
        "S00001": {"id": "S00001", "name": "Old Station"},
        "S99999": {"id": "S99999", "name": "New Station", "scope_review": "check"},
    }
    output, audit = classify_reviewed("fn", source, [old], {}, {})
    assert output == [old]
    assert next(row for row in audit if row["id"] == "S99999")["status"] == "provider_scope_review"


def test_fn_download_filters_unrelated_trenord_rows_before_review(monkeypatch):
    html = b"""
      <a onclick=\"stationDetails('S00001','Old Station')\"></a>
      <a onclick=\"stationDetails('S99999','New Station')\"></a>
      <a onclick=\"stationDetails('S12345','Other Railway Station')\"></a>
    """
    captured = {}
    calls = []
    monkeypatch.setattr(fn_generator, "download", lambda _url, _path, use_cache: calls.append(use_cache) or (json.dumps({"elements": [{"tags": {"name": "New Station", "operator": "Ferrovienord", "railway": "station"}}]}).encode() if "overpass" in _url else html))
    monkeypatch.setattr(fn_generator, "current_ids", lambda _operator: {"S00001"})
    monkeypatch.setattr(fn_generator, "load_excluded_ids", lambda *_args: set())
    monkeypatch.setattr(fn_generator, "load_country_config", lambda _country: {})
    monkeypatch.setattr(fn_generator, "write_catalog", lambda _operator, rows, fields: captured.update(rows=rows, fields=fields))
    monkeypatch.setattr(fn_generator, "finish", lambda _operator: 0)
    assert fn_generator.main(["--cache"]) == 0
    assert calls == [True, True]
    assert len(captured["rows"]) == 2
    assert captured["fields"] == ["id", "name", "scope_review"]
    by_id = {row["id"]: row for row in captured["rows"]}
    assert by_id["S00001"]["scope_review"] == ""
    assert by_id["S99999"]["scope_review"] == "check"
    assert "S12345" not in by_id


def test_confirmed_fn_station_is_added_only_from_a_saved_review_and_coordinates():
    old = _node("S00001")
    config = {
        "manual_stations": [{
            "operator": "fn", "id": "S99999", "name": "New Station",
            "lat": 45.2, "lon": 9.2, "reason": "Coordinates checked during station review.",
        }],
        "reviews": [{
            "operator": "fn", "id": "S99999", "status": "provider_scope_review",
            "source_name": "New Station", "reviewed_name": "", "decision": "confirmed_fn",
        }],
    }
    seed = prepare_reviewed_seed("fn", [old], config)
    source = {
        "S00001": {"id": "S00001", "name": "Old Station"},
        "S99999": {"id": "S99999", "name": "New Station", "scope_review": "check"},
    }
    output, audit = classify_reviewed("fn", source, seed, config, {})
    assert {str(row["id"]) for row in output} == {"S00001", "S99999"}
    assert not any(row["status"] == "provider_scope_review" for row in audit)


def test_not_fn_decision_keeps_existing_station_and_does_not_add_new_id():
    old = _node("S00001")
    config = {"reviews": [{
        "operator": "fn", "id": "S99999", "status": "provider_scope_review",
        "source_name": "New Station", "reviewed_name": "", "decision": "not_fn",
    }]}
    source = {
        "S00001": {"id": "S00001", "name": "Old Station"},
        "S99999": {"id": "S99999", "name": "New Station", "scope_review": "check"},
    }
    output, audit = classify_reviewed("fn", source, [old], config, {})
    assert output == [old]
    assert next(row for row in audit if row["id"] == "S99999")["status"] == "excluded"


def _review_scope_with_answers(monkeypatch, answers: list[str], tmp_path):
    row = _scope_row()
    config: dict = {"reviews": [], "manual_stations": []}
    monkeypatch.setattr(review, "load_country_config", lambda _country: config)
    monkeypatch.setattr(review, "load_review_rows", lambda _operator: [row])
    original = load_ndjson(ROOT / "nodes/nodes-italy-fn.json")
    output = ROOT / "nodes/nodes-italy-fn.json"
    before = output.read_bytes()
    stamp = output.stat().st_mtime_ns
    with (
        patch("builtins.input", side_effect=answers),
        patch("countries.italy.review_decisions.save_config"),
        patch("countries.italy.review_nodes.save_config"),
    ):
        result = review.review_operator("fn")
    assert load_ndjson(output) == original
    assert output.read_bytes() == before
    assert output.stat().st_mtime_ns == stamp
    return result, config


def test_terminal_yes_records_fn_id_and_coordinates_but_waits_for_generation(monkeypatch, tmp_path):
    result, config = _review_scope_with_answers(monkeypatch, ["y", "45.2,9.2"], tmp_path)
    assert result == 0
    assert config["manual_stations"][0]["id"] == "S99999"
    assert config["reviews"][0]["decision"] == "confirmed_fn"


def test_defer_cancel_and_bad_coordinates_leave_published_fn_file_unchanged(monkeypatch, tmp_path):
    for answers in (["d"], ["q"], ["y", "91,9"]):
        with monkeypatch.context() as scoped:
            result, _config = _review_scope_with_answers(scoped, list(answers), tmp_path)
            assert result == 1


def test_checked_rebuild_publishes_only_after_review_is_complete(monkeypatch, capsys):
    candidate = [_node("S00001")]
    monkeypatch.setattr(rebuild_module, "rebuild", lambda _operator, dry_run: (candidate, []))
    monkeypatch.setattr("countries.italy.review.pending_review_rows", lambda _operator: [_scope_row()])
    published = []
    monkeypatch.setattr("common.io.publish_nodes", lambda path, rows: published.append((path, rows)))
    _, _, status = rebuild_module.checked_rebuild("fn")
    assert status == 2
    assert published == []
    assert "check railway owner" in capsys.readouterr().out

    monkeypatch.setattr("countries.italy.review.pending_review_rows", lambda _operator: [])
    _, _, status = rebuild_module.checked_rebuild("fn")
    assert status == 0
    assert len(published) == 1


def test_nonterminal_and_deferred_generation_leave_the_station_file_unchanged(monkeypatch, tmp_path):
    output = ROOT / "nodes/nodes-italy-fn.json"
    before = output.read_bytes()
    stamp = output.stat().st_mtime_ns
    calls = []
    monkeypatch.setattr(
        "countries.italy.reviewed.rebuild.checked_rebuild",
        lambda operator: calls.append(operator) or ([], [_scope_row()], 2),
    )
    monkeypatch.setattr(
        "countries.italy.reviewed.paths.audit_report_path",
        lambda operator: tmp_path / "cache/italy" / operator / "reports/audit.csv",
    )
    monkeypatch.setattr(italy_common, "ROOT", tmp_path)
    monkeypatch.setattr(italy_common, "validate_file", lambda _path: [])
    monkeypatch.setattr("countries.italy.review.review_after_generation", lambda _operator: None)
    assert italy_common.finish("fn") == 2
    assert calls == ["fn"]
    assert output.read_bytes() == before
    assert output.stat().st_mtime_ns == stamp

    calls.clear()
    monkeypatch.setattr("countries.italy.review.review_after_generation", lambda _operator: 1)
    assert italy_common.finish("fn") == 2
    assert calls == ["fn"]
    assert output.read_bytes() == before
    assert output.stat().st_mtime_ns == stamp


def test_generation_rebuilds_from_saved_review_before_valid_publish(monkeypatch, tmp_path):
    outputs = [([], [_scope_row()], 2), ([_node("S00001")], [], 0)]
    calls = []
    def checked(operator):
        calls.append(operator)
        return outputs.pop(0)
    monkeypatch.setattr("countries.italy.reviewed.rebuild.checked_rebuild", checked)
    monkeypatch.setattr("countries.italy.review.review_after_generation", lambda _operator: 0)
    monkeypatch.setattr("countries.italy.reviewed.paths.audit_report_path", lambda operator: tmp_path / "cache/italy" / operator / "reports/audit.csv")
    monkeypatch.setattr(italy_common, "ROOT", tmp_path)
    monkeypatch.setattr(italy_common, "validate_file", lambda _path: [])
    assert italy_common.finish("fn") == 0
    assert calls == ["fn", "fn"]


def test_flat_italy_decisions_save_as_readable_csv_and_load_back(monkeypatch, tmp_path):
    (tmp_path / "overrides/exclusions").mkdir(parents=True)
    evidence_path = tmp_path / "gen/bootstrap/evidence/italy-exclusion-station-evidence.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(json.dumps({"records": {
        "rfi:85099": {"type": "node", "lat": 45.8, "lon": 9.0,
                       "tags": {"name": "Stabio", "uic_ref": "8517519"}},
    }}), encoding="utf-8")
    monkeypatch.setattr(review_decisions, "ROOT", tmp_path)
    monkeypatch.setattr(review_decisions, "config_path", lambda: tmp_path / "overrides/exclusions/italy.csv")
    config_module = sys.modules["common.config"]
    monkeypatch.setattr(config_module, "ROOT", tmp_path)
    config = {
        "excluded": [{
            "operator": "rfi", "id": "85099", "name": "Stabio",
            "reason": "This station belongs to SBB.", "source": "Checked station record",
            "evidence_ref": "rfi:85099",
            "tags": {"name": "Stabio", "uic_ref": "8517519"},
        }],
        "renamed": [{"operator": "eav", "from": "Old", "to": "New"}],
        "manual_stations": [{
            "operator": "fn", "id": "S99999", "name": "New Station",
            "lat": 45.2, "lon": 9.2, "reason": "Coordinates checked during station review.",
        }],
        "reviews": [{
            "operator": "fn", "id": "S99999", "status": "provider_scope_review",
            "source_name": "New Station", "reviewed_name": "", "decision": "confirmed_fn",
            "details": "",
        }],
    }
    review_decisions.save_config(config)
    exclusions_csv = (tmp_path / "overrides/exclusions/italy.csv").read_text(encoding="utf-8")
    assert "evidence_json" not in exclusions_csv.splitlines()[0]
    assert "rfi:85099" in exclusions_csv
    exclusions = load_country_config("italy")["excluded"]
    assert exclusions[0]["tags"]["uic_ref"] == "8517519"
    assert exclusions[0]["source"] == "Checked station record"
    saved_csv = (tmp_path / "overrides/italy-decisions.csv").read_text(encoding="utf-8")
    assert "provider_scope_review" not in saved_csv
    assert "confirmed_fn" not in saved_csv
    assert "Check railway owner" in saved_csv
    assert "Confirmed as an FN station" in saved_csv
    loaded = load_country_config("italy")
    assert loaded["renamed"] == config["renamed"]
    assert loaded["manual_stations"][0]["id"] == "S99999"
    assert loaded["reviews"][0]["status"] == "provider_scope_review"
    assert loaded["reviews"][0]["decision"] == "confirmed_fn"


def test_existing_italy_exceptions_are_flat_csv_and_keep_station_evidence():
    config = load_country_config("italy")
    assert len(config["renamed"]) == 20
    assert len(config["manual_stations"]) >= 23
    assert len(config["reviews"]) >= 558
    assert len(config["coordinate_overrides"]) == 6
    exclusions = config["excluded"]
    assert len(exclusions) == 47
    assert not (ROOT / "overrides/exclusions/italy.json").exists()
    stabio = next(row for row in exclusions if row.get("id") == "85099")
    assert stabio["tags"]["uic_ref"] == "8517519"
    assert stabio["lat"] == 45.8497166
    raw_rows = list(csv.DictReader((ROOT / "overrides/exclusions/italy.csv").open(encoding="utf-8-sig")))
    raw_stabio = next(row for row in raw_rows if row.get("id") == "85099")
    assert raw_stabio["evidence_ref"] == "rfi:85099"
    assert "evidence_json" not in raw_rows[0]
    evidence = json.loads((ROOT / "gen/bootstrap/evidence/italy-exclusion-station-evidence.json").read_text(encoding="utf-8"))
    assert len(evidence["records"]) == 17
    cas = next(row for row in exclusions if row.get("id") == "S13199")
    assert cas["source_url"].startswith("https://")
    coordinate_data = load_override_config(ROOT / "overrides/italy-coordinate-corrections.csv")
    assert len(coordinate_data["coordinate_overrides"]) == 6
    assert coordinate_data["coordinate_overrides"][0]["source_url"].startswith("https://")


def test_review_report_uses_plain_words_and_shared_review_reads_it(tmp_path, monkeypatch):
    report = tmp_path / "cache/italy/fn/reports/audit.csv"
    monkeypatch.setattr(publication_module, "audit_report_path", lambda _operator: report)
    monkeypatch.setattr(review_nodes, "ROOT", tmp_path)
    audit = [{
        "id": "S99999", "source_name": "New Station", "reviewed_name": "",
        "status": "provider_scope_review", "details": "old_internal_reason_code",
    }]
    publication_module.write_reviewed_output("fn", ROOT / "nodes/nodes-italy-fn.json", [_node("S00001")], audit, dry_run=True)
    with report.open(encoding="utf-8", newline="") as handle:
        saved = next(csv.DictReader(handle))
    assert saved["status"] == "Check railway owner"
    assert saved["details"] == "Trenord lists this ID, but FN ownership has not been checked."
    rows = review_nodes.load_review_rows("fn")
    assert rows[0]["status"] == "provider_scope_review"
    assert "old_internal_reason_code" not in report.read_text(encoding="utf-8")


def test_fn_ownership_filter_accepts_wikidata_and_rejects_other_owners():
    payload = {"elements": [
        {"tags": {"railway": "station", "name": "Owned", "operator:wikidata": "Q3736799"}},
        {"tags": {"railway": "station", "name": "Other", "operator": "RFI"}},
        {"tags": {"railway": "platform", "name": "Platform", "operator": "Ferrovienord"}},
    ]}
    assert fn_generator.ownership_names(json.dumps(payload).encode()) == {"OWNED"}
    with pytest.raises(ValueError, match="no Ferrovienord"):
        fn_generator.ownership_names(b'{"elements": []}')


def test_fse_reports_do_not_call_known_exclusions_unresolved(monkeypatch, tmp_path):
    from countries.italy import fse
    monkeypatch.setattr(fse, 'UNRESOLVED_OUTPUT_FILE', tmp_path / 'unresolved.json')
    monkeypatch.setattr(fse, 'EXCLUDED_OUTPUT_FILE', tmp_path / 'excluded.json')
    monkeypatch.setattr(fse, 'EXCLUDED_REASON_BY_ID', {'S13135': 'FAL station'})
    monkeypatch.setattr(fse, 'EXCLUDED_OSM_NAMES', set())
    records = [{'id': 'S13135', 'tags': {'name': 'Potenza'}}, {'id': 'S99999', 'tags': {'name': 'Unknown'}}]
    pending, excluded = fse.write_source_reports(records)
    assert [r['id'] for r in pending] == ['S99999']
    assert [r['id'] for r in excluded] == ['S13135']
    assert [r['id'] for r in load_ndjson(tmp_path / 'unresolved.json')] == ['S99999']
