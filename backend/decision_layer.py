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

from llm_explainer import CONFIDENCE_THRESHOLD, LLMRawOutput
from models import (
    AlertIn,
    ExplanationMode,
    ExplanationOutput,
    RuleOutput,
    TriageResult,
)
from router import resolve_route


def _build_explanation(
    rule_output: RuleOutput,
    llm_output: Optional[LLMRawOutput] = None,
) -> ExplanationOutput:
    """
    Construct the ExplanationOutput for this triage decision.

    Rules-only path: documented placeholders plus full rule trace.
    Hybrid path: use validated LLM narrative fields, but keep explanation_mode
    and rule_trace under deterministic control in this layer.
    """
    if llm_output is None:
        return ExplanationOutput(
            summary="Alert triaged by rules engine only. LLM explanation not yet active.",
            rationale="",
            factors_considered=[],
            uncertainty_notes="No LLM output available. All triage decisions are rules-based.",
            recommended_checks=[],
            llm_confidence_estimate=None,
            explanation_mode=ExplanationMode.rules_only,
            rule_trace=list(rule_output.matched_rules),
        )

    if llm_output.confidence < CONFIDENCE_THRESHOLD:
        return ExplanationOutput(
            summary="LLM output below confidence threshold. Falling back to rules-only explanation.",
            rationale="",
            factors_considered=[],
            uncertainty_notes=(
                f"LLM confidence {llm_output.confidence} is below the "
                f"{CONFIDENCE_THRESHOLD:.1f} threshold."
            ),
            recommended_checks=[],
            llm_confidence_estimate=llm_output.confidence,
            explanation_mode=ExplanationMode.rules_only,
            rule_trace=list(rule_output.matched_rules),
        )

    return ExplanationOutput(
        summary=llm_output.summary,
        rationale=llm_output.rationale,
        factors_considered=list(llm_output.factors_considered),
        uncertainty_notes=llm_output.uncertainty_notes,
        recommended_checks=list(llm_output.recommended_checks),
        llm_confidence_estimate=llm_output.confidence,
        explanation_mode=ExplanationMode.hybrid,
        rule_trace=list(rule_output.matched_rules),
    )


def apply(
    alert: AlertIn,
    rule_output: RuleOutput,
    llm_output: Optional[LLMRawOutput] = None,
) -> TriageResult:
    """
    Enforce all guardrails and return the final TriageResult.

    The LLM has no authority over priority or routing. Final routing always
    comes from router.resolve_route() using the rules-derived baseline.
    """
    final_priority = rule_output.baseline_priority
    final_route = resolve_route(alert, final_priority, rule_output.suggested_route)
    explanation = _build_explanation(rule_output, llm_output)

    return TriageResult(
        alert_id=alert.alert_id,
        alert=alert,
        rule_output=rule_output,
        explanation=explanation,
        final_priority=final_priority,
        final_route=final_route,
        processed_at=datetime.now(timezone.utc),
    )
