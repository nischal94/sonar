import { defineConfig, devices } from "@playwright/test";

/**
 * Sonar E2E Playwright config.
 *
 * Runs against a live stack:
 *   - Backend: http://localhost:8000 (docker compose up -d api postgres redis)
 *   - Frontend: http://localhost:5173 (docker compose up -d frontend, or `npm run dev` from frontend/)
 *
 * Local:     `cd e2e && npm test`
 * CI:        see .github/workflows/e2e.yml
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // backend tests have shared state; run serially until we have per-test isolation
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // ditto — shared DB state
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.SONAR_FRONTEND_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // No webServer config — the stack is brought up externally (docker compose +
  // npm run dev in CI). Keeping config-level concerns and infra concerns
  // separate makes local/CI parity easier to reason about.
});
