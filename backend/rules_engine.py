"""
Rules Engine (Layer 2) — deterministic, no ML, no external calls.

Design:
  RuleDefinition   — a named rule with a condition callable and outcome fields.
                     Rules are data, not code.
  Rule registries  — one list[RuleDefinition] per AlertType.
  _evaluate_ruleset() — generic evaluator; runs a registry, returns top results.
  evaluate()       — public API; dispatches to the correct registry.

Adding a new alert type:
  1. Add the value to AlertType in models.py.
  2. Define a List[RuleDefinition] (see existing examples).
  3. Register it in _RULE_REGISTRY.

Adding a rule to an existing type:
  1. Append a RuleDefinition to the relevant list.  Nothing else changes.

Route tie-breaking:
  When two fired rules share the same priority, the rule with the higher
  ROUTE_RANK wins route selection.  This ensures that repeat-escalation rules
  (which route to Charge Nurse) take precedence over lower-urgency primary rules
  at equal priority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from models import AlertIn, AlertType, Priority, PRIORITY_RANK, RuleOutput
from router import Routes, ROUTE_RANK


# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------

@dataclass
class RuleDefinition:
    rule_id:     str
    description: str
    condition:   Callable[[AlertIn], bool]
    priority:    Priority
    route:       str
    confidence:  float = field(default=1.0)   # 0–1, how reliable this rule is clinically


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _count_sirs_criteria(alert: AlertIn) -> int:
    """Count how many SIRS criteria are met in the alert's vital signs."""
    vs = alert.vital_signs
    count = 0
    if vs.temperature is not None and (vs.temperature > 38.3 or vs.temperature < 36.0):
        count += 1
    if vs.heart_rate is not None and vs.heart_rate > 90:
        count += 1
    if vs.respiratory_rate is not None and vs.respiratory_rate > 20:
        count += 1
    return count


# ---------------------------------------------------------------------------
# Rule registries
# ---------------------------------------------------------------------------

_TACHYCARDIA_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="HR_GT_130",
        description="Heart rate > 130 bpm — significant tachycardia",
        condition=lambda a: (v := a.vital_signs.heart_rate) is not None and v > 130,
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.95,
    ),
    RuleDefinition(
        rule_id="HR_110_130",
        description="Heart rate 110–130 bpm — moderate tachycardia",
        condition=lambda a: (v := a.vital_signs.heart_rate) is not None and 110 < v <= 130,
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.90,
    ),
    RuleDefinition(
        rule_id="HR_GT_100",
        description="Heart rate 100–110 bpm — mild tachycardia",
        condition=lambda a: (v := a.vital_signs.heart_rate) is not None and 100 < v <= 110,
        priority=Priority.low,
        route=Routes.BEDSIDE_ROUTINE,
        confidence=0.80,
    ),
    RuleDefinition(
        rule_id="TACHY_REPEAT_GTE_3",
        description="Tachycardia alert repeated ≥ 3 times — escalate to charge nurse",
        condition=lambda a: a.repeat_count >= 3,
        priority=Priority.high,
        route=Routes.CHARGE_NURSE,
        confidence=0.88,
    ),
]

_LOW_SPO2_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="SPO2_LT_88",
        description="SpO₂ < 88% — critical hypoxaemia",
        condition=lambda a: (v := a.vital_signs.spo2) is not None and v < 88,
        priority=Priority.critical,
        route=Routes.RAPID_RESPONSE,
        confidence=0.98,
    ),
    RuleDefinition(
        rule_id="SPO2_88_92",
        description="SpO₂ 88–92% — significant hypoxaemia",
        condition=lambda a: (v := a.vital_signs.spo2) is not None and 88 <= v < 92,
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.93,
    ),
    RuleDefinition(
        rule_id="SPO2_92_95",
        description="SpO₂ 92–95% — mild hypoxaemia",
        condition=lambda a: (v := a.vital_signs.spo2) is not None and 92 <= v < 95,
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.85,
    ),
    RuleDefinition(
        rule_id="SPO2_REPEAT_GTE_3",
        description="Low SpO₂ alert repeated ≥ 3 times — escalate",
        condition=lambda a: a.repeat_count >= 3,
        priority=Priority.high,
        route=Routes.CHARGE_NURSE,
        confidence=0.88,
    ),
]

_INFUSION_PUMP_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="PUMP_OCCLUSION",
        description="Infusion pump occlusion alarm",
        condition=lambda a: a.additional_context.get("alarm_type", "").lower() == "occlusion",
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.95,
    ),
    RuleDefinition(
        rule_id="PUMP_AIR_IN_LINE",
        description="Infusion pump air-in-line alarm",
        condition=lambda a: a.additional_context.get("alarm_type", "").lower() in ("air_in_line", "air_bubble"),
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.95,
    ),
    RuleDefinition(
        rule_id="PUMP_BATTERY_LOW",
        description="Infusion pump battery low — non-urgent, swap battery",
        condition=lambda a: a.additional_context.get("alarm_type", "").lower() == "battery_low",
        priority=Priority.medium,
        route=Routes.BEDSIDE_ROUTINE,
        confidence=0.99,
    ),
    RuleDefinition(
        rule_id="PUMP_ALARM_GENERIC",
        description="Infusion pump alarm — unrecognised alarm type",
        condition=lambda a: a.additional_context.get("alarm_type", "").lower() not in (
            "occlusion", "air_in_line", "air_bubble", "battery_low"
        ),
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.70,
    ),
    RuleDefinition(
        rule_id="PUMP_REPEAT_GTE_3",
        description="Pump alarm repeated ≥ 3 times — escalate to charge nurse",
        condition=lambda a: a.repeat_count >= 3,
        priority=Priority.high,
        route=Routes.CHARGE_NURSE,
        confidence=0.85,
    ),
]

_NURSE_CALL_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="NURSE_CALL_REPEAT_GTE_3",
        description="Nurse call repeated ≥ 3 times — escalate to charge nurse",
        condition=lambda a: a.repeat_count >= 3,
        priority=Priority.medium,
        route=Routes.CHARGE_NURSE,
        confidence=0.90,
    ),
    RuleDefinition(
        rule_id="NURSE_CALL_SINGLE",
        description="Single nurse call — routine response",
        condition=lambda a: a.repeat_count < 3,
        priority=Priority.low,
        route=Routes.BEDSIDE_ROUTINE,
        confidence=0.80,
    ),
]

_FALL_RISK_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="FALL_REPEAT_GTE_2",
        description="Fall sensor triggered ≥ 2 times — escalate",
        condition=lambda a: a.repeat_count >= 2,
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.90,
    ),
    RuleDefinition(
        rule_id="FALL_HIGH_RISK_SCORE",
        description="Fall risk score ≥ 45 (high-risk threshold on Morse scale)",
        condition=lambda a: (
            a.recent_context.fall_risk_score is not None
            and a.recent_context.fall_risk_score >= 45
        ),
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.85,
    ),
    RuleDefinition(
        rule_id="FALL_SENSOR_TRIGGERED",
        description="Fall sensor or bed-exit alarm triggered",
        condition=lambda a: True,  # always fires — alert_type itself implies trigger
        priority=Priority.medium,
        route=Routes.BEDSIDE_ROUTINE,
        confidence=0.80,
    ),
]

_SEPSIS_RULES: List[RuleDefinition] = [
    # Combined SIRS rules fire first — they drive the final priority upward.
    RuleDefinition(
        rule_id="SEPSIS_SIRS_GTE_2",
        description="Two or more SIRS criteria met — sepsis screen positive",
        condition=lambda a: _count_sirs_criteria(a) >= 2,
        priority=Priority.critical,
        route=Routes.RAPID_RESPONSE,
        confidence=0.88,
    ),
    RuleDefinition(
        rule_id="SEPSIS_SIRS_EQ_1",
        description="One SIRS criterion met — elevated concern, monitor closely",
        condition=lambda a: _count_sirs_criteria(a) == 1,
        priority=Priority.high,
        route=Routes.BEDSIDE_IMMEDIATE,
        confidence=0.75,
    ),
    # Individual criterion rules fire alongside the combined rules for full traceability.
    RuleDefinition(
        rule_id="SIRS_TEMP_ABNORMAL",
        description="Temperature outside normal range (> 38.3 °C or < 36.0 °C)",
        condition=lambda a: (v := a.vital_signs.temperature) is not None and (v > 38.3 or v < 36.0),
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.90,
    ),
    RuleDefinition(
        rule_id="SIRS_HR_GT_90",
        description="Heart rate > 90 bpm (SIRS tachycardia criterion)",
        condition=lambda a: (v := a.vital_signs.heart_rate) is not None and v > 90,
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.85,
    ),
    RuleDefinition(
        rule_id="SIRS_RR_GT_20",
        description="Respiratory rate > 20 /min (SIRS tachypnoea criterion)",
        condition=lambda a: (v := a.vital_signs.respiratory_rate) is not None and v > 20,
        priority=Priority.medium,
        route=Routes.BEDSIDE_5MIN,
        confidence=0.85,
    ),
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_RULE_REGISTRY: Dict[AlertType, List[RuleDefinition]] = {
    AlertType.tachycardia:   _TACHYCARDIA_RULES,
    AlertType.low_spo2:      _LOW_SPO2_RULES,
    AlertType.infusion_pump: _INFUSION_PUMP_RULES,
    AlertType.nurse_call:    _NURSE_CALL_RULES,
    AlertType.fall_risk:     _FALL_RISK_RULES,
    AlertType.sepsis:        _SEPSIS_RULES,
}


# ---------------------------------------------------------------------------
# Generic evaluator
# ---------------------------------------------------------------------------

def _evaluate_ruleset(
    alert: AlertIn,
    rules: List[RuleDefinition],
) -> Tuple[Priority, List[str], str, float]:
    """
    Run every rule in the set.  Among those that fire:
      - priority  → highest priority of any fired rule
      - route     → route of the rule with highest (priority_rank, route_rank)
      - confidence→ average confidence of all fired rules
    Returns (priority, matched_rule_ids, route, avg_confidence).
    """
    fired = [r for r in rules if r.condition(alert)]

    if not fired:
        return Priority.low, ["NO_RULE_MATCHED"], Routes.BEDSIDE_ROUTINE, 0.5

    # Select the "top" rule by (priority rank, route urgency rank).
    # ROUTE_RANK breaks ties so that escalation routes (Charge Nurse = 4)
    # beat lower-urgency primary routes (Bedside Immediate = 3) at equal priority.
    top = max(fired, key=lambda r: (PRIORITY_RANK[r.priority], ROUTE_RANK.get(r.route, 0)))
    avg_confidence = round(sum(r.confidence for r in fired) / len(fired), 3)

    return top.priority, [r.rule_id for r in fired], top.route, avg_confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(alert: AlertIn) -> RuleOutput:
    """
    Run the appropriate rule registry for alert.alert_type and return a RuleOutput.
    This is the only function that callers (main.py, tests) should use.
    """
    rules = _RULE_REGISTRY.get(alert.alert_type)
    if rules is None:
        return RuleOutput(
            baseline_priority=Priority.medium,
            matched_rules=["UNKNOWN_ALERT_TYPE"],
            suggested_route=Routes.BEDSIDE_ROUTINE,
            rule_confidence=0.0,
        )

    priority, matched, route, confidence = _evaluate_ruleset(alert, rules)

    return RuleOutput(
        baseline_priority=priority,
        matched_rules=matched,
        suggested_route=route,
        rule_confidence=confidence,
    )
