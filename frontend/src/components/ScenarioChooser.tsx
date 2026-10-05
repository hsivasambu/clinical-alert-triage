import { useState } from 'react'
import { api } from '../api/client'
import { SCENARIOS, buildScenarioAlert } from '../simulator/scenarios'
import type { TriageResult } from '../types'
interface Props { onResult: (result: TriageResult) => void; onCustomize: () => void }
export function ScenarioChooser({ onResult, onCustomize }: Props) {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0]
  async function run() {
    if (running) return
    setRunning(true)
    setError(null)
    try { onResult(await api.triageAlert(buildScenarioAlert(scenario))) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not run this example.') }
    finally { setRunning(false) }
  }
  return <section className="scenario-chooser" aria-labelledby="scenario-heading">
    <div className="scenario-actions">
      <label id="scenario-heading" className="form-label" htmlFor="quick-scenario">Try an example</label>
      <select className="form-input" id="quick-scenario" value={scenarioId} disabled={running}
        aria-describedby="scenario-description" onChange={(e) => { setScenarioId(e.target.value); setError(null) }}>
        {SCENARIOS.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
      </select>
      <button className="button button-primary" disabled={running} onClick={run}>{running ? 'Running example…' : 'Run example'}</button>
      <button className="button" disabled={running} onClick={onCustomize}>Advanced customization</button>
    </div>
    <p id="scenario-description" className="muted small">{scenario.description}</p>
    {running && <p className="small" role="status">Submitting simulated input to the rules and explanation pipeline…</p>}
    {error && <p className="notice notice-error" role="alert">Could not run example: {error}</p>}
  </section>
}
