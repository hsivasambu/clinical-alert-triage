import type {
  AcceptanceRecord,
  AlertAudit,
  AlertIn,
  AuditLogEntry,
  FeedbackIn,
  FeedbackRecord,
  OverrideIn,
  OverrideRecord,
  TriageResult,
} from '../types'

// Locally: VITE_API_URL is unset → Vite proxy forwards to localhost:8000
// Deployed: VITE_API_URL=https://your-app.onrender.com set in Vercel env vars
const BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // Alert triage
  triageAlert: (alert: AlertIn) =>
    request<TriageResult>('/alerts', { method: 'POST', body: JSON.stringify(alert) }),
  listAlerts: () => request<TriageResult[]>('/alerts'),
  getAlert: (alertId: string) => request<TriageResult>(`/alerts/${alertId}`),

  // Human review
  acceptAlert: (alertId: string, reviewerId: string) =>
    request<AcceptanceRecord>(`/alerts/${alertId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId }),
    }),

  submitOverride: (alertId: string, body: OverrideIn) =>
    request<OverrideRecord>(`/alerts/${alertId}/override`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  submitFeedback: (alertId: string, body: FeedbackIn) =>
    request<FeedbackRecord>(`/alerts/${alertId}/feedback`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getAlertAudit: (alertId: string) =>
    request<AlertAudit>(`/alerts/${alertId}/audit`),

  // Audit log
  listAuditLog: (params?: {
    limit?: number
    alert_type?: string
    final_priority?: string
    explanation_mode?: string
    overridden_only?: boolean
  }) => {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.alert_type) qs.set('alert_type', params.alert_type)
    if (params?.final_priority) qs.set('final_priority', params.final_priority)
    if (params?.explanation_mode) qs.set('explanation_mode', params.explanation_mode)
    if (params?.overridden_only) qs.set('overridden_only', 'true')
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<AuditLogEntry[]>(`/audit${suffix}`)
  },
}
