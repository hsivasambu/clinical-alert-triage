"""Conservative syntactic checks, not a semantic safety guarantee.

Unrecognized numeric claims are rejected. Known measurement forms must match
recorded values and cite their observation ID. Rule/observation references must
belong to the supplied catalog. Phrase patterns catch common forbidden claims;
paraphrases, implicit causation and multilingual content can escape these checks.
"""
import logging
import re
from evidence import catalog_for
from models import AlertIn, RuleOutput
from router import Routes

logger = logging.getLogger(__name__)

VALIDATION_VERSION = "evidence-contract-v5"
# Hard patterns reject: diagnoses, causal clinical claims, treatment directives, and any argument
# for lowering or rerouting the decision. A sentence or list item that hits one is dropped first
# (llm_explainer); the answer is rejected only when a required field has nothing left.
_CLINICAL = (r"diagnos\w*|differential|probable cause|likely cause|caused by|"
    r"suggests? (?:sepsis|infection|arrhythmia)|sepsis(?![- ]screen)|hypox(?:emia|aemia)|arrhythmia|"
    r"administer\w*|prescrib\w*|dosage|intubat\w*|treat(?:ment)? (?:with|for|of)|"
    r"(?:give|start|increase|decrease|stop) (?:oxygen|fluids|antibiotics|medication|insulin|heparin)")
_DECISION = (r"(?:should|recommend|must|need to) (?:downgrade|reroute|route|transfer)|"
    r"(?:lower|decrease|reduce) (?:the )?(?:priority|severity)|(?:change|override) (?:the )?(?:routing|route)")
PROHIBITED = re.compile(rf"\b(?:{_CLINICAL}|{_DECISION})\b", re.I)
# An escalation proposal is decision language by design, but still may not diagnose or treat.
CLINICAL_PROHIBITED = re.compile(rf"\b(?:{_CLINICAL})\b", re.I)
# Ordinary wording that is recorded as a flag on an accepted answer, never a rejection.
FLAGGED = re.compile(r"\b(?:due to|secondary to|consistent with|"
    r"(?:should|recommend\w*|must|need to) (?:escalat\w*|upgrad\w*|rais\w*)|"
    r"(?:raise|increase|change|override|escalate) (?:the )?(?:priority|severity))\b", re.I)
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
    if not context.issubset(observations): issues.append("context_references_mismatch")
    if len(refs) != len(output.triggering_rule_ids) or len(context) != len(output.context_evidence_ids): issues.append("duplicate_evidence_references")
    text = "\n".join([output.summary, output.rationale, *output.factors_considered, output.uncertainty_notes, *output.recommended_checks])
    if found := PROHIBITED.search(text):
        logger.warning("Narrative rejected for prohibited phrase: %r", found.group(0))
        issues.append("prohibited_content_pattern")
    issues += _evidence_issues(text, catalog, refs, context)
    issues += _contradictions(text, catalog, _proposed(output))
    return sorted(set(issues))


def _contradictions(text: str, catalog: dict, proposed=None) -> list[str]:
    """Priority/route mentions must match the decision, or the one-level-up decision an escalation proposes."""
    issues, decision = [], catalog["deterministic_decision"]
    priorities, routes = {decision["priority"].lower()}, {decision["route"]}
    if proposed is not None:  # Only the one-level-up decision the escalation could actually produce.
        order = ["Low", "Medium", "High", "Critical"]
        step = order[min(order.index(decision["priority"]) + 1, len(order) - 1)]
        priorities.add(step.lower()); routes.add(catalog["escalated_route"][step])
    for match in re.finditer(r"\b(Critical|High|Medium|Low)\s+(?:priority|severity)\b|\bpriority\s*(?:is|:|=|of)?\s*(Critical|High|Medium|Low)\b", text, re.I):
        if (match.group(1) or match.group(2)).lower() not in priorities: issues.append("priority_contradiction")
    route_spans = []
    for route in sorted({v for k, v in vars(Routes).items() if k.isupper()}, key=len, reverse=True):
        for match in re.finditer(re.escape(route), text, re.I):
            if any(a <= match.start() and match.end() <= b for a, b in route_spans): continue
            route_spans.append(match.span())
            if route not in routes: issues.append("route_contradiction")
    return issues


def flagged_wording(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in FLAGGED.finditer(text)})


def _evidence_issues(text: str, catalog: dict, refs: set, context: set) -> list[str]:
    triggers = {item["rule_id"] for item in catalog["triggering_rules"]}
    observations = {item["evidence_id"]: item for item in catalog["context_observations"]}
    issues = []
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
    # Digits inside supplied text (unit "4-East", message text, rule conditions) are quoted evidence, not claims.
    quoted = [item["condition"] for item in catalog["triggering_rules"]]
    for item in observations.values():
        values = item["value"] if isinstance(item["value"], list) else [item["value"]]
        quoted += [v for v in values if isinstance(v, str) and len(v) > 1]
    for value in quoted:
        covered += [m.span() for m in re.finditer(re.escape(value), text, re.I)]
    # Unlabeled numbers are accepted when they equal a cited observation value ("2 prior alerts"), a
    # triggering-rule threshold ("repeat count below 3") or the number of triggering rules ("1 rule").
    allowed = {item["value"] for id, item in observations.items() if id in context and item["available"]
               and isinstance(item["value"], (int, float)) and not isinstance(item["value"], bool)}
    allowed |= {float(n) for item in catalog["triggering_rules"] for n in re.findall(r"\d+(?:\.\d+)?", item["condition"])}
    allowed.add(len(triggers))
    unverified = []
    for match in re.finditer(r"(?<![\w])[-+]?\d+(?:\.\d+)?", text):
        if any(start <= match.start() and match.end() <= end for start, end in covered): continue
        if float(match.group(0)) in allowed: continue
        if match.group(0) == "24" and re.match(r"(?:h\b|-? ?hours?\b|-hour\b)", text[match.end():], re.I): continue
        unverified.append(match.group(0))
    if unverified:
        # Raw provider text is not archived; the offending tokens alone make rejections diagnosable in logs.
        logger.warning("Narrative rejected for unverified numbers: %s", ", ".join(unverified[:10]))
        issues.append("unverified_numeric_claim")
    return issues


def _proposed(output):
    escalation = getattr(output, "escalation", None)
    return escalation.proposed_priority if escalation is not None else None


def item_issues(alert: AlertIn, rules: RuleOutput, text: str, refs: set, context: set, proposed=None) -> list[str]:
    """Checks for one sentence or list item, so a bad one can be dropped instead of rejecting the answer."""
    catalog = catalog_for(alert, rules)
    issues = ["prohibited_content_pattern"] if PROHIBITED.search(text) else []
    return issues + _evidence_issues(text, catalog, refs, context) + _contradictions(text, catalog, proposed)


def validate_escalation(alert: AlertIn, rules: RuleOutput, escalation) -> list[str]:
    """Evidence and content checks for an AI escalation proposal; the decision layer applies bounds."""
    catalog = catalog_for(alert, rules)
    triggers = {item["rule_id"] for item in catalog["triggering_rules"]}
    observations = {item["evidence_id"]: item for item in catalog["context_observations"]}
    context = set(escalation.context_evidence_ids)
    issues = []
    if not context or not context.issubset({id for id, item in observations.items() if item["available"]}): issues.append("context_references_mismatch")  # Escalation must cite context.
    if CLINICAL_PROHIBITED.search(escalation.reason): issues.append("prohibited_content_pattern")
    issues += _evidence_issues(escalation.reason, catalog, triggers, context)
    return sorted(set(issues))


def rejection_reason(issues: list[str]) -> str:
    if "prohibited_content_pattern" in issues: return "content_rejected"
    if any(issue.endswith("contradiction") for issue in issues): return "contradiction"
    return "evidence_mismatch"
