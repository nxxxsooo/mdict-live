import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  timeout: 30_000,
  expect: { timeout: 6_000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4180/app/',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4180',
    url: 'http://127.0.0.1:4180/app/',
    reuseExistingServer: true,
  },
})
