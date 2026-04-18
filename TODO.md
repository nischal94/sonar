# Sonar — TODO

## Resume Here (last updated 2026-04-18, end of session 6)

**`main` HEAD** = `c305e0b` (release 0.6.0). **Tag:** `v0.6.0`. **Tests:** 113
backend pass + 4 skipped, 14/14 frontend, all CI green incl. E2E Playwright.
Working tree clean; everything pushed.

**This session (session 6) shipped Phase 2 Backfill.** Full context in
[`docs/session-notes/2026-04-18-session-6.md`](docs/session-notes/2026-04-18-session-6.md).

**Next natural move:** **pause to dogfood** the shipped surface
(Foundation + Wizard + Dashboard + Backfill closes the full day-one loop).
Dogfood checklist is at the bottom of the session-6 note. Once dogfood
findings come back as GitHub issues, triage → fix blockers inline → then
start **Phase 2 Discovery** (Ring 3 clustering + weekly digest) via
`superpowers:brainstorming` on `docs/phase-2/design.md §4.4`.

**History:** prior sessions' details live under
[`docs/session-notes/`](docs/session-notes/) (session 6 onward) and in git /
CHANGELOG / the phase-2 decision docs. Don't inline past sessions here —
the "Resume Here" section is for *next action*, not history.

---

## Phase status

### Phase 1 — ✅ Complete

Ingest pipeline, capability profile extraction, signal matching, scoring, alerts, delivery channels (Slack / email / Telegram / WhatsApp), Chrome extension, React dashboard, JWT auth. All known Phase 1 bugs closed.

### Phase 2 — **4 of 5 slices shipped, 1 remaining**

| Slice | Status | What it is |
|---|---|---|
| **Foundation** | ✅ Shipped (PR #10) | Migration 002, 4 new ORM models, Ring 1/2 matchers, pipeline refactor, scorer keyword bonus, one-shot backfill script. |
| **Wizard** | ✅ Shipped session 4 (PRs #64 + #68 + #70) | 5-step Signal Configuration Wizard at `/signals/setup`. Backend: `POST /workspace/signals/propose` + `/confirm`, `signal_proposal_events` telemetry, `app/prompts/propose_signals.py` v1 with idempotency + role-separation defense. |
| **Dashboard** | ✅ Shipped session 5 (PR #73) | Ranked People List at `/dashboard`. `incremental_trending` Celery task keeps `person_signal_summary` fresh within ~100 ms/post. 30s polling + tab-visibility pause + instant refetch on filter change. Heatmap + Trending Topics sections deferred. |
| **Backfill** | ✅ Shipped session 6 (PR #77) | Day-One Backfill. Extension captures connections → bulk upsert → Celery task runs 1st-degree Apify scrape (200 × 60 days, ~$0.40/ws) → posts flow through pipeline → completion email. Dashboard banner polls status at 5s. 2nd-degree deferred — research in issue #76. |
| **Discovery** | ⬜ Not started | Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Most experimental — best built last when there's real data. No plan yet; needs `superpowers:brainstorming` first. |

### Phase 3 — ⬜ TBD (no design yet)

Three rough directions in `CLAUDE.md`: real-time alerts, CRM integrations, team features. Run `superpowers:brainstorming` to scope when Phase 2 fully ships.

---

## Next steps in priority order

### Priority A — Dogfood the current state (recommended)

See the checklist at the bottom of
[`docs/session-notes/2026-04-18-session-6.md`](docs/session-notes/2026-04-18-session-6.md). Triage findings to GitHub issues; fix anything blocking the "day-one magic moment" inline; then ship Discovery.

**Effort:** 3–5 days of lived-in use, then a focused triage session.

### Priority B — Phase 2 Discovery slice

Ring 3 nightly HDBSCAN clustering + Weekly Digest Email. Needs brainstorming + writing-plans before implementation. Should follow dogfood so the clustering is validated against real production data, not synthetic posts.

**How to start:** `superpowers:brainstorming` with the prompt "scope Phase 2 Discovery — Ring 3 nightly clustering for emerging topics + Weekly Digest Email per `docs/phase-2/design.md §4.4`."

**Effort:** multi-session. Most uncertainty of any Phase 2 slice.

### Priority C — Pre-launch gaps (required before production)

| Gap | Status | Issue / note |
|---|---|---|
| Rate limiting | ✅ Shipped (`/auth/token` PR #61, `/workspace/register` PR #67) | Deploy precondition `--proxy-headers` tracked in #62 |
| PII / GDPR | ❌ Not started | Data retention policy + export + deletion endpoints |
| Observability baseline | ❌ Not started | structlog + Sentry + Prometheus + split `/health/live` vs `/ready` + DB backup/restore drill |
| LLM eval datasets | ⏳ Harness in spirit via structural CI gate | Activates once `signal_proposal_events` has ~100+ real completions |

These should be promoted into the numbered Priority list before Discovery expands the LLM + data surface area further.

### Priority D — Frontend dep bumps (5 coupled, REQUIRES HUMAN IN BROWSER)

React 18→19, react-dom, react-router-dom 6→7, Vite 6→8, @vitejs/plugin-react 4→6 are tightly coupled and must be evaluated as **one coordinated upgrade**. Per `CLAUDE.md` Lessons Learned: frontend dep bumps require a human running through every route in the browser, not just `npm run build`.

**Process:**
1. Block a half-day to full day with no other work in flight
2. `git checkout -b chore/deps-frontend-2026-q2`
3. Bump all 5 packages in `frontend/package.json`, `npm install`, `npm run build`
4. `docker compose up -d frontend`; manually test every route (register, login, profile/extract, signals/setup, dashboard, alerts, channels)
5. Fix breakage as it surfaces; commit, push, open PR with "browser-tested" note

**Tracked:** issue #40. **Effort:** half-day to full day.

### Priority E — Phase 3 brainstorming

After Phase 2 fully ships: run `superpowers:brainstorming` with "scope Phase 3 of Sonar — real-time alerts, CRM integrations, team features, or something else." Produces `docs/phase-3/design.md`.

---

## Open issues

- **#76** — Backfill research spikes (Apify 1st-degree actor verification + 2nd-degree ICP-filtered availability)
- **#74** — Dashboard P2/P3 polish nits from PR #73
- **#69** — Wizard /confirm P3 polish nits from PR #68
- **#65** — E2E: re-activate register/login Playwright tests (skipped in PR #64)
- **#62** — Deploy precondition: uvicorn `--proxy-headers` required before prod
- **#43** — redis 7 bump blocked upstream on celery+kombu

---

## Orthogonal cleanup (not blocking)

- **Residual Node 20 on `googleapis/release-please-action@v4`** — deprecation annotation fires on every release-please run. Waiting on googleapis to ship v4.x on Node 24 or a v5. Deadline: Node 24 forced 2026-06-02, Node 20 removed 2026-09-16. Revisit May 2026.
- **Type checking** — mypy/pyright in CI starts permissive, tightens over time. Basic setup shipped; tightening remains.
- **Memory key path migration** — per-project memory still keyed at `~/.claude/projects/-Users-nischal-Downloads-Misc-projects-project-ideas-sonar/` (old path). Consider symlinking or renaming the memory key to the new `sonar/` slug.

---

## How to resume in a new Claude Code session

```bash
cd ~/Downloads/Misc/projects/sonar
docker compose up -d postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pytest -q       # expect 113 passing + 4 skipped

claude    # launch Claude Code from inside the Sonar dir so per-project memory loads
```

Then ask Claude: **"Read TODO.md and the latest `docs/session-notes/` entry, then tell me the state."**

---

## First-time setup

Copy `.env.example` to `.env` and fill:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `SECRET_KEY` | Any random 32+ char string | ✅ Yes |
| `OPENAI_API_KEY` | platform.openai.com | ✅ Yes (embeddings + `gpt-5.4-mini`) |
| `GROQ_API_KEY` | console.groq.com (free) | ✅ Yes (Llama for med/low alerts) |
| `APIFY_API_TOKEN` | apify.com | ✅ Yes (Backfill slice) |
| `SENDGRID_API_KEY` / `SENDGRID_FROM_EMAIL` | sendgrid.com | ✅ Yes (Wizard + Backfill emails) |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | twilio.com | ❌ Optional (WhatsApp channel) |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram | ❌ Optional (Telegram channel) |

```bash
docker compose up -d --build
docker compose exec -T api alembic upgrade head
```

Then open http://localhost:5173.
