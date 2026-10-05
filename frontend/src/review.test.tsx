import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { api } from './api/client'
import type { AlertAudit, ReviewState, TriageResult } from './types'

vi.mock('./api/client', () => ({ api: {
  listAlerts: vi.fn(), triageAlert: vi.fn(), getAlertAudit: vi.fn(), acceptAlert: vi.fn(), submitOverride: vi.fn(), submitFeedback: vi.fn(),
} }))
const state = (priority: 'Critical' | 'High', status: ReviewState['review_status'] = 'unreviewed', version = 0): ReviewState => ({
  effective_priority: priority, effective_route: `${priority} route`, decision_version: version, review_status: status,
})
function result(id: string, priority: 'Critical' | 'High'): TriageResult {
  return { alert_id: id, final_priority: priority, final_route: `${priority} route`, processed_at: '2024-01-01T00:00:00Z',
    review_state: state(priority),
    alert: { alert_id: id, source_system: 'demo', alert_type: 'tachycardia', patient_id: 'P', unit: 'U', room: null, bed: null,
      timestamp: '2024-01-01T00:00:00Z', vital_signs: { heart_rate: 140, spo2: null, blood_pressure_systolic: null,
      blood_pressure_diastolic: null, respiratory_rate: null, temperature: null }, message_text: null, device_type: null,
      repeat_count: 0, additional_context: {}, recent_context: { prior_alerts_24h: 0, recent_medications: [], fall_risk_score: null,
      admission_reason: null, code_status: null } },
    rule_output: { baseline_priority: priority, matched_rules: [], suggested_route: `${priority} route`, rule_confidence: 1 },
    explanation: { summary: 'Demo', rationale: '', factors_considered: [], uncertainty_notes: '', recommended_checks: [],
      llm_confidence_estimate: null, explanation_mode: 'rules_only', rule_trace: [] } }
}
const critical = result('CRIT', 'Critical'), high = result('HIGH', 'High')
function audit(r: TriageResult): AlertAudit { return { triage_result: r, review_state: r.review_state!, overrides: [], acceptances: [], feedback: [] } }
async function select(id: string) {
  await userEvent.click(await screen.findByText(id))
  await waitFor(() => expect((screen.getByText('Accept Decision') as HTMLButtonElement).disabled).toBe(false))
}
afterEach(cleanup)
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.listAlerts).mockResolvedValue([critical, high])
  vi.mocked(api.getAlertAudit).mockImplementation(async (id) => audit(id === 'CRIT' ? critical : high))
})
describe('human review workflow', () => {
  it('does not retain Critical in the override selector after selecting High', async () => {
    render(<App />)
    await select('CRIT')
    await userEvent.click(screen.getByText('Override'))
    expect((screen.getByRole('combobox', { name: /New Priority/ }) as HTMLSelectElement).value).toBe('Critical')
    await userEvent.click(screen.getByRole('button', { name: 'View alert HIGH' }))
    const leakedSelector = screen.queryByRole('combobox', { name: /New Priority/ }) as HTMLSelectElement | null
    if (leakedSelector) expect(leakedSelector.value).toBe('High')
    await waitFor(() => expect((screen.getByText('Override') as HTMLButtonElement).disabled).toBe(false))
    await userEvent.click(screen.getByText('Override'))
    expect((screen.getByRole('combobox', { name: /New Priority/ }) as HTMLSelectElement).value).toBe('High')
  })

  it('reproduces Critical-to-High switching and clears drafts and validation errors', async () => {
    render(<App />)
    await select('CRIT')
    await userEvent.click(screen.getByText('Override'))
    expect((screen.getByRole('combobox', { name: /New Priority/ }) as HTMLSelectElement).value).toBe('Critical')
    await userEvent.click(screen.getByText('Confirm Override'))
    expect(screen.getByText('A reason is required for override.')).toBeTruthy()
    await userEvent.type(screen.getByPlaceholderText('Describe the clinical context that justifies this override...'), 'Critical draft')
    await userEvent.click(screen.getByText('Rate Explanation'))
    await userEvent.click(screen.getByText('Not Helpful'))
    await userEvent.type(screen.getByPlaceholderText('Any additional notes on explanation quality...'), 'Feedback draft')
    await select('HIGH')
    expect(screen.queryByText('A reason is required for override.')).toBeNull()
    expect(screen.queryByText('Confirm Override')).toBeNull()
    await userEvent.click(screen.getByText('Override'))
    expect((screen.getByRole('combobox', { name: /New Priority/ }) as HTMLSelectElement).value).toBe('High')
    expect((screen.getByPlaceholderText('Describe the clinical context that justifies this override...') as HTMLTextAreaElement).value).toBe('')
    await userEvent.click(screen.getByText('Rate Explanation'))
    expect((screen.getByPlaceholderText('Any additional notes on explanation quality...') as HTMLTextAreaElement).value).toBe('')
    expect(screen.queryByText('Reason category')).toBeNull()
  })
  it('loads existing history on selection and after a browser remount', async () => {
    vi.mocked(api.listAlerts).mockResolvedValue([high])
    const history = audit(high)
    history.review_state = state('High', 'accepted', 42)
    history.acceptances = [{ id: 1, alert_id: 'HIGH', reviewer_id: 'Saved reviewer', created_at: '2024-01-01T00:00:00Z',
      decision_version: 42, accepted_priority: 'High', accepted_route: 'High route' }]
    vi.mocked(api.getAlertAudit).mockResolvedValue(history)
    const view = render(<App />)
    await select('HIGH')
    expect(screen.getByText(/Accepted by Saved reviewer/)).toBeTruthy()
    view.unmount()
    render(<App />)
    await select('HIGH')
    expect(screen.getByText(/Accepted by Saved reviewer/)).toBeTruthy()
    expect(api.getAlertAudit).toHaveBeenCalledTimes(2)
  })
  it('updates queue/detail from saved override even when audit refresh fails; retry only reads history', async () => {
    render(<App />)
    await select('CRIT')
    const reviewed = { ...state('High', 'overridden', 9), effective_route: 'Reviewed route' }
    const record = { id: 9, alert_id: 'CRIT', reviewer_id: 'Dr. Demo', original_priority: 'Critical' as const,
      original_route: 'Critical route', overridden_priority: 'High' as const, overridden_route: 'Reviewed route',
      reason: 'Demo', created_at: '2024-01-01T00:00:00Z', review_state: reviewed }
    vi.mocked(api.submitOverride).mockResolvedValue(record)
    vi.mocked(api.getAlertAudit).mockRejectedValueOnce(new Error('refresh unavailable'))
    await userEvent.click(screen.getByText('Override'))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /New Priority/ }), 'High')
    await userEvent.type(screen.getByPlaceholderText('Describe the clinical context that justifies this override...'), 'Demo')
    await userEvent.click(screen.getByText('Confirm Override'))
    await screen.findByText(/Action saved. History refresh failed/)
    expect(screen.queryByText('Confirm Override')).toBeNull()
    const row = screen.getByRole('button', { name: 'View alert CRIT' }).closest('tr')!
    expect(within(row).getByText('Reviewed route', { exact: false })).toBeTruthy()
    expect(within(row).getByText('overridden')).toBeTruthy()
    expect(screen.getByText('Override recorded in audit log.')).toBeTruthy()
    const updated = { ...audit(critical), review_state: reviewed, overrides: [record] }
    vi.mocked(api.getAlertAudit).mockResolvedValue(updated)
    await userEvent.click(screen.getByText('Retry history'))
    await waitFor(() => expect(screen.queryByText(/Action saved. History refresh failed/)).toBeNull())
    expect(api.submitOverride).toHaveBeenCalledTimes(1)
    await select('HIGH')
    expect(screen.queryByText('Override recorded in audit log.')).toBeNull()
  })
  it('accepts the displayed version and updates queue status', async () => {
    render(<App />)
    await select('HIGH')
    vi.mocked(api.acceptAlert).mockResolvedValue({ id: 1, alert_id: 'HIGH', reviewer_id: 'Dr. Demo',
      created_at: '2024-01-01T00:00:00Z', decision_version: 0, accepted_priority: 'High', accepted_route: 'High route',
      review_state: state('High', 'accepted') })
    vi.mocked(api.getAlertAudit).mockRejectedValueOnce(new Error('refresh'))
    await userEvent.click(screen.getByText('Accept Decision'))
    await screen.findByText('Decision accepted and logged.')
    expect(api.acceptAlert).toHaveBeenCalledWith('HIGH', 'Dr. Demo', 0)
    expect(within(screen.getByRole('button', { name: 'View alert HIGH' }).closest('tr')!).getByText('accepted')).toBeTruthy()
  })
  it('clears saved feedback drafts before a failed history refresh', async () => {
    render(<App />)
    await select('HIGH')
    vi.mocked(api.submitFeedback).mockResolvedValue({ id: 1, alert_id: 'HIGH', reviewer_id: 'Dr. Demo', rating: 'not_helpful',
      reason_category: 'explanation_unclear', comment: 'Draft', created_at: '2024-01-01T00:00:00Z' })
    vi.mocked(api.getAlertAudit).mockRejectedValueOnce(new Error('refresh'))
    await userEvent.click(screen.getByText('Rate Explanation'))
    await userEvent.click(screen.getByText('Not Helpful'))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /Reason category/ }), 'explanation_unclear')
    await userEvent.type(screen.getByPlaceholderText('Any additional notes on explanation quality...'), 'Draft')
    await userEvent.click(screen.getByText('Submit Feedback'))
    await screen.findByText(/Action saved. History refresh failed/)
    expect(screen.queryByText('Submit Feedback')).toBeNull()
    expect(screen.getByText('Feedback recorded (1 submission)')).toBeTruthy()
    await userEvent.click(screen.getByText('Rate Explanation'))
    expect((screen.getByPlaceholderText('Any additional notes on explanation quality...') as HTMLTextAreaElement).value).toBe('')
    expect(screen.queryByText('Reason category')).toBeNull()
    expect(api.submitFeedback).toHaveBeenCalledTimes(1)
  })

  it('selects an initial example without stealing focus or overriding a later selection', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Why this decision?' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'View alert CRIT' }).getAttribute('aria-current')).toBe('true'))
    expect(document.activeElement?.getAttribute('aria-label')).not.toBe('Selected alert')
    await select('HIGH')
    vi.mocked(api.acceptAlert).mockResolvedValue({ id: 1, alert_id: 'HIGH', reviewer_id: 'Dr. Demo', created_at: '2024-01-01T00:00:00Z',
      decision_version: 0, accepted_priority: 'High', accepted_route: 'High route', review_state: state('High', 'accepted') })
    await userEvent.click(screen.getByText('Accept Decision'))
    await screen.findByText('Decision accepted and logged.')
    expect(screen.getByRole('button', { name: 'View alert HIGH' }).getAttribute('aria-current')).toBe('true')
    await userEvent.click(screen.getByRole('button', { name: /Back to queue/ }))
    expect(screen.queryByRole('heading', { name: 'Why this decision?' })).toBeNull()
  })
  it('runs a prefilled scenario and keeps it selected when a slow initial queue request completes', async () => {
    let complete!: (alerts: TriageResult[]) => void
    vi.mocked(api.listAlerts).mockReturnValue(new Promise((resolve) => { complete = resolve }))
    const scenarioResult = { ...high, alert_id: 'SCENARIO', alert: { ...high.alert, alert_id: 'SCENARIO' } }
    vi.mocked(api.triageAlert).mockResolvedValue(scenarioResult)
    vi.mocked(api.getAlertAudit).mockImplementation(async (id) => audit(id === 'SCENARIO' ? scenarioResult : critical))
    render(<App />)
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Try an example' }), 'repeat')
    expect(screen.getByText(/three repeats/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Run example' }))
    await screen.findByRole('heading', { name: 'Why this decision?' })
    expect(api.triageAlert).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.triageAlert).mock.calls[0][0]).toMatchObject({ alert_type: 'nurse_call', repeat_count: 3, source_system: 'Nurse-Call-Panel' })
    complete([critical, high])
    await screen.findByRole('button', { name: 'View alert CRIT' })
    expect(screen.getByRole('button', { name: 'View alert SCENARIO' }).getAttribute('aria-current')).toBe('true')
    expect(screen.queryByText('Alert Simulator')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Advanced customization' }))
    expect(screen.getByText('Alert Simulator')).toBeTruthy()
  })
  it('reports a failed scenario without replacing the selected alert', async () => {
    render(<App />)
    await select('HIGH')
    vi.mocked(api.triageAlert).mockRejectedValue(new Error('Service unavailable'))
    await userEvent.click(screen.getByRole('button', { name: 'Run example' }))
    await screen.findByText('Could not run example: Service unavailable')
    expect(screen.getByRole('button', { name: 'View alert HIGH' }).getAttribute('aria-current')).toBe('true')
    expect((screen.getByRole('button', { name: 'Run example' }) as HTMLButtonElement).disabled).toBe(false)
  })

})
