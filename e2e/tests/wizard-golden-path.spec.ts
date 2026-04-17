/**
 * Phase 2 Wizard golden-path E2E — PLACEHOLDER until Wizard ships.
 *
 * Once `/signals/setup` is implemented (Wizard plan Tasks 10-11), replace
 * the `.fixme` markers below with real test steps: a new user registers,
 * lands on /signals/setup, fills "what I sell", reviews proposed signals,
 * confirms, and lands on /dashboard with the expected signal rows visible.
 *
 * Kept in the suite so the intent is discoverable and the file doesn't have
 * to be created from scratch later.
 */
import { test, expect } from "@playwright/test";

test.describe("Phase 2 Wizard golden path (not shipped yet)", () => {
  test.fixme("new user completes wizard end-to-end in under 90 seconds", async ({ page }) => {
    // TODO(wizard): implement once /signals/setup ships (Wizard plan Task 10-11).
    // 1. POST /workspace/register (API, to skip auth UI fixtures)
    // 2. Log in
    // 3. Expect redirect to /signals/setup
    // 4. Fill "What do you sell?" textarea
    // 5. Click Next → ICP field
    // 6. Click Next → trigger LLM proposal
    // 7. Wait for proposed signals to render (8-10 cards)
    // 8. Accept all, click "Save and open dashboard"
    // 9. Expect URL /dashboard and at least 1 signal row visible
    expect(page).toBeTruthy();
  });

  test.fixme("wizard rejects empty what-you-sell input", async ({ page }) => {
    // TODO(wizard): input validation UX — the Next button should stay disabled
    // until the textarea has at least 5 characters.
    expect(page).toBeTruthy();
  });
});
