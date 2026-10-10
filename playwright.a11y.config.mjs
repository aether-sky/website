import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/accessibility',
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4389',
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    reducedMotion: 'reduce',
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm --filter personal-blog exec astro preview --host 127.0.0.1 --port 4389',
    url: 'http://127.0.0.1:4389',
    reuseExistingServer: false,
    timeout: 30000,
    env: { ASTRO_TELEMETRY_DISABLED: '1' },
  },
});
