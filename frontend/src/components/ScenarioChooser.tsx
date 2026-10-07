import { useState } from 'react'
import { api } from '../api/client'
import { MODE_LABELS, SCENARIOS, buildScenarioAlert, type ScenarioMode } from '../simulator/scenarios'
import type { TriageResult } from '../types'
import { About } from './Callouts'
interface Props { onResult: (result: TriageResult) => void; onCustomize: () => void }
const MODES: ScenarioMode[] = ['rules', 'ai']
const TRIED_KEY = 'tried-examples'
function loadTried(): string[] {
  try { const value = JSON.parse(localStorage.getItem(TRIED_KEY) ?? '[]'); return Array.isArray(value) ? value : [] } catch { return [] }
}
export function ScenarioChooser({ onResult, onCustomize }: Props) {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id)
  const [tried, setTried] = useState<string[]>(loadTried)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0]
  const sameMode = SCENARIOS.filter((s) => s.mode === scenario.mode)
  const allTried = sameMode.every((s) => tried.includes(s.id))
  async function run() {
    if (running) return
    setRunning(true)
    setError(null)
    try {
      onResult(await api.triageAlert(buildScenarioAlert(scenario)))
      const next = [...new Set([...tried, scenario.id])]
      setTried(next)
      try { localStorage.setItem(TRIED_KEY, JSON.stringify(next)) } catch { /* per-visitor convenience only */ }
      const upcoming = sameMode.find((s) => !next.includes(s.id))
      if (upcoming) setScenarioId(upcoming.id)
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not run this example.') }
    finally { setRunning(false) }
  }
  return <section className="scenario-chooser" aria-labelledby="scenario-heading">
    <div className="scenario-actions">
      <label id="scenario-heading" className="form-label" htmlFor="quick-scenario">Try an example</label>
      <select className="form-input" id="quick-scenario" value={scenarioId} disabled={running}
        aria-describedby="scenario-description" onChange={(e) => { setScenarioId(e.target.value); setError(null) }}>
        {MODES.map((mode) => <optgroup key={mode} label={MODE_LABELS[mode]}>
          {SCENARIOS.filter((s) => s.mode === mode).map((s) => <option key={s.id} value={s.id}>{s.title}{tried.includes(s.id) ? ' (tried)' : ''}</option>)}
        </optgroup>)}
      </select>
      <button className="button button-primary" disabled={running} onClick={run}>{running ? 'Running example…' : 'Run example'}</button>
      <button className={allTried ? 'button button-primary' : 'button'} disabled={running} onClick={onCustomize}>Create your own alert</button>
    </div>
    <About id="scenario-description" label={`About this example · ${MODE_LABELS[scenario.mode]}`}>{scenario.description}</About>
    {allTried && <p className="notice next-step" role="status">You have tried all {sameMode.length} {MODE_LABELS[scenario.mode]} examples. Next, use <strong>Create your own alert</strong> to enter your own vitals, medications and message and see how the rules{scenario.mode === 'ai' ? ' and the AI reviewer' : ''} respond.</p>}
    {running && <p className="small" role="status">Submitting simulated input to the rules and explanation pipeline…</p>}
    {error && <p className="notice notice-error" role="alert">Could not run example: {error}</p>}
  </section>
}
