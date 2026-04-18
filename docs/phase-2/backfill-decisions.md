# Sonar Phase 2 Backfill — Implementation Decisions

**Date:** 2026-04-18
**Status:** Decisions locked, ready for implementation-plan generation
**Slice:** Phase 2 — Day-One Backfill (1st-degree profile scrape + instant dashboard population)
**Builds on:** Phase 2 Foundation (`Workspace.backfill_used` shipped PR #10) + Wizard + Dashboard
**Design spec:** `docs/phase-2/design.md §4.2`

Companion doc to the design spec. Captures implementation-level decisions made during the 2026-04-18 brainstorming session. `writing-plans` should treat both this file and `design.md §4.2` as input when generating `docs/phase-2/implementation-backfill.md`.

---

## 1. Scope (Option B — 1st-degree only)

**In scope:**

- Chrome extension captures user's 1st-degree connection list from `linkedin.com/mynetwork/invite-connect/connections/`
- `POST /extension/connections/bulk` — bulk upsert `Connection` rows
- `POST /workspace/backfill/trigger` — enqueues the `day_one_backfill` Celery task (enforces `Workspace.backfill_used = false`)
- Celery task `app/workers/day_one_backfill.py` runs a 1st-degree Apify scrape and dispatches posts into the existing pipeline
- `GET /workspace/backfill/status` — polling endpoint for the dashboard banner
- Completion email via existing `app/delivery/email.py` sender
- Schema additions on `Workspace`: `backfill_started_at`, `backfill_completed_at`, `backfill_profile_count`

**Out of scope (follow-up slices):**

- 2nd-degree ICP-filtered scrape — tracked via a research spike only (see Task outline). Apify actor availability is a "known unknown" per design.md §4.2.
- CSV upload fallback for users without the extension — extension is mandatory per Phase 1, and CSV's 15-30 min LinkedIn-email-export wait would itself be a friction problem
- User-facing retry-on-failure flow — backend Celery retries exist; retry UX is a later polish
- Per-connection profile enrichment beyond what the 1st-degree Apify scrape returns
- Opt-out for the completion email — single-user onboarding moment, not a recurring email that needs opt-out UX

**Rationale:**
The hypothesis Backfill needs to validate is *"does a populated day-one dashboard drive engagement?"* 1st-degree coverage alone is sufficient to test that — and 1st-degree is the "warm network" tier with highest outreach-conversion value regardless. 2nd-degree is an additive improvement once the hypothesis is validated. Mirrors the Scope-B pattern Wizard and Dashboard used.

---

## 2. Connection Capture (Option A — Chrome extension auto-capture)

**Chrome extension changes:**

- New content script `extension/src/capture-connections.ts`
- Runs on `https://www.linkedin.com/mynetwork/invite-connect/connections/*`
- New manifest permission: host permission for that URL pattern
- New popup button "Run day-one scan" — visible when `localStorage.backfillCompleted != true`
- Click flow:
  1. Opens/focuses the connections page tab (or directs user there if not open)
  2. Scrolls the virtualized list, extracts per-row `profile_url`, `name`, `headline`, `company`
  3. Batches into chunks of 100, POSTs each to `/extension/connections/bulk`
  4. After the last chunk succeeds, calls `POST /workspace/backfill/trigger`

**Failure modes visible to user:**

- DOM mismatch: popup shows "We couldn't read your connections — LinkedIn's page may have changed. We're on it." + POSTs telemetry to backend
- Network errors: retry 3x with exponential backoff, then fail visibly

**Why not CSV upload fallback (Option C):** extension is already mandatory per Phase 1 product design (`docs/phase-2/design.md §3`). A CSV fallback would create a permanent two-path system with ongoing maintenance cost for a user segment that doesn't exist. If the extension breaks, the right fix is a quick extension update, not a permanent parallel path.

---

## 3. UX During Backfill (Option D — async polling + completion email)

**Frontend:**

- Immediately after `backfill/trigger`, user lands on `/dashboard`
- Banner at top: *"Backfill in progress — your dashboard will populate as we process your network"*
- Dashboard polls `GET /workspace/backfill/status` every **5 seconds** while `state === "running"` (faster than the normal 30s)
- On `state` transition to `"done"` or `"failed"`, banner replaced:
  - Done: *"Backfill complete — you're seeing your full 60-day network snapshot"* (auto-dismiss after 10s)
  - Failed: *"Backfill didn't complete cleanly — signals will accumulate from here. Contact support if this persists."*

**Backend completion hook:**

- On task success, enqueue a completion email via `app/delivery/email.py`:
  - Subject: *"Your Sonar dashboard is ready"*
  - Body: one-paragraph welcome + `backfill_profile_count` processed + link to `/dashboard`
- Email failure does NOT mark backfill failed; just `logger.warning`

**Why polling + email (not either alone):** polling alone loses the user if they close the tab. Email alone loses the engagement moment while the user is still in onboarding. Together, the polling drives in-session delight and the email is a safety net for anyone who bounces.

---

## 4. Cost + Idempotency (Option B — 200 × 60 days)

**Caps:**

- Max 200 connections per workspace (most-recently-active per LinkedIn's default connection-page ordering)
- 60-day post-history window
- Expected cost per workspace: ~$0.40 via Apify

**Why 200/60 and not the spec's 500/90 (Option A):**
Pre-launch Sonar expects 10-30 dogfood backfills during the build phase (broken actors, bad fixtures, debugging). At the spec's $2 cap, that's $20-60 burned before shipping — tolerable but tighter budget means more iteration freedom. 200 connections is sufficient signal to test the day-one-dashboard hypothesis. Raising the cap later is a code change, not an architectural one.

**Rate limits (via existing slowapi):**

- `/extension/connections/bulk`: **5/hour per workspace** (token-keyed; legit users call once in 3 chunks)
- `/workspace/backfill/trigger`: **2/day per workspace** (single legitimate call; retries allowed for transient failures)

**Idempotency:**

- `POST /workspace/backfill/trigger` checks `Workspace.backfill_used` — if `true`, returns `409 Conflict` with `backfill_completed_at`
- Celery task sets `backfill_used = true` at start (not end) to prevent double-enqueue during retries
- On task failure, `backfill_used` remains true — manual admin flip needed to re-run (MVP trade-off; retry UX is follow-up)

---

## 5. Apify Actor Selection

**MVP plan:** Research + document before implementation. Task 1 of the plan is a 30-min research spike producing `docs/phase-2/backfill-apify-research.md` with 2-3 actor candidates (pricing, rate limits, output schema) and the MVP pick with justification.

Candidates known at this time:
- `apify/linkedin-profile-scraper` (official)
- `curious_coder/linkedin-profile-scraper` (3rd-party, popular)
- To be identified during research

**2nd-degree research (separate spike):** Produces `docs/phase-2/backfill-2nd-degree-research.md` listing candidate actors for ICP-filtered 2nd-degree search. Lives alongside Backfill work but doesn't gate the MVP — if no viable 2nd-degree actor exists, the research note says so and the follow-up slice is deferred.

---

## 6. Error Handling

### Partial Apify success (e.g., 127 of 200 profiles returned)

- Ingest what we got via the pipeline
- `logger.warning("backfill returned N/M profiles", extra={...})` with workspace_id + actor run id
- Mark backfill `completed` with actual `backfill_profile_count`
- Completion email reflects actual count

### Apify hard failure (no profiles / API error)

- Celery retries 3x with 60-second backoff
- On final failure: `state = "failed"`, `backfill_used = true` (prevents auto-retry loop)
- User sees the "didn't complete cleanly" banner
- Dashboard continues to populate via passive Phase 1 feed capture over time

### Extension DOM mismatch

- Content script validates expected selectors exist before scrolling
- On mismatch: POSTs telemetry `/telemetry/extension-error` with `kind=connections_dom_mismatch` + user-agent + URL
- Popup shows error; no connection data sent to backend

### Email send failure

- Log only. Dashboard already works; email is a nice-to-have at this point. Not a retry candidate.

---

## 7. Task Outline (~12-13 tasks, subject to `writing-plans` refinement)

1. Apify actor research spike → `docs/phase-2/backfill-apify-research.md` (30 min)
2. Alembic migration 005 — `Workspace.backfill_started_at`, `backfill_completed_at`, `backfill_profile_count` columns
3. Update `Workspace` ORM model + unit test
4. New Apify service wrapper `app/services/apify.py` — mocked-friendly, rate-limit-aware, type-safe response
5. Celery task `app/workers/day_one_backfill.py` + unit tests (mocked Apify responses)
6. `POST /extension/connections/bulk` endpoint — bulk upsert `Connection` rows, dedupe by `linkedin_id` + tests
7. `POST /workspace/backfill/trigger` endpoint + idempotency tests (409 on re-trigger)
8. `GET /workspace/backfill/status` endpoint + tests
9. Completion-email integration + test (mock `EmailSender`)
10. Chrome extension: new content script + popup button + manifest permission
11. Frontend: dashboard banner + 5s polling during backfill + Vitest tests
12. 2nd-degree research spike → `docs/phase-2/backfill-2nd-degree-research.md` (30 min)
13. TODO.md + CLAUDE.md updates (mark Backfill shipped, document Apify service pattern)

---

## 8. Success Criteria

1. A user who completes the wizard, installs the extension, clicks "Run day-one scan" sees their dashboard populate within 5 minutes
2. Backfill cost per workspace stays below $0.50 (verify via Apify dashboard during dogfood runs)
3. Idempotency holds — re-triggering returns 409, no duplicate Apify calls
4. Completion email delivered within 30s of task completion
5. All existing tests still pass; new Backfill tests deterministic (Apify mocked in unit tests)
6. E2E Playwright: new spec exercises trigger → status polling → banner transition (marked `.fixme` pending #65)

---

## 9. Open Questions (resolve during implementation, not blocking plan generation)

- Extension host-permission scope — request for `linkedin.com/mynetwork/invite-connect/connections/*` at install, or as an optional on-demand request? Optional is friendlier but sometimes harder to wire. Spec assumes on-demand — verify during Task 10.
- `backfill_profile_count` accounting — count Apify-returned profiles, or count profiles that produced at least one matching post? Probably the former (what the user perceives as "how much was backfilled").
- Completion email rendering in Outlook vs Gmail — manual test once, skip automated email-client regression testing for MVP.
