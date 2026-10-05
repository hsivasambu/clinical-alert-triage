import type { AlertAudit } from '../types'
export function ReviewHistory({ audit }: { audit: AlertAudit }) {
  const original = audit.triage_result
  const events = [
    ...audit.overrides.map(r => ({ ...r, kind: 'Override', text: `Original system: ${r.original_priority} → ${r.original_route}. Override version ${r.id}: priority ${r.overridden_priority}; destination ${r.overridden_route ?? 'retained from preceding decision'}. Reason: ${r.reason}` })),
    ...audit.acceptances.map(r => ({ ...r, kind: 'Acceptance', text: `Accepted version ${r.decision_version ?? 'unknown (legacy)'}: ${r.accepted_priority ?? 'not recorded'} → ${r.accepted_route ?? 'not recorded'}. Reason: acceptance of this decision snapshot.` })),
    ...audit.feedback.map(r => ({ ...r, kind: 'Feedback', text: `${r.rating}; reason: ${r.reason_category ?? 'not supplied'}; ${r.comment ?? 'No comment'}. Does not change the decision.` })),
  ].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || (a.event_sequence ?? 0) - (b.event_sequence ?? 0) || a.kind.localeCompare(b.kind) || a.id - b.id)
  return <div className="review-history">
    <p><strong>Original system decision:</strong> {original.final_priority} → {original.final_route}</p>
    <p><strong>Current effective decision:</strong> {audit.review_state.effective_priority} → {audit.review_state.effective_route}; {audit.review_state.review_status}, version {audit.review_state.decision_version}</p>
    <ol className="audit-timeline"><li><strong>System decision</strong> — rules <code>{original.rule_output.matched_rules.join(', ')}</code><br /><time dateTime={original.processed_at}>{original.processed_at}</time></li>
      {events.map(e => <li key={`${e.kind}-${e.id}`}><strong>{e.kind} #{e.id}</strong> — {e.reviewer_id}<br /><time dateTime={e.created_at}>{e.created_at}</time><p>{e.text}</p></li>)}
    </ol>
    {events.some(e => e.event_sequence == null) && <p className="muted small">Legacy actions lack a cross-action sequence. Equal timestamps use stable type/ID order; their actual relative order is unknown.</p>}
  </div>
}
