import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import database
import main
from decision_layer import apply
from evidence import catalog_for
from explanation_contract import validate_narrative
from llm_explainer import LLMRawOutput, explain_with_outcome
from models import AcceptanceIn, FeedbackIn, OverrideIn, Priority, VitalSigns
from prompt_builder import build_messages
from provenance import generation_metadata
from rules_engine import evaluate
from tests.conftest import make_alert


def sample(**changes):
    alert = make_alert(vital_signs=VitalSigns(heart_rate=145, spo2=97), unit="ICU")
    rules = evaluate(alert)
    data = dict(summary="DECISION_FINAL records the High priority.",
                rationale="The router records the destination in DECISION_FINAL.",
                factors_considered=["OBS_HEART_RATE supplies recorded context."],
                uncertainty_notes="Source accuracy has not been independently verified.",
                recommended_checks=["Verify source timestamps and units."],
                triggering_rule_ids=[r for r in rules.matched_rules if r != "NO_RULE_MATCHED"],
                context_evidence_ids=["OBS_HEART_RATE", "OBS_SPO2", "OBS_UNIT"], confidence=0.99)
    data.update(changes)
    return alert, rules, data


@pytest.mark.parametrize("changes,issue,reason", [
    ({"summary": "HR 146 bpm [OBS_HEART_RATE]"}, "measurement_mismatch", "evidence_mismatch"),
    ({"summary": "HR 145 mmHg [OBS_HEART_RATE]"}, "measurement_unit_mismatch", "evidence_mismatch"),
    ({"summary": "HR 145Hz [OBS_HEART_RATE]"}, "measurement_unit_mismatch", "evidence_mismatch"),
    ({"summary": "SpO2 98 % [OBS_SPO2]"}, "measurement_mismatch", "evidence_mismatch"),
    ({"summary": "Temperature 37 C [OBS_TEMPERATURE]"}, "measurement_mismatch", "evidence_mismatch"),
    ({"triggering_rule_ids": ["FAKE_RULE"]}, "trigger_references_mismatch", "evidence_mismatch"),
    ({"context_evidence_ids": ["FAKE_OBSERVATION"]}, "context_references_mismatch", "evidence_mismatch"),
    ({"summary": "HR_GT_999 explains this decision."}, "unknown_inline_evidence_id", "evidence_mismatch"),
    ({"summary": "Critical priority is recorded."}, "priority_contradiction", "contradiction"),
    ({"rationale": "Destination is Bedside Nurse."}, "route_contradiction", "contradiction"),
    ({"summary": "This is caused by infection."}, "prohibited_content_pattern", "content_rejected"),
    ({"recommended_checks": ["Administer antibiotics."]}, "prohibited_content_pattern", "content_rejected"),
    ({"recommended_checks": ["You should downgrade the priority."]}, "prohibited_content_pattern", "content_rejected"),
    ({"summary": "Estimated probability 80 percent."}, "unverified_numeric_claim", "evidence_mismatch"),
])
def test_rejected_contract_falls_back_without_changing_decision(changes, issue, reason):
    alert, rules, data = sample(**changes)
    output = LLMRawOutput(**data)
    assert issue in validate_narrative(alert, rules, output)
    result = apply(alert, rules, output)
    baseline = apply(alert, rules)
    assert (result.final_priority, result.final_route) == (baseline.final_priority, baseline.final_route)
    assert result.explanation.fallback_reason == reason
    assert result.provenance.validation_outcome == "rejected"
    assert issue in result.provenance.validation_issues
    assert data["summary"] != result.explanation.summary


@pytest.mark.parametrize("field,value", [("summary", " "), ("rationale", "\t"), ("factors_considered", [" "]), ("recommended_checks", [""]), ("context_evidence_ids", [" "])])
def test_empty_contract_fields_rejected(field, value):
    _, _, data = sample(**{field: value})
    with pytest.raises(ValidationError): LLMRawOutput(**data)


def test_correct_measurements_and_separate_evidence_are_accepted():
    alert, rules, data = sample(summary="HR 145 bpm [OBS_HEART_RATE]; SpO2 97 % [OBS_SPO2].")
    assert validate_narrative(alert, rules, LLMRawOutput(**data)) == []
    catalog = catalog_for(alert, rules)
    assert all(r["rule_id"] != "NO_RULE_MATCHED" for r in catalog["triggering_rules"])
    assert {o["evidence_id"] for o in catalog["context_observations"]} >= {"OBS_SPO2", "OBS_HEART_RATE"}
    system, prompt = build_messages(alert, rules)
    assert catalog["deterministic_decision"]["route"] in prompt
    assert "must not propose" in system.lower()
    assert "rule_confidence" not in prompt
    assert generation_metadata(alert, rules).rendered_prompt_hash == generation_metadata(alert, rules).rendered_prompt_hash


def test_provider_provenance_cap_correlation_and_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "audit.db")
    database.init_db(); main._store.clear()
    alert, rules, data = sample()
    provider = MagicMock()
    provider.chat.completions.create.return_value = SimpleNamespace(model="returned-model-snapshot", choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(data), refusal=None))])
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: provider)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only")
    with TestClient(main.app) as client:
        response = client.post("/alerts", json=alert.model_dump(mode="json"), headers={"X-Request-ID": "portfolio-contract-test"})
        assert response.status_code == 201, response.text
        result = response.json(); p = result["provenance"]
        assert response.headers["X-Request-ID"] == p["request_correlation_id"] == "portfolio-contract-test"
        assert p["returned_model"] == "returned-model-snapshot"
        assert p["configured_model"] and p["rules_version"] and p["prompt_version"] and len(p["prompt_hash"]) == 64 and len(p["rendered_prompt_hash"]) == 64
        assert p["validation_outcome"] == "accepted_by_practical_checks" and p["generation_duration_ms"] >= 0
        e = result["explanation"]
        assert e["llm_self_reported_confidence"] == .99
        assert e["llm_confidence_estimate"] == min(.99, e["confidence_cap"])
        assert "not a calibrated" in e["confidence_cap_reason"]
        assert next(row for row in client.get("/audit").json() if row["alert_id"] == alert.alert_id)["provenance"] == p
    main._store.clear()
    assert next(r for r in database.load_triage_results() if r.alert_id == alert.alert_id).provenance.model_dump(mode="json") == p
    main._store.clear()


def test_append_only_cross_action_order_and_legacy_provenance(tmp_path):
    path = tmp_path / "audit.db"; database.init_db(path)
    alert, rules, _ = sample(); result = apply(alert, rules)
    database.log_triage(alert, rules, result, path)
    a = database.log_acceptance(alert.alert_id, AcceptanceIn(reviewer_id="A", decision_version=0), path, result)
    o = database.log_override(alert.alert_id, OverrideIn(reviewer_id="B", overridden_priority=Priority.medium, reason="Demo review"), result.final_priority, result.final_route, path)
    f = database.log_feedback(alert.alert_id, FeedbackIn(reviewer_id="C", rating="not_helpful", reason_category="other"), path)
    a2 = database.log_acceptance(alert.alert_id, AcceptanceIn(reviewer_id="D", decision_version=o.id), path, result)
    assert a.event_sequence < o.event_sequence < f.event_sequence < a2.event_sequence
    audit = database.get_alert_audit(alert.alert_id, result, path)
    assert audit["acceptances"][1]["event_sequence"] == a2.event_sequence
    assert audit["acceptances"][0]["accepted_priority"] == "High"
    assert audit["review_state"]["effective_priority"] == "Medium"
    with sqlite3.connect(path) as conn:
        saved = json.loads(conn.execute("SELECT final_response_json FROM audit_log").fetchone()[0])
        assert saved["final_priority"] == "High"
        # Simulate a historical record with missing provenance and evidence fields.
        saved.pop("provenance")
        for key in ["triggering_rule_ids", "context_observations", "referenced_context_ids", "llm_self_reported_confidence", "confidence_cap", "confidence_cap_reason"]: saved["explanation"].pop(key)
        conn.execute("INSERT INTO audit_log (alert_id,alert_type,patient_id,unit,baseline_priority,final_priority,final_route,explanation_mode,rule_confidence,alert_json,rule_output_json,final_response_json,created_at) SELECT 'LEGACY',alert_type,patient_id,unit,baseline_priority,final_priority,final_route,explanation_mode,rule_confidence,alert_json,rule_output_json,?,created_at FROM audit_log LIMIT 1", (json.dumps(saved),))
    database.init_db(path)
    assert next(row for row in database.get_audit_log(db_path=path) if row["alert_id"] == "LEGACY")["provenance"] is None
    assert any(r.provenance is None for r in database.load_triage_results(path))


@pytest.mark.parametrize("changes,reason", [({"summary": "HR 146 bpm [OBS_HEART_RATE]"}, "evidence_mismatch"), ({"summary": "Critical priority is recorded."}, "contradiction"), ({"summary": "This is caused by infection."}, "content_rejected")])
def test_rejection_provenance_persists_through_api(changes, reason, monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "audit.db")
    database.init_db(); main._store.clear()
    alert, rules, data = sample(**changes)
    provider = MagicMock()
    provider.chat.completions.create.return_value = SimpleNamespace(model="mock-model", choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(data), refusal=None))])
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: provider)
    monkeypatch.setenv("OPENAI_API_KEY", "mock-only")
    client = TestClient(main.app)
    response = client.post("/alerts", json=alert.model_dump(mode="json"), headers={"X-Request-ID": "invalid id with spaces"})
    assert response.status_code == 201
    p = response.json()["provenance"]
    assert p["validation_outcome"] == "rejected" and p["validation_issues"]
    assert p["fallback_reason"] == reason and p["returned_model"] == "mock-model"
    assert p["request_correlation_id"] == response.headers["X-Request-ID"] != "invalid id with spaces"
    assert client.get("/audit").json()[0]["provenance"] == p
    main._store.clear()
    assert database.load_triage_results()[0].provenance.model_dump(mode="json") == p


def test_no_match_policy_marker_is_not_a_trigger_but_can_be_described():
    alert = make_alert()
    rules = evaluate(alert)
    _, _, data = sample(summary="NO_RULE_MATCHED marks the default decision.", triggering_rule_ids=[], context_evidence_ids=["OBS_UNIT"], factors_considered=["OBS_UNIT provides context."])
    assert rules.matched_rules == ["NO_RULE_MATCHED"]
    assert validate_narrative(alert, rules, LLMRawOutput(**data)) == []
