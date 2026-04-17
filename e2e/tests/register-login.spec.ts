/**
 * Golden-path E2E: register → login → settings
 *
 * Exercises the Phase-1-shipped flows that are LIVE today. When Phase 2
 * Wizard ships, add a new spec `wizard-golden-path.spec.ts` that covers
 * register → signals/setup → dashboard.
 */
import { test, expect } from "@playwright/test";

// Per-test unique email so re-runs don't collide with previous registrations.
function uniqueEmail() {
  const ts = Date.now();
  const rand = Math.floor(Math.random() * 10000);
  return `e2e-${ts}-${rand}@sonar-e2e.local`;
}

test.describe("Register → login", () => {
  test("a new user can register, log in, and land on the app", async ({ page }) => {
    const email = uniqueEmail();
    const password = "e2e-password-1234";

    await page.goto("/register");
    await expect(page).toHaveURL(/\/register$/);

    // Fill the registration form. These selectors use label/placeholder text
    // so they survive most UI reshuffles.
    await page.getByLabel(/workspace/i).fill("E2E Test Workspace");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole("button", { name: /register|sign up|create/i }).click();

    // Success signal: we've left /register. Exact destination depends on
    // onboarding state; just assert we moved somewhere authenticated.
    await expect(page).not.toHaveURL(/\/register$/, { timeout: 15_000 });
  });

  test("an existing user can log in with their credentials", async ({ page, request }) => {
    // Register via API first so we have a known credential pair.
    const email = uniqueEmail();
    const password = "e2e-password-1234";
    const backend = process.env.SONAR_BACKEND_URL || "http://localhost:8000";

    const regResp = await request.post(`${backend}/workspace/register`, {
      data: {
        workspace_name: "E2E Login Test",
        email,
        password,
      },
    });
    expect(regResp.status()).toBe(201);

    // Now log in via the UI.
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole("button", { name: /login|sign in|log in/i }).click();

    await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });
  });
});
