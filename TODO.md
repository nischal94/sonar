# Sonar — TODO

## Resume Here (last updated 2026-04-12)

**Current state:** clean. `main` HEAD = `ab91c1f`. 54/54 tests passing. 0 open PRs. 1 open issue (#40 — dependency audit, deferred). Phase 1 + Phase 2 Foundation shipped. All Phase 1 cleanup + Phase 2 follow-up issues closed (#5, #6, #7, #8, #11, #14, #17, #18, #21, #22, #25). Committer leak (Gmail + hostname) fully remediated via `git filter-branch` + force-push — `main` now shows 40 noreply + 17 GitHub squash-merge committers, zero leaks. `.github/` scaffold (release-drafter, Dependabot, PR/issue templates) live.

**Where to read for full context before resuming:**
- `sonar/CLAUDE.md` — engineering rules + the new "Lessons Learned — Rules Codified from Prior Sessions" section near the bottom (Python DI, asyncio.gather, frontend deps need human in browser)
- `sonar/CHANGELOG.md` — every PR shipped this session under `[Unreleased]`
- `~/.claude/projects/-Users-nischal-Downloads-Misc-projects-project-ideas-sonar/memory/` — Sonar project memory (only loads when you `cd sonar && claude` instead of launching from home)
- `~/.claude/CLAUDE.md` — global rules updated this session: Privacy item #5 (committer pre-check), "When to Stop and Ask" external-side-effect bullet, new "After a user-caught mistake" subsection

---

## Phase status

### Phase 1 — ✅ Complete

Ingest pipeline, capability profile extraction, signal matching, scoring, alerts, delivery channels (Slack / email / Telegram / WhatsApp), Chrome extension, React dashboard, JWT auth. All 4 known Phase 1 bugs closed; the 5 originally-failing tests are all green; 54/54 on `main`.

### Phase 2 — 1 of 5 slices shipped, 4 remaining

| Slice | Status | What it is |
|---|---|---|
| **Foundation** | ✅ Shipped (PR #10) | Migration 002, 4 new ORM models, Ring 1/2 matchers, pipeline refactor, scorer keyword bonus, one-shot backfill script, 24 new tests |
| **Wizard** | ⬜ Not started | Signal Configuration Wizard — backend API + frontend UI for users to configure their buying-intent signals. Plan should exist at `docs/phase-2/implementation-wizard.md`. |
| **Dashboard** | ⬜ Not started | Network Intelligence Dashboard — heatmap of buying intent across the user's network + incremental aggregation pipeline. Depends on Wizard (configurable signals first). |
| **Backfill** | ⬜ Not started | Day-One Backfill — Chrome extension + Apify integration to seed the system with historical posts on first install. Depends on Phase 1 extension working + signals to match against. |
| **Discovery** | ⬜ Not started | Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Most experimental — best built last when there's real data. |

**Recommended order:** Wizard → Dashboard → Backfill → Discovery (matches dependency direction).

### Phase 3 — ⬜ TBD (no design yet)

Per `sonar/CLAUDE.md`, Phase 3 has only a placeholder with three rough directions:
- **Real-time alerts** — push notifications when high-priority intent fires (vs. current batch flow)
- **CRM integrations** — Salesforce / HubSpot / Attio sync so detected intent flows into the user's existing pipeline
- **Team features** — multi-seat per workspace with assignment, comments, shared filters

No design spec exists for any of these. When Phase 2 ships, run a brainstorming session via `superpowers:brainstorming` to scope Phase 3 properly.

---

## Next steps in priority order

### Priority 1 — Wire up CI gates (top tech-debt)

**Why:** Top tech-debt item per `sonar/CLAUDE.md` "Engineering Standards" → "CI and code quality". Without CI, every PR needs manual test runs, dep bumps can't be auto-merged safely, and regressions sneak in. The `.github/` scaffold is already in place — we just need a `ci.yml` workflow. **Should land before any Phase 2 slice work** so new code is auto-validated.

**What to add in `.github/workflows/ci.yml`:**
- `ruff check` (lint + format check) on every PR
- `mypy` or `pyright` (start permissive, tighten over time per `sonar/CLAUDE.md` Engineering Standards)
- `pytest -q` with coverage reporting (target 70-85% meaningful coverage)
- Backend container build sanity check (`docker compose build api`)
- Frontend `npm run build` sanity check
- Pre-commit hook check (block secrets, trailing whitespace, large files, lint violations)

**How to start:** read `.github/workflows/release-drafter.yml` for the workflow style, then plan via `superpowers:writing-plans` before executing. Plan should cover: which Python version matrix, how to spin up Postgres + pgvector for tests, whether to use the existing `api` container or a fresh runner image.

**Effort:** half a session. **Blocks:** Priority 4+ ideally should land after this.

---

### Priority 2 — Issue #40 backend dep bumps (3 packages, individually)

**Why:** 3 backend major bumps were closed-with-defer during the Dependabot first-run burst. Each is independently evaluatable now via the existing test suite. Rule from `feedback_dep_audit_split.md`: backend majors get branch + test + merge, one at a time, not batched.

**Packages and per-library smoke tests:**

- **`redis 5.0.0 → 7.4.0`** — redis-py went through 5 → 6 → 7 with breaking API changes. Smoke test: enqueue a Celery job, verify it processes through `worker` container. Verify connection-pool behavior under concurrent load.
- **`numpy 1.26.0 → 2.4.4`** — numpy 2.0 has breaking changes in scalar behavior, dtype promotion, removed aliases. Smoke test: `pytest tests/test_scorer.py tests/test_matcher.py tests/test_ring2_matcher.py -v` and manually exercise the scorer with a sample alert.
- **`pgvector 0.3.0 → 0.4.2`** — 0.x minor, semver allows breaking changes. Smoke test: run migrations top-to-bottom, run Ring 2 cosine similarity query against seeded data, verify embedding column type is unchanged.

**Process per package** (per `feedback_dep_audit_split.md`):
1. `git checkout -b chore/deps-<package>`
2. Bump the version in `backend/pyproject.toml`
3. `docker compose exec -T api uv sync --all-extras` (regenerates `uv.lock`)
4. `docker compose exec -T api pytest -q` — must remain 54/54
5. Run the library-specific smoke test above
6. Commit with `chore(deps): bump <package> from X to Y` (Conventional Commits — release-drafter will auto-label)
7. Push, open PR, run `superpowers:code-reviewer`, merge if green, update CHANGELOG

**Effort:** ~1 hour total for all 3, sequentially.

---

### Priority 3 — Issue #40 frontend dep bumps (5 coupled, REQUIRES HUMAN IN BROWSER)

**Why:** React 18→19, react-dom, react-router-dom 6→7, Vite 6→8, @vitejs/plugin-react 4→6 are tightly coupled and must be evaluated as **one coordinated upgrade**. The `Lessons Learned` section in `sonar/CLAUDE.md` codifies this: "Frontend dependency bumps require a human in the browser." `npm run build` succeeding is not sufficient — runtime React behavior, routing, auth flow, form submission, and dashboard interactions all fail silently without browser testing.

**Process:**
1. Block off half a day to a full day with no other work in flight
2. `git checkout -b chore/deps-frontend-2026-q2`
3. Bump all 5 packages in `frontend/package.json` simultaneously
4. `cd frontend && npm install` (regenerates `package-lock.json`)
5. `npm run build` — must succeed (necessary but not sufficient)
6. `docker compose up -d frontend`
7. **Manually test in the browser**, every route, every flow:
   - `/register` workspace registration
   - `/login` and JWT cookie handling
   - `/profile/extract` capability profile UI
   - `/ingest` post submission (dev exercise via API)
   - `/alerts` list view
   - `/alerts/<id>` detail view
   - `/channels` channel config (Slack/email/Telegram/WhatsApp)
8. Fix breakage as it surfaces — React 19 deprecated patterns, react-router-dom v7 API changes, Vite 8 bundling differences
9. Commit, push, open PR, merge with explicit note that browser-tested

**Do NOT attempt without time blocked off and a human at the keyboard.**

**Effort:** half-day to a full day.

---

### Priority 4 — Phase 2 Wizard slice

**Why:** Foundation is shipped (PR #10). Wizard is the next dependency-direction step — it builds the configuration UI/API on top of the data model Foundation laid. Dashboard, Backfill, and Discovery all assume configurable signals exist (Wizard's deliverable).

**How to start:**
1. Verify the plan exists: `cat docs/phase-2/implementation-wizard.md`
2. If yes, dispatch the implementer through `superpowers:subagent-driven-development` — same per-task subagent flow that worked for Foundation
3. If no, run `superpowers:brainstorming` first to design it, then `superpowers:writing-plans` to plan it, then implement

**Pre-req:** CI gates from Priority 1 should ideally be in place first so the new code is auto-validated as it lands.

**Effort:** multi-session. Foundation took ~14 tasks; Wizard is likely similar.

---

### Priority 5 — Phase 2 Dashboard slice

**Why:** Network Intelligence Dashboard — the user-facing UI that visualizes buying intent across the user's network as a heatmap, plus the incremental aggregation pipeline that powers it. Depends on Wizard's configurable signals existing.

**How to start:** `cat docs/phase-2/implementation-dashboard.md`, then same flow as Wizard.

**Effort:** multi-session. Larger than Wizard because it involves a real frontend build, not just backend.

---

### Priority 6 — Phase 2 Backfill slice

**Why:** Day-One Backfill — when a new user installs the Chrome extension, immediately seed their workspace with historical posts via Apify integration so they don't see an empty dashboard for 2 weeks waiting for organic feed observation. Depends on Phase 1 extension working (it is) + signals existing (Wizard).

**How to start:** `cat docs/phase-2/implementation-backfill.md`. Will involve work in both `backend/` and `extension/` directories.

**Effort:** multi-session.

---

### Priority 7 — Phase 2 Discovery slice

**Why:** Ring 3 nightly HDBSCAN clustering identifies emerging topics in the user's network that don't match any configured signal — surfacing "things you didn't think to look for." Plus a Weekly Digest Email summarizing the week's intent. Most experimental of the Phase 2 slices — best built last when there's real production data to validate the clustering on.

**How to start:** `cat docs/phase-2/implementation-discovery.md`. Will involve heavy use of pgvector and clustering algorithms.

**Effort:** multi-session, with the most uncertainty of the four.

---

### Priority 8 — GitHub-side email privacy hardening (one-time, requires browser, 30 seconds)

I can't flip these via API. Do them the next time you open GitHub:

1. **github.com → Settings → Emails → "Keep my email addresses private"** ☐
2. **github.com → Settings → Emails → "Block command line pushes that expose my email"** ☐

After these are on, GitHub will reject any future push with a non-noreply email at the protocol level — belt-and-suspenders on top of the global `git config user.email` set this session. Without these, a future session that loses or overrides the global git config could re-introduce the leak before any session-start check fires.

---

### Priority 9 — (Optional) GitHub Support: scrub dangling commits

**Why:** The `git filter-branch` rewrite removed leaked emails from `main`, but GitHub's internal reflog still serves the old commits via direct-SHA URLs (`github.com/nischal94/sonar/commit/<old-sha>`) until garbage collection runs — typically days to weeks for unreferenced objects. Most search-engine crawlers don't index dangling commits, so practical exposure is small.

**If you want full removal:** open a support ticket at https://support.github.com/ requesting:

> Please garbage collect / scrub unreachable objects from `nischal94/sonar`. We performed a `git filter-branch` history rewrite on 2026-04-12 to remove a leaked personal email (`nischalsharma94@gmail.com`) and a hostname-synthesized fallback (`nischal@Nischals-MacBook-Pro.local`). I want the dangling commits removed from the reflog so they aren't accessible via direct-SHA URLs.

**Skip this** if direct-SHA URL exposure is acceptable risk for your use case.

---

### Priority 10 — Phase 3 brainstorming (after Phase 2 ships)

**Why:** Phase 3 is currently TBD with only three rough directions in `sonar/CLAUDE.md`. When Phase 2 is fully shipped (all 4 remaining slices done), the natural next step is a structured brainstorming session to scope Phase 3 properly.

**How to start:** run `superpowers:brainstorming` with the prompt "scope Phase 3 of Sonar — real-time alerts, CRM integrations, team features, or something else." The brainstorming skill will help you decide which direction is highest leverage and produce a `docs/phase-3/design.md`.

**Effort:** one focused session for the design, then multi-session implementation using the same Foundation playbook.

---

## Orthogonal cleanup (not blocking, do when convenient)

- **CHANGELOG release** — when you cut a `v0.1.0` release, move the `[Unreleased]` block to a versioned section. release-drafter is already configured to auto-draft the release notes; you just need to review the draft at https://github.com/nischal94/sonar/releases and click Publish.
- **Pre-commit hooks** — `sonar/CLAUDE.md` Engineering Standards lists pre-commit hooks (block secrets, trailing whitespace, large files, lint violations) as part of the CI tooling goal. Bundle with Priority 1.
- **Type checking** — same. mypy/pyright in CI starts permissive, tightens over time.
- **Eval datasets for LLM features** — `sonar/CLAUDE.md` Engineering Standards "LLM and agent discipline" requires golden datasets + CI gates for prompt-dependent features. Required for Ring 2 semantic matching, context generator, and the future signal proposal wizard.
- **Observability** — structured logging via `structlog`, error tracking (Sentry), Prometheus metrics, health check splits (liveness vs readiness), DB backups with restore drill. Per `sonar/CLAUDE.md` "Observability — required before launch."
- **Rate limiting** — `/auth/token` and any credential-checking endpoint per `sonar/CLAUDE.md` Security. Required before launch.
- **PII / GDPR** — data retention policy + export + deletion endpoints per `sonar/CLAUDE.md` Security. Required before launch.

---

## How to resume in a new Claude Code session

```bash
# Bring the dev environment back up
cd ~/Downloads/Misc/projects/project-ideas/sonar
docker compose up -d postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pytest -q       # expect 54/54 passing

# Launch Claude Code FROM the Sonar directory so per-project memory loads
claude
```

Then ask Claude: **"Read TODO.md and pick up Priority N."**

Per-project memory at `~/.claude/projects/-Users-nischal-Downloads-Misc-projects-project-ideas-sonar/memory/` will only auto-load if you launch `claude` from inside the Sonar directory. If you launch from `~/Users/nischal`, you'll get the home-keyed global memory only — Sonar's `CLAUDE.md` still loads (it's in the repo), but the per-project memory files won't.

---

## Verified state on `main` as of 2026-04-12

| | |
|---|---|
| HEAD SHA | `ab91c1f` |
| Tests | 54/54 passing |
| Open PRs | 0 |
| Open issues | 1 (#40 — dependency audit, deferred) |
| Committer audit | 40 commits = `10312650+nischal94@users.noreply.github.com` (clean noreply, author + committer) + 17 = `noreply@github.com` (GitHub squash-merge), zero leaked emails |
| Branch protection | restored — `allow_force_pushes: false`, `allow_deletions: false`, all other restrictions disabled |
| Active branches on origin | `main` only (all merged PR branches deleted) |
| Draft release | `v0.1.0` at https://github.com/nischal94/sonar/releases (auto-drafted by release-drafter from PR labels) |
| Global git config (this Mac) | `user.email = 10312650+nischal94@users.noreply.github.com`, `user.name = Nischal` |

**Sonar repo is at a clean stopping point.** Pick up any Priority above and go.

---

## First-time setup (preserved from original TODO)

Before running the app for the first time, copy `.env.example` to `.env` and fill in:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `SECRET_KEY` | Any random 32+ char string | ✅ Yes |
| `OPENAI_API_KEY` | platform.openai.com | ✅ Yes (embeddings + GPT-4o mini) |
| `GROQ_API_KEY` | console.groq.com (free) | ✅ Yes (Llama for med/low alerts) |
| `SENDGRID_API_KEY` | sendgrid.com | ❌ Optional |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | twilio.com | ❌ Optional |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram | ❌ Optional |
| `APIFY_API_TOKEN` | apify.com | ❌ Optional |

Once `.env` is ready:
```bash
cd sonar
docker compose up --build
docker compose exec api alembic upgrade head
```

Then open http://localhost:5173
