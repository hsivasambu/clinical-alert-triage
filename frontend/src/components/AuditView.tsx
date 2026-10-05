import { fallbackLabel } from '../fallbackLabels'
import { Dialog } from './Dialog'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AlertType, AuditLogEntry, ExplanationMode } from '../types'
import { ALERT_TYPE_LABELS } from '../simulator/presets'
import { PRIORITIES } from '../types'

interface Props {
  onClose: () => void
}

const ALERT_TYPES: AlertType[] = ['tachycardia', 'low_spo2', 'infusion_pump', 'nurse_call', 'fall_risk', 'sepsis']
const EXPLANATION_MODES: ExplanationMode[] = ['hybrid', 'rules_only']

interface Filters {
  alert_type: string
  final_priority: string
  explanation_mode: string
  overridden_only: boolean
}

const DEFAULT_FILTERS: Filters = {
  alert_type: '',
  final_priority: '',
  explanation_mode: '',
  overridden_only: false,
}

export function AuditView({ onClose }: Props) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  async function load(f: Filters) {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listAuditLog({
        alert_type: f.alert_type || undefined,
        final_priority: f.final_priority || undefined,
        explanation_mode: f.explanation_mode || undefined,
        overridden_only: f.overridden_only || undefined,
        limit: 200,
      })
      setEntries(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load audit log.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(filters) }, [filters])

  return (
    <Dialog titleId="audit-modal-title" className="audit-modal" onClose={onClose}>
        <div className="audit-header">
          <div>
            <h2 id="audit-modal-title" className="dialog-title">Audit Log</h2>
            <span style={{ marginLeft: 10, fontSize: 12, color: '#90caf9', background: '#1a4a7a', padding: '2px 8px', borderRadius: 4 }}>
              Append-only | All decisions and human actions
            </span>
          </div>
          <button onClick={onClose} className="audit-close-btn" aria-label="Close audit log">x</button>
        </div>

        <div className="audit-filter-bar">
          <label>Alert type<select
            className="audit-filter-select"
            value={filters.alert_type}
            onChange={(e) => setFilter('alert_type', e.target.value)}
          >
            <option value="">All types</option>
            {ALERT_TYPES.map((t) => <option key={t} value={t}>{ALERT_TYPE_LABELS[t]}</option>)}
          </select></label>

          <label>Original priority<select
            className="audit-filter-select"
            value={filters.final_priority}
            onChange={(e) => setFilter('final_priority', e.target.value)}
          >
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select></label>

          <label>Explanation mode<select
            className="audit-filter-select"
            value={filters.explanation_mode}
            onChange={(e) => setFilter('explanation_mode', e.target.value)}
          >
            <option value="">All modes</option>
            {EXPLANATION_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select></label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#444', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={filters.overridden_only}
              onChange={(e) => setFilter('overridden_only', e.target.checked)}
            />
            Overridden only
          </label>

          <button
            onClick={() => setFilters(DEFAULT_FILTERS)}
            className="audit-clear-btn"
          >
            Clear filters
          </button>

          <span role="status" style={{ marginLeft: 'auto', fontSize: 12, color: '#566579' }}>
            {loading ? 'Loading...' : `${entries.length} entr${entries.length !== 1 ? 'ies' : 'y'}`}
          </span>
        </div>

        <div className="audit-table-wrapper">
          {error && <p role="alert" style={{ color: 'red', padding: 16 }}>Error: {error}</p>}
          {!loading && !error && entries.length === 0 && (
            <p style={{ color: '#566579', padding: 24, textAlign: 'center' }}>No entries match the current filters.</p>
          )}
          {!loading && !error && entries.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f5f5f5', zIndex: 1 }}>
                <tr>
                  {['Processing time', 'Alert ID', 'Type', 'Patient', 'Unit', 'Priority', 'Mode', 'Actions'].map((h) => (
                    <th key={h} className="audit-th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <FragmentRow
                    key={entry.id}
                    entry={entry}
                    expanded={expandedId === entry.id}
                    onToggle={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
    </Dialog>
  )
}

function FragmentRow({ entry, expanded, onToggle }: { entry: AuditLogEntry; expanded: boolean; onToggle: () => void }) {
  return (
    <>
      <tr
        onClick={onToggle}
        style={{
          cursor: 'pointer',
          background: expanded ? '#eef4ff' : 'white',
          borderBottom: '1px solid #eee',
        }}
      >
        <td className="audit-td">{new Date(entry.created_at).toLocaleString()}</td>
        <td className="audit-td" style={{ fontFamily: 'monospace', fontSize: 11 }}><button className="alert-select" aria-expanded={expanded} onClick={event => { event.stopPropagation(); onToggle() }}>{entry.alert_id}</button></td>
        <td className="audit-td">{ALERT_TYPE_LABELS[entry.alert_type]}</td>
        <td className="audit-td">{entry.patient_id}</td>
        <td className="audit-td">{entry.unit}</td>
        <td className="audit-td">
          <span className={`badge priority-${entry.final_priority.toLowerCase()}`}>{entry.final_priority}</span>
        </td>
        <td className="audit-td">
          <span style={{ color: entry.explanation_mode === 'hybrid' ? '#1e5d8a' : '#566579' }}>
            {entry.explanation_mode === 'hybrid' ? 'Recorded AI narrative' : 'Recorded rules explanation'}
          </span>
          {entry.explanation_mode === 'rules_only' && <div className="small muted">{fallbackLabel(entry.fallback_reason)}</div>}
        </td>
        <td className="audit-td">
          <ActionPills entry={entry} />
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: '#f8f9ff' }}>
          <td colSpan={8} style={{ padding: '10px 20px', borderBottom: '1px solid #dde' }}>
            <ExpandedRow entry={entry} />
          </td>
        </tr>
      )}
    </>
  )
}

function ActionPills({ entry }: { entry: AuditLogEntry }) {
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {entry.acceptance_count > 0 && (
        <span className="audit-pill" style={{ background: '#e8f5e9', color: '#2e7d32' }}>
          Accepted
        </span>
      )}
      {entry.override_count > 0 && (
        <span className="audit-pill" style={{ background: '#fff3e0', color: '#e65100' }}>
          {entry.override_count} override{entry.override_count !== 1 ? 's' : ''}
        </span>
      )}
      {entry.feedback_count > 0 && (
        <span className="audit-pill" style={{ background: '#e3f2fd', color: '#1565c0' }}>
          {entry.feedback_count} feedback
        </span>
      )}
      {entry.override_count === 0 && entry.acceptance_count === 0 && entry.feedback_count === 0 && (
        <span style={{ color: '#566579', fontSize: 11 }}>-</span>
      )}
    </div>
  )
}

function ExpandedRow({ entry }: { entry: AuditLogEntry }) {
  return (
    <div style={{ display: 'flex', gap: 24, fontSize: 12 }}>
      <div>
        <div className="audit-expand-label">Baseline priority</div>
        <div>{entry.baseline_priority}</div>
      </div>
      <div>
        <div className="audit-expand-label">Final priority</div>
        <div>{entry.final_priority}</div>
      </div>
      <div>
        <div className="audit-expand-label">Final route</div>
        <div>{entry.final_route}</div>
      </div>
      <div>
        <div className="audit-expand-label">Rule confidence</div>
        <div>{entry.rule_confidence.toFixed(2)}</div>
      </div>
      <div>
        <div className="audit-expand-label">Processing time</div>
        <div>{new Date(entry.created_at).toLocaleString()}</div>
      </div>
    </div>
  )
}
