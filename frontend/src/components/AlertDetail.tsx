import type { AlertAudit, TriageResult } from '../types'
import { ExplanationPanel } from './ExplanationPanel'
import { HumanReview } from './HumanReview'

interface Props {
  result: TriageResult
  audit: AlertAudit | null
  reviewerId: string
  onReviewerIdChange: (id: string) => void
  onAuditUpdate: (audit: AlertAudit) => void
}

export function AlertDetail({ result, audit, reviewerId, onReviewerIdChange, onAuditUpdate }: Props) {
  const { alert, rule_output, explanation, final_priority, final_route } = result
  const bloodPressure =
    alert.vital_signs.blood_pressure_systolic != null && alert.vital_signs.blood_pressure_diastolic != null
      ? `${alert.vital_signs.blood_pressure_systolic}/${alert.vital_signs.blood_pressure_diastolic} mmHg`
      : null

  return (
    <div style={{ fontSize: 14, lineHeight: 1.6 }}>
      <Section title="Alert">
        <Row label="ID" value={alert.alert_id} />
        <Row label="Type" value={alert.alert_type} />
        <Row label="Patient" value={alert.patient_id} />
        <Row label="Source system" value={alert.source_system} />
        <Row label="Unit" value={alert.unit} />
        {alert.room && <Row label="Room" value={alert.room} />}
        {alert.bed && <Row label="Bed" value={alert.bed} />}
        <Row label="Timestamp" value={new Date(alert.timestamp).toLocaleString()} />
        <Row label="Repeat count" value={String(alert.repeat_count)} />
        {alert.device_type && <Row label="Device type" value={alert.device_type} />}
        {alert.message_text && <Row label="Message" value={alert.message_text} />}
      </Section>

      <Section title="Vitals">
        {alert.vital_signs.heart_rate != null && <Row label="Heart rate" value={`${alert.vital_signs.heart_rate} bpm`} />}
        {alert.vital_signs.spo2 != null && <Row label="SpO2" value={`${alert.vital_signs.spo2}%`} />}
        {bloodPressure && <Row label="Blood pressure" value={bloodPressure} />}
        {alert.vital_signs.respiratory_rate != null && <Row label="Resp. rate" value={`${alert.vital_signs.respiratory_rate} /min`} />}
        {alert.vital_signs.temperature != null && <Row label="Temperature" value={`${alert.vital_signs.temperature} C`} />}
      </Section>

      <Section title="Recent Context">
        <Row label="Prior alerts (24h)" value={String(alert.recent_context.prior_alerts_24h)} />
        {alert.recent_context.fall_risk_score != null && (
          <Row label="Fall risk score" value={String(alert.recent_context.fall_risk_score)} />
        )}
        {alert.recent_context.admission_reason && (
          <Row label="Admission reason" value={alert.recent_context.admission_reason} />
        )}
        {alert.recent_context.code_status && <Row label="Code status" value={alert.recent_context.code_status} />}
        {alert.recent_context.recent_medications.length > 0 && (
          <ListRow label="Recent medications" items={alert.recent_context.recent_medications} />
        )}
      </Section>

      <Section title="Rules Engine Output">
        <Row label="Baseline priority" value={rule_output.baseline_priority} />
        <Row label="Suggested route" value={rule_output.suggested_route} />
        <Row label="Rule confidence" value={rule_output.rule_confidence.toFixed(2)} />
        <ListRow label="Matched rules" items={rule_output.matched_rules} monospace />
      </Section>

      <Section title="Final Decision">
        <Row label="Final priority" value={final_priority} />
        <Row label="Final route" value={final_route} />
        <Row label="Explanation mode" value={explanation.explanation_mode} />
      </Section>

      <ExplanationPanel
        explanation={explanation}
        ruleOutput={rule_output}
        finalPriority={final_priority}
        finalRoute={final_route}
      />

      <HumanReview
        result={result}
        audit={audit}
        reviewerId={reviewerId}
        onReviewerIdChange={onReviewerIdChange}
        onAuditUpdate={onAuditUpdate}
      />
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: 13, textTransform: 'uppercase', color: '#555', letterSpacing: 1 }}>
        {title}
      </h3>
      <div style={{ background: '#fafafa', border: '1px solid #eee', borderRadius: 6, padding: '10px 14px' }}>
        {children}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 4 }}>
      <span style={{ color: '#666', minWidth: 140 }}>{label}:</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function ListRow({ label, items, monospace = false }: { label: string; items: string[]; monospace?: boolean }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ color: '#666', marginBottom: 4 }}>{label}:</div>
      {items.length > 0 ? (
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {items.map((item) => (
            <li key={item} style={{ fontFamily: monospace ? 'monospace' : undefined }}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <span style={{ color: '#999', fontStyle: 'italic' }}>None</span>
      )}
    </div>
  )
}
