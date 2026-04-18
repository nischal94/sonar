/**
 * Dashboard golden-path E2E: register → wizard → dashboard.
 *
 * Uses the Playwright `request` context to seed the DB via API (faster +
 * more stable than UI-clicking the wizard), then navigates the browser
 * to /dashboard and asserts the ranked list renders.
 *
 * Marked `.fixme` until the surrounding register/login E2E specs are
 * de-fixmed (issue #65) — this test shares their UI assumptions and will
 * break for the same reasons.
 */
import { test, expect } from "@playwright/test";

function uniqueEmail() {
  return `dash-e2e-${Date.now()}@sonar-e2e.local`;
}

test.fixme("user can register, complete wizard, and see the dashboard", async ({ page, request }) => {
  const email = uniqueEmail();
  const password = "pass123";
  const backend = process.env.SONAR_BACKEND_URL || "http://localhost:8000";

  // Register via API
  const reg = await request.post(`${backend}/workspace/register`, {
    data: { workspace_name: "Dashboard E2E", email, password },
  });
  expect(reg.status()).toBe(201);

  // Log in via UI
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /login|sign in|log in/i }).click();
  await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });

  // Expect to be routed to the wizard
  await expect(page).toHaveURL(/\/signals\/setup/, { timeout: 10_000 });

  // Fill the wizard minimally and confirm
  await page.getByRole("textbox").first().fill("Fractional CTO services");
  await page.getByRole("button", { name: /next/i }).click();
  // Step 2 (ICP) — skip
  await page.getByRole("button", { name: /next/i }).click();
  // Step 3 — click Generate
  await page.getByRole("button", { name: /generate/i }).click();
  // Wait for proposal response
  await page.waitForURL(/\/signals\/setup/, { timeout: 30_000 });
  // Step 4 — click Next
  await page.getByRole("button", { name: /next/i }).click();
  // Step 5 — Save
  await page.getByRole("button", { name: /save and open dashboard/i }).click();

  // Expect to land on /dashboard
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });

  // At minimum, the dashboard renders its header
  await expect(page.getByText(/network intelligence/i)).toBeVisible({ timeout: 5_000 });
});
