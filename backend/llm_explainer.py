"""
LLM Explainability Layer (Layer 3).

Public API:
    is_enabled() -> bool          True when OPENAI_API_KEY is set.
    explain(alert, rule_output)   Returns LLMRawOutput on success, None on any failure.

Fallback contract:
    None is returned — and must be handled as rules_only mode — in every case where:
      - OPENAI_API_KEY is absent
      - The API call times out or raises any error
      - The response is not parseable JSON
      - The JSON does not match the required schema (missing / wrong-type fields)
      - confidence is below CONFIDENCE_THRESHOLD (handled downstream in decision_layer)

    The system remains fully functional with llm_output=None.
    decision_layer.apply() treats None as rules_only and never degrades the priority floor.

Safety constraints (enforced here and in decision_layer):
    - LLMRawOutput has NO priority or routing fields — the LLM cannot touch those.
    - rule_trace is always set by decision_layer from rule_output, never by the LLM.
    - No clinical diagnosis or treatment content is solicited by the prompts.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from models import AlertIn, RuleOutput
from prompt_builder import build_messages

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.5   # below this → decision_layer falls back to rules_only
_REQUEST_TIMEOUT     = 15.0  # seconds; prevents indefinite hang
_MODEL               = os.environ.get("LLM_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

class LLMRawOutput(BaseModel):
    """
    Validated shape of the LLM's JSON response.

    All fields are required and must be non-empty.  Pydantic rejects any
    response that is missing a field or violates the constraints, triggering
    fallback to rules_only mode.

    Intentionally has NO priority, routing, or diagnosis fields —
    the LLM has no authority over those.
    """
    summary:              str        = Field(min_length=1)
    rationale:            str        = Field(min_length=1)
    factors_considered:   list[str]  = Field(min_length=1)
    uncertainty_notes:    str        = Field(min_length=1)
    recommended_checks:   list[str]  = Field(min_length=1)
    confidence:           float      = Field(ge=0.0, le=1.0)


def _confidence_cap(alert: AlertIn) -> float:
    """
    Apply a deterministic cap to LLM confidence based on input completeness.

    The model still chooses the raw score, but sparse/noisy alerts should not
    present the same apparent certainty as strong, well-instrumented alerts.
    """
    vs = alert.vital_signs
    vitals_present = sum(
        value is not None
        for value in (
            vs.heart_rate,
            vs.spo2,
            vs.blood_pressure_systolic,
            vs.blood_pressure_diastolic,
            vs.respiratory_rate,
            vs.temperature,
        )
    )

    ctx = alert.recent_context
    context_signals = sum(
        (
            ctx.prior_alerts_24h > 0,
            bool(ctx.recent_medications),
            ctx.fall_risk_score is not None,
            bool(ctx.admission_reason),
            bool(ctx.code_status),
        )
    )

    additional_values = {
        str(v).lower()
        for v in alert.additional_context.values()
        if isinstance(v, (str, int, float, bool))
    }
    noisy_markers = {
        "partial",
        "incomplete",
        "partial_backfill",
        "intermittent_signal",
        "poor",
        "fair",
        "unknown",
        "delayed",
        "duplicate",
        "noisy",
    }
    has_noisy_marker = bool(additional_values & noisy_markers)

    if vitals_present <= 1 and context_signals <= 1:
        return 0.68 if has_noisy_marker else 0.72
    if vitals_present <= 2:
        return 0.74 if has_noisy_marker else 0.78
    if vitals_present <= 3 or context_signals <= 1 or has_noisy_marker:
        return 0.82
    return 0.95


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """Return True when OPENAI_API_KEY is set in the environment."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def explain(alert: AlertIn, rule_output: RuleOutput) -> Optional[LLMRawOutput]:
    """
    Call the LLM and return a validated LLMRawOutput, or None on any failure.

    Callers must treat None as rules_only — decision_layer.apply() does this
    automatically when llm_output=None is passed.
    """
    if not is_enabled():
        logger.debug("LLM disabled — OPENAI_API_KEY not set. Running in rules_only mode.")
        return None

    try:
        return _call_llm(alert, rule_output)
    except Exception as exc:
        # Catch-all: any unhandled exception must not propagate to the API layer.
        logger.warning(
            "Unexpected error in LLM explainer for alert %s: %s: %s",
            alert.alert_id, type(exc).__name__, exc,
        )
        return None


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _call_llm(alert: AlertIn, rule_output: RuleOutput) -> Optional[LLMRawOutput]:
    """
    Build messages, call OpenAI, parse and validate the response.
    Raises on unexpected errors — explain() catches everything.
    """
    # Lazy import: openai is only required at runtime when LLM is enabled.
    # This lets the rest of the system import llm_explainer even without openai installed,
    # which keeps rules_only mode functional without openai in requirements.
    try:
        from openai import OpenAI, OpenAIError
    except ImportError:
        logger.warning("openai package not installed. Running in rules_only mode.")
        return None

    system_msg, user_msg = build_messages(alert, rule_output)

    try:
        client = OpenAI(timeout=_REQUEST_TIMEOUT)
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,  # low temperature for consistent, structured output
        )
    except OpenAIError as exc:
        logger.warning(
            "OpenAI API error for alert %s: %s: %s",
            alert.alert_id, type(exc).__name__, exc,
        )
        return None

    raw_text = response.choices[0].message.content
    if not raw_text or not raw_text.strip():
        logger.warning("LLM returned empty content for alert %s", alert.alert_id)
        return None

    return _parse_and_validate(alert, raw_text)


def _parse_and_validate(alert: AlertIn, raw_text: str) -> Optional[LLMRawOutput]:
    """
    Parse JSON and validate against LLMRawOutput schema.
    Returns None (with a warning) on any parsing or validation failure.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned malformed JSON for alert %s: %s", alert.alert_id, exc)
        return None

    if not isinstance(data, dict):
        logger.warning(
            "LLM response for alert %s is not a JSON object (got %s)",
            alert.alert_id, type(data).__name__,
        )
        return None

    try:
        result = LLMRawOutput(**data)
    except ValidationError as exc:
        logger.warning(
            "LLM output failed schema validation for alert %s: %s",
            alert.alert_id, exc,
        )
        return None

    capped_confidence = min(result.confidence, _confidence_cap(alert))
    if capped_confidence != result.confidence:
        result = result.model_copy(update={"confidence": round(capped_confidence, 2)})

    return result
