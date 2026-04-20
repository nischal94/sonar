# Sonar — Project Status & Plan

> **This is the single source of truth for the project.** Read top-to-bottom to resume. Sections below follow a fixed order: Next Session Action Plan → Phase status → Reference processes → Open issues → Orthogonal cleanup → Session log → Resume / setup commands. Older session forensics (`docs/session-notes/`) are preserved as historical artifacts but new session records go in the Session log section below, not there.

---

## Next Session Action Plan (last rewritten 2026-04-20, end of session 8)

**State at resume:** `main` HEAD = `481f299` (check with `git log -1`). Tests: 136 backend pass. CI green on `main`. Working tree clean. **PR #114 open** on branch `eval/calibration-v1` with the calibration harness + findings — needs review + merge before session-9 work starts.

### 1. ✅ Review + merge PR #114 (calibration findings)

**What:** Read `eval/calibration/findings-dogfood-martech.md` and `eval/calibration/phase-2.6-evidence.md` on PR #114. If the interpretation holds up, merge. Close issue #106 ("threshold calibration") as superseded by #113 ("matching model not viable — Phase 2.6 required") — reference #113 in the close comment.
**Why now:** The calibration evidence is currently only on a feature branch. Every subsequent decision depends on it being canonical in `main`. Keeping it unmerged risks losing it or losing the thread.
**Blocks:** Item 2 (Phase 2.6 brainstorm should reference the merged evidence, not a PR branch).
**Effort:** 15–30 min (read, merge, close #106).

### 2. 🧭 Phase 2.6 — Fit × Intent scoring design brainstorm (the central session-9 activity)

**What:** Run `superpowers:brainstorming` with the problem framed per issue #113: "design a Fit × Intent hybrid scoring model for Sonar that fixes the failure modes in `eval/calibration/phase-2.6-evidence.md`." Produce `docs/phase-2-6/design.md` covering: the fit-encoder choice (BGE / E5 / OpenAI 3-large with asymmetric prompts), per-connection `fit_score` schema + inputs (headline + company + role vs. ICP profile), how to capture ICP disqualifiers (competitors, vendors in same category), how to combine with intent (multiplicative vs additive), persistence-of-prior-signals (Bayesian bump across posts from same high-intent author), calibration plan (re-use `backend/scripts/calibrate_matching.py`, same 30-post dogfood dataset as "before/after" baseline).
**Why now:** This is the single most important open question for the product. The calibration proved the current primitive cannot ship. Every other Phase 2 item (Discovery) and Phase 3 item (real-time, CRM, team) depends on matching being meaningful. Nothing matters more than getting this right.
**Blocks:** Phase 2 Discovery, all Phase 3 work, any launch plan.
**Effort:** Full session for brainstorming + design doc. Implementation is another 2–3 sessions after.

### 3. 🔒 Hardening: issues #107 + #108 (do before first external user)

**#107 — CORS service-worker routing.** Route extension fetches through the background service worker (whose origin is `chrome-extension://<id>`, already allowed). Remove `https://www.linkedin.com` from `app/main.py` `allow_origins`. Closes the `/auth/token` response-read exposure the session-7 CORS widening created. **Effort:** ~1 hour.

**#108 — Apify token to `Authorization` header.** Move from URL query param (`?token=apify_api_...`) to `Authorization: Bearer` header in `app/services/apify.py`. Verify harvestapi accepts header auth. Stops the plaintext-token leak into every worker log line. **Effort:** ~30 minutes.

**Why now:** Both are security-adjacent and small. Best done in one commit *before* any external user signs up. Not blocked on Phase 2.6 — can ship in parallel or in a gap between brainstorm and implementation.

### 4. 🛠 Small quality fixes (any time, low effort)

- **#110 — Ring 1 dead.** Signals are full phrases; Ring 1 does literal substring match; produces zero hits. Partially overlaps with Phase 2.6 (may disappear if Phase 2.6 reshapes what a "signal" is). Decide in Phase 2.6 design whether to fix standalone or fold in.
- **#111 — Dashboard slider default (0.65) ignores workspace `matching_threshold`.** Small frontend fix: pass the workspace's stored threshold on initial render. ~30 minutes. Not urgent.
- **Dogfood DB cleanup (per PR #112 body).** Run `UPDATE connections SET relationship_score = NULL WHERE relationship_score = 0.5 AND NOT has_interacted;` on the dogfood workspace to let the fixed scorer see correct values. Already done in session 8; noted here in case a fresh environment is restored from a snapshot.

### 5. 🧭 Phase 2 Discovery (DEFERRED until Phase 2.6 ships)

**What:** Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Per `docs/phase-2/design.md §4.4`.
**Why not now:** Clustering posts by the current matching signal clusters noise (F1 = 0.27). Discovery is building on sand until Phase 2.6 lands.
**When to revisit:** After Phase 2.6 ships *and* re-calibration against the dogfood dataset produces F1 ≥ 0.6.
**Effort:** Multi-session when it's time.

### 6. 🚧 Pre-launch tier (gates before first external paying customer — NOT next-session work)

Tracked so they don't surprise:
- **PII/GDPR:** data retention policy + export + deletion endpoints. Not started.
- **Observability:** structlog + Sentry + Prometheus + split `/health/live` vs `/ready` + DB backup/restore drill. Not started.
- **LLM eval harness:** activates once `signal_proposal_events` has ~100+ real completions.
- **Frontend dep bumps:** React 18→19, Vite 6→8, react-router-dom 6→7. Tracked in #40. Requires human in browser — plan a dedicated half-day.

None of these belong in session 9; all gate first external customer.

---

## Phase status

### Phase 1 — ✅ Complete

Ingest pipeline, capability profile extraction, signal matching, scoring, alerts, delivery channels (Slack / email / Telegram / WhatsApp), Chrome extension, React dashboard, JWT auth. All known Phase 1 bugs closed.

### Phase 2 — **4 of 5 original slices shipped; re-sequenced after session-8 calibration finding**

| Slice | Status | What it is |
|---|---|---|
| **Foundation** | ✅ Shipped (PR #10) | Migration 002, 4 new ORM models, Ring 1/2 matchers, pipeline refactor, scorer keyword bonus, one-shot backfill script. |
| **Wizard** | ✅ Shipped session 4 (PRs #64 + #68 + #70) | 5-step Signal Configuration Wizard at `/signals/setup`. Backend: `POST /workspace/signals/propose` + `/confirm`, `signal_proposal_events` telemetry, `app/prompts/propose_signals.py` v1. |
| **Dashboard** | ✅ Shipped session 5 (PR #73) | Ranked People List at `/dashboard`. `incremental_trending` Celery task keeps `person_signal_summary` fresh within ~100 ms/post. |
| **Backfill** | ✅ Shipped session 6 (PR #77), wiring completed session 7 (PR #104) | Day-One Backfill. Extension → bulk upsert → Celery Apify scrape → pipeline → completion email. |
| **2.5 — Calibration evidence** | 🟡 PR #114 open | Session-8 output. Labeled 30-post dogfood dataset + findings report + Phase 2.6 evidence pool + reusable `calibrate_matching.py` harness. Proves the current post-only matching primitive scores near-randomly (F1 = 0.27, distributions inverted). Issue #113. |
| **2.6 — Fit × Intent scoring** | ⬜ Design pending | New slice replacing the narrow "threshold calibration" framing of #106. Per-connection fit score from headline + company + role, combined multiplicatively with per-post intent score. Matches industry standard (6sense / Apollo / Demandbase). Required before Discovery can build on a useful signal. Next-session work: `superpowers:brainstorming` → `docs/phase-2-6/design.md`. |
| **Discovery** (original final slice) | ⬜ Deferred until 2.6 ships | Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Clustering the current signal clusters noise; deferred until Phase 2.6 re-calibrates to F1 ≥ 0.6. |

### Phase 3 — ⬜ TBD (no design yet)

Three rough directions in `CLAUDE.md`: real-time alerts, CRM integrations, team features. Deprioritized vs Phase 2.6. Run `superpowers:brainstorming` to scope when 2.6 ships.

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

### Matching quality — current state

- **#105** — ✅ Closed by PR #112 (session 8). `Connection.relationship_score` was forced to 0.5 by ORM default, bypassing `DEGREE_BASE_SCORE` fallback. Migration 007 made the column nullable; backfill route sets it explicitly.
- **#106** — 🟡 Superseded by #113 (to be closed with cross-link on session-9 merge of PR #114).
- **#113** — 🔴 **Open + critical.** Current post-only matching primitive cannot discriminate buying intent from noise (F1 = 0.27, distributions inverted). Phase 2.6 Fit × Intent redesign required before further threshold work. Evidence in `eval/calibration/` (PR #114).
- **#110** — Ring 1 matcher dead (signals are full phrases, matcher expects keywords). May disappear if Phase 2.6 reshapes signal shape; revisit during #113 design.
- **#111** — Dashboard slider default 0.65 ignores workspace `matching_threshold`. Small frontend fix; pick up any time.

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

### Session 8 — 2026-04-20 — Login page, scorer fix, and the calibration finding that reshaped Phase 2

- **Merged:** PR #109 (frontend `/login` page — returning users had no UI path back in). PR #112 (fixes issue #105: `Connection.relationship_score` was forced to `0.5` by ORM default, bypassing `DEGREE_BASE_SCORE` fallback; migration 007 makes column nullable).
- **Open:** PR #114 — calibration harness + labeled 30-post dogfood dataset + findings report + Phase 2.6 evidence pool. Awaiting review/merge.
- **Filed:** #110 (Ring 1 dead — phrases vs keywords), #111 (dashboard slider default), **#113 (matching model not viable — Phase 2.6 required)**.
- **Calibration headline:** F1_max = 0.27 against hand-labeled dogfood dataset (4 yes / 26 no). Cosine distributions of real-matches and non-matches are *inverted* at the top — the #1 and #2 highest-cosine posts in the whole dataset are from competing vendors (NotifyVisitors CPO, MoEngage sales director). No threshold can recover usable precision + recall. The current post-only Ring 2 primitive cannot ship.
- **Roadmap change:** Added Phase 2.5 (calibration evidence) and Phase 2.6 (Fit × Intent scoring) between Phase 2 Backfill and Phase 2 Discovery. Discovery deferred until 2.6 achieves F1 ≥ 0.6 against the same dataset. Issue #106 superseded by #113.

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
docker compose exec -T api pytest -q       # expect 136 passing

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
