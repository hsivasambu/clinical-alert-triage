import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import database
import main
from decision_layer import apply
from llm_explainer import LLMOutcome
from models import AlertIn, AlertType, VitalSigns
from rules_engine import evaluate
from tests.conftest import make_alert


def triage(alert):
    return apply(alert, evaluate(alert), LLMOutcome(fallback_reason="llm_disabled"))


@pytest.mark.parametrize("type,missing,measured", [(AlertType.tachycardia, "heart_rate", 95), (AlertType.low_spo2, "spo2", 98)])
def test_absent_is_not_normal_even_when_default_decisions_match(type, missing, measured):
    absent = triage(make_alert(alert_type=type))
    present = triage(make_alert(alert_type=type, vital_signs=VitalSigns(**{missing: measured})))
    assert absent.final_priority == present.final_priority == "Low"
    assert absent.rule_output.evaluation_status == "no_rule_matched"
    assert absent.rule_output.missing_fields == [f"vital_signs.{missing}"]
    assert present.rule_output.missing_fields == []
    assert "Insufficient data" in absent.explanation.uncertainty_notes
    assert "Insufficient data" not in present.explanation.uncertainty_notes
    assert "NO_RULE_MATCHED" in absent.explanation.uncertainty_notes
    assert "does not establish normality or safety" in present.explanation.uncertainty_notes


def test_partial_screen_counts_available_criteria_only():
    result = triage(make_alert(alert_type=AlertType.sepsis, vital_signs=VitalSigns(heart_rate=110)))
    assert result.final_priority == "High"
    assert "SEPSIS_SIRS_EQ_1" in result.rule_output.matched_rules
    assert "SEPSIS_SIRS_GTE_2" not in result.rule_output.matched_rules
    assert set(result.rule_output.missing_fields) == {"vital_signs.temperature", "vital_signs.respiratory_rate"}


def test_measurement_absence_does_not_prevent_repeat_rule():
    result = triage(make_alert(repeat_count=3))
    assert result.final_priority == "High"
    assert result.final_route == "Charge Nurse"
    assert result.rule_output.missing_fields == ["vital_signs.heart_rate"]
    assert "TACHY_REPEAT_GTE_3" in result.explanation.rule_trace


@pytest.mark.parametrize("alarm", [None, "", "unknown", "OCCLUSION"])
def test_pump_typed_alarm_and_null_infusate_do_not_crash(alarm):
    alert = make_alert(alert_type=AlertType.infusion_pump, additional_context={"alarm_type": alarm, "infusate": None, "metadata": {"sensor": "demo"}})
    result = triage(alert)
    assert result.final_priority == ("High" if alarm == "OCCLUSION" else "Medium")
    assert alert.additional_context.model_dump()["metadata"] == {"sensor": "demo"}
    assert result.rule_output.missing_fields == (["additional_context.alarm_type", "additional_context.infusate"] if not alarm else ["additional_context.infusate"])


def test_omitted_vitals_and_counts_are_auditable_defaults():
    raw = make_alert(alert_type=AlertType.nurse_call).model_dump(mode="json")
    raw.pop("vital_signs"); raw.pop("repeat_count")
    result = triage(AlertIn.model_validate(raw))
    assert result.final_priority == "Low"
    assert result.rule_output.missing_fields == ["repeat_count"]
    assert "default of 0" in " ".join(result.explanation.factors_considered)


def test_zero_is_provided_not_missing():
    result = triage(make_alert(alert_type=AlertType.low_spo2, vital_signs=VitalSigns(spo2=0)))
    assert result.final_priority == "Critical"
    assert result.rule_output.missing_fields == []
    assert "Observed SpO2: 0 %" in " ".join(result.explanation.factors_considered)


INVALID = [
    ("vital_signs", "heart_rate", -1), ("vital_signs", "heart_rate", 401),
    ("vital_signs", "spo2", 101), ("vital_signs", "spo2", "85"), ("vital_signs", "spo2", True),
    ("vital_signs", "respiratory_rate", 101), ("vital_signs", "temperature", 61),
    ("vital_signs", "blood_pressure_systolic", 401), ("vital_signs", "blood_pressure_diastolic", -1),
    ("vital_signs", "hearrt_rate", 100), ("recent_context", "fall_risk_score", 126),
    ("recent_context", "fall_risk_score", 4.5), ("recent_context", "prior_alerts_24h", True),
    ("additional_context", "alarm_type", []), ("additional_context", "alarm_type", 1),
    ("additional_context", "infusate", {"name": "heparin"}),
    (None, "patient_id", "  "), (None, "unit", ""), (None, "alert_id", 10),
    (None, "repeat_count", -1), (None, "repeat_count", 1.5), (None, "repeat_count", "3"),
    (None, "timestamp", "2025-01-01T00:00:00"), (None, "timestamp", "not-a-date"),
    (None, "timestamp", 12345), (None, "timestamp", "12345"), (None, "fallback_reason", "provider_timeout"),
]


@pytest.mark.parametrize("parent,field,value", INVALID)
def test_invalid_inputs_return_422_before_rules_or_provider(parent, field, value, monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "audit.db")
    database.init_db(); main._store.clear()
    raw = copy.deepcopy(make_alert(alert_type=AlertType.infusion_pump).model_dump(mode="json"))
    target = raw[parent] if parent else raw
    target[field] = value
    def unexpected(*args, **kwargs): raise AssertionError("invalid input reached evaluation")
    monkeypatch.setattr("main.rules_engine.evaluate", unexpected)
    monkeypatch.setattr("main.llm_explainer.explain_with_outcome", unexpected)
    resp = TestClient(main.app).post("/alerts", json=raw)
    assert resp.status_code == 422, resp.text
    assert database.get_audit_log() == []
    assert main._store == {}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_measurements_rejected(value):
    with pytest.raises(ValidationError): VitalSigns(heart_rate=value)


def test_all_repository_samples_validate_and_receive_complete_explanations():
    for path in (Path(__file__).resolve().parents[2] / "sample_data").glob("alerts_*.json"):
        alert = AlertIn.model_validate_json(path.read_text())
        result = triage(alert)
        assert result.explanation.rule_evidence
        assert all(getattr(result.explanation, field) for field in ["summary", "rationale", "factors_considered", "uncertainty_notes", "recommended_checks"]), path


@pytest.mark.parametrize("field,value", [("spo2", float("nan")), ("heart_rate", float("inf")), ("metadata", {"nested": [float("nan")]})])
def test_nonfinite_raw_json_returns_422_not_a_server_error(field, value, monkeypatch):
    raw = make_alert().model_dump(mode="json")
    if field == "metadata": raw["additional_context"][field] = value
    else: raw["vital_signs"][field] = value
    monkeypatch.setattr("main.rules_engine.evaluate", lambda *args: pytest.fail("invalid number reached rules"))
    response = TestClient(main.app).post("/alerts", content=json.dumps(raw), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
