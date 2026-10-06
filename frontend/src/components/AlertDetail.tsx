import { GenerationDetails } from './GenerationDetails'
import { fallbackLabel } from '../fallbackLabels'
import { ALERT_TYPE_LABELS } from '../simulator/presets'
import { isHistoricalFixture } from '../queue'
import { VITAL_LABELS } from '../observations'
import type { AlertAudit, ExplanationOutput, TriageResult } from '../types'
import { ExplanationPanel } from './ExplanationPanel'
import { HumanReview } from './HumanReview'
import { About, Output } from './Callouts'
// Says in the header whether the AI context review changed the rules decision.
export function AIDecisionNote({ explanation }: { explanation: ExplanationOutput }) {
  const a = explanation.ai_adjustment
  if (a?.status === 'applied') return <div className="ai-decision-note"><Output kind="ai" title="AI changed this decision">
    <p className="decision-line">Rules: <span className={`badge priority-${a.baseline_priority.toLowerCase()}`}>{a.baseline_priority}</span> → AI-supported: <span className={`badge priority-${a.applied_priority.toLowerCase()}`}>{a.applied_priority}</span></p>
    <p>{a.reason}</p></Output></div>
  if (a?.status === 'declined') return <p className="ai-decision-note muted small">The AI proposed {a.proposed_priority}, but it was not applied; the rules decision stands. See "AI escalation" below.</p>
  if (explanation.explanation_mode === 'hybrid') return <p className="ai-decision-note muted small">The AI reviewed the patient context and proposed no change to the rules decision.</p>
  return null
}
interface Props { result: TriageResult; audit: AlertAudit | null; reviewerId: string; onReviewerIdChange: (id: string) => void; onAuditUpdate: (audit: AlertAudit) => void }
export function AlertDetail({ result, audit, reviewerId, onReviewerIdChange, onAuditUpdate }: Props) {
  const { alert, rule_output, explanation, final_priority, final_route } = result
  const review = audit?.review_state ?? result.review_state
  const priority = review?.effective_priority ?? final_priority
  const route = review?.effective_route ?? final_route
  const humanChanged = (review?.decision_version ?? 0) > 0
  return <article className="alert-detail">
    <header className="decision-header panel">
      <div className="section-heading"><div><p className="eyebrow">{humanChanged ? 'Current human decision' : explanation.ai_adjustment?.status === 'applied' ? 'System decision · AI-supported escalation' : 'System decision · deterministic rules'}</p><h2>{ALERT_TYPE_LABELS[alert.alert_type]}</h2></div><a className="button" href="#human-review">Review alert ↓</a></div>
      <p className="muted small">Alert {alert.alert_id} · Patient {alert.patient_id} · {alert.unit}</p>
      <p className="muted small">Alert time: {new Date(alert.timestamp).toLocaleString()}{isHistoricalFixture(result) ? ' · Fixed historical fixture' : ''} · Processing time: {new Date(result.processed_at).toLocaleString()}</p>
      <div className="decision-line"><span className={`badge priority-${priority.toLowerCase()}`}>{priority}</span><strong>{route}</strong><span className="badge">{review?.review_status ?? 'unreviewed'}</span></div>
      <AIDecisionNote explanation={explanation} />
      {humanChanged && <p className="original-decision small">Original system decision: <strong>{final_priority}</strong> → {final_route}. Human version {review?.decision_version}.</p>}
    </header>
    <ExplanationPanel explanation={explanation} ruleOutput={rule_output} finalPriority={final_priority} finalRoute={final_route} alert={alert} />
    <HumanReview result={result} audit={audit} reviewerId={reviewerId} onReviewerIdChange={onReviewerIdChange} onAuditUpdate={onAuditUpdate} />
    <div className="details-stack">
      <details className="panel disclosure"><summary>Source metadata <span className="muted small">Observed input</span></summary><dl className="metadata">
        <Row label="Alert ID" value={alert.alert_id} /><Row label="Source system" value={alert.source_system} /><Row label="Patient" value={alert.patient_id} /><Row label="Unit" value={alert.unit} />
        <Row label="Room / bed" value={[alert.room, alert.bed].filter(Boolean).join(' / ') || 'Not provided'} /><Row label="Alert time" value={new Date(alert.timestamp).toLocaleString()} /><Row label="Device" value={alert.device_type ?? 'Not provided'} /><Row label="Source message" value={alert.message_text ?? 'Not provided'} />
      </dl></details>
      <details className="panel disclosure"><summary>Full context <span className="muted small">Observed input</span></summary>
        <h3>Vital signs</h3><dl className="metadata">{Object.entries(alert.vital_signs).map(([key, value]) => <Row key={key} label={VITAL_LABELS[key]?.[0] ?? key} value={value == null ? 'Not provided' : `${value} ${VITAL_LABELS[key]?.[1] ?? ''}`} />)}</dl>
        <h3>Recent context</h3><dl className="metadata"><Row label="Repeat count" value={String(alert.repeat_count)} />{Object.entries(alert.recent_context).map(([key, value]) => <Row key={key} label={key.replace(/_/g, ' ')} value={value == null ? 'Not provided' : Array.isArray(value) ? value.join(', ') || 'None provided' : String(value)} />)}</dl>
        <h3>Additional context</h3>{Object.keys(alert.additional_context).length ? <pre>{JSON.stringify(alert.additional_context, null, 2)}</pre> : <p className="muted">None provided.</p>}
      </details>
      <details className="panel disclosure"><summary>Technical details <span className="muted small">Rules & provenance</span></summary><dl className="metadata">
        <Row label="Original system priority" value={final_priority} /><Row label="Original system route" value={final_route} /><Row label="Baseline priority" value={rule_output.baseline_priority} /><Row label="Rule suggested route" value={rule_output.suggested_route} /><Row label="Manual demo rule weight" value={rule_output.rule_confidence.toFixed(2)} /><Row label="Explanation mode" value={explanation.explanation_mode} /><Row label="AI escalation" value={explanation.ai_adjustment ? `${explanation.ai_adjustment.status}: proposed ${explanation.ai_adjustment.proposed_priority}, final ${explanation.ai_adjustment.applied_priority}` : 'None proposed'} /><Row label="Rules-only reason" value={explanation.explanation_mode === 'rules_only' ? fallbackLabel(explanation.fallback_reason) : 'Not applicable: recorded AI narrative'} /><Row label="Explanation version" value={explanation.explanation_version ?? 'Not recorded'} /><Row label="Self-reported explanation estimate (capped)" value={explanation.llm_confidence_estimate?.toFixed(2) ?? 'Not available'} /><Row label="Processing time" value={new Date(result.processed_at).toLocaleString()} /><Row label="Matched rule IDs" value={rule_output.matched_rules.join(', ') || 'No matched rules returned'} />
      </dl><About>Rule weights are manually assigned demo metadata, not measured clinical reliability.</About><GenerationDetails provenance={result.provenance} /></details>
    </div>
  </article>
}
function Row({ label, value }: { label: string; value: string }) { return <><dt>{label}</dt><dd>{value}</dd></> }
