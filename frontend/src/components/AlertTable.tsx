import { useEffect, useState } from 'react'
import type { TriageResult } from '../types'
import { ALERT_TYPE_LABELS } from '../simulator/presets'
import { alertAge, isHistoricalFixture } from '../queue'
interface Props { results: TriageResult[]; selectedId: string | null; onSelect: (id: string) => void }
export function AlertTable({ results, selectedId, onSelect }: Props) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 60000); return () => clearInterval(timer) }, [])
  return <div className="queue-table-wrap"><table className="queue-table">
    <caption className="sr-only">Simulated alerts with current effective decisions. Age is measured from alert time, not processing time.</caption>
    <thead><tr>{['Priority', 'Alert', 'Patient / unit', 'Alert age', 'Review'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
    <tbody>{results.map(r => <tr key={r.alert_id} className={selectedId === r.alert_id ? 'is-selected' : ''} onClick={() => onSelect(r.alert_id)}>
      <td data-label="Priority"><span className={`badge priority-${(r.review_state?.effective_priority ?? r.final_priority).toLowerCase()}`}>{r.review_state?.effective_priority ?? r.final_priority}</span></td>
      <td data-label="Alert"><button className="alert-select" aria-label={`View alert ${r.alert_id}`} aria-current={selectedId === r.alert_id ? 'true' : undefined} onClick={e => { e.stopPropagation(); onSelect(r.alert_id) }}>{ALERT_TYPE_LABELS[r.alert.alert_type]}<span className="sr-only">{r.alert_id}</span></button></td>
      <td data-label="Patient / unit"><strong>{r.alert.patient_id}</strong><div className="muted small">{r.alert.unit}</div></td>
      <td data-label="Alert age">{isHistoricalFixture(r) ? <span className="small">Historical fixture</span> : <span title={`Alert time: ${new Date(r.alert.timestamp).toLocaleString()}`}>{alertAge(r.alert.timestamp, now)}</span>}</td>
      <td data-label="Review"><span className="badge">{r.review_state?.review_status ?? 'unreviewed'}</span></td>
    </tr>)}</tbody>
  </table></div>
}
