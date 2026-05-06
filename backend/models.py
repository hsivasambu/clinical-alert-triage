from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlertType(str, Enum):
    tachycardia   = "tachycardia"
    low_spo2      = "low_spo2"
    infusion_pump = "infusion_pump"
    nurse_call    = "nurse_call"
    fall_risk     = "fall_risk"
    sepsis        = "sepsis"


class Priority(str, Enum):
    critical = "Critical"
    high     = "High"
    medium   = "Medium"
    low      = "Low"


class ExplanationMode(str, Enum):
    hybrid     = "hybrid"      # rules + LLM both active
    rules_only = "rules_only"  # LLM absent, invalid, or low-confidence


# Numeric rank — single source of truth for priority comparison across all layers.
PRIORITY_RANK: Dict[str, int] = {
    Priority.critical: 4,
    Priority.high:     3,
    Priority.medium:   2,
    Priority.low:      1,
}


# ---------------------------------------------------------------------------
# Alert input — expanded MVP model
# ---------------------------------------------------------------------------

class VitalSigns(BaseModel):
    heart_rate:              Optional[float] = Field(None, description="Beats per minute")
    spo2:                    Optional[float] = Field(None, description="Oxygen saturation (%)")
    blood_pressure_systolic: Optional[float] = Field(None, description="Systolic mmHg")
    blood_pressure_diastolic:Optional[float] = Field(None, description="Diastolic mmHg")
    respiratory_rate:        Optional[float] = Field(None, description="Breaths per minute")
    temperature:             Optional[float] = Field(None, description="Degrees Celsius")


class RecentContext(BaseModel):
    """Structured patient context available at the time of the alert."""
    prior_alerts_24h:   int        = Field(0,  ge=0, description="Alerts fired in the past 24 hours")
    recent_medications: List[str]  = Field(default_factory=list, description="Medications given in the past 4 hours")
    fall_risk_score:    Optional[int]  = Field(None, ge=0, description="Morse fall scale score or equivalent")
    admission_reason:   Optional[str]  = None
    code_status:        Optional[str]  = Field(None, description="e.g. 'full_code', 'dnr', 'dni'")


class AlertIn(BaseModel):
    alert_id:           str
    source_system:      str            = Field(description="System or device that generated the alert")
    alert_type:         AlertType
    patient_id:         str
    unit:               str
    room:               Optional[str]  = None
    bed:                Optional[str]  = None
    timestamp:          datetime
    vital_signs:        VitalSigns
    message_text:       Optional[str]  = Field(None, description="Free-text message from the device or system")
    device_type:        Optional[str]  = Field(None, description="e.g. 'cardiac_monitor', 'infusion_pump'")
    repeat_count:       int            = Field(0, ge=0, description="Consecutive times this alert has fired")
    recent_context:     RecentContext  = Field(default_factory=RecentContext)
    additional_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Alert-type-specific extras not covered by structured fields (e.g. alarm_type for pumps)",
    )


# ---------------------------------------------------------------------------
# Layer 2 output
# ---------------------------------------------------------------------------

class RuleOutput(BaseModel):
    """Output of the deterministic rules engine."""
    baseline_priority: Priority
    matched_rules:     List[str] = Field(description="IDs of every rule that fired — full audit trace")
    suggested_route:   str
    rule_confidence:   float     = Field(1.0, ge=0.0, le=1.0, description="Aggregate confidence of matched rules")


# ---------------------------------------------------------------------------
# Layer 3 output — explainability schema
# ---------------------------------------------------------------------------

class ExplanationOutput(BaseModel):
    """
    Structured explainability schema populated by the decision layer.

    With no LLM active, all narrative fields carry documented placeholder values
    and explanation_mode is 'rules_only'.  When llm_explainer.py is wired in,
    the LLM replaces summary / rationale / factors_considered / uncertainty_notes
    / recommended_checks and sets llm_confidence_estimate.
    rule_trace and explanation_mode are always set by the decision layer,
    never by the LLM.
    """
    summary:                str             = "Alert triaged by rules engine only. LLM explanation not yet active."
    rationale:              str             = ""
    factors_considered:     List[str]       = Field(default_factory=list)
    uncertainty_notes:      str             = ""
    recommended_checks:     List[str]       = Field(default_factory=list)
    llm_confidence_estimate:Optional[float] = Field(None, ge=0.0, le=1.0)
    explanation_mode:       ExplanationMode = ExplanationMode.rules_only
    rule_trace:             List[str]       = Field(
        default_factory=list,
        description="Matched rule IDs — always populated for audit traceability",
    )


# ---------------------------------------------------------------------------
# Layer 4 output — final triage result
# ---------------------------------------------------------------------------

class TriageResult(BaseModel):
    """Full output of the decision layer — stored in audit log and returned to UI."""
    alert_id:       str
    alert:          AlertIn
    rule_output:    RuleOutput
    explanation:    ExplanationOutput
    final_priority: Priority
    final_route:    str
    processed_at:   datetime


# ---------------------------------------------------------------------------
# Layer 5 — human review models (override, feedback, acceptance)
# ---------------------------------------------------------------------------

FeedbackRating = Literal["helpful", "not_helpful"]

FEEDBACK_REASON_CATEGORIES = [
    "explanation_unclear",
    "incorrect_rule_cited",
    "missing_clinical_context",
    "routing_disagree",
    "too_verbose",
    "other",
]


class OverrideIn(BaseModel):
    """Request body for POST /alerts/{id}/override."""
    reviewer_id:         str      = Field(min_length=1)
    overridden_priority: Priority
    overridden_route:    Optional[str] = None
    reason:              str      = Field(min_length=1, description="Required: clinician rationale for override")


class OverrideRecord(BaseModel):
    """Persisted override — includes original values for full audit trail."""
    id:                  int
    alert_id:            str
    reviewer_id:         str
    original_priority:   Priority
    original_route:      str
    overridden_priority: Priority
    overridden_route:    Optional[str]
    reason:              str
    created_at:          datetime


class FeedbackIn(BaseModel):
    """Request body for POST /alerts/{id}/feedback."""
    reviewer_id:     str            = Field(min_length=1)
    rating:          FeedbackRating
    reason_category: Optional[str]  = Field(None, description="Required when rating is not_helpful")
    comment:         Optional[str]  = None

    @model_validator(mode="after")
    def validate_feedback(self) -> "FeedbackIn":
        if self.rating == "not_helpful" and not self.reason_category:
            raise ValueError("reason_category is required when rating is 'not_helpful'")
        if self.reason_category and self.reason_category not in FEEDBACK_REASON_CATEGORIES:
            raise ValueError(f"reason_category must be one of: {', '.join(FEEDBACK_REASON_CATEGORIES)}")
        return self


class FeedbackRecord(BaseModel):
    """Persisted explanation quality feedback."""
    id:              int
    alert_id:        str
    reviewer_id:     str
    rating:          str
    reason_category: Optional[str]
    comment:         Optional[str]
    created_at:      datetime


class AcceptanceIn(BaseModel):
    """Request body for POST /alerts/{id}/accept."""
    reviewer_id: str = Field(min_length=1)


class AcceptanceRecord(BaseModel):
    """Persisted acceptance — records that reviewer agreed with the AI triage."""
    id:          int
    alert_id:    str
    reviewer_id: str
    created_at:  datetime


class AlertAudit(BaseModel):
    """Full audit record for a single alert — triage + all human actions."""
    triage_result: TriageResult
    overrides:     List[OverrideRecord]
    feedback:      List[FeedbackRecord]
    acceptances:   List[AcceptanceRecord]
