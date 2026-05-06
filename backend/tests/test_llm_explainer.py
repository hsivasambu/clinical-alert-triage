"""
Tests for the LLM explainability layer.

All OpenAI network calls are mocked - no API key or network access required.
Tests cover:
  - Valid structured LLM output -> LLMRawOutput returned, decision layer uses hybrid mode
  - Malformed JSON from LLM -> None, rules_only fallback
  - Missing required fields -> None, rules_only fallback
  - Low confidence -> LLMRawOutput returned, decision layer applies rules_only
  - API timeout -> None, rules_only fallback
  - API error -> None, rules_only fallback
  - No API key set -> None, rules_only fallback
  - Guardrail preservation: priority floor and rule_trace always intact
"""

import json
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from models import AlertType, ExplanationMode, Priority, RecentContext, VitalSigns
from rules_engine import evaluate
from decision_layer import apply
from llm_explainer import LLMRawOutput, CONFIDENCE_THRESHOLD, explain, is_enabled
from tests.conftest import make_alert


def _valid_llm_payload(**overrides: Any) -> dict:
    """Return a payload that passes LLMRawOutput validation."""
    base = {
        "summary": "Heart rate of 145 bpm triggered a High priority alert.",
        "rationale": (
            "The heart rate exceeds the 130 bpm threshold defined by rule HR_GT_130. "
            "This level of tachycardia warrants prompt bedside assessment."
        ),
        "factors_considered": ["Heart rate 145 bpm", "Threshold: HR > 130", "No repeat count"],
        "uncertainty_notes": "No information on patient's baseline heart rate or recent activity.",
        "recommended_checks": ["Verify lead placement and signal quality", "Assess patient responsiveness"],
        "confidence": 0.88,
    }
    base.update(overrides)
    return base


def _mock_openai_response(payload: dict) -> MagicMock:
    """Create a mock OpenAI ChatCompletion response returning the given payload."""
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _patch_openai(return_value: Any = None, side_effect: Any = None):
    """Patch openai.OpenAI so .chat.completions.create returns/raises as specified."""
    mock_client = MagicMock()
    if side_effect:
        mock_client.chat.completions.create.side_effect = side_effect
    else:
        mock_client.chat.completions.create.return_value = return_value
    return patch("openai.OpenAI", return_value=mock_client)


class TestIsEnabled:

    def test_enabled_when_key_set(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            assert is_enabled() is True

    def test_disabled_when_key_absent(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            assert is_enabled() is False


class TestValidLLMOutput:

    def test_returns_llm_raw_output_on_valid_response(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        payload = _valid_llm_payload()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert isinstance(result, LLMRawOutput)
        assert result.summary == payload["summary"]
        assert 0.0 <= result.confidence <= payload["confidence"]

    def test_all_fields_present_in_valid_output(self):
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=110.0, temperature=39.0),
        )
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(
            summary="Sepsis screen positive: two SIRS criteria met.",
            factors_considered=["HR 110 bpm > 90", "Temp 39 C > 38.3 C"],
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert len(result.factors_considered) == 2
        assert len(result.recommended_checks) >= 1
        assert result.uncertainty_notes != ""

    def test_decision_layer_uses_hybrid_mode_for_valid_output(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=0.90))

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.explanation_mode == ExplanationMode.hybrid
        assert triage.explanation.summary == llm_out.summary
        assert triage.explanation.llm_confidence_estimate == 0.90

    def test_rule_trace_always_comes_from_rules_engine_not_llm(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload())

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.rule_trace == rule_output.matched_rules
        assert "SPO2_LT_88" in triage.explanation.rule_trace


class TestMalformedOutput:

    def test_non_json_response_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        msg = MagicMock()
        msg.content = "Sorry, I cannot help with that."
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=resp):
                result = explain(alert, rule_output)

        assert result is None

    def test_missing_required_field_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        payload = _valid_llm_payload()
        del payload["summary"]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is None

    def test_empty_string_field_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(summary="")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is None

    def test_empty_list_field_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(factors_considered=[])

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is None

    def test_confidence_out_of_range_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(confidence=1.5)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is None

    def test_empty_response_content_returns_none(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        msg = MagicMock()
        msg.content = ""
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=resp):
                result = explain(alert, rule_output)

        assert result is None

    def test_fallback_to_rules_only_mode_after_invalid_output(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        triage = apply(alert, rule_output, llm_output=None)

        assert triage.explanation.explanation_mode == ExplanationMode.rules_only
        assert triage.explanation.rule_trace == rule_output.matched_rules


class TestLowConfidenceFallback:

    def test_low_confidence_output_still_parsed(self):
        alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=4)
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(confidence=0.3)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert result.confidence == 0.3

    def test_decision_layer_uses_rules_only_for_low_confidence(self):
        alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=4)
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=0.3))

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.explanation_mode == ExplanationMode.rules_only
        assert triage.explanation.llm_confidence_estimate == 0.3

    def test_decision_layer_threshold_is_0_5(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=CONFIDENCE_THRESHOLD))

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.explanation_mode == ExplanationMode.hybrid

    def test_confidence_just_below_threshold_is_rules_only(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=CONFIDENCE_THRESHOLD - 0.01))

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.explanation_mode == ExplanationMode.rules_only


class TestConfidenceCalibration:

    def test_rich_alert_keeps_high_confidence(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(
                heart_rate=124.0,
                spo2=83.0,
                blood_pressure_systolic=92.0,
                blood_pressure_diastolic=54.0,
                respiratory_rate=31.0,
                temperature=38.0,
            ),
            unit="2-ICU Step-Down",
            recent_context=RecentContext(
                prior_alerts_24h=4,
                recent_medications=["high_flow_oxygen_documented"],
                admission_reason="acute hypoxic respiratory failure",
                code_status="full_code",
            ),
            additional_context={"waveform_quality": "good", "trend_direction": "worsening"},
        )
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(confidence=0.90)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert result.confidence == 0.90

    def test_moderate_alert_is_capped_below_high_confidence_band(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(
                heart_rate=118.0,
                spo2=95.0,
                blood_pressure_systolic=110.0,
                blood_pressure_diastolic=68.0,
            ),
            recent_context=RecentContext(
                prior_alerts_24h=1,
                recent_medications=["albuterol nebulizer"],
                admission_reason="shortness of breath evaluation",
                code_status="full_code",
            ),
            additional_context={"signal_quality": "fair"},
        )
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(confidence=0.90)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert result.confidence == 0.82

    def test_sparse_noisy_alert_is_capped_into_lower_band(self):
        alert = make_alert(
            alert_type=AlertType.fall_risk,
            vital_signs=VitalSigns(),
            recent_context=RecentContext(),
            additional_context={"sensor_status": "intermittent_signal", "data_quality": "partial"},
        )
        rule_output = evaluate(alert)
        payload = _valid_llm_payload(confidence=0.88)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(return_value=_mock_openai_response(payload)):
                result = explain(alert, rule_output)

        assert result is not None
        assert 0.60 <= result.confidence <= 0.75
        assert result.confidence == 0.68


class TestAPIFailures:

    def test_timeout_returns_none(self):
        alert = make_alert(alert_type=AlertType.sepsis)
        rule_output = evaluate(alert)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("llm_explainer._call_llm", side_effect=Exception("Connection timed out")):
                result = explain(alert, rule_output)

        assert result is None

    def test_api_error_returns_none(self):
        alert = make_alert(alert_type=AlertType.sepsis)
        rule_output = evaluate(alert)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with _patch_openai(side_effect=Exception("API error 503")):
                result = explain(alert, rule_output)

        assert result is None

    def test_no_api_key_returns_none_immediately(self):
        alert = make_alert(alert_type=AlertType.tachycardia)
        rule_output = evaluate(alert)
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}

        with patch.dict(os.environ, env, clear=True):
            result = explain(alert, rule_output)

        assert result is None


class TestGuardrailPreservation:

    def test_priority_floor_preserved_with_valid_llm_output(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        rule_output = evaluate(alert)
        assert rule_output.baseline_priority == Priority.critical

        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=0.95))
        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.final_priority == Priority.critical

    def test_priority_floor_preserved_with_low_confidence_llm(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=0.2))
        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.final_priority == Priority.critical
        assert triage.explanation.explanation_mode == ExplanationMode.rules_only

    def test_priority_floor_preserved_when_llm_is_none(self):
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=110.0, temperature=39.0),
        )
        rule_output = evaluate(alert)
        triage = apply(alert, rule_output, llm_output=None)

        assert triage.final_priority == Priority.critical

    def test_rule_trace_intact_in_hybrid_mode(self):
        alert = make_alert(
            alert_type=AlertType.sepsis,
            vital_signs=VitalSigns(heart_rate=110.0, temperature=39.0, respiratory_rate=22.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload(confidence=0.85))
        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.explanation.explanation_mode == ExplanationMode.hybrid
        assert "SEPSIS_SIRS_GTE_2" in triage.explanation.rule_trace
        assert "SIRS_TEMP_ABNORMAL" in triage.explanation.rule_trace

    def test_rule_trace_intact_in_rules_only_mode(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        triage = apply(alert, rule_output, llm_output=None)

        assert "HR_GT_130" in triage.explanation.rule_trace

    def test_llm_has_no_routing_authority(self):
        alert = make_alert(
            alert_type=AlertType.low_spo2,
            vital_signs=VitalSigns(spo2=85.0),
        )
        rule_output = evaluate(alert)
        llm_out = LLMRawOutput(**_valid_llm_payload())

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.final_route in (
            "Rapid Response Team",
            "ICU Team (Intensivist + Nurse)",
        )

    def test_llm_cannot_escalate_priority_even_if_extra_attribute_is_present(self):
        alert = make_alert(
            alert_type=AlertType.tachycardia,
            vital_signs=VitalSigns(heart_rate=145.0),
        )
        rule_output = evaluate(alert)
        assert rule_output.baseline_priority == Priority.high

        llm_out = SimpleNamespace(
            summary="Explainability only.",
            rationale="Heart rate exceeds the high-priority threshold.",
            factors_considered=["Heart rate 145 bpm"],
            uncertainty_notes="No recent baseline available.",
            recommended_checks=["Recheck telemetry signal"],
            confidence=0.95,
            suggested_priority=Priority.critical,
        )

        triage = apply(alert, rule_output, llm_output=llm_out)

        assert triage.final_priority == Priority.high

    def test_rules_only_mode_has_populated_rule_trace(self):
        alert = make_alert(
            alert_type=AlertType.fall_risk,
            recent_context=__import__("models").RecentContext(fall_risk_score=65),
        )
        rule_output = evaluate(alert)
        triage = apply(alert, rule_output, llm_output=None)

        assert triage.explanation.explanation_mode == ExplanationMode.rules_only
        assert len(triage.explanation.rule_trace) > 0
        assert "FALL_HIGH_RISK_SCORE" in triage.explanation.rule_trace
