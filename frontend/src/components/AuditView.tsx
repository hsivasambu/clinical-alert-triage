import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AlertType, AuditLogEntry, ExplanationMode, Priority } from '../types'
import { PRIORITIES } from '../types'

interface Props {
  onClose: () => void
}

const ALERT_TYPES: AlertType[] = ['tachycardia', 'low_spo2', 'infusion_pump', 'nurse_call', 'fall_risk', 'sepsis']
const EXPLANATION_MODES: ExplanationMode[] = ['hybrid', 'rules_only']

const PRIORITY_COLOR: Record<Priority, string> = {
  Critical: '#c0392b',
  High: '#e67e22',
  Medium: '#d4ac0d',
  Low: '#27ae60',
}

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
    <div style={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <div>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Audit Log</span>
            <span style={{ marginLeft: 10, fontSize: 12, color: '#90caf9', background: '#1a4a7a', padding: '2px 8px', borderRadius: 4 }}>
              Append-only | All decisions and human actions
            </span>
          </div>
          <button onClick={onClose} style={styles.closeBtn}>x</button>
        </div>

        <div style={styles.filterBar}>
          <select
            style={styles.filterSelect}
            value={filters.alert_type}
            onChange={(e) => setFilter('alert_type', e.target.value)}
          >
            <option value="">All types</option>
            {ALERT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          <select
            style={styles.filterSelect}
            value={filters.final_priority}
            onChange={(e) => setFilter('final_priority', e.target.value)}
          >
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>

          <select
            style={styles.filterSelect}
            value={filters.explanation_mode}
            onChange={(e) => setFilter('explanation_mode', e.target.value)}
          >
            <option value="">All modes</option>
            {EXPLANATION_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>

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
            style={styles.clearBtn}
          >
            Clear filters
          </button>

          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#888' }}>
            {loading ? 'Loading...' : `${entries.length} entr${entries.length !== 1 ? 'ies' : 'y'}`}
          </span>
        </div>

        <div style={styles.tableWrapper}>
          {error && <p style={{ color: 'red', padding: 16 }}>Error: {error}</p>}
          {!loading && !error && entries.length === 0 && (
            <p style={{ color: '#888', padding: 24, textAlign: 'center' }}>No entries match the current filters.</p>
          )}
          {!loading && !error && entries.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f5f5f5', zIndex: 1 }}>
                <tr>
                  {['Time', 'Alert ID', 'Type', 'Patient', 'Unit', 'Priority', 'Mode', 'Actions'].map((h) => (
                    <th key={h} style={styles.th}>{h}</th>
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
      </div>
    </div>
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
        <td style={styles.td}>{new Date(entry.created_at).toLocaleTimeString()}</td>
        <td style={{ ...styles.td, fontFamily: 'monospace', fontSize: 11 }}>{entry.alert_id}</td>
        <td style={styles.td}>{entry.alert_type}</td>
        <td style={styles.td}>{entry.patient_id}</td>
        <td style={styles.td}>{entry.unit}</td>
        <td style={styles.td}>
          <span
            style={{
              background: PRIORITY_COLOR[entry.final_priority],
              color: 'white',
              padding: '2px 7px',
              borderRadius: 3,
              fontWeight: 600,
              fontSize: 11,
            }}
          >
            {entry.final_priority}
          </span>
        </td>
        <td style={styles.td}>
          <span style={{ color: entry.explanation_mode === 'hybrid' ? '#2980b9' : '#888' }}>
            {entry.explanation_mode}
          </span>
        </td>
        <td style={styles.td}>
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
        <span style={{ ...styles.pill, background: '#e8f5e9', color: '#2e7d32' }}>
          Accepted
        </span>
      )}
      {entry.override_count > 0 && (
        <span style={{ ...styles.pill, background: '#fff3e0', color: '#e65100' }}>
          {entry.override_count} override{entry.override_count !== 1 ? 's' : ''}
        </span>
      )}
      {entry.feedback_count > 0 && (
        <span style={{ ...styles.pill, background: '#e3f2fd', color: '#1565c0' }}>
          {entry.feedback_count} feedback
        </span>
      )}
      {entry.override_count === 0 && entry.acceptance_count === 0 && entry.feedback_count === 0 && (
        <span style={{ color: '#bbb', fontSize: 11 }}>-</span>
      )}
    </div>
  )
}

function ExpandedRow({ entry }: { entry: AuditLogEntry }) {
  return (
    <div style={{ display: 'flex', gap: 24, fontSize: 12 }}>
      <div>
        <div style={styles.expandLabel}>Baseline priority</div>
        <div>{entry.baseline_priority}</div>
      </div>
      <div>
        <div style={styles.expandLabel}>Final priority</div>
        <div>{entry.final_priority}</div>
      </div>
      <div>
        <div style={styles.expandLabel}>Final route</div>
        <div>{entry.final_route}</div>
      </div>
      <div>
        <div style={styles.expandLabel}>Rule confidence</div>
        <div>{entry.rule_confidence.toFixed(2)}</div>
      </div>
      <div>
        <div style={styles.expandLabel}>Timestamp</div>
        <div>{new Date(entry.created_at).toLocaleString()}</div>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: 16,
  },
  modal: {
    background: 'white',
    borderRadius: 10,
    width: '100%',
    maxWidth: 1000,
    maxHeight: '92vh',
    display: 'flex',
    flexDirection: 'column' as const,
    boxShadow: '0 8px 40px rgba(0,0,0,0.25)',
  },
  header: {
    background: '#1a3a5c',
    color: 'white',
    padding: '14px 20px',
    borderRadius: '10px 10px 0 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'white',
    fontSize: 18,
    cursor: 'pointer',
    padding: '0 4px',
  },
  filterBar: {
    padding: '12px 16px',
    borderBottom: '1px solid #eee',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap' as const,
    background: '#fafafa',
    flexShrink: 0,
  },
  filterSelect: {
    padding: '5px 8px',
    border: '1px solid #ddd',
    borderRadius: 5,
    fontSize: 13,
    background: 'white',
  },
  clearBtn: {
    padding: '5px 12px',
    border: '1px solid #ccc',
    borderRadius: 5,
    background: 'white',
    cursor: 'pointer',
    fontSize: 13,
    color: '#555',
  },
  tableWrapper: {
    flex: 1,
    overflowY: 'auto' as const,
  },
  th: {
    padding: '8px 12px',
    borderBottom: '2px solid #ddd',
    fontWeight: 600,
    textAlign: 'left' as const,
    whiteSpace: 'nowrap' as const,
  },
  td: {
    padding: '8px 12px',
  },
  pill: {
    fontSize: 11,
    padding: '1px 6px',
    borderRadius: 10,
    fontWeight: 500,
  },
  expandLabel: {
    color: '#888',
    marginBottom: 2,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
    fontSize: 10,
  },
}
