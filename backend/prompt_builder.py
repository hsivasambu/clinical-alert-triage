"""
Prompt builder — constructs (system_message, user_message) tuples from alert
data, rule output, and prompt templates stored in prompts/.

Templates use Python's string.Template syntax ($variable_name).
safe_substitute() is used so an unrecognised placeholder is left as-is
rather than raising an error.

Template lookup order:
  1. prompts/{alert_type}_prompt.md   (type-specific)
  2. prompts/explainability_prompt.md (generic fallback)
"""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Tuple

from models import AlertIn, RuleOutput

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

def _load(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_user_template(alert_type_value: str) -> str:
    specific = _PROMPTS_DIR / f"{alert_type_value}_prompt.md"
    if specific.exists():
        return specific.read_text(encoding="utf-8")
    return _load("explainability_prompt.md")


# ---------------------------------------------------------------------------
# Context formatters
# ---------------------------------------------------------------------------

def _fmt_vitals(alert: AlertIn) -> str:
    vs = alert.vital_signs
    lines: list[str] = []
    if vs.heart_rate is not None:
        lines.append(f"  Heart rate:        {vs.heart_rate} bpm")
    if vs.spo2 is not None:
        lines.append(f"  SpO2:              {vs.spo2}%")
    if vs.blood_pressure_systolic is not None and vs.blood_pressure_diastolic is not None:
        lines.append(f"  Blood pressure:    {vs.blood_pressure_systolic}/{vs.blood_pressure_diastolic} mmHg")
    if vs.respiratory_rate is not None:
        lines.append(f"  Respiratory rate:  {vs.respiratory_rate} /min")
    if vs.temperature is not None:
        lines.append(f"  Temperature:       {vs.temperature} °C")
    return "\n".join(lines) if lines else "  (no vitals available)"


def _fmt_context(alert: AlertIn) -> str:
    ctx = alert.recent_context
    lines: list[str] = [f"  Prior alerts (24h): {ctx.prior_alerts_24h}"]
    if ctx.fall_risk_score is not None:
        lines.append(f"  Fall risk score:    {ctx.fall_risk_score}")
    if ctx.admission_reason:
        lines.append(f"  Admission reason:   {ctx.admission_reason}")
    if ctx.code_status:
        lines.append(f"  Code status:        {ctx.code_status}")
    if ctx.recent_medications:
        lines.append(f"  Recent medications: {', '.join(ctx.recent_medications)}")
    return "\n".join(lines)


def _fmt_rules(rule_output: RuleOutput) -> str:
    return "\n".join(f"  - {r}" for r in rule_output.matched_rules)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_messages(alert: AlertIn, rule_output: RuleOutput) -> Tuple[str, str]:
    """
    Return (system_message, user_message) for the given alert and rule output.
    The system message is the same for all alert types.
    The user message is built from the alert-type-specific template.
    """
    system_msg = _load("system_prompt.md")

    user_template = Template(_load_user_template(alert.alert_type.value))
    user_msg = user_template.safe_substitute(
        alert_id          = alert.alert_id,
        alert_type        = alert.alert_type.value,
        patient_id        = alert.patient_id,
        unit              = alert.unit,
        room              = alert.room or "unknown",
        bed               = alert.bed or "unknown",
        repeat_count      = alert.repeat_count,
        message_text      = alert.message_text or "(none)",
        device_type       = alert.device_type or "unknown",
        vitals_section    = _fmt_vitals(alert),
        context_section   = _fmt_context(alert),
        baseline_priority = rule_output.baseline_priority.value,
        matched_rules     = _fmt_rules(rule_output),
        suggested_route   = rule_output.suggested_route,
        rule_confidence   = f"{rule_output.rule_confidence:.2f}",
    )

    return system_msg, user_msg
