"""Authoritative evidence catalog. Context is observed input, never a fired rule."""
from models import AlertIn, EvidenceObservation, Priority, RuleOutput
from router import resolve_route_with_reason
from rules_engine import evidence_for

VITAL_NAMES = {
    "heart_rate": ("Heart rate", "bpm"), "spo2": ("SpO2", "%"),
    "blood_pressure_systolic": ("Systolic pressure", "mmHg"), "blood_pressure_diastolic": ("Diastolic pressure", "mmHg"),
    "respiratory_rate": ("Respiratory rate", "/min"), "temperature": ("Temperature", "C"),
}


def observations_for(alert: AlertIn) -> list[EvidenceObservation]:
    rows = [EvidenceObservation(evidence_id=f"OBS_{key.upper()}", label=label,
            value=getattr(alert.vital_signs, key), unit=unit, available=getattr(alert.vital_signs, key) is not None)
            for key, (label, unit) in VITAL_NAMES.items()]
    rows += [EvidenceObservation(evidence_id="OBS_UNIT", label="Unit", value=alert.unit),
             EvidenceObservation(evidence_id="OBS_REPEAT_COUNT", label="Repeat count", value=alert.repeat_count if "repeat_count" in alert.model_fields_set else None, available="repeat_count" in alert.model_fields_set)]
    for key in ["alarm_type", "infusate"]:
        value = getattr(alert.additional_context, key)
        if value is not None:
            rows.append(EvidenceObservation(evidence_id=f"OBS_{key.upper()}", label=key.replace("_", " "), value=value))
    ctx = alert.recent_context
    if ctx.fall_risk_score is not None:
        rows.append(EvidenceObservation(evidence_id="OBS_FALL_RISK_SCORE", label="Fall-risk score", value=ctx.fall_risk_score))
    # Patient context the rules do not evaluate; the model may cite it when proposing a bounded escalation.
    if ctx.prior_alerts_24h:
        rows.append(EvidenceObservation(evidence_id="OBS_PRIOR_ALERTS_24H", label="Prior alerts in last 24h", value=ctx.prior_alerts_24h))
    if ctx.recent_medications:
        rows.append(EvidenceObservation(evidence_id="OBS_RECENT_MEDICATIONS", label="Recent medications", value=list(ctx.recent_medications)))
    for key in ["admission_reason", "code_status"]:
        value = getattr(ctx, key)
        if value:
            rows.append(EvidenceObservation(evidence_id=f"OBS_{key.upper()}", label=key.replace("_", " ").capitalize(), value=value))
    # Untrusted source context is retained separately; it cannot create rule evidence.
    for key in ["message_text", "device_type"]:
        value = getattr(alert, key)
        if value:
            rows.append(EvidenceObservation(evidence_id=f"OBS_{key.upper()}", label=f"Recorded {key.replace('_', ' ')}", value=value))
    return rows


def catalog_for(alert: AlertIn, rules: RuleOutput) -> dict:
    route, rationale = resolve_route_with_reason(alert, rules.baseline_priority, rules.suggested_route)
    # Destination the router would pick at each priority, so narrative that mentions a proposed escalation is not a contradiction.
    escalated_route = {p.value: resolve_route_with_reason(alert, p, rules.suggested_route)[0] for p in Priority}
    return {"deterministic_decision": {"evidence_id": "DECISION_FINAL", "priority": rules.baseline_priority.value, "route": route, "routing_reason": rationale},
            "escalated_route": escalated_route,
            "triggering_rules": [item.model_dump() for item in evidence_for(alert, rules) if item.rule_id != "NO_RULE_MATCHED"],
            "policy_markers": [id for id in rules.matched_rules if id == "NO_RULE_MATCHED"],
            "context_observations": [item.model_dump() for item in observations_for(alert)], "missing_inputs": rules.missing_fields}
