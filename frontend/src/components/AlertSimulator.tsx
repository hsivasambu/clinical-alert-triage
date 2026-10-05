import { useState } from 'react'
import { api } from '../api/client'
import type { AlertType, TriageResult } from '../types'
import { buildAlert, generateAlertId } from '../simulator/buildAlert'
import { ALERT_TYPE_LABELS, PRESETS, type PresetFields } from '../simulator/presets'

interface FormState extends PresetFields {
  alert_id: string
  timestamp: string
}

interface Props {
  onResult: (result: TriageResult) => void
  onClose: () => void
}

const ALERT_TYPES: AlertType[] = ['tachycardia', 'low_spo2', 'infusion_pump', 'nurse_call', 'fall_risk', 'sepsis']

function nowLocalDatetime(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

function buildDefaultForm(type: AlertType): FormState {
  return {
    ...PRESETS[type],
    alert_id: generateAlertId(),
    timestamp: nowLocalDatetime(),
  }
}

function validateForm(form: FormState): string | null {
  if (!form.alert_id.trim()) return 'Alert ID is required.'
  if (!form.patient_id.trim()) return 'Patient ID is required.'
  if (!form.unit.trim()) return 'Unit is required.'
  if (form.additional_context.trim()) {
    try {
      const parsed = JSON.parse(form.additional_context)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        return 'Additional context must be a JSON object.'
      }
    } catch {
      return 'Additional context must be valid JSON.'
    }
  }
  return null
}

export function AlertSimulator({ onResult, onClose }: Props) {
  const [form, setForm] = useState<FormState>(() => buildDefaultForm('tachycardia'))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function applyPreset(type: AlertType) {
    setForm((prev) => ({
      ...buildDefaultForm(type),
      alert_id: prev.alert_id,
    }))
    setError(null)
  }

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit() {
    const validationError = validateForm(form)
    if (validationError) {
      setError(validationError)
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const alert = buildAlert(form)
      const result = await api.triageAlert(alert)
      onResult(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submission failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="simulator-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="simulator-modal">
        <div className="simulator-modal-header">
          <div>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Alert Simulator</span>
            <span style={{ marginLeft: 10, fontSize: 12, color: '#90caf9', background: '#1a4a7a', padding: '2px 8px', borderRadius: 4 }}>
              Rules are decision authority | LLM is explainability only
            </span>
          </div>
          <button onClick={onClose} className="simulator-close-btn" aria-label="Close">x</button>
        </div>

        <div className="simulator-modal-body">
          <div style={{ marginBottom: 20 }}>
            <label className="simulator-section-label">Quick Presets</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {ALERT_TYPES.map((type) => (
                <button
                  key={type}
                  onClick={() => applyPreset(type)}
                  className="simulator-preset-btn" style={{
                    background: form.alert_type === type ? '#1a3a5c' : '#eef2f7',
                    color: form.alert_type === type ? 'white' : '#333',
                    borderColor: form.alert_type === type ? '#1a3a5c' : '#ccd',
                  }}
                >
                  {ALERT_TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          <FormSection title="Alert Identity">
            <FieldRow>
              <Field label="Alert ID *" hint="Auto-generated; must be unique">
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    className="simulator-input" style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }}
                    value={form.alert_id}
                    onChange={(e) => set('alert_id', e.target.value)}
                  />
                  <button
                    onClick={() => set('alert_id', generateAlertId())}
                    className="simulator-secondary-btn"
                    title="Regenerate ID"
                  >
                    Reroll
                  </button>
                </div>
              </Field>
              <Field label="Alert Type *">
                <select
                  className="simulator-input"
                  value={form.alert_type}
                  onChange={(e) => {
                    const t = e.target.value as AlertType
                    setForm((prev) => ({ ...prev, alert_type: t, message_text: PRESETS[t].message_text }))
                  }}
                >
                  {ALERT_TYPES.map((t) => (
                    <option key={t} value={t}>{ALERT_TYPE_LABELS[t]}</option>
                  ))}
                </select>
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Patient ID *">
                <input className="simulator-input" value={form.patient_id} onChange={(e) => set('patient_id', e.target.value)} />
              </Field>
              <Field label="Source System">
                <input className="simulator-input" value={form.source_system} onChange={(e) => set('source_system', e.target.value)} />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Unit *">
                <input className="simulator-input" value={form.unit} onChange={(e) => set('unit', e.target.value)} />
              </Field>
              <Field label="Room">
                <input className="simulator-input" value={form.room} onChange={(e) => set('room', e.target.value)} />
              </Field>
              <Field label="Bed">
                <input className="simulator-input" value={form.bed} onChange={(e) => set('bed', e.target.value)} />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Timestamp">
                <input
                  className="simulator-input"
                  type="datetime-local"
                  value={form.timestamp}
                  onChange={(e) => set('timestamp', e.target.value)}
                />
              </Field>
              <Field label="Repeat Count" hint=">=3 triggers escalation for most alert types">
                <input
                  className="simulator-input"
                  type="number"
                  min="0"
                  value={form.repeat_count}
                  onChange={(e) => set('repeat_count', e.target.value)}
                />
              </Field>
            </FieldRow>

            <FieldRow>
              <Field label="Device Type">
                <input className="simulator-input" value={form.device_type} onChange={(e) => set('device_type', e.target.value)} />
              </Field>
              <Field label="Message Text">
                <input className="simulator-input" value={form.message_text} onChange={(e) => set('message_text', e.target.value)} />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Vital Signs">
            <FieldRow>
              <Field label="Heart Rate (bpm)">
                <input className="simulator-input" type="number" value={form.heart_rate} onChange={(e) => set('heart_rate', e.target.value)} placeholder="e.g. 95" />
              </Field>
              <Field label="SpO2 (%)">
                <input className="simulator-input" type="number" value={form.spo2} onChange={(e) => set('spo2', e.target.value)} placeholder="e.g. 97" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="BP Systolic (mmHg)">
                <input className="simulator-input" type="number" value={form.blood_pressure_systolic} onChange={(e) => set('blood_pressure_systolic', e.target.value)} placeholder="e.g. 120" />
              </Field>
              <Field label="BP Diastolic (mmHg)">
                <input className="simulator-input" type="number" value={form.blood_pressure_diastolic} onChange={(e) => set('blood_pressure_diastolic', e.target.value)} placeholder="e.g. 80" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Respiratory Rate (/min)">
                <input className="simulator-input" type="number" value={form.respiratory_rate} onChange={(e) => set('respiratory_rate', e.target.value)} placeholder="e.g. 16" />
              </Field>
              <Field label="Temperature (C)">
                <input className="simulator-input" type="number" step="0.1" value={form.temperature} onChange={(e) => set('temperature', e.target.value)} placeholder="e.g. 37.0" />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Clinical Context">
            <FieldRow>
              <Field label="Prior Alerts (24h)">
                <input className="simulator-input" type="number" min="0" value={form.prior_alerts_24h} onChange={(e) => set('prior_alerts_24h', e.target.value)} />
              </Field>
              <Field label="Fall Risk Score" hint="Morse scale; >=45 = high risk">
                <input className="simulator-input" type="number" min="0" max="125" value={form.fall_risk_score} onChange={(e) => set('fall_risk_score', e.target.value)} placeholder="0-125" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Admission Reason">
                <input className="simulator-input" value={form.admission_reason} onChange={(e) => set('admission_reason', e.target.value)} />
              </Field>
              <Field label="Code Status">
                <input className="simulator-input" value={form.code_status} onChange={(e) => set('code_status', e.target.value)} placeholder="e.g. Full, DNR" />
              </Field>
            </FieldRow>
            <FieldRow>
              <Field label="Recent Medications" hint="Comma-separated">
                <input
                  className="simulator-input"
                  value={form.recent_medications}
                  onChange={(e) => set('recent_medications', e.target.value)}
                  placeholder="e.g. metoprolol, furosemide"
                />
              </Field>
            </FieldRow>
          </FormSection>

          <FormSection title="Additional Context (optional JSON)">
            <textarea
              className="simulator-input" style={{ width: '100%', minHeight: 80, fontFamily: 'monospace', fontSize: 12, resize: 'vertical', boxSizing: 'border-box' }}
              value={form.additional_context}
              onChange={(e) => set('additional_context', e.target.value)}
              placeholder={'{\n  "key": "value"\n}'}
              spellCheck={false}
            />
          </FormSection>
        </div>

        <div className="simulator-modal-footer">
          {error && (
            <div style={{ flex: 1, color: '#c0392b', fontSize: 13, background: '#fdf2f2', border: '1px solid #f5c6c6', borderRadius: 4, padding: '6px 10px' }}>
              {error}
            </div>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            <button onClick={onClose} className="simulator-cancel-btn" disabled={submitting}>Cancel</button>
            <button onClick={handleSubmit} className="simulator-submit-btn" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit Alert'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, color: '#666', marginBottom: 8 }}>
        {title}
      </div>
      <div style={{ background: '#fafafa', border: '1px solid #e8e8e8', borderRadius: 6, padding: '12px 14px' }}>
        {children}
      </div>
    </div>
  )
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>{children}</div>
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ flex: 1, minWidth: 160 }}>
      <label style={{ display: 'block', fontSize: 12, color: '#555', marginBottom: 4, fontWeight: 500 }}>
        {label}
        {hint && <span style={{ color: '#999', fontWeight: 400, marginLeft: 5 }}>- {hint}</span>}
      </label>
      {children}
    </div>
  )
}
