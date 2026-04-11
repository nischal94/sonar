# Sonar — Project Instructions for Claude Code

**Read this file in full before taking any action in this repo.** It contains every project-specific rule, convention, test baseline, known bug, and phase context you need. If something looks wrong or contradicts what you expect, trust this file over your assumptions — it is updated in the same session as the changes it describes.

---

## Product Overview

Sonar is a **network-aware LinkedIn buying-intent intelligence product**. A Chrome extension passively observes the user's own LinkedIn feed, the backend matches posts against the user's configured signals (what they sell + their ICP), and surfaces the people in their network showing intent to buy. The core differentiation vs. Sales Navigator: **post-level signals from the user's actual network**, not account-level events from a curated corporate database.

- **Repo:** `github.com/nischal94/sonar` (public, MIT license)
- **Product name:** Sonar (finalized)
- **Target users:** Agencies and product companies — multi-tenant SaaS
- **Core data source:** Chrome extension observing the logged-in user's LinkedIn feed (not a crawler, not Apify for random posts)
- **Moat:** network-scoped intent signals, not a stranger firehose

---

## Git Safety Rules (NON-NEGOTIABLE)

These rules exist because a previous session deleted 5,778 lines of planning docs by bundling `git rm` with a `.gitignore` change in one commit. The goal is narrow: prevent destructive-operation disasters. Not every change needs a PR — only destructive operations need strict gating.

### Destructive operations — always require explicit user confirmation
- **NEVER** run `git rm` on tracked files without explicit instruction naming the files being removed.
- **NEVER** commit deletions totaling more than 50 lines of existing tracked content without asking first.
- **NEVER** run `git reset --hard`, `git push --force`, `git push --force-with-lease`, `git clean -f`, or `git checkout --` on tracked paths without explicit confirmation.
- **NEVER** rewrite, amend, or squash commits that have already been pushed.
- **NEVER** delete, truncate, or mass-rewrite files in `docs/` without explicit instruction — these are user planning content, not agent scratch space.
- **NEVER** combine "stop tracking" with "delete content" in one commit. When untracking, use `git rm --cached` as a standalone commit separate from any `.gitignore` change.

### Small changes — direct to main is fine
Direct pushes to main are the default for:
- Typo fixes
- Config tweaks (adding an env var, changing a default)
- Dependency version bumps that pass tests
- File renames via `git mv` (no content change)
- Documentation updates (including updates to this file)
- CLAUDE.md or rules updates
- Single-file small fixes

No branch required. No PR required. Commit, push to main, done.

### Complex changes — use a feature branch + PR
Use a feature branch and open a PR for:
- New features (multiple files, new logic)
- Refactors that change behavior or touch many files
- Database schema changes / migrations
- Security-sensitive changes (auth, crypto, token handling)
- Anything touching more than ~50 lines across multiple files
- Anything the user explicitly says to branch

Branch naming: `feat/<scope>-<short-description>`, `fix/<bug>`, `chore/<topic>`, `refactor/<scope>`.

---

## Review Discipline (HARD RULE — was ambiguous before, now explicit)

**"Self-review" does NOT mean reading the implementer's own report. It means dispatching `superpowers:code-reviewer` as a separate subagent to review the code independently.** This rule exists because an earlier session interpreted self-review as "I trust the implementer's self-assessment" and pushed a security-sensitive PR (PR #4, the python-jose → pyjwt migration) without running the reviewer skill. The reviewer was run retroactively and caught nothing, but the discipline gap was real and could have let a real bug through.

### When to run `superpowers:code-reviewer`

**Always, without exception, before opening any PR.** Including:
- Implementation tasks dispatched via `superpowers:subagent-driven-development` — the skill requires TWO reviews after each task (spec compliance first, then code quality). Both are mandatory. Skipping them is a rule violation, not a shortcut.
- Security-sensitive PRs (auth, crypto, secrets, authorization)
- Database migrations
- Dependency swaps that affect a security-relevant library
- Multi-file refactors

**The one legitimate exception:** trivial docs-only changes that don't touch code (like updating this file). Even then, a human eye on the diff before commit is the bar — not zero review.

### Before merging any PR

1. The user must explicitly say "merge" (or equivalent) in their most recent message.
2. Before clicking merge, dispatch `superpowers:code-reviewer` if it wasn't run during implementation, and wait for approval.
3. If the reviewer finds must-fix issues, fix them first, re-review, then merge.
4. Destructive changes in a PR (file deletions, schema drops, dependency downgrades) require a re-confirm from the user even after they said "merge".

---

## Development Environment

**The Sonar dev stack runs entirely inside Docker containers.** You do NOT need Python, `uv`, postgres, or pgvector installed on the host. The `api` container has everything.

### Prerequisites (host)
- **OrbStack** (or any Docker runtime) running. OrbStack is free for personal indie use; no sign-in required. Start it with `open -a OrbStack` if the daemon isn't responding.
- Nothing else on the host.

### Stack services (`docker-compose.yml` at repo root)
- `postgres` — `pgvector/pgvector:pg16` image, DB/user/pass all `sonar`, port 5432
- `redis` — `redis:7-alpine`, port 6379
- `api` — FastAPI + uv + Python 3.12, reads `.env`, mounts `./backend:/app`
- `worker` — Celery worker
- `beat` — Celery beat
- `frontend` — Vite dev server, port 5173

### Required `.env` at repo root (gitignored)

The backend's `pydantic-settings` requires ALL of these keys to exist at startup. For Foundation/Phase-1 dev work, placeholder values are fine because tests mock the LLM and messaging providers. When you actually need real LLM calls, replace the placeholders.

```
DATABASE_URL=postgresql+asyncpg://sonar:sonar@postgres:5432/sonar
REDIS_URL=redis://redis:6379/0
SECRET_KEY=local-dev-secret-key-do-not-use-in-prod-replace-me
OPENAI_API_KEY=placeholder-openai-key
GROQ_API_KEY=placeholder-groq-key
SENDGRID_API_KEY=placeholder-sendgrid-key
SENDGRID_FROM_EMAIL=dev@localhost
TWILIO_ACCOUNT_SID=placeholder-twilio-sid
TWILIO_AUTH_TOKEN=placeholder-twilio-token
TWILIO_WHATSAPP_FROM=+10000000000
TELEGRAM_BOT_TOKEN=placeholder-telegram-token
APIFY_API_TOKEN=placeholder-apify-token
EXTENSION_VERSION=1.0.0
```

Note: the hostnames `postgres` and `redis` are docker-compose service names, only resolvable inside the compose network. They are NOT `localhost` from the host's perspective. If you ever see a connection-refused error hitting `localhost:5432`, check whether you're running the command inside a container or on the host.

### Bringing the stack up
```bash
docker compose up -d --build postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pytest   # sanity check
```

### Running commands against the backend

**All backend commands run inside the `api` container. Never use `cd backend && uv run <x>`.** The host does not have `uv`, Python, or any of the deps. The correct pattern is:

```bash
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic downgrade -1
docker compose exec -T api pytest
docker compose exec -T api pytest tests/test_signal_model.py -v
docker compose exec -T api uv sync --all-extras     # after editing pyproject.toml
docker compose exec -T api python scripts/foo.py
```

The `-T` flag disables TTY allocation, which you want when piping or capturing output.

### psql for inspecting the database
```bash
docker compose exec -T postgres psql -U sonar -d sonar -c "\dt"
docker compose exec -T postgres psql -U sonar -d sonar -c "\d signals"
```

---

## Test Baseline (as of `1f13583`)

**The test suite has 31 tests total.** As of the PR #4 merge, the baseline on `main` is:

- **26 passing** — core pipeline, matcher, scorer, context_generator, keyword_filter, feedback trainer, profile extractor
- **5 failing** — all pre-existing Phase 1 bugs, none blocking Foundation:
  1. `test_delivery_router.py::test_router_calls_slack_for_configured_workspace` — delivery router assertion mismatch
  2-4. Three tests failing with `module 'bcrypt' has no attribute '__about__'` — passlib pinned on an incompatibility with bcrypt 4.1+. See "Known Pre-existing Bugs" below.
  5. One auth-related test that transitively hits the same passlib issue
- **0 errors** (was 4 errors earlier; the conftest fixture bug was fixed on the `feat/phase-2-foundation-impl` branch and will come back to main when that branch merges)

**When running Foundation implementation on the `feat/phase-2-foundation-impl` branch, expect the baseline to be 26 pass + 5 new model tests = 31 passing (plus the same 5 pre-existing failures).** Any new test failure outside that set is a regression you caused — stop and debug.

---

## Known Pre-existing Bugs (not blocking Foundation, but tracked)

These are tracked in GitHub issues (to be opened — see the session's remediation plan). Do NOT include fixes for these in Phase 2 Foundation implementation; they belong in their own focused PRs.

1. **`passlib` + `bcrypt>=4.1` incompatibility** — `passlib` references `bcrypt.__about__` which was removed in bcrypt 4.1. Three tests fail as a result. Fix: pin `bcrypt<4.1` or swap `passlib` for `argon2-cffi` / `bcrypt` directly. Security-sensitive so belongs in its own PR.

2. **`test_router_calls_slack_for_configured_workspace`** — asserts Slack sender's `.send()` was called once, but the router doesn't call it. Either the router logic was never finished or the test is outdated. Needs investigation.

3. **pytest-asyncio strict-mode fixture issue on `main`** — `@pytest.fixture` decorators on `async def` fixtures are silently ignored under pytest-asyncio 1.x strict mode, causing tests that depend on `test_engine`/`db_session` to error out at collection time. Already fixed on `feat/phase-2-foundation-impl` (commit `b29afa5`); will propagate to main when Foundation merges.

4. **`auth.py` hardening — optional defense-in-depth** — PR #4 reviewer suggested adding `options={"require": ["exp", "sub"]}` to `jwt.decode()` so missing-claim failures become explicit PyJWT errors rather than relying on the `KeyError` catch. Not blocking, worth a follow-up.

---

## Nomenclature

### File and directory structure

```
sonar/
├── CLAUDE.md                              # This file
├── CHANGELOG.md                           # Running log of notable changes
├── README.md                              # Public-facing product overview
├── TODO.md                                # Setup checklist (real API keys etc.)
├── .env                                   # Local config (gitignored — see Development Environment)
├── docker-compose.yml                     # Full dev stack
├── backend/                               # FastAPI + Celery + SQLAlchemy
├── frontend/                              # React + Vite + TypeScript
├── extension/                             # Chrome MV3 extension
└── docs/
    ├── phase-1/
    │   ├── design.md                      # Original Phase 1 product design (historical)
    │   └── implementation.md              # Phase 1 implementation plan (completed)
    ├── phase-2/
    │   ├── design.md                      # Phase 2 design spec
    │   ├── implementation-foundation.md   # Phase 2 Foundation plan (in progress)
    │   ├── implementation-wizard.md       # Phase 2 Wizard plan (future)
    │   ├── implementation-dashboard.md    # Phase 2 Dashboard plan (future)
    │   ├── implementation-backfill.md     # Phase 2 Backfill plan (future)
    │   └── implementation-discovery.md    # Phase 2 Discovery plan (future)
    └── phase-3/                           # (does not exist yet)
```

**Rules:**
- Group docs by phase as directories: `docs/phase-N/`.
- Inside each phase directory:
  - `design.md` — the spec ("what and why"). Always this name.
  - `implementation.md` — the implementation plan, when a phase has **one** plan (like Phase 1).
  - `implementation-<feature>.md` — the implementation plan for each shippable slice, when a phase has **multiple** plans (like Phase 2). The `implementation-` prefix keeps the naming consistent with single-plan phases; the `<feature>` suffix distinguishes the slice.
- No date prefixes in filenames — git history has dates, filenames are for humans.
- No `specs/` vs `plans/` subdirectories — the filename carries the distinction.
- No `archive/` directory — old phases are just `phase-N/`, not "archived." They stay tracked and readable.
- No `sonar-` prefix in filenames — we're already in the Sonar repo.
- No `docs/superpowers/` subdirectory — that was internal tooling naming, removed.

### Branch naming

| Prefix | Purpose | Example |
|---|---|---|
| `feat/` | New feature work | `feat/phase-2-foundation-impl` |
| `fix/` | Bug fixes | `fix/migrate-jose-to-pyjwt` |
| `chore/` | Tooling/config | `chore/dependabot-config` |
| `docs/` | Docs-only changes | `docs/phase-2-spec` |
| `refactor/` | Non-feature refactors | `refactor/pipeline-structure` |

Feature branches for Phase N work follow `feat/phase-N-<feature>` or `feat/phase-N-<feature>-impl` when distinguishing plan from implementation. Phases are sequential: `feat/phase-2-wizard` branches from main *after* Foundation is merged, not from the Foundation branch itself.

### Commit messages (Conventional Commits)

```
<type>(<scope>): <short description>

<optional body explaining the why, not the what>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`.
Scopes for this repo: `pipeline`, `models`, `services`, `workers`, `frontend`, `extension`, `db`, `scripts`, `auth`, or omit when it's broad.

### Conversation terminology

| Avoid | Use |
|---|---|
| "Plan 1", "Plan 2 of 5" | "Phase 2 Foundation plan", "Foundation" |
| "Sub-plan", "sub-project" | Just the feature name |
| "the spec" (ambiguous) | "the Phase 2 spec" |
| "the PR" (ambiguous) | "the Foundation PR", "PR #5" |
| "the doc" (ambiguous) | Specific name |

When referencing by number (necessary evil), use the GitHub-assigned PR number.

---

## Phase Roadmap

- **Phase 1** — ingest pipeline, capability profile, signal matching, alerts, delivery channels. Historical docs at `docs/phase-1/`. Status: code shipped but never end-to-end tested until the Phase 2 Foundation session fixed the dev environment.
- **Phase 2** — Signal Configuration Wizard, Day-One Backfill, Network Intelligence Dashboard, Three-Ring Trending Topics, Weekly Digest Email. Design spec at `docs/phase-2/design.md`. Implementation split into 5 sequential plans.
  - **Foundation** — data model + pipeline refactor + Ring 1/2 matching. *In progress — see status below.*
  - **Wizard** — signal configuration wizard backend + frontend
  - **Dashboard** — network intelligence dashboard + incremental aggregation
  - **Backfill** — day-one backfill (extension + Apify)
  - **Discovery** — Ring 3 nightly clustering + weekly digest
- **Phase 3** — TBD (real-time alerts, CRM integrations, team features)

## Phase 2 Foundation — Current Status

**Branch:** `feat/phase-2-foundation-impl`

**Completed (5 of 14 tasks):**
- ✅ Task 1 — Alembic migration 002 + pgvector ORM (`cd656b0`, `15a5e31`)
- ✅ Task 2 — `Signal` ORM model (`4b05098`)
- ✅ Task 3 — `PersonSignalSummary` ORM model (`77ae6dd`)
- ✅ Task 4 — `CompanySignalSummary` ORM model (`3b802a2`)
- ✅ Task 5 — `Trend` ORM model (`2720f44`)
- ✅ Task 7 — `Workspace.backfill_used` (absorbed into Task 1 fixup commit `15a5e31`)
- ✅ Prerequisite — conftest async fixture fix (`b29afa5`)

**Remaining (8 tasks):**
- Task 6 — Add Phase 2 JSONB columns to Post model
- Task 8 — Ring 1 matcher service (keyword matching, pure function)
- Task 9 — Ring 2 matcher service (pgvector similarity query)
- Task 10 — Extend `context_generator` prompt with `themes` output
- Task 11 — Scorer accepts `keyword_match_strength` input
- Task 12 — Pipeline refactor: keyword filter from gate to scoring input (BIGGEST task — requires spec + code quality review both)
- Task 13 — One-shot `backfill_signals_from_keywords.py` script + smoke test
- Task 14 — Regression tests + final verification

**Branch sync note:** The `feat/phase-2-foundation-impl` branch was created before PR #4 (pyjwt migration) merged to main. When resuming Foundation work, first merge main into the feature branch to pick up the pyjwt change:
```bash
git checkout feat/phase-2-foundation-impl
git merge main
```

---

## Tech Stack

**Backend:** FastAPI, SQLAlchemy 2.x (async), Alembic, Celery, Redis, Postgres + pgvector, OpenAI SDK + Groq SDK for LLM providers, PyJWT for auth (migrated from python-jose in PR #4 to drop ecdsa vulnerability).

**Frontend:** React 18, Vite 6, TypeScript, axios, react-router-dom v6.

**Extension:** Chrome Manifest V3, plain JS (no bundler).

**Dev infra:** Docker Compose via OrbStack (or any Docker runtime).

**Signal matching:**
- Keyword pre-filter → embedding cosine similarity → 3-dimension combined score (relevance 50%, relationship 30%, timing 20%)
- Relationship score defaults by connection degree: 1st=0.90, 2nd=0.60, 3rd=0.30 + interaction boost
- Timing decays linearly over 24 hours
- HIGH priority (≥0.80) → GPT-4o-mini for outreach drafts
- MEDIUM/LOW → Groq + Llama-3.3-70B
- Thresholds are per-workspace tunable via `workspaces.matching_threshold` (default 0.72)

**Embedding model:** OpenAI `text-embedding-3-small`, 1536 dim. This is hardcoded across the system — DO NOT introduce a second embedding model without migrating the existing stored vectors.

---

## Build / Test Commands Reference

```bash
# Start the stack (first time or after Dockerfile change)
docker compose up -d --build

# Apply all migrations (Phase 1 + Phase 2 if on feature branch)
docker compose exec -T api alembic upgrade head

# Rollback the most recent migration
docker compose exec -T api alembic downgrade -1

# Run the full test suite
docker compose exec -T api pytest

# Run a single test file
docker compose exec -T api pytest tests/test_signal_model.py -v

# Run a single test function
docker compose exec -T api pytest tests/test_ring1_matcher.py::test_should_match_exact_phrase -v

# Install / update Python deps after editing pyproject.toml
docker compose exec -T api uv sync --all-extras

# Inspect the database
docker compose exec -T postgres psql -U sonar -d sonar -c "\dt"
docker compose exec -T postgres psql -U sonar -d sonar -c "\d signals"

# Frontend (separate container)
cd frontend && npm install && npm run build

# Extension: load `extension/` as unpacked extension in Chrome
```

---

## File Editing Conventions

- **Prefer `Edit` over `Write`** for existing files. `Write` silently overwrites the entire file contents if you've seen the file in the current session, which is dangerous for files you haven't fully read.
- **Read before editing.** This is enforced by the Edit tool and for good reason.
- **Small-scope commits.** One concern per commit, even if multiple concerns are being fixed in the same session. Separate commits for: lockfile regeneration, dependency swap, code using the dependency, tests.

---

## Quick Reference — What to do first when resuming this project

1. `git status` on the current branch
2. `git log --oneline -10` to see recent commits
3. `docker compose ps` to verify stack is running (start with `docker compose up -d` if not)
4. `docker compose exec -T api pytest -q 2>&1 | tail -5` to verify test baseline is intact
5. Read this file (`CLAUDE.md`) fully
6. Check `docs/phase-2/implementation-foundation.md` for Phase 2 task status
7. Check open PRs and Dependabot alerts: `gh pr list && gh api repos/nischal94/sonar/dependabot/alerts --jq '.[] | select(.state == "open")'`
