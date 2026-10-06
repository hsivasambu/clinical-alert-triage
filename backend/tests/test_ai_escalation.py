"""Bounded AI escalation: one level up at most, never down, evidence-checked and audited."""
import pytest

from decision_layer import apply
from explanation_contract import validate_narrative
from llm_explainer import LLMRawOutput
from models import AlertType, ExplanationMode, Priority, RecentContext
from router import Routes
from rules_engine import evaluate
from tests.conftest import make_alert


def nurse_call():
    return make_alert(alert_type=AlertType.nurse_call, unit="4-East Surgical", recent_context=RecentContext(
        prior_alerts_24h=2, recent_medications=["lorazepam", "oxycodone"], fall_risk_score=72,
        admission_reason="Hip replacement recovery"))


def output(alert, escalation, confidence=0.8, **changes):
    rules = evaluate(alert)
    data = dict(summary="DECISION_FINAL records the deterministic decision.",
                rationale="NURSE_CALL_SINGLE matched and the router recorded DECISION_FINAL.",
                factors_considered=["OBS_PRIOR_ALERTS_24H shows 2 prior alerts in the last 24h."],
                uncertainty_notes="Source accuracy has not been independently verified.",
                recommended_checks=["Verify source timestamps and units."],
                triggering_rule_ids=[r for r in rules.matched_rules if r != "NO_RULE_MATCHED"],
                context_evidence_ids=["OBS_PRIOR_ALERTS_24H"], confidence=confidence, escalation=escalation)
    data.update(changes)
    return rules, LLMRawOutput(**data)


def proposal(priority="Medium", reason="OBS_RECENT_MEDICATIONS and OBS_FALL_RISK_SCORE warrant earlier bedside review.",
             ids=("OBS_RECENT_MEDICATIONS", "OBS_FALL_RISK_SCORE")):
    return {"proposed_priority": priority, "reason": reason, "context_evidence_ids": list(ids)}


def test_context_counts_are_accepted_in_narrative():
    alert = nurse_call()
    rules, out = output(alert, None)
    assert validate_narrative(alert, rules, out) == []


def test_escalation_is_applied_one_level_and_audited():
    alert = nurse_call()
    rules, out = output(alert, proposal())
    result = apply(alert, rules, out)
    assert rules.baseline_priority == Priority.low
    assert result.explanation.explanation_mode == ExplanationMode.hybrid
    adj = result.explanation.ai_adjustment
    assert adj.status == "applied" and adj.decline_reason is None
    assert result.final_priority == Priority.medium == adj.applied_priority
    assert adj.baseline_priority == Priority.low and adj.applied_route == result.final_route


def test_proposed_priority_case_is_normalized():
    alert = nurse_call()
    rules, out = output(alert, proposal(priority="medium "))
    assert apply(alert, rules, out).final_priority == Priority.medium


def test_escalation_is_capped_at_one_level():
    alert = nurse_call()
    rules, out = output(alert, proposal(priority="Critical"))
    result = apply(alert, rules, out)
    assert result.final_priority == Priority.medium
    assert result.explanation.ai_adjustment.proposed_priority == Priority.critical


def test_router_still_chooses_destination_after_escalation():
    alert = make_alert(alert_type=AlertType.nurse_call, repeat_count=3, unit="ICU",
                       recent_context=RecentContext(prior_alerts_24h=4))
    rules, out = output(alert, proposal(priority="High", reason="OBS_PRIOR_ALERTS_24H warrants earlier review.", ids=["OBS_PRIOR_ALERTS_24H"]),
                        rationale="NURSE_CALL_REPEAT_GTE_3 matched and the router recorded DECISION_FINAL.",
                        factors_considered=["OBS_PRIOR_ALERTS_24H shows 4 prior alerts."])
    result = apply(alert, rules, out)
    assert rules.baseline_priority == Priority.medium
    assert result.final_priority == Priority.high and result.final_route == Routes.ICU_TEAM


@pytest.mark.parametrize("escalation,confidence,decline", [
    (proposal(priority="Low"), 0.8, "not_an_escalation"),
    (proposal(ids=["OBS_NOT_SUPPLIED"]), 0.8, "evidence_mismatch"),
    (proposal(ids=["OBS_HEART_RATE"]), 0.8, "evidence_mismatch"),  # Supplied but unavailable.
    (proposal(reason="OBS_RECENT_MEDICATIONS suggests sepsis."), 0.8, "content_rejected"),
    (proposal(reason="OBS_FALL_RISK_SCORE of 90 warrants review."), 0.8, "evidence_mismatch"),
])
def test_unsupported_escalations_are_recorded_but_not_applied(escalation, confidence, decline):
    alert = nurse_call()
    rules, out = output(alert, escalation, confidence=confidence)
    result = apply(alert, rules, out)
    assert result.final_priority == rules.baseline_priority
    assert result.explanation.ai_adjustment.status == "declined"
    assert result.explanation.ai_adjustment.decline_reason == decline


def test_rejected_narrative_ignores_escalation():
    alert = nurse_call()
    rules, out = output(alert, proposal(), summary="This is caused by medication.")
    result = apply(alert, rules, out)
    assert result.explanation.explanation_mode == ExplanationMode.rules_only
    assert result.explanation.ai_adjustment is None and result.final_priority == Priority.low


def test_critical_baseline_cannot_be_escalated_or_downgraded():
    alert = make_alert(alert_type=AlertType.low_spo2, unit="ICU", recent_context=RecentContext(prior_alerts_24h=2))
    alert.vital_signs.spo2 = 85
    rules = evaluate(alert)
    assert rules.baseline_priority == Priority.critical
    out = LLMRawOutput(summary="DECISION_FINAL records the deterministic decision.", rationale="SPO2_LT_88 matched.",
        factors_considered=["OBS_SPO2 supplies context."], uncertainty_notes="Not verified.", recommended_checks=["Verify source."],
        triggering_rule_ids=[r for r in rules.matched_rules if r != "NO_RULE_MATCHED"], context_evidence_ids=["OBS_SPO2"], confidence=0.8,
        escalation=proposal(priority="High", reason="OBS_PRIOR_ALERTS_24H warrants review.", ids=["OBS_PRIOR_ALERTS_24H"]))
    result = apply(alert, rules, out)
    assert result.final_priority == Priority.critical
    assert result.explanation.ai_adjustment.decline_reason == "not_an_escalation"


@pytest.mark.parametrize("sentence,accepted", [
    ("OBS_UNIT records 4-East Surgical.", True),  # Digits inside a supplied value.
    ("NURSE_CALL_SINGLE matched because the repeat count is below 3.", True),  # Rule threshold.
    ("1 rule matched: NURSE_CALL_SINGLE.", True),
    ("OBS_FALL_RISK_SCORE is 72.", True),
    ("OBS_UNIT records 5-East Surgical.", False),
    ("OBS_PRIOR_ALERTS_24H shows 7 prior alerts.", False),
    ("Review within 15 minutes.", False),
])
def test_numbers_must_come_from_supplied_evidence(sentence, accepted):
    alert = nurse_call()
    rules, out = output(alert, None, summary=sentence, context_evidence_ids=["OBS_UNIT", "OBS_PRIOR_ALERTS_24H", "OBS_FALL_RISK_SCORE"])
    assert (validate_narrative(alert, rules, out) == []) is accepted


def test_inline_observation_ids_are_added_to_citations():
    import json
    from llm_explainer import _parse_and_validate
    from provenance import generation_metadata
    alert = nurse_call()
    rules = evaluate(alert)
    raw = dict(summary="OBS_FALL_RISK_SCORE and OBS_RECENT_MEDICATIONS are recorded.", rationale="NURSE_CALL_SINGLE matched; DECISION_FINAL is recorded.",
               factors_considered=["OBS_UNIT is recorded."], uncertainty_notes="Not verified.", recommended_checks=["Verify source."],
               triggering_rule_ids=["NURSE_CALL_SINGLE"], context_evidence_ids=["OBS_UNIT"], confidence=0.8, escalation=None)
    result = _parse_and_validate(alert, rules, json.dumps(raw), generation_metadata(alert, rules))
    assert result.context_evidence_ids == ["OBS_UNIT", "OBS_FALL_RISK_SCORE", "OBS_RECENT_MEDICATIONS"]


def ai_supported_example():
    """The frontend "AI-supported decision" scenario as the live demo submits it."""
    from models import AlertIn
    return AlertIn.model_validate({
        "alert_id": "SIM-AI-SUPPORT", "source_system": "Nurse-Call-Panel", "alert_type": "nurse_call", "patient_id": "P-10042",
        "unit": "4-East Surgical", "room": "312", "bed": "A", "timestamp": "2026-10-06T19:23:38Z", "repeat_count": 0,
        "message_text": "Patient reports feeling dizzy and is trying to get up to the bathroom alone",
        "vital_signs": {}, "recent_context": {"prior_alerts_24h": 2, "recent_medications": ["lorazepam", "oxycodone"],
        "fall_risk_score": 72, "admission_reason": "Hip replacement recovery", "code_status": "Full"}})


@pytest.mark.parametrize("context_ids,factors", [
    # Live failure: references outside the supplied observations rejected the whole answer.
    (["OBS_FALL_RISK_SCORE", "DECISION_FINAL", "NURSE_CALL_SINGLE"], ["OBS_FALL_RISK_SCORE is recorded."]),
    (["OBS_DIZZINESS", "OBS_RECENT_MEDICATIONS"], ["OBS_RECENT_MEDICATIONS is recorded.", "OBS_DIZZINESS is recorded in the message."]),
    ([], ["OBS_PRIOR_ALERTS_24H records 2 prior alerts in the last 24h; room 312 is noted."]),
])
def test_ai_supported_example_survives_reference_mistakes(monkeypatch, context_ids, factors):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import openai
    from llm_explainer import explain_with_outcome
    monkeypatch.setenv("OPENAI_API_KEY", "test"); monkeypatch.setenv("LLM_ENABLED", "true")
    raw = {"summary": "A single assistance call matched NURSE_CALL_SINGLE; DECISION_FINAL records the decision.",
           "rationale": "NURSE_CALL_SINGLE is the only triggering rule, so the router kept the rule-selected destination.",
           "factors_considered": [*factors, "OBS_UNIT records 4-East Surgical."],
           "uncertainty_notes": "No vital signs were supplied.", "recommended_checks": ["Verify the recorded medication list."],
           "triggering_rule_ids": [], "context_evidence_ids": context_ids, "confidence": 0.8,
           "escalation": {"proposed_priority": "Medium", "reason": "OBS_RECENT_MEDICATIONS, OBS_FALL_RISK_SCORE and OBS_MESSAGE_TEXT warrant earlier bedside review.",
                          "context_evidence_ids": ["OBS_RECENT_MEDICATIONS", "OBS_FALL_RISK_SCORE", "OBS_STAFFING"]}}
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(model="gpt-4o-mini-2024-07-18", choices=[SimpleNamespace(
        finish_reason="stop", message=SimpleNamespace(content=json.dumps(raw), refusal=None))])
    monkeypatch.setattr(openai, "OpenAI", MagicMock(return_value=client))
    alert = ai_supported_example(); rules = evaluate(alert)
    result = apply(alert, rules, explain_with_outcome(alert, rules))
    assert result.explanation.explanation_mode == ExplanationMode.hybrid, result.provenance.validation_issues
    assert result.provenance.validation_outcome == "accepted_by_practical_checks"
    assert set(result.explanation.referenced_context_ids) <= {o.evidence_id for o in result.explanation.context_observations}
    assert result.explanation.ai_adjustment.status == "applied" and result.final_priority == Priority.medium
    assert "OBS_STAFFING" not in result.explanation.ai_adjustment.context_evidence_ids


def test_invented_rule_id_still_rejects(monkeypatch):
    from llm_explainer import LLMFallbackError, _parse_and_validate
    from provenance import generation_metadata
    import json
    alert = ai_supported_example(); rules = evaluate(alert)
    raw = dict(summary="DECISION_FINAL is recorded.", rationale="NURSE_CALL_SINGLE matched.", factors_considered=["OBS_UNIT is recorded."],
               uncertainty_notes="Not verified.", recommended_checks=["Verify source."], triggering_rule_ids=["FABRICATED_RULE"],
               context_evidence_ids=["OBS_UNIT"], confidence=0.8)
    with pytest.raises(LLMFallbackError):
        _parse_and_validate(alert, rules, json.dumps(raw), generation_metadata(alert, rules))
