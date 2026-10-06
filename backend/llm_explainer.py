"""Optional narrative provider. Structured outcomes retain fallback provenance.

explain_with_outcome() is the API pipeline entry point; explain() remains an
optional-output compatibility helper for callers that do not persist provenance.
Provider rejection and conservative evidence/phrase checks are recognized;
these syntactic checks do not guarantee semantic safety. Raw failures/provider payloads are not returned.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StringConstraints, ValidationError, field_validator

from models import AlertIn, FallbackReason, GenerationProvenance, Priority, RuleOutput
from explanation_contract import rejection_reason, validate_narrative
from provenance import generation_metadata
from prompt_builder import build_messages

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.5   # below this → decision_layer falls back to rules_only
ESCALATION_CONFIDENCE_THRESHOLD = 0.6  # below this an escalation proposal is recorded but not applied
_REQUEST_TIMEOUT     = 15.0  # seconds; prevents indefinite hang
_MODEL               = os.environ.get("LLM_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# LLM output schema
# ---------------------------------------------------------------------------

NonEmptyText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]

class EscalationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposed_priority: Priority
    reason: NonEmptyText
    context_evidence_ids: list[NonEmptyText] = Field(min_length=1)

    @field_validator("proposed_priority", mode="before")
    @classmethod
    def _title_case(cls, value):
        return value.strip().title() if isinstance(value, str) else value


class LLMRawOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: NonEmptyText
    rationale: NonEmptyText
    factors_considered: list[NonEmptyText] = Field(min_length=1)
    uncertainty_notes: NonEmptyText
    recommended_checks: list[NonEmptyText] = Field(min_length=1)
    triggering_rule_ids: list[NonEmptyText]
    context_evidence_ids: list[NonEmptyText]
    escalation: Optional[EscalationProposal] = None
    _self_reported_confidence: Optional[float] = PrivateAttr(default=None)
    _confidence_cap_value: Optional[float] = PrivateAttr(default=None)
    _confidence_cap_reason: Optional[str] = PrivateAttr(default=None)
    confidence: float = Field(ge=0.0, le=1.0, strict=True, allow_inf_nan=False)


@dataclass(frozen=True)
class LLMOutcome:
    output: Optional[LLMRawOutput] = None
    fallback_reason: Optional[FallbackReason] = None
    provenance: Optional[GenerationProvenance] = None


class LLMFallbackError(Exception):
    def __init__(self, reason: FallbackReason):
        self.reason = reason
        super().__init__(reason)


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
        for v in alert.additional_context.model_dump().values()
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
    return os.environ.get("LLM_ENABLED", "true").lower() not in {"false", "0", "no"} and bool(os.environ.get("OPENAI_API_KEY", "").strip())


def explain_with_outcome(alert: AlertIn, rule_output: RuleOutput, correlation_id: str | None = None, *, allow_provider: bool = True) -> LLMOutcome:
    metadata = generation_metadata(alert, rule_output, correlation_id)
    metadata.configured_model = _MODEL
    start = time.perf_counter()
    output, reason = None, None
    enabled = allow_provider and is_enabled()
    if not enabled:
        reason = "llm_disabled"
        metadata.validation_outcome = "not_attempted"
    else:
        try:
            output = _call_llm(alert, rule_output, metadata)
            reason = "low_confidence" if output.confidence < CONFIDENCE_THRESHOLD else None
            metadata.validation_outcome = "low_confidence" if reason else "accepted_by_practical_checks"
        except LLMFallbackError as exc:
            reason = exc.reason
            metadata.validation_outcome = "rejected" if reason in {"schema_invalid", "malformed_output", "content_rejected", "evidence_mismatch", "contradiction"} else "provider_error"
            if not metadata.validation_issues: metadata.validation_issues = [reason]
        except TimeoutError:
            reason = "provider_timeout"
            metadata.validation_outcome = "provider_error"
        except Exception:
            logger.warning("LLM provider failure for alert %s", alert.alert_id)
            reason = "provider_failure"
            metadata.validation_outcome = "provider_error"
    metadata.fallback_reason = reason
    metadata.generation_duration_ms = round((time.perf_counter() - start) * 1000, 3) if enabled else 0.0
    return LLMOutcome(output=output, fallback_reason=reason, provenance=metadata)


def explain(alert: AlertIn, rule_output: RuleOutput) -> Optional[LLMRawOutput]:
    """Compatibility helper; use explain_with_outcome to retain failure reasons."""
    return explain_with_outcome(alert, rule_output).output


def _call_llm(alert: AlertIn, rule_output: RuleOutput, metadata: GenerationProvenance) -> LLMRawOutput:
    try:
        from openai import APITimeoutError, OpenAI, OpenAIError
    except ImportError:
        raise LLMFallbackError("provider_failure") from None
    system_msg, user_msg = build_messages(alert, rule_output)
    try:
        client = OpenAI(timeout=_REQUEST_TIMEOUT, max_retries=0)
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}, temperature=0.2,
        )
    except (APITimeoutError, TimeoutError):
        raise LLMFallbackError("provider_timeout") from None
    except OpenAIError:
        raise LLMFallbackError("provider_failure") from None
    returned_model = getattr(response, "model", None)
    metadata.returned_model = returned_model if isinstance(returned_model, str) else None
    if not response.choices:
        raise LLMFallbackError("malformed_output")
    choice = response.choices[0]
    refusal = getattr(choice.message, "refusal", None)
    if (isinstance(refusal, str) and refusal.strip()) or choice.finish_reason == "content_filter":
        raise LLMFallbackError("content_rejected")
    raw_text = choice.message.content
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise LLMFallbackError("malformed_output")
    return _parse_and_validate(alert, rule_output, raw_text, metadata)


def _parse_and_validate(alert: AlertIn, rules: RuleOutput, raw_text: str, metadata: GenerationProvenance) -> LLMRawOutput:
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        raise LLMFallbackError("malformed_output") from None
    try:
        result = LLMRawOutput.model_validate(data)
    except ValidationError:
        raise LLMFallbackError("schema_invalid") from None
    issues = validate_narrative(alert, rules, result)
    if issues:
        metadata.validation_issues = issues
        raise LLMFallbackError(rejection_reason(issues))
    raw_confidence = result.confidence
    cap = _confidence_cap(alert)
    capped_confidence = min(raw_confidence, cap)
    if capped_confidence != result.confidence:
        result = result.model_copy(update={"confidence": round(capped_confidence, 2)})
    result._self_reported_confidence = raw_confidence
    result._confidence_cap_value = cap
    result._confidence_cap_reason = "Deterministic demo cap based on the count of available measurements/context signals and configured noisy-source markers; not a calibrated probability or clinical reliability measure."
    return result
