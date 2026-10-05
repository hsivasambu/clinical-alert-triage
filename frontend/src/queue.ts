import { PRIORITIES, type TriageResult } from './types'
export interface QueueFilters { search: string; priority: string; status: string; sort: string }
export const DEFAULT_QUEUE_FILTERS: QueueFilters = { search: '', priority: '', status: '', sort: 'severity' }
export function filterQueue(results: TriageResult[], filters: QueueFilters) {
  const query = filters.search.trim().toLowerCase()
  const priority = (r: TriageResult) => r.review_state?.effective_priority ?? r.final_priority
  const timestamp = (r: TriageResult) => Date.parse(r.alert.timestamp) || 0
  return results.filter(r => (!query || [r.alert_id, r.alert.patient_id, r.alert.unit].some(value => value.toLowerCase().includes(query)))
    && (!filters.priority || priority(r) === filters.priority)
    && (!filters.status || (r.review_state?.review_status ?? 'unreviewed') === filters.status))
    .sort((a, b) => (filters.sort === 'severity' ? PRIORITIES.indexOf(priority(a)) - PRIORITIES.indexOf(priority(b)) : 0)
      || timestamp(b) - timestamp(a) || (a.alert_id < b.alert_id ? -1 : a.alert_id > b.alert_id ? 1 : 0))
}
// IDs and observed timestamps from the repository sample_data fixtures.
const FIXTURE_TIMES: Record<string, string> = {"EDGE-AMB-001": "2026-04-19T01:14:00Z", "EDGE-CRIT-001": "2026-04-19T01:10:00Z", "EDGE-NOISE-001": "2026-04-19T01:18:00Z", "ALERT-005": "2024-04-14T13:45:00Z", "ALERT-003": "2024-04-14T10:05:00Z", "ALERT-002": "2024-04-14T08:32:00Z", "ALERT-004": "2024-04-14T11:20:00Z", "ALERT-006": "2024-04-14T14:10:00Z", "ALERT-101": "2024-04-14T14:10:00Z", "ALERT-001": "2024-04-14T08:32:00Z"}
export function isHistoricalFixture(r: TriageResult) { return Date.parse(FIXTURE_TIMES[r.alert_id]) === Date.parse(r.alert.timestamp) }
export function alertAge(timestamp: string, now: number) {
  const minutes = Math.floor((now - Date.parse(timestamp)) / 60000)
  if (!Number.isFinite(minutes)) return 'Unknown time'
  if (minutes < 0) return 'Future timestamp'
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h`
  return `${Math.floor(minutes / 1440)}d`
}
