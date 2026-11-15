import { defineConfig, devices } from "@playwright/test";

const PORT = 8765;

/**
 * End-to-end tests drive the real built app against the real API server running with the simulated Valkyrie
 * (no credentials, no network, no cost). Build first: `npm run build`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    viewport: { width: 1360, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1360, height: 900 } } }],
  webServer: {
    command: `uv run python -m rb_server --fake --port ${PORT}`,
    cwd: "..",
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 90_000,
    // A throw-away result cache and arena database, both recreated before every run (see e2e/global-setup.ts), so the
    // tests start from the same state and never touch the team's real arena.
    env: { ROYALEBENCH_CACHE_DIR: "runs/evals-e2e", ROYALEBENCH_ARENA_DB: "runs/e2e-arena/arena.db" },
  },
});
