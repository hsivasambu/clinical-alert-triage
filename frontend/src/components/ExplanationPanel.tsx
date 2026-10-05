import { fallbackLabel } from '../fallbackLabels'
import { VITAL_LABELS } from '../observations'
import type { AlertIn, ExplanationOutput, Priority, RuleOutput } from '../types'
import { ruleLabel } from '../ruleLabels'
interface Props { explanation: ExplanationOutput; ruleOutput: RuleOutput; finalPriority: Priority; finalRoute: string; alert: AlertIn }
export function ExplanationPanel({ explanation, ruleOutput, finalPriority, finalRoute, alert }: Props) {
  const ai = explanation.explanation_mode === 'hybrid'
  const evidenceLabel = (id: string) => explanation.rule_evidence?.find(item => item.rule_id === id)?.condition ?? ruleLabel(id)
  const missing = ruleOutput.missing_fields ?? []
  const noMatch = ruleOutput.matched_rules.includes('NO_RULE_MATCHED')
  const provenance = ai ? 'Recorded AI narrative' : 'Recorded system explanation'
  return <section className="panel explanation" aria-labelledby="explanation-heading">
    <div className="section-heading"><h3 id="explanation-heading">Why this decision?</h3><span className={`badge ${ai ? 'badge-ai' : ''}`}>{provenance}</span></div>
    <p className="muted small">Saved with the original system decision; selecting an alert does not generate a new explanation. Human changes are recorded separately.</p>
    {typeof alert.additional_context.local_demo === 'string' && <p className="notice"><strong>Local demonstration:</strong> {alert.additional_context.local_demo}</p>}
    {!ai && <p className="muted small fallback-label"><strong>Rules-only reason:</strong> {fallbackLabel(explanation.fallback_reason)}. Explanation uses recorded input and configured rules.</p>}
    {(noMatch || missing.length > 0) && <div className="notice" role="note">{noMatch && <p><strong>NO_RULE_MATCHED:</strong> the existing default is Low → Bedside Nurse (manual demo rule weight 0.5). This does not establish normality or safety.</p>}{missing.length > 0 && <p><strong>Insufficient data:</strong> {missing.join(', ')} not provided. Available-input rules still apply; absent values are not normal measurements.</p>}</div>}
    <section className="explanation-block"><h4>Summary <span className="provenance">{provenance}</span></h4><p className="summary-text">{explanation.summary || 'No summary was returned.'}</p></section>
    <section className="explanation-block"><h4>Triggering factors <span className="provenance">Deterministic rules</span></h4>
      {ruleOutput.matched_rules.filter(id => id !== 'NO_RULE_MATCHED').length ? <ul>{ruleOutput.matched_rules.filter(id => id !== 'NO_RULE_MATCHED').map((id) => <li key={id}>{evidenceLabel(id)}</li>)}</ul> : <p className="muted">No triggering rules were returned.</p>}
      {explanation.context_observations && explanation.context_observations.length > 0 && <div className="context-observations"><h5>Contextual observations <span className="provenance">Recorded input · not triggering rule evidence</span></h5><ul>{explanation.context_observations.map(o => <li key={o.evidence_id}><code>{o.evidence_id}</code> — {o.label}: <strong>{o.available ? typeof o.value === 'object' ? JSON.stringify(o.value) : String(o.value) : 'Not provided'} {o.available ? o.unit : ''}</strong></li>)}</ul></div>}
      {explanation.factors_considered.length > 0 && <><p className="provenance">{provenance} · commentary on referenced evidence</p><ul>{explanation.factors_considered.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
    </section>

    {explanation.llm_confidence_estimate != null && <p className="muted small">Self-reported explanation estimate: {explanation.llm_self_reported_confidence?.toFixed(2) ?? 'raw value not recorded (legacy)'}. Displayed estimate: {explanation.llm_confidence_estimate.toFixed(2)}. Deterministic cap: {explanation.confidence_cap?.toFixed(2) ?? 'not recorded'}. {explanation.confidence_cap_reason ?? 'Cap rationale not recorded.'} This is not calibrated clinical reliability.</p>}
    <section className="explanation-block"><h4>Routing rationale <span className="provenance">Deterministic output</span></h4>
      <p>The rules returned <strong>{ruleOutput.baseline_priority}</strong> with suggested destination <strong>{ruleOutput.suggested_route}</strong>. The system decision is <strong>{finalPriority}</strong> → <strong>{finalRoute}</strong>.</p>
      {explanation.rationale ? <div className="narrative"><span className="provenance">{provenance}</span><p>{explanation.rationale}</p></div> : <p className="muted small">No additional routing narrative was returned.</p>}
    </section>
    <section className="explanation-block"><h4>Uncertainty <span className="provenance">{provenance}</span></h4><div className="notice">{explanation.uncertainty_notes || 'No uncertainty notes were returned.'}</div></section>
    <section className="explanation-block"><h4>Rule evidence <span className="provenance">Observed input + rule trace</span></h4>
      <div className="observations"><span>Repeat count: <strong>{alert.repeat_count}</strong></span>{Object.entries(alert.vital_signs).map(([key, value]) => <span key={key}>{VITAL_LABELS[key]?.[0] ?? key}: <strong>{value == null ? 'Not provided' : `${value} ${VITAL_LABELS[key]?.[1] ?? ''}`} </strong></span>)}</div>
      {explanation.rule_trace.length ? <ul className="rule-evidence">{explanation.rule_trace.map((id) => <li key={id}><span>{evidenceLabel(id)}</span><code>{id}</code></li>)}</ul> : <p className="muted">No rule trace was returned.</p>}
    </section>
    <section className="explanation-block"><h4>Verification guidance <span className="provenance">{provenance}</span></h4>{explanation.recommended_checks.length ? <ol>{explanation.recommended_checks.map((item, i) => <li key={i}>{item}</li>)}</ol> : <p className="muted">No verification guidance was returned.</p>}</section>
  </section>
}
