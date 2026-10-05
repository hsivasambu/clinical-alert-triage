import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const fixture = JSON.parse(readFileSync(new URL('./alert.json', import.meta.url), 'utf8'))
const result = fixture
const history = { triage_result: result, review_state: result.review_state, overrides: [], feedback: [], acceptances: [] }
for (const width of [1440, 1024, 768, 390, 320]) {
  test(`queue, explanation, long text and review controls at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const longResult = structuredClone(result)
    longResult.alert.unit = 'Simulated unit '.repeat(8)
    longResult.alert.message_text = 'Observed source message '.repeat(30)
    longResult.explanation.summary = result.explanation.summary.repeat(8)
    longResult.alert.additional_context = { long_input: 'x'.repeat(350) }
    longResult.explanation.rule_trace.push('UNKNOWN_LONG_RULE_' + 'X'.repeat(200))
    await page.route('**/alerts', (route) => route.fulfill({ json: [longResult] }))
    await page.route('**/alerts/*/audit', (route) => route.fulfill({ json: { ...history, triage_result: longResult } }))
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Why this decision?' })).toBeVisible()
    await page.getByRole('button', { name: 'Back to queue' }).click()
    await expect(page.getByRole('heading', { name: 'Alert Queue' })).toBeVisible()
    await expect(page.getByRole('button', { name: `View alert ${result.alert_id}` })).toBeVisible()
    await page.getByRole('button', { name: `View alert ${result.alert_id}` }).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Why this decision?' })).toBeVisible()
    await expect(page.locator('.detail-pane')).toBeFocused()
    if (width <= 760) {
      await expect(page.locator('.queue-pane')).toBeHidden()
      const bounds = await page.locator('.detail-pane').boundingBox()
      expect(bounds!.width).toBeGreaterThan(width - 40)
    } else {
      await expect(page.locator('.queue-pane')).toBeVisible()
      const queue = await page.locator('.queue-pane').boundingBox()
      const detail = await page.locator('.detail-pane').boundingBox()
      expect(queue!.x + queue!.width).toBeLessThanOrEqual(detail!.x)
    }
    const headings = await page.locator('.explanation h4').allTextContents()
    expect(headings).toHaveLength(6)
    const children = await page.locator('.alert-detail').evaluate((node) => Array.from(node.children).map((c) => c.className))
    expect(children[0]).toContain('decision-header')
    expect(children[1]).toContain('explanation')
    await expect(page.locator('details[open]')).toHaveCount(0)
    await page.getByRole('link', { name: 'Review alert' }).click()
    await expect(page.getByLabel('Reviewer ID')).toBeVisible()
    await page.getByRole('button', { name: 'Override', exact: true }).click()
    await expect(page.getByLabel('New Priority')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Override', exact: false }).first()).toHaveAttribute('aria-expanded', 'true')
    await page.getByLabel('Clinical Reason').fill('Demonstration review '.repeat(25))
    for (const title of ['Source metadata', 'Full context', 'Technical details']) await page.locator('summary').filter({ hasText: title }).click()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    expect(overflow).toBe(false)
    await page.screenshot({ path: `test-results/layout-${width}.png`, fullPage: true })
    await page.getByRole('button', { name: 'Back to queue' }).click()
    await expect(page.getByRole('heading', { name: 'Alert Queue' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Alert Queue' })).toBeFocused()
  })
}
for (const width of [1440, 390]) {
  test(`empty, loading, failure and retry at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    let complete: () => void = () => {}
    const pending = new Promise<void>((resolve) => { complete = resolve })
    await page.route('**/alerts', async (route) => { await pending; await route.fulfill({ json: [] }) })
    await page.goto('/')
    await expect(page.getByRole('status')).toHaveText('Loading alerts…')
    complete()
    await expect(page.getByRole('heading', { name: 'No alerts yet' })).toBeVisible()
    await page.unroute('**/alerts')
    await page.route('**/alerts', (route) => route.fulfill({ status: 503, body: 'Unavailable' }))
    await page.reload()
    await expect(page.getByRole('alert')).toContainText('Could not load alerts')
    await page.unroute('**/alerts')
    await page.route('**/alerts', (route) => route.fulfill({ json: [result] }))
    await page.route('**/alerts/*/audit', (route) => route.fulfill({ status: 503, body: 'Unavailable' }))
    await page.getByRole('button', { name: 'Retry loading alerts' }).click()
    await expect(page.getByRole('alert')).toContainText('Review history could not be loaded')
    await expect(page.getByRole('button', { name: 'Accept Decision' })).toBeDisabled()
    await page.unroute('**/alerts/*/audit')
    await page.route('**/alerts/*/audit', (route) => route.fulfill({ json: history }))
    await page.getByRole('button', { name: 'Retry history' }).click()
    await expect(page.getByRole('button', { name: 'Accept Decision' })).toBeEnabled()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  })
}

test('AI narrative and human changes remain separate from the original system decision', async ({ page }) => {
  const reviewed = structuredClone(result)
  reviewed.review_state = { effective_priority: 'Low', effective_route: 'Charge Nurse', decision_version: 3, review_status: 'overridden' }
  reviewed.explanation.explanation_mode = 'hybrid'
  reviewed.explanation.rationale = 'Demonstration narrative returned by the explanation service.'
  reviewed.explanation.factors_considered = ['Demonstration factor returned by the explanation service.']
  reviewed.explanation.recommended_checks = ['Demonstration guidance returned by the explanation service.']
  await page.route('**/alerts', (route) => route.fulfill({ json: [reviewed] }))
  await page.route('**/alerts/*/audit', (route) => route.fulfill({ json: { ...history, review_state: reviewed.review_state } }))
  await page.goto('/')
  await page.getByRole('button', { name: `View alert ${result.alert_id}` }).click()
  await expect(page.locator('.decision-header')).toContainText('Current human decision')
  await expect(page.locator('.decision-header')).toContainText('Original system decision: High')
  await expect(page.locator('.explanation .badge')).toHaveText('Recorded AI narrative')
  await expect(page.locator('.explanation')).toContainText('The system decision is High')
  await expect(page.locator('.explanation')).not.toContainText('Charge Nurse')
})
