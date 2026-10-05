from __future__ import annotations

from datetime import datetime
from enum import Enum
import math
import re
from typing import Dict, List, Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StrictStr, field_validator, model_validator


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
    # Broad demo ingestion bounds, not clinical reference ranges.
    model_config = ConfigDict(extra="forbid")
    heart_rate: Optional[float] = Field(None, ge=0, le=400, strict=True, allow_inf_nan=False)
    spo2: Optional[float] = Field(None, ge=0, le=100, strict=True, allow_inf_nan=False)
    blood_pressure_systolic: Optional[float] = Field(None, ge=0, le=400, strict=True, allow_inf_nan=False)
    blood_pressure_diastolic: Optional[float] = Field(None, ge=0, le=300, strict=True, allow_inf_nan=False)
    respiratory_rate: Optional[float] = Field(None, ge=0, le=100, strict=True, allow_inf_nan=False)
    temperature: Optional[float] = Field(None, ge=0, le=60, strict=True, allow_inf_nan=False)


class RecentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prior_alerts_24h: int = Field(0, ge=0, le=1000000, strict=True)
    recent_medications: List[StrictStr] = Field(default_factory=list)
    fall_risk_score: Optional[int] = Field(None, ge=0, le=125, strict=True)
    admission_reason: Optional[StrictStr] = None
    code_status: Optional[StrictStr] = None


class AdditionalContext(BaseModel):
    """Known rule/router inputs are typed; other observed JSON metadata is retained."""
    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: Dict[str, JsonValue] = Field(init=False)
    alarm_type: Optional[StrictStr] = Field(None, max_length=100)
    infusate: Optional[StrictStr] = Field(None, max_length=256)

    @model_validator(mode="after")
    def finite_metadata(self):
        def check(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("additional metadata numbers must be finite JSON values")
            if isinstance(value, dict):
                for child in value.values(): check(child)
            if isinstance(value, list):
                for child in value: check(child)
        check(self.model_dump())
        return self


class AlertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: StrictStr = Field(min_length=1, max_length=128)
    source_system: StrictStr = Field(min_length=1, max_length=256)
    alert_type: AlertType
    patient_id: StrictStr = Field(min_length=1, max_length=128)
    unit: StrictStr = Field(min_length=1, max_length=256)
    room: Optional[StrictStr] = None
    bed: Optional[StrictStr] = None
    timestamp: AwareDatetime
    vital_signs: VitalSigns = Field(default_factory=VitalSigns)
    message_text: Optional[StrictStr] = None
    device_type: Optional[StrictStr] = None
    repeat_count: int = Field(0, ge=0, le=1000000, strict=True)
    recent_context: RecentContext = Field(default_factory=RecentContext)
    additional_context: AdditionalContext = Field(default_factory=AdditionalContext)

    @field_validator("alert_id", "source_system", "patient_id", "unit")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain non-whitespace characters")
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_format(cls, value):
        if isinstance(value, (int, float, bool)):
            raise ValueError("timestamp must be an ISO 8601 datetime with timezone, not an epoch number")
        if isinstance(value, str) and not re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]", value):
            raise ValueError("timestamp must be an ISO 8601 datetime with timezone")
        return value


# ---------------------------------------------------------------------------
# Layer 2 output
# ---------------------------------------------------------------------------

class RuleOutput(BaseModel):
    """Output of the deterministic rules engine."""
    missing_fields: List[str] = Field(default_factory=list)
    evaluation_status: Optional[Literal["matched", "no_rule_matched"]] = None
    baseline_priority: Priority
    matched_rules:     List[str] = Field(description="IDs of every rule that fired — full audit trace")
    suggested_route:   str
    rule_confidence:   float     = Field(1.0, ge=0.0, le=1.0, description="Aggregate confidence of matched rules")


# ---------------------------------------------------------------------------
# Layer 3 output — explainability schema
# ---------------------------------------------------------------------------

FallbackReason = Literal[
    "llm_disabled", "provider_failure", "provider_timeout", "malformed_output",
    "schema_invalid", "low_confidence", "content_rejected", "not_supplied",
]


class RuleEvidence(BaseModel):
    rule_id: str
    condition: str


class ExplanationOutput(BaseModel):
    """Recorded narrative plus deterministic trace and optional LLM fallback reason.

    Nullable provenance fields preserve legacy records without guessing why they
    fell back or rewriting their original narrative.
    """
    summary: str = ""
    rationale: str = ""
    factors_considered: List[str] = Field(default_factory=list)
    uncertainty_notes: str = ""
    recommended_checks: List[str] = Field(default_factory=list)
    llm_confidence_estimate: Optional[float] = Field(None, ge=0.0, le=1.0)
    explanation_mode: ExplanationMode = ExplanationMode.rules_only
    rule_trace: List[str] = Field(default_factory=list)
    rule_evidence: List[RuleEvidence] = Field(default_factory=list)
    fallback_reason: Optional[FallbackReason] = None
    explanation_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Layer 4 output — final triage result
# ---------------------------------------------------------------------------

class ReviewState(BaseModel):
    effective_priority: Priority
    effective_route: str
    decision_version: int = 0  # 0 = original system decision; otherwise override ID
    review_status: Literal["unreviewed", "overridden", "accepted"] = "unreviewed"


class TriageResult(BaseModel):
    """Full output of the decision layer — stored in audit log and returned to UI."""
    alert_id:       str
    alert:          AlertIn
    rule_output:    RuleOutput
    explanation:    ExplanationOutput
    final_priority: Priority
    final_route:    str
    processed_at:   datetime
    review_state: Optional[ReviewState] = None


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
    review_state: Optional[ReviewState] = None


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
    decision_version: Optional[int] = Field(None, ge=0)


class AcceptanceRecord(BaseModel):
    """Persisted acceptance — records that reviewer agreed with the AI triage."""
    id:          int
    alert_id:    str
    reviewer_id: str
    created_at:  datetime
    decision_version: Optional[int] = None
    accepted_priority: Optional[Priority] = None
    accepted_route: Optional[str] = None
    review_state: Optional[ReviewState] = None


class AlertAudit(BaseModel):
    """Full audit record for a single alert — triage + all human actions."""
    triage_result: TriageResult
    overrides:     List[OverrideRecord]
    feedback:      List[FeedbackRecord]
    acceptances:   List[AcceptanceRecord]
    review_state: ReviewState
