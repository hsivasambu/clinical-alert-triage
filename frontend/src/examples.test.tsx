import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from './api/client'
import { ScenarioChooser } from './components/ScenarioChooser'
import { buildAlert } from './simulator/buildAlert'
import { PRESETS } from './simulator/presets'
import { SCENARIOS, buildScenarioAlert } from './simulator/scenarios'
import type { TriageResult } from './types'

vi.mock('./api/client', () => ({ api: { triageAlert: vi.fn() } }))
afterEach(cleanup)
describe('example catalog', () => {
  it('has five unique examples for each mode', () => {
    expect(new Set(SCENARIOS.map((s) => s.id)).size).toBe(SCENARIOS.length)
    expect(SCENARIOS.filter((s) => s.mode === 'rules')).toHaveLength(5)
    expect(SCENARIOS.filter((s) => s.mode === 'ai')).toHaveLength(5)
  })
  it('builds a fresh alert each run without sharing nested objects', () => {
    const [a, b] = [buildScenarioAlert(SCENARIOS[5]), buildScenarioAlert(SCENARIOS[5])]
    expect(a.alert_id).not.toBe(b.alert_id)
    expect(a.recent_context).not.toBe(SCENARIOS[5].alert.recent_context)
  })
})
describe('example chooser', () => {
  it('groups examples, moves to the next untried one and then points to Create your own alert', async () => {
    vi.mocked(api.triageAlert).mockResolvedValue({} as TriageResult)
    const onCustomize = vi.fn()
    render(<ScenarioChooser onResult={() => {}} onCustomize={onCustomize} />)
    const select = screen.getByRole('combobox', { name: 'Try an example' })
    expect(within(select).getByRole('group', { name: 'Rules-based routing' })).toBeTruthy()
    expect(within(select).getByRole('group', { name: 'AI-supported decision' })).toBeTruthy()
    await userEvent.selectOptions(select, 'ai-support')
    for (let i = 0; i < 5; i++) {
      expect(screen.queryByText(/You have tried all/)).toBeNull()
      await userEvent.click(screen.getByRole('button', { name: 'Run example' }))
    }
    const ids = vi.mocked(api.triageAlert).mock.calls.map(([alert]) => alert.patient_id)
    expect(new Set(ids).size).toBe(5)
    expect(screen.getByText(/You have tried all 5 AI-supported decision examples/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Create your own alert' }))
    expect(onCustomize).toHaveBeenCalled()
  })
})
describe('custom alert pump fields', () => {
  const form = { ...PRESETS.infusion_pump, alert_id: 'LOCAL', timestamp: '2025-01-01T00:00:00Z' }
  it('sends pump alarm type and medication as typed context', () => {
    expect(buildAlert({ ...form, alarm_type: 'battery_low', infusate: 'insulin' }).additional_context).toEqual({ alarm_type: 'battery_low', infusate: 'insulin' })
  })
  it('sends no pump context for other alert types', () => {
    expect(buildAlert({ ...form, alert_type: 'tachycardia' }).additional_context).toEqual({})
  })
})
