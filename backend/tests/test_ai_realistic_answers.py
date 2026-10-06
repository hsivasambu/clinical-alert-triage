"""Realistic gpt-4o-mini style answers for the "AI-supported decision" demo, run through every check.

Each answer carries the kinds of slips seen on the live demo (unsupplied IDs, empty citations,
ordinary causal wording, numbers, priority words, escalation language in the narrative). A
reasonable answer must come through as AI output with its escalation applied.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest

from decision_layer import apply
from llm_explainer import explain_with_outcome
from models import AlertIn, ExplanationMode, Priority
from rules_engine import evaluate

ESCALATION = {"proposed_priority": "Medium", "reason": "Sedating medications (OBS_RECENT_MEDICATIONS), a high fall-risk score (OBS_FALL_RISK_SCORE) and the patient getting up alone while dizzy (OBS_MESSAGE_TEXT) warrant earlier bedside review than a routine call.",
              "context_evidence_ids": ["OBS_RECENT_MEDICATIONS", "OBS_FALL_RISK_SCORE", "OBS_MESSAGE_TEXT"]}


def answer(**changes):
    base = {
        "summary": "A single nurse call from 4-East Surgical matched NURSE_CALL_SINGLE, so the rules assigned Low priority routed to the Bedside Nurse (DECISION_FINAL).",
        "rationale": "NURSE_CALL_SINGLE is the only triggering rule because the repeat count is below 3. The router kept the rule-selected destination.",
        "factors_considered": ["The patient has 2 prior alerts in the last 24 hours (OBS_PRIOR_ALERTS_24H).",
                               "Recent medications include lorazepam and oxycodone (OBS_RECENT_MEDICATIONS).",
                               "The fall-risk score is 72 (OBS_FALL_RISK_SCORE)."],
        "uncertainty_notes": "No vital signs were provided, so the current physiological state is unknown.",
        "recommended_checks": ["Verify the medication list and administration times in the source record.", "Confirm the fall-risk score timestamp."],
        "triggering_rule_ids": ["NURSE_CALL_SINGLE"],
        "context_evidence_ids": ["OBS_PRIOR_ALERTS_24H", "OBS_RECENT_MEDICATIONS", "OBS_FALL_RISK_SCORE"],
        "escalation": ESCALATION, "confidence": 0.82}
    base.update(changes)
    return base


ANSWERS = {
    "clean": answer(),
    "unsupplied_ids_and_empty_context": answer(context_evidence_ids=["DECISION_FINAL", "NURSE_CALL_SINGLE", "OBS_DIZZINESS"],
        factors_considered=["Recent sedating medications are recorded.", "The patient reports dizziness."]),
    "due_to_wording": answer(rationale="The priority is Low due to a single call matching NURSE_CALL_SINGLE. However, the context is consistent with an increased fall concern."),
    "escalation_language_in_narrative": answer(summary="The rules assigned Low priority, but I recommend escalating to Medium priority because of sedating medications and fall risk.",
        rationale="NURSE_CALL_SINGLE matched. We should raise the priority given the context."),
    "diagnosis_sentence_dropped": answer(uncertainty_notes="No vital signs were provided. The dizziness may be caused by orthostatic hypotension. Medication timing is unknown."),
    "treatment_check_dropped": answer(recommended_checks=["Verify the medication list.", "Consider holding oxycodone and administering fluids."]),
    "numbers_and_time_windows": answer(factors_considered=["2 prior alerts in 24h (OBS_PRIOR_ALERTS_24H).", "Fall-risk score of 72 exceeds the usual threshold of 45.", "Patient attempted to walk within 10 minutes of the call."]),
    "missing_escalation_citations": answer(escalation={"proposed_priority": "medium", "reason": "OBS_FALL_RISK_SCORE and OBS_RECENT_MEDICATIONS warrant earlier review.", "context_evidence_ids": []}),
    "treated_as_wording": answer(uncertainty_notes="Missing vital signs are treated as unavailable, not normal."),
}


def demo_alert():
    return AlertIn.model_validate({
        "alert_id": "SIM-AI-SUPPORT", "source_system": "Nurse-Call-Panel", "alert_type": "nurse_call", "patient_id": "P-10042",
        "unit": "4-East Surgical", "room": "312", "bed": "A", "timestamp": "2026-10-06T19:23:38Z", "repeat_count": 0,
        "message_text": "Patient reports feeling dizzy and is trying to get up to the bathroom alone", "vital_signs": {},
        "recent_context": {"prior_alerts_24h": 2, "recent_medications": ["lorazepam", "oxycodone"], "fall_risk_score": 72,
                           "admission_reason": "Hip replacement recovery", "code_status": "Full"}})


def run(monkeypatch, raw):
    monkeypatch.setenv("OPENAI_API_KEY", "test"); monkeypatch.setenv("LLM_ENABLED", "true")
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(model="gpt-4o-mini-2024-07-18", choices=[SimpleNamespace(
        finish_reason="stop", message=SimpleNamespace(content=json.dumps(raw), refusal=None))])
    monkeypatch.setattr(openai, "OpenAI", MagicMock(return_value=client))
    alert = demo_alert(); rules = evaluate(alert)
    return apply(alert, rules, explain_with_outcome(alert, rules))


@pytest.mark.parametrize("name", ANSWERS)
def test_reasonable_answers_come_through_with_escalation(monkeypatch, name):
    result = run(monkeypatch, ANSWERS[name])
    assert result.explanation.explanation_mode == ExplanationMode.hybrid, (name, result.provenance.validation_issues)
    assert result.explanation.ai_adjustment.status == "applied", result.explanation.ai_adjustment
    assert result.final_priority == Priority.medium and result.rule_output.baseline_priority == Priority.low
    shown = " ".join([result.explanation.summary, result.explanation.rationale, result.explanation.uncertainty_notes,
                      *result.explanation.factors_considered, *result.explanation.recommended_checks]).lower()
    for banned in ["caused by", "hypotension", "administering", "10 minutes", "45"]:
        assert banned not in shown, (name, banned)


def test_flagged_wording_is_recorded(monkeypatch):
    result = run(monkeypatch, ANSWERS["due_to_wording"])
    assert "flagged_wording" in result.provenance.validation_issues


@pytest.mark.parametrize("raw", [
    answer(summary="Diagnosis: orthostatic hypotension."),  # Nothing valid left in a required field.
    answer(recommended_checks=["Administer fluids."]),
    answer(triggering_rule_ids=["FABRICATED_RULE"]),
])
def test_unusable_answers_still_fall_back(monkeypatch, raw):
    result = run(monkeypatch, raw)
    assert result.explanation.explanation_mode == ExplanationMode.rules_only
    assert result.final_priority == Priority.low


def test_narrative_may_not_claim_more_than_one_level(monkeypatch):
    raw = answer(summary="The rules assigned Low priority, but this needs Critical priority. OBS_FALL_RISK_SCORE is recorded.")
    result = run(monkeypatch, raw)
    assert "Critical priority" not in result.explanation.summary and result.final_priority == Priority.medium
