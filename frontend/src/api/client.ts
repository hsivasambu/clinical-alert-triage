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

export type DemoState = 'initializing' | 'ready' | 'unavailable'
export type AlertList = TriageResult[] & { demoState?: DemoState }
export const READ_TIMEOUT_MS = 10000
export const WRITE_TIMEOUT_MS = 25000

async function request<T>(path: string, init?: RequestInit, inspect?: (res: Response) => void): Promise<T> {
  const controller = new AbortController()
  const mutation = init?.method === 'POST'
  const timer = setTimeout(() => controller.abort(), mutation ? WRITE_TIMEOUT_MS : READ_TIMEOUT_MS)
  try {
    const res = await fetch(BASE + path, {
      headers: { 'Content-Type': 'application/json' }, ...init, signal: controller.signal,
    })
    inspect?.(res)
    if (!res.ok) {
      const body = await res.text()
      let detail = body
      try {
        const parsed = JSON.parse(body)
        if (Array.isArray(parsed.detail)) detail = parsed.detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.filter(part => part !== 'body').join('.')}: ${item.msg}`).join('; ')
        else if (typeof parsed.detail === 'string') detail = parsed.detail
      } catch { /* Non-JSON errors retain their response text. */ }
      throw new Error(`${res.status} ${res.statusText}: ${detail}`)
    }
    return await res.json() as T
  } catch (error) {
    if (controller.signal.aborted) throw new Error(mutation
      ? 'Request timed out. The action may have been saved. Reload the queue/history before retrying; do not submit it again automatically.'
      : 'Request timed out. The demo service is unavailable or still starting; retry loading.')
    throw error
  } finally { clearTimeout(timer) }
}

export const api = {
  // Alert triage
  triageAlert: (alert: AlertIn) =>
    request<TriageResult>('/alerts', { method: 'POST', body: JSON.stringify(alert) }),
  listAlerts: async (): Promise<AlertList> => {
    let demoState: DemoState = 'ready' // Compatibility with older servers.
    const alerts = await request<TriageResult[]>('/alerts', undefined, res => {
      const value = res.headers.get('X-Demo-State')
      if (value === 'initializing' || value === 'ready' || value === 'unavailable') demoState = value
    })
    return Object.assign(alerts, { demoState })
  },
  getAlert: (alertId: string) => request<TriageResult>(`/alerts/${alertId}`),

  // Human review
  acceptAlert: (alertId: string, reviewerId: string, decisionVersion?: number) =>
    request<AcceptanceRecord>(`/alerts/${alertId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId, decision_version: decisionVersion }),
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
