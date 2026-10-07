"""The UI's example catalog (frontend/src/simulator/examples.json) behaves as each example claims.

Rules-based examples: the rules alone decide. AI-supported examples: the rules give Low or Medium and the
patient context carries enough supplied evidence that a gpt-4o-mini style context review is applied.
"""
import json
from pathlib import Path

import pytest

from decision_layer import apply
from evidence import observations_for
from models import AlertIn, ExplanationMode, Priority
from rules_engine import evaluate
from tests.test_ai_realistic_answers import run

EXAMPLES = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/simulator/examples.json").read_text())
AI = [e for e in EXAMPLES if e["mode"] == "ai"]
RULES = [e for e in EXAMPLES if e["mode"] == "rules"]
NEXT = {Priority.low: Priority.medium, Priority.medium: Priority.high, Priority.high: Priority.critical}
CONTEXT_IDS = ["OBS_RECENT_MEDICATIONS", "OBS_FALL_RISK_SCORE", "OBS_PRIOR_ALERTS_24H", "OBS_MESSAGE_TEXT"]


def alert(example):
    return AlertIn.model_validate({**example["alert"], "alert_id": f"SIM-{example['id']}", "timestamp": "2026-10-07T01:00:00Z"})


def model_answer(example):
    a = alert(example); rules = evaluate(a)
    proposed = NEXT[rules.baseline_priority].value
    ctx = a.recent_context
    return a, rules, {
        "escalation": {"recommend": True, "proposed_priority": proposed.lower(),
            "reason": f"The patient received {', '.join(ctx.recent_medications)} (OBS_RECENT_MEDICATIONS), has a fall-risk score of {ctx.fall_risk_score} "
                      f"(OBS_FALL_RISK_SCORE) and {ctx.prior_alerts_24h} prior alerts today (OBS_PRIOR_ALERTS_24H), and the message (OBS_MESSAGE_TEXT) "
                      "describes a new change, which makes a delay riskier.",
            "context_evidence_ids": CONTEXT_IDS},
        "summary": f"The rules matched {', '.join(rules.matched_rules)} and assigned {rules.baseline_priority.value} priority (DECISION_FINAL).",
        "rationale": f"{rules.matched_rules[0]} is the triggering rule. The router kept the destination recorded in DECISION_FINAL.",
        "factors_considered": [f"Recent medications include {', '.join(ctx.recent_medications)} (OBS_RECENT_MEDICATIONS).",
                               f"{ctx.prior_alerts_24h} prior alerts in the last 24 hours (OBS_PRIOR_ALERTS_24H).",
                               f"The recorded message says: {a.message_text} (OBS_MESSAGE_TEXT)."],
        "uncertainty_notes": "Medication timing is not recorded, and the message text has not been verified at the bedside.",
        "recommended_checks": ["Verify the medication list and timestamps in the source record.", "Confirm the alert source and unit."],
        "triggering_rule_ids": rules.matched_rules, "context_evidence_ids": ["OBS_RECENT_MEDICATIONS", "OBS_PRIOR_ALERTS_24H"],
        "confidence": 0.78}


def test_five_examples_per_mode():
    assert len(AI) == 5 and len(RULES) == 5 and len({e["id"] for e in EXAMPLES}) == 10


@pytest.mark.parametrize("example", AI, ids=[e["id"] for e in AI])
def test_ai_examples_leave_room_and_supply_context(example):
    a = alert(example); rules = evaluate(a)
    assert rules.baseline_priority in (Priority.low, Priority.medium)
    supplied = {item.evidence_id for item in observations_for(a)}
    assert set(CONTEXT_IDS) <= supplied  # Medications, fall risk, prior alerts and a message for the model to weigh.


@pytest.mark.parametrize("example", AI, ids=[e["id"] for e in AI])
def test_ai_examples_escalate_with_a_context_review(monkeypatch, example):
    a, rules, raw = model_answer(example)
    monkeypatch.setattr("tests.test_ai_realistic_answers.demo_alert", lambda: a)
    result = run(monkeypatch, raw)
    assert result.explanation.explanation_mode == ExplanationMode.hybrid, result.provenance.validation_issues
    assert result.explanation.ai_adjustment.status == "applied", result.explanation.ai_adjustment
    assert result.final_priority == NEXT[rules.baseline_priority]


@pytest.mark.parametrize("example", RULES, ids=[e["id"] for e in RULES])
def test_rules_examples_are_decided_by_rules(example):
    a = alert(example); result = apply(a, evaluate(a))
    assert result.final_priority in (Priority.medium, Priority.high, Priority.critical)
    assert example["alert"]["recent_context"]["prior_alerts_24h"] == 0 and not example["alert"]["recent_context"]["recent_medications"]
