import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fixture from '../e2e/fallback.json'
import { ReviewHistory } from './components/ReviewHistory'
import { GenerationDetails } from './components/GenerationDetails'
import { ExplanationPanel } from './components/ExplanationPanel'
import { AuditView } from './components/AuditView'
import { api } from './api/client'
import type { AlertAudit, AuditLogEntry, TriageResult } from './types'
vi.mock('./api/client', () => ({ api: { listAuditLog: vi.fn(), getAlertAudit: vi.fn() } }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const result = fixture as TriageResult
const at = '2026-10-05T12:00:00Z'
const history: AlertAudit = { triage_result: result,
  review_state: { effective_priority: 'High', effective_route: 'Reviewed destination', decision_version: 7, review_status: 'accepted' },
  overrides: [{ id: 7, event_sequence: 2, alert_id: result.alert_id, reviewer_id: 'Reviewer B', original_priority: 'Low', original_route: result.final_route, overridden_priority: 'High', overridden_route: 'Reviewed destination', reason: 'Scenario review reason', created_at: at }],
  acceptances: [{ id: 8, event_sequence: 3, alert_id: result.alert_id, reviewer_id: 'Reviewer C', decision_version: 7, accepted_priority: 'High', accepted_route: 'Reviewed destination', created_at: at }],
  feedback: [{ id: 9, event_sequence: 1, alert_id: result.alert_id, reviewer_id: 'Reviewer A', rating: 'not_helpful', reason_category: 'other', comment: 'Needs clearer evidence', created_at: at }] }
it('orders actions across types with timestamps, reviewers, reasons and decision snapshots', () => {
  const { container } = render(<ReviewHistory audit={history} />)
  const events = [...container.querySelectorAll('li')].map(li => li.textContent)
  expect(events[1]).toContain('Reviewer A'); expect(events[2]).toContain('Reviewer B'); expect(events[3]).toContain('Reviewer C')
  expect(events[2]).toContain('Scenario review reason'); expect(events[3]).toContain('Accepted version 7: High')
  expect(container.querySelectorAll('time')).toHaveLength(4)
  expect(screen.getByText(/Current effective decision:/).parentElement?.textContent).toContain('High')
  expect(screen.getByText(/Original system decision:/).parentElement?.textContent).toContain('Low')
})
it('identifies missing legacy provenance and uncertain tied-event order', () => {
  render(<><GenerationDetails /><ReviewHistory audit={{ ...history, feedback: history.feedback.map(e => ({ ...e, event_sequence: null })) }} /></>)
  expect(screen.getByText(/provenance was not recorded/)).toBeTruthy()
  expect(screen.getByText(/actual relative order is unknown/)).toBeTruthy()
})
it('renders referenced context values from structured data and qualifies explanation scores', () => {
  const { container } = render(<ExplanationPanel alert={result.alert} ruleOutput={result.rule_output} finalPriority={result.final_priority} finalRoute={result.final_route} explanation={{ ...result.explanation, explanation_mode: 'hybrid', context_observations: [{ evidence_id: 'OBS_HEART_RATE', label: 'Heart rate', value: 145, unit: 'bpm', available: true }], llm_confidence_estimate: .74, llm_self_reported_confidence: .99, confidence_cap: .74, confidence_cap_reason: 'Available-input heuristic.' }} />)
  expect(container.querySelectorAll('.explanation-block')).toHaveLength(6)
  expect(screen.getByText('145 bpm')).toBeTruthy()
  expect(screen.getByText(/Self-reported explanation estimate:/).textContent).toContain('0.99')
  expect(screen.getByText(/Self-reported explanation estimate:/).textContent).toContain('Deterministic cap: 0.74')
  expect(screen.getByText(/Recorded input · not triggering rule evidence/)).toBeTruthy()
})
it('loads expanded audit history and retries a failed read without writing an action', async () => {
  const entry: AuditLogEntry = { id: 1, alert_id: result.alert_id, alert_type: result.alert.alert_type, patient_id: result.alert.patient_id, unit: result.alert.unit, baseline_priority: 'Low', final_priority: 'Low', final_route: result.final_route, explanation_mode: 'rules_only', rule_confidence: .5, created_at: at, override_count: 1, acceptance_count: 1, feedback_count: 1 }
  vi.mocked(api.listAuditLog).mockResolvedValue([entry])
  vi.mocked(api.getAlertAudit).mockRejectedValueOnce(new Error('History read failed')).mockResolvedValue(history)
  render(<AuditView onClose={() => {}} />)
  await userEvent.click(await screen.findByRole('button', { name: result.alert_id }))
  expect((await screen.findByRole('alert')).textContent).toContain('History read failed')
  await userEvent.click(screen.getByRole('button', { name: 'Retry history' }))
  expect(await screen.findByText(/Current effective decision:/)).toBeTruthy()
  expect(within(screen.getByRole('dialog')).getByText(/Scenario review reason/)).toBeTruthy()
  expect(api.getAlertAudit).toHaveBeenCalledTimes(2)
})
