"""
Decision Layer / Guardrails (Layer 4).

Non-negotiable safety constraints from CLAUDE.md:
  1. final_priority >= baseline_priority (rules floor is inviolable).
  2. LLM has explainability authority only - it cannot change priority or route.
  3. If LLM output is absent, invalid, or confidence < threshold -> rules_only.
  4. Every decision is auditable via explanation.rule_trace.

This module accepts an optional LLM explainability payload, but the final
priority and route still come only from the rules engine and router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from llm_explainer import CONFIDENCE_THRESHOLD, LLMOutcome, LLMRawOutput
import deterministic_explanation
from rules_engine import evidence_for
from models import (
    AlertIn,
    ExplanationMode,
    ExplanationOutput,
    RuleOutput,
    TriageResult,
)
from router import resolve_route_with_reason


def _build_explanation(alert: AlertIn, rules: RuleOutput, route: str, routing_reason: str,
                       outcome: LLMOutcome) -> ExplanationOutput:
    output = outcome.output
    reason = outcome.fallback_reason
    if output is None or reason is not None or output.confidence < CONFIDENCE_THRESHOLD:
        return deterministic_explanation.build(alert, rules, route, routing_reason,
            reason or ("low_confidence" if output is not None else "not_supplied"),
            output.confidence if output is not None else None)
    return ExplanationOutput(summary=output.summary, rationale=output.rationale,
        factors_considered=list(output.factors_considered), uncertainty_notes=output.uncertainty_notes,
        recommended_checks=list(output.recommended_checks), llm_confidence_estimate=output.confidence,
        explanation_mode=ExplanationMode.hybrid, rule_trace=list(rules.matched_rules),
        rule_evidence=evidence_for(alert, rules), explanation_version="validated-llm-v1")


def apply(
    alert: AlertIn,
    rule_output: RuleOutput,
    llm_output: Optional[LLMRawOutput | LLMOutcome] = None,
) -> TriageResult:
    """
    Enforce all guardrails and return the final TriageResult.

    The LLM has no authority over priority or routing. Final routing always
    comes from router.resolve_route() using the rules-derived baseline.
    """
    final_priority = rule_output.baseline_priority
    final_route, routing_reason = resolve_route_with_reason(alert, final_priority, rule_output.suggested_route)
    outcome = llm_output if isinstance(llm_output, LLMOutcome) else LLMOutcome(output=llm_output)
    explanation = _build_explanation(alert, rule_output, final_route, routing_reason, outcome)

    return TriageResult(
        alert_id=alert.alert_id,
        alert=alert,
        rule_output=rule_output,
        explanation=explanation,
        final_priority=final_priority,
        final_route=final_route,
        processed_at=datetime.now(timezone.utc),
    )
