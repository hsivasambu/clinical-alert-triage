import { describe, expect, it } from 'vitest'
import fixture from '../e2e/alert.json'
import { DEFAULT_QUEUE_FILTERS, filterQueue, alertAge, isHistoricalFixture } from './queue'
import type { TriageResult } from './types'
const make = (id: string, priority: 'High' | 'Critical', timestamp: string, status: 'accepted' | 'unreviewed' = 'unreviewed'): TriageResult => ({
  ...fixture as TriageResult, alert_id: id, alert: { ...fixture.alert as TriageResult['alert'], alert_id: id, timestamp, patient_id: 'PAT-42', unit: 'North' },
  final_priority: 'High', review_state: { effective_priority: priority, effective_route: 'Demo', decision_version: 1, review_status: status },
})
const items = [make('Z', 'High', '2025-02-01T00:00:00Z'), make('B', 'Critical', '2025-01-01T00:00:00Z'), make('A', 'Critical', '2025-01-01T00:00:00Z', 'accepted')]
describe('queue ordering and filters', () => {
  it('sorts effective severity, alert time, then ID without mutating input', () => {
    expect(filterQueue(items, DEFAULT_QUEUE_FILTERS).map(r => r.alert_id)).toEqual(['A', 'B', 'Z'])
    expect(filterQueue(items, { ...DEFAULT_QUEUE_FILTERS, sort: 'newest' }).map(r => r.alert_id)).toEqual(['Z', 'A', 'B'])
    expect(items[0].alert_id).toBe('Z')
  })
  it('combines case-insensitive IDs/unit search with effective priority and current status', () => {
    for (const search of [' pat-42 ', 'north', 'a']) expect(filterQueue(items, { ...DEFAULT_QUEUE_FILTERS, search, priority: 'Critical', status: 'accepted' }).map(r => r.alert_id)).toEqual(['A'])
    expect(filterQueue(items, { ...DEFAULT_QUEUE_FILTERS, search: 'unknown' })).toEqual([])
  })
  it('labels known fixed fixtures and handles invalid/future age', () => {
    expect(isHistoricalFixture({ ...items[0], alert_id: 'ALERT-001', alert: { ...items[0].alert, timestamp: '2024-04-14T08:32:00Z' } })).toBe(true)
    expect(alertAge('invalid', Date.now())).toBe('Unknown time')
    expect(alertAge('2026-01-01', Date.parse('2025-01-01'))).toBe('Future timestamp')
  })
})
