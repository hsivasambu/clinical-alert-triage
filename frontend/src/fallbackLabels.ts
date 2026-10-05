import type { FallbackReason } from './types'
export const FALLBACK_LABELS: Record<FallbackReason, string> = {
  llm_disabled: 'LLM disabled', provider_failure: 'Provider failure', provider_timeout: 'Provider timeout',
  malformed_output: 'Malformed provider response', schema_invalid: 'Provider output failed schema validation',
  low_confidence: 'LLM confidence below the explanation threshold', content_rejected: 'Provider refusal or prohibited content detected',
  evidence_mismatch: 'Narrative evidence did not match recorded input', contradiction: 'Narrative contradicted the deterministic decision',
  not_supplied: 'No LLM outcome supplied by the local caller',
}
export function fallbackLabel(reason?: FallbackReason | null) { return reason ? FALLBACK_LABELS[reason] : 'Reason not recorded (legacy record)' }
