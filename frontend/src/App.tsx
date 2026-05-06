import { useEffect, useState } from 'react'
import { api } from './api/client'
import { AlertTable } from './components/AlertTable'
import { AlertDetail } from './components/AlertDetail'
import { AlertSimulator } from './components/AlertSimulator'
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

  // Per-alert audit data: loaded on demand when a review action completes
  const [auditMap, setAuditMap] = useState<Record<string, AlertAudit>>({})

  useEffect(() => {
    api.listAlerts()
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function handleSimulatorResult(result: TriageResult) {
    setResults((prev) => {
      const without = prev.filter((r) => r.alert_id !== result.alert_id)
      return [result, ...without]
    })
    setSelectedId(result.alert_id)
    setSimulatorOpen(false)
  }

  function handleAuditUpdate(alertId: string, audit: AlertAudit) {
    setAuditMap((prev) => ({ ...prev, [alertId]: audit }))
  }

  const selected = results.find((r) => r.alert_id === selectedId) ?? null
  const selectedAudit = selectedId ? (auditMap[selectedId] ?? null) : null
  const hybridCount = results.filter((r) => r.explanation.explanation_mode === 'hybrid').length

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh', background: '#f8f9fa' }}>
      <header style={{ background: '#1a3a5c', color: 'white', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 20, fontWeight: 700 }}>Clinical Alert Triage</span>
        <span style={{ fontSize: 12, background: '#2980b9', padding: '2px 8px', borderRadius: 4 }}>
          MVP | {hybridCount > 0 ? 'hybrid active' : 'rules-only'}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
          <button
            onClick={() => setAuditViewOpen(true)}
            style={{
              padding: '7px 16px',
              background: 'transparent',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.4)',
              borderRadius: 6,
              fontWeight: 500,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Audit Log
          </button>
          <button
            onClick={() => setSimulatorOpen(true)}
            style={{
              padding: '7px 18px',
              background: '#27ae60',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            + Simulate Alert
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', height: 'calc(100vh - 52px)' }}>
        {/* Alert queue */}
        <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
          <h2 style={{ margin: '0 0 16px', fontSize: 16 }}>
            Alert Queue
            <span style={{ marginLeft: 8, color: '#888', fontWeight: 400, fontSize: 13 }}>
              {results.length} alert{results.length !== 1 ? 's' : ''}
            </span>
          </h2>

          {loading && <p>Loading...</p>}
          {error && <p style={{ color: 'red' }}>Error: {error}</p>}
          {!loading && !error && results.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: 60, color: '#aaa' }}>
              <p style={{ fontSize: 15 }}>No alerts yet.</p>
              <p style={{ fontSize: 13 }}>
                Click{' '}
                <button
                  onClick={() => setSimulatorOpen(true)}
                  style={{ background: 'none', border: 'none', color: '#2980b9', cursor: 'pointer', fontSize: 13, padding: 0, textDecoration: 'underline' }}
                >
                  Simulate Alert
                </button>{' '}
                to create your first one.
              </p>
            </div>
          )}
          {!loading && !error && results.length > 0 && (
            <AlertTable results={results} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </div>

        {/* Detail panel */}
        <div
          style={{
            width: 440,
            borderLeft: '1px solid #ddd',
            background: 'white',
            overflow: 'auto',
            padding: 24,
          }}
        >
          {selected ? (
            <AlertDetail
              result={selected}
              audit={selectedAudit}
              reviewerId={reviewerId}
              onReviewerIdChange={setReviewerId}
              onAuditUpdate={(audit) => handleAuditUpdate(selected.alert_id, audit)}
            />
          ) : (
            <div style={{ marginTop: 40, textAlign: 'center', color: '#aaa' }}>
              <p>Select an alert to inspect the triage output.</p>
              <p style={{ fontSize: 12, marginTop: 8 }}>
                Each result shows the rules engine decision,<br />
                explanation mode, and full audit trail.
              </p>
            </div>
          )}
        </div>
      </div>

      {simulatorOpen && (
        <AlertSimulator
          onResult={handleSimulatorResult}
          onClose={() => setSimulatorOpen(false)}
        />
      )}

      {auditViewOpen && (
        <AuditView onClose={() => setAuditViewOpen(false)} />
      )}
    </div>
  )
}
