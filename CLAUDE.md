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

## Engineering Standards

Every Phase 2+ contribution aims to meet these. When skipping something, call it out explicitly in the PR.

### CI and code quality
- **CI must run on every PR** — build, test, lint, format check, type check. Currently missing; highest-priority tech debt.
- **Single linter/formatter per language** — `ruff` for Python, `biome` (or `eslint`+`prettier`) for TS. Green on every PR.
- **Pre-commit hooks** — block secrets, trailing whitespace, large files, lint violations before the commit happens.
- **Type checking in CI** — `mypy` or `pyright` on Python, `tsc --noEmit` on TS. Start permissive, tighten over time.

### Testing
- **Green main, always.** No "N failures are pre-existing, it's fine" baselines. Every failing test is either fixed, deleted, or tracked as a GitHub issue with a deadline.
- **Deterministic tests** — no `datetime.now()`, no unseeded random, no network. Use `freezegun` / seeded fixtures.
- **Test behavior, not implementation.** Assert on observable outcomes. Mock only at system boundaries (LLM providers, external HTTP, email/SMS).
- **Test coverage is a floor, not a ceiling.** 70-85% meaningful > 100% trivial. `pytest --cov` reported per PR.

### Security
- **Secrets in `.env` (gitignored) for dev only.** Production secrets come from a secrets manager at deploy time. `SECRET_KEY` rotates on a schedule.
- **Rate limiting on `/auth/token`** and any endpoint that checks credentials. Required before launch.
- **JWT with `algorithms=[...]` always.** Never trust the `alg` header. Enforced in `auth.py` (PR #4).
- **All user input validated at the boundary via Pydantic.** Never trust LLM output, LinkedIn post content, or webhook payloads without validation. Parameterized SQL always; never f-string a query.
- **PII and GDPR:** user data has a documented retention policy. Data export and deletion endpoints must exist before launch.

### LLM and agent discipline — Sonar is LLM-heavy; read carefully
- **Prompts are code.** Live in `app/prompts/<name>.py`, version-controlled, reviewed on every change. No dynamic string-building into system prompts.
- **Prompts live in `app/prompts/<name>.py`.** Each prompt module exports `PROMPT_VERSION: str`, a static `SYSTEM_PROMPT`, a `build_user_message(...)` function that composes the user turn (the ONLY place user input is interpolated), and a `RESPONSE_JSON_SCHEMA` for OpenAI Structured Outputs. Every call logs `PROMPT_VERSION` alongside. Bump the version on every content change. First entry under this convention: `app/prompts/propose_signals.py` (Wizard slice, 2026-04-17).

- **`max_tokens` on every LLM call.** No exceptions. Input token count estimated before sending to catch blowup early.
- **Cost tracked per workspace/feature.** Log `{workspace_id, feature, input_tokens, output_tokens, cost_usd}` on every call. Hard per-workspace daily cap so runaway loops can't eat the budget.
- **Single routing layer for model selection.** Cheap models (Groq) for bulk work; expensive models (`gpt-5.4-mini`) for critical work. Fallback chains defined explicitly. Upgraded from `gpt-4o-mini` on 2026-04-17 as part of the Wizard slice (PR #64). Single routing layer preserved via `OPENAI_MODEL_EXPENSIVE` constant in `app/config.py`. To bump again, edit the constant and update this rule in lockstep.
- **External HTTP integrations follow the Apify/SendGrid pattern.** Define a `Protocol` class (the interface), a `Real{Service}` implementation (production), and a `get_{service}` factory used with FastAPI `Depends()`. Tests inject a `Fake{Service}` via `app.dependency_overrides` — never `patch()` on module globals. See `app/services/apify.py` for the canonical example added in the Backfill slice (2026-04-18).
- **Prompt injection defense is mandatory.** User-controlled input (LinkedIn post content!) goes in the **user message** position only. Never f-string user input into the system prompt.
- **LLM output is untrusted.** Parse with Pydantic / strict JSON schemas. Retry on parse failure (budget: 2 retries). Never pass output directly to shell / SQL / file paths without validation.
- **Structured outputs where supported.** OpenAI `response_format=<PydanticModel>` is the default path.
- **Embedding model consistency.** `text-embedding-3-small` (1536 dim) is the single system embedding. Never mix models; it silently breaks cosine similarity.
- **Eval datasets for LLM features.** Golden dataset + CI gate for every prompt-dependent feature before it ships. Required for Ring 2 semantic matching, context generator, and future signal proposal wizard.
- **Response caching** by hash of `(provider, model, prompt, temperature)`. Embeddings especially — cache by content hash; it's the highest-leverage cost reduction we can make.
- **Temperature = 0 for classifiers and extractors**, higher (0.5-0.8) for creative tasks (outreach drafts, summaries). Document the choice per prompt.
- **Human-in-the-loop for high-stakes LLM decisions** — outreach drafts, signal proposals, anything customer-facing needs a review queue.
- **Incremental aggregation pattern.** Pipeline post-scoring work (updating `person_signal_summary`, Redis counters, etc.) lives in `app/workers/incremental_trending.py` and chains to the end of `pipeline.py`. Target runtime <100 ms per call. Future per-post aggregation features (Ring 3 counters, company rollups) follow the same chain-at-end pattern — do NOT inline new aggregation into `pipeline.py` itself. First entry under this convention: Dashboard slice (session 5, 2026-04-18).

### Agent workflow — how Claude Code sessions work on this project
- **Read this file in full at session start.** Everything you need is here. If it's out of date, update it in the same commit as the state change — never "cleanup PR later."
- **Verify before trusting memory or stale context.** Before claiming a file or resource exists, verify with `ls` / `git` / `gh api`. In-session context ages within a single session; stored memory ages faster.
- **Code review means dispatching `superpowers:code-reviewer`, not self-review.** Never merge without it.
- **Two-stage review after each task** — spec compliance first, then code quality. Both mandatory; skipping them violates the subagent-driven-development skill.
- **Multi-task plans use `superpowers:subagent-driven-development`** — fresh subagent per task, never batched into one dispatch.
- **Answer subagent questions completely before letting them proceed.** Questions before work are free; guesses after work are expensive.
- **Don't delegate understanding.** The controller must understand the task well enough to judge the result. "Figure it out for me" is an anti-pattern.

### Observability — required before launch
- **Structured logging** via `structlog` with request-ID correlation threading HTTP → Celery → DB.
- **Error tracking** (Sentry or equivalent) capturing every unhandled exception in prod with stack trace + correlation ID.
- **Metrics exported** (Prometheus format via `prometheus-fastapi-instrumentator`): request rate, error rate, p99 latency, Celery queue depth, DB connection pool usage.
- **Health checks split: liveness vs readiness.** `/health/live` for orchestrator restart decisions, `/health/ready` for load-balancer routing.
- **Database backups** with a documented, tested restore drill.
- **LLM cost metric per workspace** as a first-class dashboard.

### Database and migrations
- **Every migration has a working `downgrade()`.** Tested against realistic data before merge (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`).
- **Expand / contract pattern for breaking schema changes.** Never rename or drop a column in one migration while old code is still running.
- **Never add `NOT NULL` without a default** — it locks large tables and takes production down.
- **pgvector embedding columns in BOTH the migration and the ORM** — use `pgvector.sqlalchemy.Vector(1536)` in the ORM so `Base.metadata.create_all` builds it for tests.
- **Don't bundle Phase 1 gap fixes into Phase 2 migrations without an explicit comment** explaining what you're fixing and why.
- **NEVER run `alembic downgrade base` (or any `alembic downgrade` below `head`) against the `sonar` dev DB.** It runs `DROP TABLE` on every table and wipes all rows. For migration round-trip tests, override `sqlalchemy.url` inside the test fixture to point at `sonar_test` — see `backend/tests/test_migration_008_009_010.py::alembic_cfg` for the canonical pattern. Never embed `alembic downgrade` as a shell-step "fresh start" in an implementation plan. Phase 2.6 Task 1 (2026-04-21) lost all session-8 dogfood data this way.
- **Snapshot the dogfood DB before any multi-migration phase.** First command of any migration-touching session:
  ```bash
  mkdir -p snapshots/
  docker compose exec -T postgres pg_dump -U sonar sonar > snapshots/$(date +%Y-%m-%d)-pre-<phase>.sql
  ```
  `snapshots/` is gitignored (dumps may carry PII). Local safety only. Without this, an accidental destructive command during plan execution has no recovery path.
- **Codex review is mandatory for plans that touch migrations or shared DBs.** "Any plan that runs commands against shared DBs must be codex-reviewed" — time-saved by skipping is minutes; time-lost to an unrecovered wipe is hours-to-days. Phase 2.6's destructive step would have been caught by codex.

### Deployment and release
- **Semver + git tags** on every release. No "main-only" implicit versions.
- **CHANGELOG.md** updated under `[Unreleased]` as PRs merge; moved to versioned sections on release.
- **Feature flags for gradual rollout.** Every new user-visible feature ships behind a flag that can be flipped off without a redeploy.
- **Rollback plan documented per deploy.** "How do we undo this?" is answered before the deploy, not during.
- **Environment parity** — dev / staging / prod run the same container images; only the injected config differs.

### Process discipline
- **GitHub Issues for every bug, tech-debt item, and follow-up.** Not in commit messages, not in CLAUDE.md prose. In issues, with labels.
- **Conventional Commits** (`feat(scope): ...`, `fix(scope): ...`). Commit messages explain the *why*, not the *what*.
- **Issue and PR templates** in `.github/` — minimal bug template + minimal PR template.
- **TODO.md is the single source of truth for project status and next-session work.** Read it top-to-bottom to resume. Required section order: Next Session Action Plan → Phase status → Reference processes → Open issues → Orthogonal cleanup → Session log → Resume / setup commands. TODO.html is a styled mirror that must be updated in the same commit with the same facts (main HEAD, tests, CI, action items, issues, session log entries).

- **`docs/session-notes/` is retired (2026-04-20, session 7).** Files for sessions 1–7 are preserved as historical artifacts, but no new entries are added. Long-form forensics have better homes:
  - **PR descriptions** for the "why this fix was needed" context (GitHub preserves them, searchable from the commit).
  - **Commit message bodies** for per-commit reasoning.
  - **Issue bodies** for "why this matters" context on filed follow-ups.
  - **CLAUDE.md Lessons Learned** for durable rules codified from a session's discovery.
  - **TODO.md Session log** (below) for the terse chronological thread — 3-5 bullets per session, what merged, what was filed, any structural changes.

- **TODO.md's Next Session Action Plan section is a numbered ordered list, not a prose narrative.** Rule codified in session 7 after the next-session plan existed only in the chat transcript (which vanishes) while TODO.md held a narrative paragraph. The next session must be able to read TODO.md and execute item 1 without reconstructing context from git log or chat.

  **Required structure for the Next Session Action Plan section:**

  ```markdown
  ## Next Session Action Plan (last rewritten YYYY-MM-DD, end of session N)

  **State at resume:** main HEAD = <sha>. Tests: <N passing + M skipped>. CI: <status>. Working tree: <clean/dirty>.

  ### 1. <emoji> <short action title>

  **What:** concrete step the next session executes.
  **Why now:** rationale for this being the next thing, not a different item.
  **Blocks:** what this blocks downstream / what blocks this upstream.
  **Effort:** rough time estimate.

  ### 2. ... (same template)
  ```

  **Template rules:**
  - Numbered, in execution order, top-down. Item 1 is literally the first thing to do.
  - Each item has all four fields (What / Why now / Blocks / Effort). No prose-only items.
  - Rewritten end-to-end every session — not patched, not appended. If an item was completed, delete it; if still relevant, re-evaluate its position.
  - No "Priority A / Priority B / Priority C" static taxonomy — those are buckets that stale quietly. Ordered numbered list only.
  - Pre-launch gaps that are NOT next-session-eligible (e.g. PII/GDPR endpoints, observability baseline) go in a dedicated lower-priority item with an explicit "not next-session work" label, so they're tracked without polluting the active plan.

- **Session log section: append the new session's entry, don't rewrite.** At session end, prepend a new `### Session N — YYYY-MM-DD — <title>` block to the top of the Session log (newest first). 3-5 bullets max. Pointers (PR links, issue links) over narrative. If the session genuinely produced a longer forensic that doesn't fit, write it into the relevant PR description or a CLAUDE.md Lessons Learned entry, not a separate file.

---

## Lessons Learned — Rules Codified from Prior Sessions

The rules below were added after specific failures in prior Claude Code sessions. Each references the Sonar issue / PR where the bug manifested so the pattern is traceable. When you hit a similar pattern, apply these rules without waiting to rediscover them.

### Python test mocking: prefer DI, patch at the lookup site

`unittest.mock.patch("X.Y")` does NOT affect importers that did `from X import Y` at module load time — the importer has its own local binding that the patch never touches. This bug shipped **twice** in Sonar before being fixed structurally:

- **Issue #6 / PR #16** — `test_delivery_router.py` patched `app.delivery.router.SlackSender`, but `CHANNEL_SENDERS` held a direct reference to the class captured at import time. The real `SlackSender` ran, raised, `asyncio.gather(return_exceptions=True)` swallowed the error, and the mock assertion failed with a confusing "not called" message.
- **Issue #11 / PR #20** — `test_e2e.py` patched `app.services.embedding.embedding_provider`, but `app.routers.profile` had already done `from app.services.embedding import embedding_provider`. The router's local binding was untouched; the real `_LazyEmbeddingProvider` instantiated a client with the placeholder API key and 401'd.

**Rule when adding or modifying Python tests:**

1. **Router-layer dependencies** — use FastAPI `Depends()`. Tests use `app.dependency_overrides[get_provider] = lambda: fake`. The override layer sits above Python's import binding and cannot be defeated by `from ... import ...`. See `backend/app/services/embedding.py::get_embedding_provider`, `backend/app/services/llm.py::get_llm_client`, and `backend/app/routers/profile.py::extract_profile` for the canonical pattern.
2. **Service-layer dependencies** — use constructor injection with a module-level default. Tests pass a fake directly. See `backend/app/delivery/router.py::DeliveryRouter(senders=...)` for the canonical pattern.
3. **When `patch()` is unavoidable** — patch at the *lookup site* (the module that references the name), not the *definition site*. Example: `patch("app.routers.profile.embedding_provider")`, not `patch("app.services.embedding.embedding_provider")`.
4. **Never introduce a new module-level singleton without a `get_*` factory or a constructor-injected seam.** The footgun only exists when there's a singleton and no DI path.

### asyncio.gather: iterate results, re-raise CancelledError

`await asyncio.gather(*tasks, return_exceptions=True)` returns exception objects as values. Discarding the return value silently drops every failure — no log, no metric, no breadcrumb. This was the systemic weakness that let issue #6 hide for months: the real `SlackSender` was raising, `gather` swallowed it, the mock assertion failed with a confusing "not called" error. Codified in PRs #24 (issue #18) and #39 (issue #25).

**Rule when calling `asyncio.gather(..., return_exceptions=True)`:**

1. **Always iterate results.** Never discard the return value.
2. **Correlate each result to its input** via a parallel list captured in the same loop pass (e.g. `invoked_channels` alongside `tasks` in `DeliveryRouter.deliver`). A failure log must be able to name the failing component.
3. **Re-raise `CancelledError` before the generic `Exception` check.** `asyncio.CancelledError` inherits from `BaseException`, not `Exception`, so `isinstance(result, Exception)` silently skips it. Swallowing cancellation violates structured concurrency — if the outer task was cancelled, propagate it. See `backend/app/delivery/router.py::DeliveryRouter.deliver` for the canonical pattern.
4. **Log each exception** with the repo's `[Module] Operation failed: reason. context=...` format from `~/.claude/rules/error-messages.md`, passing `exc_info=result` to preserve the stack trace.

### Frontend dependency bumps require a human in the browser

Sonar's frontend (`frontend/`) has **no automated integration tests**. `npm run build` succeeds if the bundle compiles — it proves nothing about whether React rendering, routing, auth flow, form submission, or dashboard interactions actually work at runtime. The backend suite (54/54 green) says nothing about a React or React Router regression. Codified from the April 2026 dependency-audit session (issue #40).

**Rule when evaluating frontend dependency PRs:**

1. **Minor/point bumps in the same major line** — verify `npm run build` succeeds, then merge.
2. **Major version bumps** (React, Vite, `react-router-dom`, `@vitejs/plugin-react`, `react-dom`) — never blind-merge. These packages are tightly coupled; they must be evaluated as ONE coordinated upgrade, not individually.
3. **Any frontend major bump** — requires a human running `docker compose up -d frontend`, navigating every route in the browser, and exercising auth + ingest + alerts before the PR merges. If no human is available, defer via a tracking issue and close the PR with a reference. Issue #40 is the canonical template.
4. **Do not trust the backend test suite** for frontend regressions. Backend 54/54 green says nothing about dashboard behavior.

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
RESEND_API_KEY=placeholder-resend-key
RESEND_FROM_EMAIL=onboarding@resend.dev
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

All of these now have GitHub issues. Do NOT include fixes for these in Phase 2 Foundation implementation; each belongs in its own focused PR.

1. **`passlib` + `bcrypt>=4.1` incompatibility** — Issue [#5](https://github.com/nischal94/sonar/issues/5). `passlib` references `bcrypt.__about__` which was removed in bcrypt 4.1. Three tests fail as a result. Fix: pin `bcrypt<4.1` or swap `passlib` for `bcrypt` / `argon2-cffi` directly. Security-sensitive so belongs in its own PR.

2. **`test_router_calls_slack_for_configured_workspace`** — Issue [#6](https://github.com/nischal94/sonar/issues/6). Asserts Slack sender's `.send()` was called once, but the router doesn't call it. Either the router logic was never finished or the test is outdated / the mock is patched at the wrong import path. Needs investigation.

3. **`auth.py` hardening — defense-in-depth** — Issue [#7](https://github.com/nischal94/sonar/issues/7). Add `options={"require": ["exp", "sub"]}` to `jwt.decode()` so missing-claim failures become explicit PyJWT errors rather than relying on the `KeyError` catch. Not blocking, worth a follow-up.

4. **`Connection` model missing FK constraints** — Issue [#8](https://github.com/nischal94/sonar/issues/8). `workspace_id` and `user_id` columns on `Connection` are declared without `ForeignKey(...)` — the DB-level FK exists but the ORM doesn't know about it. Same pattern as `Post.connection_id` which was fixed during Task 1 fixup.

5. **conftest `event_loop` vs `test_engine` scoping trap** — Issue [#9](https://github.com/nischal94/sonar/issues/9). `conftest.py` keeps a session-scoped `event_loop` fixture while `test_engine` is now function-scoped. Tests pass today because pytest-asyncio 1.x tolerantly ignores the override and emits a DeprecationWarning. Will break when pytest-asyncio 2.x removes the shim. Should be addressed before Task 14 final verification.

6. **pytest-asyncio strict-mode fixture issue** — already fixed on `feat/phase-2-foundation-impl` (commit `b29afa5`); will propagate to main when Foundation merges. The fix is what unblocked Tasks 2-5 and Phase 1 tests running at all.

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
- HIGH priority (≥0.80) → `gpt-5.4-mini` for outreach drafts
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
