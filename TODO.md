# Sonar — Project Status & Plan

> **This is the single source of truth for the project.** Read top-to-bottom to resume. Sections below follow a fixed order: Next Session Action Plan → Phase status → Reference processes → Open issues → Orthogonal cleanup → Session log → Resume / setup commands. Older session forensics (`docs/session-notes/`) are preserved as historical artifacts but new session records go in the Session log section below, not there.

---

## Next Session Action Plan (last rewritten 2026-04-21, end of session 11)

**State at resume:** Two active branches. `feat/phase-2-6-migrations` at `8e191c9` has PR #119 open — 21 commits, 188 tests green, Phase 2.6 Tasks 1–8 + #120 blocker fix + #121/#122 quality fixes + CLAUDE.md hardening. `docs/phase-3-design` at `8e191c9` has Phase 3 design doc (passed 4 review skills: ENG + CODEX + CEO + DESIGN) + 2395-line implementation plan, no PR yet. CEO plan persisted at `~/.gstack/projects/nischal94-sonar/ceo-plans/2026-04-21-phase-3-target-scoped-intent.md`.

### 1. 🔬 Manual browser walkthrough of the 7-step wizard + Phase 2.6 Task 9 calibration

**What:** Phase 2.6's PR #119 needs two gates before merge: (a) `docker compose up -d frontend && open http://localhost:5173/signals/setup`, walk all 6 steps, screenshot for PR, (b) run `analyze-hybrid` for Dwao + CleverTap per `docs/phase-2-6/design.md §5` — pick winning λ satisfying DoD on both. **Dogfood data was wiped in Phase 2.6 Task 1 alembic downgrade incident** — the session-8 30-post labeled dataset now references post UUIDs that no longer exist. Calibration requires regenerating dogfood data (LinkedIn extension or Apify backfill) OR deferring Task 9 entirely and merging PR #119 with flag off (safe: default `use_hybrid_scoring=FALSE`).
**Why now:** Phase 2.6 code is shippable-with-flag-off. Merging frees the branch for Phase 3 to stack cleanly on fresh main.
**Blocks:** Phase 3 implementation start (wants clean main).
**Effort:** Browser walkthrough 10–15 min. Calibration 1–2 hours (if dogfood data available) OR defer.

### 2. 🚀 Merge PR #119 (Phase 2.6) + open PR for `docs/phase-3-design`

**What:** After item 1 gates pass, merge PR #119. Then `gh pr create` on `docs/phase-3-design` → main; 2 files (`docs/phase-3/design.md`, `docs/phase-3/implementation.md`). Pure docs PR; `superpowers:code-reviewer` is nice-to-have, not required.
**Why now:** Two docs on a branch with no PR is dead weight. PR creates a review surface for the plan.
**Effort:** 5 min merge + 5 min PR open.

### 3. 🏗 Begin Phase 3 implementation

**What:** After both PRs merge, execute Phase 3's 18-task implementation plan via `superpowers:subagent-driven-development` (same discipline Phase 2.6 used). Plan at `docs/phase-3/implementation.md`. First task is migrations 012–014b + ORM updates.
**Prerequisites (codified at top of implementation.md):**
- `/careful` umbrella enabled at session start
- `pg_dump snapshots/$(date +%Y-%m-%d)-pre-phase-3.sql` taken FIRST
- `/design-consultation` produces `docs/DESIGN.md` before any frontend task (Tasks 9, 10, 11, 13)
**Why now:** Pivot away from Chrome-extension attack surface (CEO review called the decision; codex review stress-tested; eng review validated architecture; design review specified UI hierarchy and interaction states).
**Effort:** 8–12 weeks eng per honest estimate after codex flagged the "scoring engine unchanged" overclaim (alert schema + context_generator + dashboard aggregation are real rewrites, not just ingest swap).

### 4. 🛠 Low-priority follow-ups (open issues, any time)

- [#123](https://github.com/nischal94/sonar/issues/123) — pipeline fit_score race. Idempotent; low priority until traffic scales.
- [#124](https://github.com/nischal94/sonar/issues/124) — `workspace.hybrid_lambda` column. Pending Task 9 calibration outcome; close as "no action" if λ=0.3 wins.
- [#125](https://github.com/nischal94/sonar/issues/125) — convert inline prompts in `extract_capability_profile` + `context_generator` to prompt modules. Tech debt follow-up from #121 fix.
- From session-8 era (still open): [#107](https://github.com/nischal94/sonar/issues/107) CORS, [#108](https://github.com/nischal94/sonar/issues/108) Apify token — both close STRUCTURALLY when Phase 3 v3.2 disables extension capture.

### 5. 🧭 Phase 2 Discovery (DEFERRED)

**What:** Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Per `docs/phase-2/design.md §4.4`.
**Why not now:** Clustering the current post distribution clusters noise. Per Phase 3 §11.4 CEO decisions, company-page targets (v3.1) are a prerequisite for cross-target trend clustering. Discovery belongs in v3.1+.

### 6. 🚧 Pre-launch tier (NOT next-session work, tracked so it doesn't surprise)

- **PII/GDPR:** data retention policy + export + deletion endpoints. Not started.
- **Observability:** structlog + Sentry + Prometheus + split `/health/live` vs `/ready` + DB backup/restore drill. Not started. Phase 3 §7 scrape-health metric is a start.
- **LLM eval harness:** activates once `signal_proposal_events` has ~100+ real completions.
- **Frontend dep bumps:** React 18→19, Vite 6→8, react-router-dom 6→7. Tracked in #40.
- **SOC 2 + SSO:** Needed for enterprise motion. Post-first-10-customers per Phase 3 CEO plan.

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

### Phase 2.6 — 🟡 PR #119 open (21 commits, 188 tests), awaits Task 9 calibration + merge

Fit × Intent hybrid scoring. 8 code tasks shipped (migrations 008–011, ICP + seller_mirror prompt, fit_scorer service, extended `/profile/extract`, pipeline branch on `use_hybrid_scoring`, one-shot `backfill_fit_scores.py`, wizard ICP review step + `/profile/update-icp`, `analyze-hybrid` calibration subcommand) + `#120` blocker fix (delivery formatters handle null `relationship_score`) + `#121` PROMPT_VERSION logging + `#122` per-field wizard dirty flags + CLAUDE.md hardening (`alembic downgrade base` is destructive; `pg_dump` before migrations; codex-review mandatory on migration plans). Task 9 (operational) pending: calibration run + flag flip per design §5. Flag defaults FALSE so PR mergeable as-is.

### Phase 3 — 🟡 Design + implementation plan complete on `docs/phase-3-design` branch, no PR yet

Target-Scoped Intent. Chrome-extension-to-server-side ingest pivot. Design doc `docs/phase-3/design.md` passed 4 review skills (plan-eng-review, codex, plan-ceo-review, plan-design-review — all CLEAR). Implementation plan `docs/phase-3/implementation.md` has 18 bite-sized TDD tasks (mirror of Phase 2.6 plan shape). CEO plan persisted at `~/.gstack/projects/nischal94-sonar/ceo-plans/2026-04-21-phase-3-target-scoped-intent.md` with vision + GTM + first-10-customer profile. Estimated 8–12 weeks eng. v3.0 scope: people-only targets (companies v3.1), 10-min/25-100-typical tiered sizing, four-lever cost model, CRM sync (Salesforce + HubSpot) promoted from v3.1, warm-intro degree-1 lookup promoted to v3.0, Slack bot deferred to v3.1.

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

### Session 11 — 2026-04-21 — Phase 3 design doc + 18-task implementation plan + CLAUDE.md hardening

- **Pivot decided:** Chrome-extension passive-feed ingest → server-side Apify target-list scraping. Rationale: security attack surface, enterprise-readiness, multi-surface foundation. Phase 2.6 scoring engine carries forward; alert + context_generator + dashboard aggregation need rewrite (honest scope correction from codex review).
- **Docs shipped on `docs/phase-3-design`:** `docs/phase-3/design.md` (4 reviews CLEAR) + `docs/phase-3/implementation.md` (18 TDD-style tasks, 2395 lines).
- **CEO plan persisted:** `~/.gstack/projects/nischal94-sonar/ceo-plans/2026-04-21-phase-3-target-scoped-intent.md`.
- **CLAUDE.md hardened** (from the Phase 2.6 Task 1 alembic wipe scar): 3 new rules in "Database and migrations" section — NEVER `alembic downgrade base` against dev DB; `pg_dump` snapshot before multi-migration phases; codex-review mandatory on plans touching migrations. `snapshots/` added to `.gitignore`.
- **Memory scars filed (4):** `feedback_alembic_downgrade_is_destructive`, `feedback_pre_phase_snapshot`, `feedback_codex_review_is_not_optional_on_plans`, `feedback_careful_umbrella_for_migrations`. Indexed in MEMORY.md under new "Database & Migration Safety" section.
- **Next session starts with:** (1) Task 9 calibration or defer + merge PR #119, (2) open PR for `docs/phase-3-design`, (3) begin Phase 3 implementation via `superpowers:subagent-driven-development`.

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
