# Sonar — Project Status & Plan

> **This is the single source of truth for the project.** Read top-to-bottom to resume. Sections below follow a fixed order: Next Session Action Plan → Phase status → Reference processes → Open issues → Orthogonal cleanup → Session log → Resume / setup commands. Older session forensics (`docs/session-notes/`) are preserved as historical artifacts but new session records go in the Session log section below, not there.

---

## Next Session Action Plan (last rewritten 2026-04-20, end of session 7)

**State at resume:** `main` HEAD = `af54add` (check with `git log -1`). Tests: 129 backend pass + 3 real-OpenAI skipped. All CI green. Working tree clean.

### 1. ⏱ Verify the end-to-end loop (5 min — do this FIRST)

**What:** Open `http://localhost:5173`, log in, check the intent-matches pane shows the 8 backfilled posts that crossed `matching_threshold=0.30` on the dogfood workspace.
**Why now:** It's the only thing left unverified from session 7. All code merged + pushed; only the dashboard render is unseen. If it works, Backfill is truly shipped. If it doesn't, the chain has one more bug before #105 matters.
**Blocks:** nothing downstream, but unresolved until the dashboard is eyed.
**Effort:** 5 minutes.

### 2. 🐛 Fix issue #105 — `relationship_score` default fallback bug (BLOCKER)

**What:** Scorer returns `0.5` for every 1st-degree connection instead of the documented `0.9`. Investigate `app/workers/scorer.py` (or wherever scoring lives), locate the default-fallback path, fix to read `Connection.degree`, add a regression test that inserts a degree=1 Connection + Post and asserts `relationship_score ≥ 0.9`.
**Why now:** Blocks #106 directly — calibration against a broken scorer produces a broken threshold. Also raises combined-score ceiling on backfilled posts from 0.77 → 0.89, which materially improves matching quality for live signals too.
**Blocks:** #106 (threshold calibration).
**Effort:** ~1-2 hours. Small isolated fix.

### 3. 🎯 Plan and execute issue #106 — threshold calibration

**What:** Build a golden eval dataset of ~100-200 real LinkedIn posts labeled "IS a buying-intent signal" vs "isn't" against the dogfood workspace's signals. Run the scorer against the set at thresholds 0.2–0.9. Plot precision/recall. Pick the threshold at the elbow (may split live vs. backfill).
**Why now:** The `0.72` default was never empirically tuned. Live dogfood showed it's unreachable for any post older than 24h. Users deploying with default settings will see empty dashboards.
**Blocks:** confidence in the product's matching claim. Nothing structural waits on it, but the product is "half-broken by design" until it's done.
**Effort:** Full session on its own — most uncertainty of any next item. Includes hand-labeling work.

### 4. 🔒 Hardening: issues #107 + #108 (both small, do before first external user)

**#107 — CORS service-worker routing.** Route extension fetches through the background service worker (whose origin is `chrome-extension://<id>`, already allowed). Remove `https://www.linkedin.com` from `app/main.py` `allow_origins`. Closes the `/auth/token` response-read exposure tonight's CORS widening created. **Effort:** ~1 hour.

**#108 — Apify token to Authorization header.** Move from URL query param (`?token=apify_api_...`) to `Authorization: Bearer` header in `app/services/apify.py`. Verify harvestapi accepts header auth. Stops the plaintext-token leak into every worker log line. **Effort:** ~30 minutes.

**Why now:** Both are security-adjacent and small. Best done in one commit before any external user signs up.

### 5. 🧭 Phase 2 Discovery slice (the final Phase 2 slice)

**What:** Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Per `docs/phase-2/design.md §4.4`.
**Why now:** After #105 + #106, matching quality is trustworthy enough to build discovery on top of. Before that, clusters would form around noise.
**Start with:** `superpowers:brainstorming` to scope decisions (which clustering approach, digest template, schedule, opt-in flow).
**Effort:** Multi-session. Most uncertainty of any Phase 2 slice.

### 6. 🚧 Pre-launch tier (gates before first external paying customer)

Not next-session work, but tracked so it doesn't surprise:
- **PII/GDPR:** data retention policy + export + deletion endpoints. Not started.
- **Observability:** structlog + Sentry + Prometheus + split `/health/live` vs `/ready` + DB backup/restore drill. Not started.
- **LLM eval harness:** activates once `signal_proposal_events` has ~100+ real completions.
- **Frontend dep bumps:** React 18→19, Vite 6→8, react-router-dom 6→7. Tracked in #40. Requires human in browser — plan a dedicated half-day.

None of these block session-8 work; all gate first external customer.

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
| **Backfill** | ✅ Shipped session 6 (PR #77), wiring completed session 7 (PR #104) | Day-One Backfill. Extension captures connections → bulk upsert → Celery task runs 1st-degree Apify scrape (200 × 60 days, ~$0.40/ws) → posts flow through pipeline → completion email. Dashboard banner polls status at 5s. Session 7 dogfood discovered the trigger endpoint had never been wired to Celery (PR #104 fixed) and surfaced DOM / CORS / URL-normalization bugs along the end-to-end path. 2nd-degree deferred — research in issue #76. |
| **Discovery** | ⬜ Not started | Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Most experimental — best built last when there's real data. No plan yet; needs `superpowers:brainstorming` first. |

### Phase 3 — ⬜ TBD (no design yet)

Three rough directions in `CLAUDE.md`: real-time alerts, CRM integrations, team features. Run `superpowers:brainstorming` to scope when Phase 2 fully ships.

---

## Reference processes (not in the action plan above because they need their own runbook)

### Frontend dep bumps — coordinated 5-package upgrade (issue #40)

React 18→19, react-dom, react-router-dom 6→7, Vite 6→8, @vitejs/plugin-react 4→6 are tightly coupled and must be evaluated as **one coordinated upgrade**. Per `CLAUDE.md` Lessons Learned: frontend dep bumps require a human running through every route in the browser, not just `npm run build`.

**Process:**
1. Block a half-day to full day with no other work in flight
2. `git checkout -b chore/deps-frontend-2026-q2`
3. Bump all 5 packages in `frontend/package.json`, `npm install`, `npm run build`
4. `docker compose up -d frontend`; manually test every route (register, login, profile/extract, signals/setup, dashboard, alerts, channels)
5. Fix breakage as it surfaces; commit, push, open PR with "browser-tested" note

### Phase 3 brainstorming (after all Phase 2 slices ship)

Run `superpowers:brainstorming` with "scope Phase 3 of Sonar — real-time alerts, CRM integrations, team features, or something else." Produces `docs/phase-3/design.md`.

---

## Open issues

### Blockers on matching quality (from session 7 dogfood)

- **#105** — `relationship_score` returns 0.5 default instead of 0.9 for
  degree=1 connections. Scorer isn't reading `Connection.degree`. Fix this
  BEFORE #106 so calibration runs against correct scorer output.
- **#106** — `matching_threshold` calibration: build golden eval dataset +
  ROC analysis. The 0.72 default was never empirically tuned. Blocked on
  #105.

### Hardening (from session 7 dogfood)

- **#107** — CORS hardening: route extension fetches through service
  worker, drop linkedin.com origin. Current CORS allows linkedin.com
  scripts to POST to `/auth/token` and read the response.
- **#108** — Apify API token leaks into worker logs (passed as URL query
  param). Move to `Authorization` header.

### Pre-launch

- **#80** — Pre-launch: verify Resend sender domain before first customer email
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

## Session log (newest first, terse; full forensics live in git commits + PR descriptions)

### Session 7 — 2026-04-20 — First live dogfood + Backfill Celery wiring + doc consolidation

- **Merged:** PR #103 (Wizard: `max_tokens` → `max_completion_tokens` rename on gpt-5.4-mini; tolerate top-level-list LLM output). PR #104 (Backfill: wired day_one_backfill Celery task — the trigger endpoint had never been wired despite shipping with green tests; plus CORS widening for linkedin.com origin, Apify `profile_url` canonicalization, LinkedIn DOM-selector rewrite, Pydantic length truncation).
- **Filed:** #105 (scorer `relationship_score` returns 0.5 default instead of 0.9), #106 (`matching_threshold` calibration via golden eval dataset), #107 (CORS service-worker routing), #108 (Apify token in URL query param).
- **Structural doc change:** TODO.md is now the single source of truth with a rigid section order (see header). Session records go in this Session log, not `docs/session-notes/` (which is preserved as history for sessions 1–7 but not added to). TODO.html mirrors TODO.md. CLAUDE.md Process discipline updated with the required template for the Next Session Action Plan.
- **Longer forensic for this session** preserved as [`docs/session-notes/2026-04-20-session-7.md`](docs/session-notes/2026-04-20-session-7.md) — final entry in that directory.

### Session 6 — 2026-04-18 — Phase 2 Backfill slice shipped

- Merged PR #77 (Backfill) + PR #75 (release 0.6.0, tag `v0.6.0`).
- First external-HTTP integration pattern (`Protocol + Real + Fake + get_{service}`) canonicalized in `app/services/apify.py`.
- Forensic: [`docs/session-notes/2026-04-18-session-6.md`](docs/session-notes/2026-04-18-session-6.md).

### Sessions 1–5 — Phase 1 complete + Phase 2 Foundation, Wizard, Dashboard

- Foundation (PR #10), Wizard (PRs #64, #68, #70), Dashboard (PR #73). Details in commit log + PR descriptions. No session-note files for sessions 1–5 under the previous convention.

---

## How to resume in a new Claude Code session

```bash
cd ~/Downloads/Misc/projects/sonar
docker compose up -d postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pytest -q       # expect 129 passing + 3 skipped

claude    # launch Claude Code from inside the Sonar dir so per-project memory loads
```

Then ask Claude: **"Read TODO.md, then tell me the state and execute item 1 of the Next Session Action Plan."**

---

## First-time setup

Copy `.env.example` to `.env` and fill:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `SECRET_KEY` | Any random 32+ char string | ✅ Yes |
| `OPENAI_API_KEY` | platform.openai.com | ✅ Yes (embeddings + `gpt-5.4-mini`) |
| `GROQ_API_KEY` | console.groq.com (free) | ✅ Yes (Llama for med/low alerts) |
| `APIFY_API_TOKEN` | apify.com | ✅ Yes (Backfill slice) |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | resend.com | ✅ Yes (Wizard + Backfill emails) |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | twilio.com | ❌ Optional (WhatsApp channel) |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram | ❌ Optional (Telegram channel) |

```bash
docker compose up -d --build
docker compose exec -T api alembic upgrade head
```

Then open http://localhost:5173.
