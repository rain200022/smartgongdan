import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:15173',
    actionTimeout: 10_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run python -m scripts.e2e_server',
      cwd: fileURLToPath(new URL('..', import.meta.url)),
      url: 'http://127.0.0.1:18000/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --port 15173',
      url: 'http://127.0.0.1:15173',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:18000' },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
