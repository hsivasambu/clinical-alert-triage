"""Recorded rules-only narratives: input facts, rule evidence, and router reasoning.

No diagnosis, treatment, or inferred missing measurement is generated here.
"""
from models import AlertIn, AlertType, ExplanationOutput, FallbackReason, RuleOutput
from rules_engine import evidence_for

ALERT_NAMES = {
    AlertType.tachycardia: "Heart-rate alert", AlertType.low_spo2: "Oxygen-saturation alert",
    AlertType.infusion_pump: "Infusion-pump alert", AlertType.nurse_call: "Nurse-call alert",
    AlertType.fall_risk: "Fall-risk alert", AlertType.sepsis: "Screening alert",
}
from evidence import VITAL_NAMES, observations_for


def build(alert: AlertIn, rules: RuleOutput, route: str, routing_reason: str,
          reason: FallbackReason, confidence: float | None = None) -> ExplanationOutput:
    evidence = evidence_for(alert, rules)
    factors = []
    for field, (label, unit) in VITAL_NAMES.items():
        value = getattr(alert.vital_signs, field)
        factors.append(f"Observed {label}: {value:g} {unit}." if value is not None else f"{label}: not provided; no normal value is assumed.")
    factors.append(f"Observed repeat count: {alert.repeat_count}." if "repeat_count" in alert.model_fields_set
                   else "Repeat count not provided; the evaluator uses its documented default of 0.")
    if alert.alert_type == AlertType.infusion_pump:
        factors.append(f"Observed alarm type: {alert.additional_context.alarm_type!r}." if alert.additional_context.alarm_type
                       else "Pump alarm type: not provided; the generic pump rule applies.")
        factors.append(f"Observed infusion value: {alert.additional_context.infusate!r}." if alert.additional_context.infusate
                       else "Infusion value: not provided; no drug keyword is assumed.")
    if alert.alert_type == AlertType.fall_risk:
        score = alert.recent_context.fall_risk_score
        factors.append(f"Observed fall-risk score: {score}." if score is not None else "Fall-risk score: not provided; the alert-type base rule still applies.")
    no_match = "NO_RULE_MATCHED" in rules.matched_rules
    summary = (f"{ALERT_NAMES[alert.alert_type]} {alert.alert_id}: no registered rule matched the supplied inputs. "
               if no_match else f"{ALERT_NAMES[alert.alert_type]} {alert.alert_id}: {len(evidence)} rule condition(s) matched. ")
    summary += f"The deterministic decision is {rules.baseline_priority.value}, routed to {route}."
    uncertainty = "This explanation describes supplied input and configured demo rules, not a clinical assessment. Missing measurements are unavailable, not normal."
    if rules.missing_fields:
        uncertainty += " Insufficient data for some rule or routing checks: " + ", ".join(rules.missing_fields) + ". Available-input rules still apply."
    else:
        uncertainty += " Inputs used by this alert's rule conditions are available; source accuracy and freshness are not independently verified."
    if no_match:
        uncertainty += " NO_RULE_MATCHED uses the existing Low / Bedside Nurse default with manual demo rule weight 0.5; this does not establish normality or safety. Human review is required to assess the incomplete or non-triggering input."
    checks = ["Verify the recorded alert/patient identifiers, unit, alert time, and source before accepting the decision.",
              "Compare the observed values and units against the recorded rule conditions; check source accuracy and freshness.",
              "Review the deterministic priority and destination, then accept or record a reasoned human override. The original system decision remains preserved."]
    if rules.missing_fields:
        checks.insert(1, "Verify unavailable rule inputs with the source: " + ", ".join(rules.missing_fields) + ". Do not infer values from their absence.")
    return ExplanationOutput(summary=summary, triggering_rule_ids=[id for id in rules.matched_rules if id != "NO_RULE_MATCHED"], context_observations=observations_for(alert),
        rationale=("No registered condition matched; the evaluator uses its documented default priority and destination. " if no_match else "Rules select the highest matched priority and use route urgency to break ties. ") + routing_reason + " Priority and route are independent of LLM output.",
        factors_considered=factors, uncertainty_notes=uncertainty, recommended_checks=checks,
        rule_trace=list(rules.matched_rules), rule_evidence=evidence, fallback_reason=reason,
        llm_confidence_estimate=confidence, explanation_version="deterministic-v2")
