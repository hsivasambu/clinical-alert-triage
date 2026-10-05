import { afterEach, expect, it, vi } from 'vitest'
import { api, READ_TIMEOUT_MS, WRITE_TIMEOUT_MS } from './client'
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
function stalledFetch() {
  const fetch = vi.fn((_url, init: RequestInit) => new Promise((_resolve, reject) => {
    init.signal!.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }))
  vi.stubGlobal('fetch', fetch); return fetch
}
it('times out stalled reads without leaving timers or retrying inside the API client', async () => {
  vi.useFakeTimers(); const fetch = stalledFetch()
  const assertion = expect(api.listAlerts()).rejects.toThrow('Request timed out')
  await vi.advanceTimersByTimeAsync(READ_TIMEOUT_MS); await assertion
  expect(fetch).toHaveBeenCalledTimes(1); expect(vi.getTimerCount()).toBe(0)
})
it('warns that a timed-out mutation may have committed and never retries it automatically', async () => {
  vi.useFakeTimers(); const fetch = stalledFetch()
  const assertion = expect(api.acceptAlert('EXAMPLE', 'Synthetic reviewer', 0)).rejects.toThrow('action may have been saved')
  await vi.advanceTimersByTimeAsync(WRITE_TIMEOUT_MS); await assertion
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('carries the readiness header while preserving the array response contract', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]', { headers: { 'X-Demo-State': 'initializing', 'Content-Type': 'application/json' } })))
  const result = await api.listAlerts()
  expect(result).toHaveLength(0); expect(result.demoState).toBe('initializing')
})
