import type { TriageResult } from '../types'
interface Props { results: TriageResult[]; selectedId: string | null; onSelect: (id: string) => void }
export function AlertTable({ results, selectedId, onSelect }: Props) {
  return <div className="queue-table-wrap"><table className="queue-table">
    <caption className="sr-only">Simulated alerts with current effective decisions</caption>
    <thead><tr><th scope="col">Alert</th><th scope="col">Priority / review</th><th scope="col">Destination</th></tr></thead>
    <tbody>{results.map((r) => <tr key={r.alert_id} className={selectedId === r.alert_id ? 'is-selected' : ''} onClick={() => onSelect(r.alert_id)}>
      <td data-label="Alert"><button className="alert-select" aria-label={`View alert ${r.alert_id}`} aria-current={selectedId === r.alert_id ? 'true' : undefined} onClick={(e) => { e.stopPropagation(); onSelect(r.alert_id) }}>{r.alert_id}</button>
        <div className="muted small">{r.alert.alert_type.replace(/_/g, ' ')} · {r.alert.patient_id}</div><div className="muted small">{r.alert.unit}</div></td>
      <td data-label="Priority / review"><span className={`badge priority-${(r.review_state?.effective_priority ?? r.final_priority).toLowerCase()}`}>{r.review_state?.effective_priority ?? r.final_priority}</span><div className="small review-status">{r.review_state?.review_status ?? 'unreviewed'}</div></td>
      <td data-label="Destination">{r.review_state?.effective_route ?? r.final_route}<div className="muted small">{r.explanation.explanation_mode === 'hybrid' ? 'Recorded AI narrative' : 'Rules only'} · {new Date(r.processed_at).toLocaleTimeString()}</div></td>
    </tr>)}</tbody>
  </table></div>
}
