// TypeScript types mirroring the backend Pydantic models.
// Keep in sync with backend/models.py.

export type AlertType =
  | 'tachycardia'
  | 'low_spo2'
  | 'infusion_pump'
  | 'nurse_call'
  | 'fall_risk'
  | 'sepsis'

export type Priority = 'Critical' | 'High' | 'Medium' | 'Low'

export type ExplanationMode = 'hybrid' | 'rules_only'

export type FeedbackRating = 'helpful' | 'not_helpful'

export const PRIORITIES: Priority[] = ['Critical', 'High', 'Medium', 'Low']

export const FEEDBACK_REASON_CATEGORIES = [
  'explanation_unclear',
  'incorrect_rule_cited',
  'missing_clinical_context',
  'routing_disagree',
  'too_verbose',
  'other',
] as const

export interface VitalSigns {
  heart_rate: number | null
  spo2: number | null
  blood_pressure_systolic: number | null
  blood_pressure_diastolic: number | null
  respiratory_rate: number | null
  temperature: number | null
}

export interface RecentContext {
  prior_alerts_24h: number
  recent_medications: string[]
  fall_risk_score: number | null
  admission_reason: string | null
  code_status: string | null
}

export interface AlertIn {
  alert_id: string
  source_system: string
  alert_type: AlertType
  patient_id: string
  unit: string
  room: string | null
  bed: string | null
  timestamp: string
  vital_signs: VitalSigns
  message_text: string | null
  device_type: string | null
  repeat_count: number
  recent_context: RecentContext
  additional_context: Record<string, unknown>
}

export interface RuleOutput {
  baseline_priority: Priority
  matched_rules: string[]
  suggested_route: string
  rule_confidence: number
}

export interface ExplanationOutput {
  summary: string
  rationale: string
  factors_considered: string[]
  uncertainty_notes: string
  recommended_checks: string[]
  llm_confidence_estimate: number | null
  explanation_mode: ExplanationMode
  rule_trace: string[]
}

export interface TriageResult {
  alert_id: string
  alert: AlertIn
  rule_output: RuleOutput
  explanation: ExplanationOutput
  final_priority: Priority
  final_route: string
  processed_at: string
}

// ---------------------------------------------------------------------------
// Human review models
// ---------------------------------------------------------------------------

export interface OverrideIn {
  reviewer_id: string
  overridden_priority: Priority
  overridden_route?: string
  reason: string
}

export interface OverrideRecord {
  id: number
  alert_id: string
  reviewer_id: string
  original_priority: Priority
  original_route: string
  overridden_priority: Priority
  overridden_route: string | null
  reason: string
  created_at: string
}

export interface FeedbackIn {
  reviewer_id: string
  rating: FeedbackRating
  reason_category?: string
  comment?: string
}

export interface FeedbackRecord {
  id: number
  alert_id: string
  reviewer_id: string
  rating: FeedbackRating
  reason_category: string | null
  comment: string | null
  created_at: string
}

export interface AcceptanceRecord {
  id: number
  alert_id: string
  reviewer_id: string
  created_at: string
}

export interface AlertAudit {
  triage_result: TriageResult
  overrides: OverrideRecord[]
  feedback: FeedbackRecord[]
  acceptances: AcceptanceRecord[]
}

export interface AuditLogEntry {
  id: number
  alert_id: string
  alert_type: AlertType
  patient_id: string
  unit: string
  baseline_priority: Priority
  final_priority: Priority
  final_route: string
  explanation_mode: ExplanationMode
  rule_confidence: number
  created_at: string
  override_count: number
  feedback_count: number
  acceptance_count: number
}
