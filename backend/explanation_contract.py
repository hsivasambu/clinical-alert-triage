"""Conservative syntactic checks, not a semantic safety guarantee.

Unrecognized numeric claims are rejected. Known measurement forms must match
recorded values and cite their observation ID. Rule/observation references must
belong to the supplied catalog. Phrase patterns catch common forbidden claims;
paraphrases, implicit causation and multilingual content can escape these checks.
"""
import re
from evidence import catalog_for
from models import AlertIn, RuleOutput
from router import Routes

VALIDATION_VERSION = "evidence-contract-v1"
PROHIBITED = re.compile(
    r"\b(?:diagnos\w*|differential|probable cause|likely cause|caused by|due to|secondary to|consistent with|"
    r"suggests? (?:sepsis|infection|arrhythmia)|sepsis|hypox(?:emia|aemia)|arrhythmia|"
    r"treat\w*|administer\w*|prescrib\w*|dosage|intubat\w*|"
    r"(?:give|start|increase|decrease|stop) (?:oxygen|fluids|antibiotics|medication|insulin|heparin)|"
    r"(?:should|recommend|must|need to) (?:escalate|downgrade|upgrade|reroute|route|transfer|change)|"
    r"(?:change|override|raise|lower|increase|decrease) (?:the )?(?:priority|severity|routing|route))\b", re.I)
MEASUREMENTS = {
    "heart_rate": r"(?:heart rate|HR)", "spo2": r"(?:SpO2|SpO₂|oxygen saturation)",
    "respiratory_rate": r"(?:respiratory rate|RR)", "temperature": r"(?:temperature|temp)",
    "blood_pressure_systolic": r"(?:systolic(?: pressure)?|SBP)", "blood_pressure_diastolic": r"(?:diastolic(?: pressure)?|DBP)",
    "repeat_count": r"(?:repeat count)", "fall_risk_score": r"(?:fall[- ]risk score)",
}


def validate_narrative(alert: AlertIn, rules: RuleOutput, output) -> list[str]:
    catalog = catalog_for(alert, rules)
    triggers = {item["rule_id"] for item in catalog["triggering_rules"]}
    observations = {item["evidence_id"]: item for item in catalog["context_observations"]}
    refs = set(output.triggering_rule_ids)
    context = set(output.context_evidence_ids)
    issues = []
    if refs != triggers: issues.append("trigger_references_mismatch")
    if not context or not context.issubset(observations): issues.append("context_references_mismatch")
    if len(refs) != len(output.triggering_rule_ids) or len(context) != len(output.context_evidence_ids): issues.append("duplicate_evidence_references")
    text = "\n".join([output.summary, output.rationale, *output.factors_considered, output.uncertainty_notes, *output.recommended_checks])
    if PROHIBITED.search(text): issues.append("prohibited_content_pattern")
    known_ids = triggers | set(observations) | set(catalog["policy_markers"]) | {"DECISION_FINAL"}
    for id in re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text):
        if id not in known_ids: issues.append("unknown_inline_evidence_id")
        elif id in triggers and id not in refs: issues.append("uncited_inline_rule")
        elif id in observations and id not in context: issues.append("uncited_inline_observation")
    # Recognize labeled numeric observations. Threshold prose and unrecognized
    # numeric formats are rejected: the server renders rule conditions instead.
    covered = []
    units = {"heart_rate": "bpm", "spo2": "%", "respiratory_rate": "/min", "temperature": "C", "blood_pressure_systolic": "mmHg", "blood_pressure_diastolic": "mmHg"}
    for key, label in MEASUREMENTS.items():
        pattern = rf"\b{label}\s*(?::|of|is|equals|=)?\s*(-?\d+(?:\.\d+)?)(?![\d.])"
        for match in re.finditer(pattern, text, re.I):
            id = f"OBS_{key.upper()}"
            observation = observations.get(id)
            if not observation or not observation["available"] or id not in context or float(match.group(1)) != observation["value"]:
                issues.append("measurement_mismatch")
            supplied_unit = re.match(r"\s*(bpm|mmHg|kPa|Hz|%|°?C|°?F|K|/min|beats/min|breaths/min)(?![A-Za-z])", text[match.end():], re.I)
            if supplied_unit:
                normalized = supplied_unit.group(1).replace("°", "").lower()
                aliases = {"beats/min": "bpm", "breaths/min": "/min"}
                if aliases.get(normalized, normalized) != units.get(key, "").lower(): issues.append("measurement_unit_mismatch")
            covered.append(match.span(1))
    for match in re.finditer(r"(?<![\w])[-+]?\d+(?:\.\d+)?", text):
        if not any(start <= match.start() and match.end() <= end for start, end in covered): issues.append("unverified_numeric_claim")
    decision = catalog["deterministic_decision"]
    for match in re.finditer(r"\b(Critical|High|Medium|Low)\s+(?:priority|severity)\b|\bpriority\s*(?:is|:|=|of)?\s*(Critical|High|Medium|Low)\b", text, re.I):
        if (match.group(1) or match.group(2)).lower() != decision["priority"].lower(): issues.append("priority_contradiction")
    route_spans = []
    for route in sorted({v for k, v in vars(Routes).items() if k.isupper()}, key=len, reverse=True):
        for match in re.finditer(re.escape(route), text, re.I):
            if any(a <= match.start() and match.end() <= b for a, b in route_spans): continue
            route_spans.append(match.span())
            if route != decision["route"]: issues.append("route_contradiction")
    return sorted(set(issues))


def rejection_reason(issues: list[str]) -> str:
    if "prohibited_content_pattern" in issues: return "content_rejected"
    if any(issue.endswith("contradiction") for issue in issues): return "contradiction"
    return "evidence_mismatch"
