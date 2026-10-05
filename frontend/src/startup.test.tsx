import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { api } from './api/client'
import type { AlertList } from './api/client'
vi.mock('./api/client', () => ({ api: { listAlerts: vi.fn(), getAlertAudit: vi.fn() } }))
const pending = (): AlertList => Object.assign([], { demoState: 'initializing' as const })
beforeEach(() => { vi.useFakeTimers(); vi.resetAllMocks() })
afterEach(() => { cleanup(); vi.useRealTimers() })
it('distinguishes initializing from ready-empty and polls until seeding finishes', async () => {
  vi.mocked(api.listAlerts).mockResolvedValueOnce(pending()).mockResolvedValueOnce(Object.assign([], { demoState: 'ready' as const }))
  render(<App />)
  await act(async () => { await Promise.resolve() })
  expect(screen.getByText(/Initializing demo alerts/)).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'No alerts yet' })).toBeNull()
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
  expect(screen.getByRole('heading', { name: 'No alerts yet' })).toBeTruthy()
  expect(screen.queryByText(/Initializing demo alerts/)).toBeNull()
  expect(api.listAlerts).toHaveBeenCalledTimes(2)
})
it('bounds initialization refresh to six reads and preserves the initializing state', async () => {
  vi.mocked(api.listAlerts).mockResolvedValue(pending())
  render(<App />)
  await act(async () => { await vi.advanceTimersByTimeAsync(30000) })
  expect(api.listAlerts).toHaveBeenCalledTimes(6)
  expect(screen.getByText(/Automatic refresh paused after six checks/)).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'No alerts yet' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Retry loading alerts' })).toBeTruthy()
})
it('bounds unavailable retries, never presents failure as empty, and cleans up timers', async () => {
  vi.mocked(api.listAlerts).mockRejectedValue(new Error('Service down'))
  const view = render(<App />)
  await act(async () => { await vi.advanceTimersByTimeAsync(30000) })
  expect(api.listAlerts).toHaveBeenCalledTimes(3)
  expect(screen.getByRole('alert').textContent).toContain('Service down')
  expect(screen.queryByRole('heading', { name: 'No alerts yet' })).toBeNull()
  view.unmount(); await vi.advanceTimersByTimeAsync(30000)
  expect(api.listAlerts).toHaveBeenCalledTimes(3)
})
