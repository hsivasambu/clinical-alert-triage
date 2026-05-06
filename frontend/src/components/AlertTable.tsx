import type { Priority, TriageResult } from '../types'

const PRIORITY_COLOR: Record<Priority, string> = {
  Critical: '#c0392b',
  High: '#e67e22',
  Medium: '#f1c40f',
  Low: '#27ae60',
}

interface Props {
  results: TriageResult[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function AlertTable({ results, selectedId, onSelect }: Props) {
  if (results.length === 0) {
    return <p style={{ color: '#888' }}>No alerts processed yet.</p>
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
      <thead>
        <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
          <th style={th}>Priority</th>
          <th style={th}>Alert ID</th>
          <th style={th}>Type</th>
          <th style={th}>Patient</th>
          <th style={th}>Unit</th>
          <th style={th}>Route</th>
          <th style={th}>Mode</th>
          <th style={th}>Time</th>
        </tr>
      </thead>
      <tbody>
        {results.map((r) => (
          <tr
            key={r.alert_id}
            onClick={() => onSelect(r.alert_id)}
            style={{
              cursor: 'pointer',
              background: selectedId === r.alert_id ? '#eef4ff' : 'white',
              borderBottom: '1px solid #eee',
            }}
          >
            <td style={td}>
              <span
                style={{
                  background: PRIORITY_COLOR[r.final_priority],
                  color: 'white',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontWeight: 600,
                  fontSize: 12,
                }}
              >
                {r.final_priority}
              </span>
            </td>
            <td style={{ ...td, fontFamily: 'monospace' }}>{r.alert_id}</td>
            <td style={td}>{r.alert.alert_type}</td>
            <td style={td}>{r.alert.patient_id}</td>
            <td style={td}>{r.alert.unit}</td>
            <td style={td}>{r.final_route}</td>
            <td style={td}>
              <span style={{ color: r.explanation.explanation_mode === 'hybrid' ? '#2980b9' : '#888' }}>
                {r.explanation.explanation_mode}
              </span>
            </td>
            <td style={td}>{new Date(r.processed_at).toLocaleTimeString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const th: React.CSSProperties = {
  padding: '8px 12px',
  borderBottom: '2px solid #ddd',
  fontWeight: 600,
}

const td: React.CSSProperties = {
  padding: '8px 12px',
}
