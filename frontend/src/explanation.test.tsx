import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import fixture from '../e2e/fallback.json'
import { ExplanationPanel } from './components/ExplanationPanel'
import { FALLBACK_LABELS } from './fallbackLabels'
import { buildAlert } from './simulator/buildAlert'
import { PRESETS } from './simulator/presets'
import type { AIAdjustment, FallbackReason, TriageResult } from './types'
afterEach(cleanup)
const result = fixture as TriageResult
const panel = (reason: FallbackReason | null = 'provider_timeout') => <ExplanationPanel alert={result.alert} ruleOutput={result.rule_output} finalPriority={result.final_priority} finalRoute={result.final_route} explanation={{ ...result.explanation, fallback_reason: reason }} />
describe('recorded deterministic explanation', () => {
  it('populates six sections, labels the local simulation, and exposes absent values and no match', () => {
    const { container } = render(panel())
    expect(container.querySelectorAll('.explanation-block h4')).toHaveLength(6)
    expect(screen.getByText(/No live provider call was made/)).toBeTruthy()
    expect(screen.getByText(/Provider timeout/)).toBeTruthy()
    expect(screen.getByText(/NO_RULE_MATCHED:/)).toBeTruthy()
    expect(screen.getByText(/Insufficient data:/)).toBeTruthy()
    expect(container.querySelectorAll('.observations strong')).toHaveLength(7)
    expect(container.querySelector('.observations')?.textContent).toContain('Not provided')
    expect(container.querySelector('.rule-evidence')?.textContent).toContain('No registered condition matched')
    expect(container.querySelectorAll('.explanation-block')[5].textContent).toContain('Verify unavailable rule inputs')
  })
  it.each(Object.keys(FALLBACK_LABELS) as FallbackReason[])('labels fallback reason %s', reason => {
    const { container } = render(panel(reason))
    expect(container.querySelector('.fallback-label')?.textContent).toContain(FALLBACK_LABELS[reason])
  })
  it('does not guess why a legacy record fell back', () => {
    const { container } = render(panel(null))
    expect(container.querySelector('.fallback-label')?.textContent).toContain('Reason not recorded (legacy record)')
  })
})
describe('AI-supported decision', () => {
  const adjustment: Omit<AIAdjustment, 'status'> = { proposed_priority: 'High', baseline_priority: 'Low', applied_priority: 'Medium', baseline_route: 'Bedside Nurse', applied_route: 'Bedside Nurse',
    reason: 'OBS_FALL_RISK_SCORE warrants earlier review.', context_evidence_ids: ['OBS_FALL_RISK_SCORE'] }
  const withAdjustment = (extra: Partial<AIAdjustment> & Pick<AIAdjustment, 'status'>) => <ExplanationPanel alert={result.alert} ruleOutput={result.rule_output} finalPriority="Medium" finalRoute="Bedside Nurse"
    explanation={{ ...result.explanation, explanation_mode: 'hybrid', ai_adjustment: { ...adjustment, ...extra } }} />
  it('shows an applied escalation and its one-level cap', () => {
    const { container } = render(withAdjustment({ status: 'applied' }))
    const block = container.querySelector('.ai-adjustment')?.textContent
    expect(block).toContain('Priority raised from Low to Medium (capped at one level above the rules)')
    expect(block).toContain('OBS_FALL_RISK_SCORE')
  })
  it('shows why a proposal was declined', () => {
    const { container } = render(withAdjustment({ status: 'declined', applied_priority: 'Low', decline_reason: 'low_confidence' }))
    expect(container.querySelector('.ai-adjustment')?.textContent).toContain('Not applied: the model\'s confidence was below the escalation threshold')
  })
})
describe('simulator numeric serialization', () => {
  const form = { ...PRESETS.tachycardia, alert_id: 'LOCAL', timestamp: '2025-01-01T00:00:00Z' }
  it('preserves unavailable measurements as null and provided zero as zero', () => {
    expect(buildAlert({ ...form, spo2: '', heart_rate: '0' }).vital_signs).toMatchObject({ spo2: null, heart_rate: 0 })
  })
  it.each(['145bpm', 'NaN', 'Infinity'])('rejects malformed measurement %s rather than dropping it', heart_rate => {
    expect(() => buildAlert({ ...form, heart_rate })).toThrow('finite numbers')
  })
  it.each(['3abc', '-1', '1.5'])('rejects invalid repeat count %s rather than truncating it', repeat_count => {
    expect(() => buildAlert({ ...form, repeat_count })).toThrow()
  })
  it('uses typed pump keys from the existing preset message and infusion value', () => {
    expect(buildAlert({ ...form, ...PRESETS.infusion_pump }).additional_context).toMatchObject({ alarm_type: 'occlusion', infusate: 'heparin' })
  })
  it('requires an actual timestamp and identity', () => {
    expect(() => buildAlert({ ...form, timestamp: '' })).toThrow('alert time')
    expect(() => buildAlert({ ...form, patient_id: '' })).toThrow('Patient ID')
  })
})
