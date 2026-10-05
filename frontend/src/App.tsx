import { useEffect, useRef, useState } from 'react'
import { api } from './api/client'
import { AlertTable } from './components/AlertTable'
import { AlertDetail } from './components/AlertDetail'
import { AlertSimulator } from './components/AlertSimulator'
import { ScenarioChooser } from './components/ScenarioChooser'
import { AuditView } from './components/AuditView'
import type { AlertAudit, TriageResult } from './types'

export default function App() {
  const [results, setResults] = useState<TriageResult[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [simulatorOpen, setSimulatorOpen] = useState(false)
  const [auditViewOpen, setAuditViewOpen] = useState(false)

  // Shared reviewer ID across all review actions in this session
  const [reviewerId, setReviewerId] = useState('Dr. Demo')

  // Per-alert history is loaded on selection and refreshed after review actions.
  const [auditMap, setAuditMap] = useState<Record<string, AlertAudit>>({})

  // Auto-select only until the first example or visitor selection, including Back.
  const initialSelectionDone = useRef(false)
  const focusSelection = useRef(false)
  const detailRef = useRef<HTMLElement>(null)
  const queueRef = useRef<HTMLHeadingElement>(null)
  function loadAlerts() {
    setLoading(true)
    setError(null)
    api.listAlerts()
      .then((available) => setResults((current) => {
        // A slow initial GET must not discard a scenario just created by the visitor.
        const currentIds = new Set(current.map((r) => r.alert_id))
        return [...current, ...available.filter((r) => !currentIds.has(r.alert_id))]
      }))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(loadAlerts, [])
  useEffect(() => {
    if (!initialSelectionDone.current && results.length > 0) {
      initialSelectionDone.current = true
      const example = results.find((r) => r.alert.alert_type === 'tachycardia') ?? results[0]
      setSelectedId(example.alert_id)
    }
  }, [results])
  useEffect(() => {
    if (selectedId && focusSelection.current) {
      detailRef.current?.focus()
      focusSelection.current = false
    }
  }, [selectedId])

  function selectAlert(id: string) {
    initialSelectionDone.current = true
    focusSelection.current = true
    setSelectedId(id)
    // Selecting an already-open example still moves keyboard focus to its detail.
    if (id === selectedId) { detailRef.current?.focus(); focusSelection.current = false }
  }

  function handleSimulatorResult(result: TriageResult) {
    setResults((prev) => {
      const without = prev.filter((r) => r.alert_id !== result.alert_id)
      return [result, ...without]
    })
    selectAlert(result.alert_id)
    setSimulatorOpen(false)
  }

  function handleAuditUpdate(alertId: string, audit: AlertAudit) {
    setAuditMap((prev) => ({ ...prev, [alertId]: audit }))
    setResults((prev) => prev.map((r) => r.alert_id === alertId ? { ...r, review_state: audit.review_state } : r))
  }

  const selected = results.find((r) => r.alert_id === selectedId) ?? null
  const selectedAudit = selectedId ? (auditMap[selectedId] ?? null) : null
  const hybridCount = results.filter((r) => r.explanation.explanation_mode === 'hybrid').length

  return (
    <div className="app-shell">
      <a className="skip-link" href="#queue">Skip to alert queue</a>
      <header className="app-header">
        <div><p className="eyebrow">Portfolio / simulated alerts</p><h1>Clinical Alert Triage</h1></div>
        <div className="actions"><span className="badge">{hybridCount > 0 ? `${hybridCount} recorded AI explanation${hybridCount === 1 ? '' : 's'}` : 'Rules-only examples'}</span>
          <button className="button button-outline" onClick={() => setAuditViewOpen(true)}>Audit Log</button><a className="button button-outline" href="#quick-scenario">Try an example ↓</a></div>
      </header>
      <section className="demo-intro" aria-labelledby="intro-heading">
        <div className="intro-copy">
          <div className="section-heading"><h2 id="intro-heading">How it works</h2><span className="badge">Simulated data · Portfolio demo</span></div>
          <p><strong>Rules assign priority and routing.</strong> <strong>AI explains</strong> when available; it never decides. <strong>Humans review</strong> and retain final control. Every action is recorded.</p>
          <nav className="intro-links" aria-label="About this project">
            <a href="https://github.com/hsivasambu/clinical-alert-triage" target="_blank" rel="noopener noreferrer">Repository <span className="sr-only">(opens in a new tab)</span>↗</a>
            <a href="https://blog.harry-sivasambu.com/blog/clinical-alert-triage" target="_blank" rel="noopener noreferrer">Project blog <span className="sr-only">(opens in a new tab)</span>↗</a>
          </nav>
        </div>
        <ScenarioChooser onResult={handleSimulatorResult} onCustomize={() => setSimulatorOpen(true)} />
      </section>
      <main className={`workspace ${selected ? 'has-selection' : ''}`}>
        <section className="queue-pane" aria-labelledby="queue" aria-busy={loading}>
          <div className="section-heading"><h2 id="queue" ref={queueRef} tabIndex={-1}>Alert Queue</h2><span className="muted">{results.length} alerts</span></div>
          <p className="muted">Select a simulated alert to follow its decision and explanation.</p>
          {loading && <div className="empty-state" role="status">Loading alerts…</div>}
          {error && <div className="notice notice-error" role="alert"><p>Could not load alerts: {error}</p><button className="button" onClick={loadAlerts}>Retry loading alerts</button></div>}
          {!loading && !error && results.length === 0 && <div className="empty-state"><h3>No alerts yet</h3><p>Create a simulated alert to explore the workflow.</p><a className="button button-primary" href="#quick-scenario">Choose an example</a></div>}
          {results.length > 0 && <AlertTable results={results} selectedId={selectedId} onSelect={selectAlert} />}
        </section>
        <section className="detail-pane" ref={detailRef} tabIndex={-1} aria-label="Selected alert">
          {selected ? <><button className="button back-action" onClick={() => { initialSelectionDone.current = true; setSelectedId(null); requestAnimationFrame(() => queueRef.current?.focus()) }}>← Back to queue</button>
            <AlertDetail key={selected.alert_id} result={selected} audit={selectedAudit} reviewerId={reviewerId} onReviewerIdChange={setReviewerId} onAuditUpdate={(audit) => handleAuditUpdate(selected.alert_id, audit)} />
          </> : <div className="empty-state"><span className="eyebrow">Decision → explanation → review</span><h2>Explore an alert</h2><p>Select an alert from the queue to see the original rules decision, explanation, and human review history.</p></div>}
        </section>
      </main>
      {simulatorOpen && <AlertSimulator onResult={handleSimulatorResult} onClose={() => setSimulatorOpen(false)} />}
      {auditViewOpen && <AuditView onClose={() => setAuditViewOpen(false)} />}
    </div>
  )
}
