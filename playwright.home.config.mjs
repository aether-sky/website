import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/home',
  outputDir: './home-test-results',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4397',
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 1000 },
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  webServer: [{
    command: 'node scripts/python.mjs services/home/server.py --static-dir apps/home/dist --blog-dir apps/blog/dist-site --port 4397',
    url: 'http://127.0.0.1:4397/health',
    reuseExistingServer: false,
    timeout: 15000,
  }, {
    command: 'node scripts/python.mjs tests/home/live_server.py',
    url: 'http://127.0.0.1:4398/health',
    reuseExistingServer: false,
    timeout: 15000,
  }],
});
