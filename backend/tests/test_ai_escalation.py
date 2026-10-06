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
    (proposal(), 0.55, "low_confidence"),
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
