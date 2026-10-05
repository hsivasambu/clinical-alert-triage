import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './integration', outputDir: './playwright-results-integration', workers: 1,
  use: { baseURL: 'http://127.0.0.1:5175', channel: process.env.PLAYWRIGHT_BROWSER === 'chromium' ? undefined : 'msedge', headless: true },
  webServer: [
    { command: `"${process.env.DEMO_TEST_PYTHON ?? 'python'}" ../backend/e2e_server.py`, url: 'http://127.0.0.1:8011/ready', reuseExistingServer: false },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5175', url: 'http://127.0.0.1:5175', reuseExistingServer: false, env: { VITE_API_URL: 'http://127.0.0.1:8011' } },
  ],
})
