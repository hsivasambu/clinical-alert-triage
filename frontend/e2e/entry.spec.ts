import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const original = JSON.parse(readFileSync(new URL('./alert.json', import.meta.url), 'utf8'))

for (const width of [1440, 390]) {
  test(`first visit → prefilled example → recorded explanation → human review at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    let current: typeof original | null = null
    let postCount = 0
    let acceptance: Record<string, unknown> | null = null
    await page.route('**/alerts', async (route) => {
      if (route.request().method() === 'POST') {
        postCount++
        const input = route.request().postDataJSON()
        expect(input.alert_type).toBe('nurse_call')
        expect(input.repeat_count).toBe(3)
        expect(input.alert_id).toMatch(/^SIM-/)
        current = { ...structuredClone(original), alert_id: input.alert_id, alert: input,
          rule_output: { baseline_priority: 'Medium', matched_rules: ['NURSE_CALL_REPEAT_GTE_3'], suggested_route: 'Charge Nurse', rule_confidence: 0.9 },
          final_priority: 'Medium', final_route: 'Charge Nurse',
          explanation: { ...original.explanation, rule_trace: ['NURSE_CALL_REPEAT_GTE_3'] },
          review_state: { effective_priority: 'Medium', effective_route: 'Charge Nurse', decision_version: 0, review_status: 'unreviewed' } }
        await route.fulfill({ status: 201, json: current })
      } else await route.fulfill({ json: current ? [current] : [] })
    })
    await page.route('**/alerts/*/audit', (route) => route.fulfill({ json: {
      triage_result: current, review_state: current!.review_state, overrides: [], feedback: [], acceptances: acceptance ? [acceptance] : [],
    } }))
    await page.route('**/alerts/*/accept', async (route) => {
      const input = route.request().postDataJSON()
      expect(input).toEqual({ reviewer_id: 'Demo visitor', decision_version: 0 })
      current!.review_state.review_status = 'accepted'
      acceptance = { id: 1, alert_id: current!.alert_id, reviewer_id: input.reviewer_id, decision_version: 0,
        accepted_priority: current!.final_priority, accepted_route: current!.final_route, created_at: new Date().toISOString(), review_state: current!.review_state }
      await route.fulfill({ status: 201, json: acceptance })
    })
    await page.goto('/')
    await expect(page.getByText('Simulated data · Portfolio demo')).toBeVisible()
    await expect(page.getByText('Rules assign priority and routing.')).toBeVisible()
    await expect(page.getByRole('link', { name: /Repository/ })).toHaveAttribute('href', 'https://github.com/hsivasambu/clinical-alert-triage')
    await expect(page.getByRole('link', { name: /Project blog/ })).toHaveAttribute('href', 'https://blog.harry-sivasambu.com/blog/clinical-alert-triage')
    await expect(page.getByRole('heading', { name: 'No alerts yet' })).toBeVisible()
    await page.getByRole('combobox', { name: 'Try an example' }).selectOption('repeat')
    await expect(page.locator('#scenario-description')).toContainText('three repeats')
    await page.screenshot({ path: `test-results/entry-${width}.png`, fullPage: true })
    await page.getByRole('button', { name: 'Run example' }).click()
    await expect(page.getByRole('heading', { name: 'Why this decision?' })).toBeVisible()
    await expect(page.locator('.simulator-modal')).toHaveCount(0)
    await expect(page.locator('.decision-header')).toContainText('Medium')
    await expect(page.locator('.decision-header')).toContainText('Charge Nurse')
    await expect(page.locator('.explanation .badge')).toHaveText('Recorded system explanation')
    await expect(page.locator('.explanation')).toContainText('selecting an alert does not generate a new explanation')
    await expect(page.locator('.rule-evidence')).toContainText('Nurse call repeated ≥ 3 times')
    await page.getByRole('link', { name: 'Review alert' }).click()
    await page.getByLabel('Reviewer ID').fill('Demo visitor')
    await page.getByRole('button', { name: 'Accept Decision' }).click()
    await expect(page.getByRole('status')).toContainText('Decision accepted and logged.')
    await expect(page.locator('.decision-header')).toContainText('accepted')
    await page.reload()
    await expect(page.locator('.decision-header')).toContainText('accepted')
    await expect(page.locator('#human-review')).toContainText('Accepted by Demo visitor')
    expect(postCount).toBe(1)
    await page.getByRole('button', { name: 'Back to queue' }).click()
    await expect(page.getByRole('heading', { name: 'Alert Queue' })).toBeVisible()
    await page.getByRole('button', { name: 'Advanced customization' }).click()
    await expect(page.getByText('Alert Simulator', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  })
}

test('initial example selection leaves introduction focus alone and respects subsequent user selections', async ({ page }) => {
  const other = { ...structuredClone(original), alert_id: 'OTHER', alert: { ...original.alert, alert_id: 'OTHER', alert_type: 'nurse_call' } }
  await page.route('**/alerts', (route) => route.fulfill({ json: [other, original] }))
  await page.route('**/alerts/*/audit', (route) => {
    const selected = route.request().url().includes('/OTHER/') ? other : original
    return route.fulfill({ json: { triage_result: selected, review_state: selected.review_state, overrides: [], feedback: [], acceptances: [] } })
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: `View alert ${original.alert_id}` })).toHaveAttribute('aria-current', 'true')
  await expect(page.locator('.detail-pane')).not.toBeFocused()
  await page.getByRole('button', { name: 'View alert OTHER' }).click()
  await expect(page.getByRole('button', { name: 'View alert OTHER' })).toHaveAttribute('aria-current', 'true')
  await page.getByRole('button', { name: 'Back to queue' }).click()
  await expect(page.locator('.alert-detail')).toHaveCount(0)
})
