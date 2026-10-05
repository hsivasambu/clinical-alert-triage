"""All providers are mocked. Test failure provenance through API + append-only audit."""
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

import database
import main
from decision_layer import apply
from llm_explainer import CONFIDENCE_THRESHOLD, LLMOutcome, LLMRawOutput, explain_with_outcome
from models import AlertType, VitalSigns
from rules_engine import evaluate
from tests.conftest import make_alert


def payload(confidence=0.8):
    return dict(summary="Validated recorded narrative.", rationale="Recorded rule rationale.",
                factors_considered=["Recorded input."], uncertainty_notes="Source not independently verified.",
                recommended_checks=["Verify source."], confidence=confidence)


def response(content=None, refusal=None, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=refusal), finish_reason=finish)])


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "audit.db")
    database.init_db()
    main._store.clear()
    yield
    main._store.clear()


@pytest.mark.parametrize("case,reason", [
    ("disabled", "llm_disabled"), ("failure", "provider_failure"), ("timeout", "provider_timeout"),
    ("python_timeout", "provider_timeout"), ("malformed", "malformed_output"), ("empty", "malformed_output"),
    ("no_choices", "malformed_output"), ("schema", "schema_invalid"), ("non_object", "schema_invalid"),
    ("whitespace", "schema_invalid"), ("blank_item", "schema_invalid"), ("extra_authority", "schema_invalid"),
    ("nan", "schema_invalid"), ("low", "low_confidence"), ("refusal", "content_rejected"), ("filtered", "content_rejected"),
])
def test_fallback_path_persists_reason_and_preserves_decision(case, reason, monkeypatch, isolated_db):
    data = payload(0.3 if case == "low" else 0.8)
    if case == "schema": del data["summary"]
    if case == "whitespace": data["summary"] = "  "
    if case == "blank_item": data["recommended_checks"] = ["  "]
    if case == "extra_authority": data["suggested_priority"] = "Low"
    if case == "nan": data["confidence"] = float("nan")
    raw = "not JSON" if case == "malformed" else "" if case == "empty" else "[]" if case == "non_object" else json.dumps(data)
    fake = MagicMock()
    fake.chat.completions.create.return_value = response(raw, "Provider refused" if case == "refusal" else None, "content_filter" if case == "filtered" else "stop")
    if case == "no_choices": fake.chat.completions.create.return_value = SimpleNamespace(choices=[])
    if case == "failure": fake.chat.completions.create.side_effect = RuntimeError("provider failure")
    if case == "timeout": fake.chat.completions.create.side_effect = openai.APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
    if case == "python_timeout": fake.chat.completions.create.side_effect = TimeoutError()
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(openai, "OpenAI", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "" if case == "disabled" else "mock-key")
    alert = make_alert(alert_id=f"FALLBACK-{case}", alert_type=AlertType.low_spo2, vital_signs=VitalSigns(spo2=85), unit="ICU")
    client = TestClient(main.app)
    resp = client.post("/alerts", json=alert.model_dump(mode="json"))
    assert resp.status_code == 201, resp.text
    result = resp.json()
    explanation = result["explanation"]
    assert result["final_priority"] == "Critical"
    assert result["final_route"] == "ICU Team (Intensivist + Nurse)"
    assert explanation["explanation_mode"] == "rules_only"
    assert explanation["fallback_reason"] == reason
    for section in ["summary", "rationale", "factors_considered", "uncertainty_notes", "rule_evidence", "recommended_checks"]:
        assert explanation[section], section
    assert "85 %" in " ".join(explanation["factors_considered"])
    assert "ICU keyword classifier" in explanation["rationale"]
    assert "Validated recorded narrative" not in explanation["summary"]
    assert explanation["rule_trace"] == result["rule_output"]["matched_rules"]
    assert client.get(f"/alerts/{alert.alert_id}").json()["explanation"] == explanation
    assert client.get("/alerts").json()[0]["explanation"] == explanation
    assert client.get(f"/alerts/{alert.alert_id}/audit").json()["triage_result"]["explanation"] == explanation
    assert client.get("/audit").json()[0]["fallback_reason"] == reason
    main._store.clear()
    restored = database.load_triage_results()[0]
    assert restored.explanation.model_dump(mode="json") == explanation
    with sqlite3.connect(database.DB_PATH) as conn:
        saved = json.loads(conn.execute("SELECT final_response_json FROM audit_log").fetchone()[0])
        assert saved["explanation"] == explanation
    if case == "disabled": factory.assert_not_called()
    else: factory.assert_called_once_with(timeout=15.0, max_retries=0)


def test_valid_narrative_threshold_and_routing_are_independent(monkeypatch):
    alert = make_alert(alert_type=AlertType.infusion_pump, additional_context={"alarm_type": "occlusion", "infusate": "heparin"})
    rules = evaluate(alert)
    outputs = [None, LLMOutcome(fallback_reason="provider_failure"), LLMRawOutput(**payload(0.49)), LLMRawOutput(**payload(CONFIDENCE_THRESHOLD)), LLMRawOutput(**payload(0.95))]
    results = [apply(alert, rules, output) for output in outputs]
    assert {(r.final_priority, r.final_route) for r in results} == {("High", "Pharmacy + Bedside Nurse")}
    assert results[2].explanation.fallback_reason == "low_confidence"
    assert results[3].explanation.fallback_reason is None
    assert results[3].explanation.explanation_mode == "hybrid"
    assert results[3].explanation.summary == "Validated recorded narrative."


def test_unexpected_adapter_failure_is_classified(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setattr("llm_explainer._call_llm", MagicMock(side_effect=RuntimeError()))
    alert = make_alert()
    assert explain_with_outcome(alert, evaluate(alert)).fallback_reason == "provider_failure"


def test_legacy_audit_provenance_is_unknown_and_json_unchanged(isolated_db):
    result = apply(make_alert(), evaluate(make_alert()))
    database.log_triage(result.alert, result.rule_output, result)
    legacy = result.model_dump(mode="json")
    legacy["explanation"].pop("fallback_reason")
    legacy["explanation"].pop("explanation_version")
    original = json.dumps(legacy)
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("UPDATE audit_log SET final_response_json = ?, fallback_reason = NULL", (original,))
    database.init_db()
    assert database.load_triage_results()[0].explanation.fallback_reason is None
    assert database.get_audit_log()[0]["fallback_reason"] is None
    with sqlite3.connect(database.DB_PATH) as conn:
        assert conn.execute("SELECT final_response_json FROM audit_log").fetchone()[0] == original


def test_blank_key_is_disabled_without_invoking_provider(monkeypatch):
    factory = MagicMock(side_effect=AssertionError("provider should not be called"))
    monkeypatch.setenv("OPENAI_API_KEY", "  ")
    monkeypatch.setattr(openai, "OpenAI", factory)
    alert = make_alert()
    assert explain_with_outcome(alert, evaluate(alert)).fallback_reason == "llm_disabled"
    factory.assert_not_called()


@pytest.mark.parametrize("type,vitals,unit,extras,route,reason_part", [
    (AlertType.low_spo2, VitalSigns(spo2=85), "ICU", {}, "ICU Team (Intensivist + Nurse)", "Critical priority"),
    (AlertType.low_spo2, VitalSigns(spo2=85), "North", {}, "Rapid Response Team", "outside the ICU keyword classifier"),
    (AlertType.tachycardia, VitalSigns(heart_rate=145), "ICU", {}, "ICU Team (Intensivist + Nurse)", "High priority"),
    (AlertType.infusion_pump, VitalSigns(), "ICU", {"alarm_type": "occlusion", "infusate": "heparin"}, "ICU Team (Intensivist + Nurse)", "High priority"),
    (AlertType.infusion_pump, VitalSigns(), "North", {"alarm_type": "occlusion", "infusate": "heparin"}, "Pharmacy + Bedside Nurse", "configured drug keyword list"),
    (AlertType.tachycardia, VitalSigns(heart_rate=145), "North", {}, "Bedside Nurse (immediate)", "retains the rule-selected destination"),
])
def test_routing_reason_comes_from_the_branch_that_selected_the_route(type, vitals, unit, extras, route, reason_part):
    alert = make_alert(alert_type=type, vital_signs=vitals, unit=unit, additional_context=extras)
    result = apply(alert, evaluate(alert), LLMOutcome(fallback_reason="llm_disabled"))
    assert result.final_route == route
    assert reason_part in result.explanation.rationale
