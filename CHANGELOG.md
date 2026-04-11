# Changelog

All notable changes to Sonar are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [Unreleased]

### Added
- `CHANGELOG.md` — running log of notable changes across the project
- `CLAUDE.md` — comprehensive project instructions for AI agents, rebuilt to reflect actual project state
- `docs/phase-2/design.md` — Phase 2 Network Intelligence design spec (Signal Configuration Wizard, Day-One Backfill, Network Intelligence Dashboard, Three-Ring Trending Topics, Weekly Digest Email)
- `docs/phase-2/implementation-foundation.md` — Phase 2 Foundation implementation plan (14 tasks, TDD-structured)
- `docs/phase-1/design.md` — Original Phase 1 product design (restored from deleted history)
- `docs/phase-1/implementation.md` — Original Phase 1 implementation plan (restored from deleted history)
- Minimal branch protection on `main` — blocks force-pushes and branch deletion, but does NOT require PRs for small changes (direct pushes still allowed)
- Dependabot alerts monitoring via `gh api repos/nischal94/sonar/dependabot/alerts`
- **Phase 2 Foundation (PR #10):** data model, matchers, and pipeline refactor. Adds Alembic migration 002 with new tables `signals` (pgvector + HNSW index), `person_signal_summary`, `company_signal_summary`, `trends`; JSONB columns on `posts` (`ring1_matches`, `ring2_matches`, `themes`, `engagement_counts`); `connections.mutual_count`; `workspaces.backfill_used`. Four new ORM models mirroring the migration. Two new services: `app/services/ring1_matcher.py` (pure-function keyword matching) and `app/services/ring2_matcher.py` (pgvector cosine-similarity query with configurable cutoff). `AlertContext` dataclass gains `themes: list[str]`. `scorer.compute_combined_score` gains `keyword_match_strength: float = 0.0` boosting relevance by up to +0.15. One-shot `scripts/backfill_signals_from_keywords.py` migrates existing `signal_keywords` arrays into the new `signals` table. 24 new tests across 5 files.
- **Regression test (PR #24):** `test_router_logs_channel_failure_and_continues_siblings` pins three guarantees — failing channels don't cancel siblings, failures log once with correlated context (channel, alert id, workspace id), `exc_info=result` kwarg preserved so stack traces aren't silently dropped.
- **Provider DI via FastAPI `Depends()` (closes #21):** `get_embedding_provider()` and `get_llm_client()` factories in `app/services/embedding.py` and `app/services/llm.py`. `app/routers/profile.py` uses `Depends(get_embedding_provider)` and `Depends(get_llm_client)`; `extract_capability_profile` accepts an optional `llm_override` parameter. Tests now swap providers via `app.dependency_overrides`, which sits above Python's import binding and cannot be defeated by `from ... import ...`. `test_e2e.py` migrated from `patch()` to `dependency_overrides`. Also lands `Sender` + `SenderFactory` Protocols in `app/delivery/router.py` so `DeliveryRouter(senders=...)`'s type hint documents the real contract instead of the loose `dict[str, type]`.
- **Autouse provider-singleton reset fixture (closes #22):** `conftest.py::_reset_provider_singletons` clears `embedding._provider`, `llm._openai`, `llm._groq` after each test so a real client accidentally populated by one test cannot leak into another. Four lines of cross-test state hygiene.
- **`DeliveryRouter` re-raises `CancelledError` (closes #25):** `gather` results loop now checks `isinstance(result, asyncio.CancelledError)` before the `Exception` branch and re-raises. `CancelledError` inherits from `BaseException` so the existing `Exception` check was already skipping it — but swallowing cancellation violates structured concurrency. New regression test `test_router_propagates_cancellation` asserts `CancelledError` propagates out of `deliver()`.
- **`.github/` project infrastructure:** first `.github/` scaffold for the repo.
  - `.github/workflows/release-drafter.yml` + `.github/release-drafter.yml` — release-drafter v6 runs on every push to `main` and every PR event. An autolabeler parses Conventional Commits prefixes in PR titles (`feat`, `fix`, `refactor`, `docs`, `chore`, `security`, …) and tags PRs automatically. A GitHub Release draft is continuously updated with merged PRs grouped into Keep-a-Changelog categories (Added / Changed / Fixed / Security / Docs / Tests / Chores). Releases are *drafted*, never auto-published.
  - `.github/pull_request_template.md` — summary/changes/test-plan/checklist layout, including an explicit reminder to update `CHANGELOG.md` under `[Unreleased]` and to run `superpowers:code-reviewer` for security-sensitive PRs.
  - `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md` + `config.yml` — structured issue templates; blank issues disabled.
  - `.github/dependabot.yml` — weekly updates for backend (`pip` ecosystem against `/backend/pyproject.toml`) and frontend (`npm` against `/frontend`), plus monthly updates for `github-actions`. Labels `dependencies` + ecosystem tag, commit prefix `chore(deps)` / `chore(ci)`.

### Fixed
- `backend/Dockerfile` — created (did not exist, was blocking `docker compose up --build`)
- `backend/alembic.ini` — fixed DB hostname from `localhost` to `postgres` (service name) so alembic works inside the `api` container
- `backend/alembic/versions/001_initial_schema.py` — replaced non-existent `postgresql.TIMESTAMPTZ()` with `postgresql.TIMESTAMP(timezone=True)` in 18 places
- `backend/app/models/_types.py` — new type shim providing a `TIMESTAMPTZ` subclass of `TIMESTAMP(timezone=True)` so existing `Column(TIMESTAMPTZ)` usage sites keep working
- `backend/app/models/{alert,connection,feedback,outreach,post,user,workspace}.py` — import `TIMESTAMPTZ` from the new `_types` shim instead of the non-existent `sqlalchemy.dialects.postgresql.TIMESTAMPTZ`
- `backend/pyproject.toml` — added `pydantic[email]`, `email-validator`, and `python-multipart` (required for `EmailStr` schemas and FastAPI form-data parsing, respectively)
- `backend/uv.lock` — tracked lockfile for reproducible builds (previously untracked, hiding Phase 1 deps)
- `frontend/package-lock.json` — regenerated to resolve axios CVE-2026-40175 and CVE-2025-62718 (Dependabot alerts #2 and #3)
- **Security (PR #4):** migrated JWT handling from `python-jose` to `PyJWT` to drop transitively-included `ecdsa` (Dependabot alert #4 — Minerva timing attack on P-256, no upstream fix available). Exception handling equivalence: `jose.JWTError` → `jwt.PyJWTError`. Tokens remain wire-compatible (HS256 + identical claim layout). Manually verified via round-trip testing; reviewer approved for security-sensitive correctness.
- **`bcrypt<4.1` pin (PR #12, closes #5):** `passlib` 1.7.4 references `bcrypt.__about__`, which was removed in bcrypt 4.1+, causing three Phase 1 tests to fail at import time. Pinned `bcrypt<4.1` in `pyproject.toml` and regenerated `uv.lock`. Chose this over swapping `passlib` for `bcrypt`/`argon2-cffi` directly as the smallest-blast-radius fix; long-term migration tracked separately. Test baseline: 45 pass / 5 fail → 48 pass / 2 fail.
- **Connection ORM foreign keys (PR #13, closes #8):** `Connection.workspace_id` and `Connection.user_id` were bare `Column(UUID)` without `ForeignKey(...)`. The DB-level FK on `workspace_id` already existed; on `user_id` it did not. This PR declared both on the ORM side so `Base.metadata.create_all` (used by the test DB) would stop creating orphan-tolerant tables. Matches the pattern applied earlier to `Post.connection_id`. No schema change.
- **Slack router test mock target (PR #16, closes #6):** `test_router_calls_slack_for_configured_workspace` patched `app.delivery.router.SlackSender`, but `CHANNEL_SENDERS` held a direct reference to the original class captured at import time, so the patch did nothing. The real sender ran, `.send()` raised, `asyncio.gather(..., return_exceptions=True)` swallowed it silently, and the mock assertion failed with a confusing "not called" error. Fixed by switching to `patch.dict("app.delivery.router.CHANNEL_SENDERS", {"slack": mock_class})`. Root cause for both this and PR #20: patch where the name is looked up, not where it's defined.
- **JWT claim enforcement (PR #15, closes #7):** `jwt.decode` in `get_current_user` now passes `options={"require": ["exp", "sub"]}`, so tokens missing either claim fail loudly with a `PyJWTError` at decode time instead of sneaking through to a later `KeyError` catch. Two new regression tests (`test_get_current_user_rejects_token_missing_sub`, `test_get_current_user_rejects_token_missing_exp`) hit `/workspace/channels` with hand-crafted tokens and assert 401. Defense-in-depth hardening flagged by the PR #4 security reviewer.
- **`connections.user_id` DB-level FK (PR #19, closes #14):** migration 003 adds `connections_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`. Uses the two-phase `ADD CONSTRAINT ... NOT VALID` + `VALIDATE CONSTRAINT` pattern so the migration is safe against a large production table — phase 1 holds `ACCESS EXCLUSIVE` only for the catalog update; phase 2 scans under `SHARE UPDATE EXCLUSIVE`, which does not block reads or writes. Explicit `ON DELETE RESTRICT` declared on both migration and ORM (`Connection.user_id`) to prevent default-drift between the two. Includes a pre-flight orphan check that raises a repairable error with counts + repair query if any orphan rows exist. Test baseline: 51 pass / 1 fail (test_e2e only).
- **`test_e2e` mock path (PR #20, closes #11):** `test_full_pipeline_end_to_end` patched `app.services.embedding.embedding_provider`, but `app.routers.profile:11` does `from app.services.embedding import embedding_provider` at import time — the router had its own local binding that the patch never touched. The real `_LazyEmbeddingProvider` instantiated an `AsyncOpenAI` client with the placeholder API key and returned a 401. Fixed by switching the patch target to `app.routers.profile.embedding_provider` — the site where the name is actually looked up. Added an inline comment naming the rule so future contributors don't repeat the mistake. Test baseline flipped from 51 pass / 1 fail → **52 pass / 0 fail**, the first fully-green `main` in the repo's history.
- **`DeliveryRouter.deliver` gather failure logging (PR #24, closes #18):** `await asyncio.gather(*tasks, return_exceptions=True)` was discarding its results entirely — every exception raised inside a sender's `.send()` was silently swallowed with no log, no metric, no breadcrumb. This was the systemic weakness that let issue #6 hide for months. Fix: track `invoked_channels` alongside `tasks`, iterate `gather` results after the call, and `logger.error(...)` each exception with `channel`, `alert_id`, `workspace_id`, and `exc_info=result` (stack trace preserved). `return_exceptions=True` is intentionally preserved so one failing channel never cancels siblings — only visibility changes. New regression test `test_router_logs_channel_failure_and_continues_siblings`.

### Changed
- Docs structure flattened: removed `docs/superpowers/specs/`, `docs/superpowers/plans/`, `docs/archive/` in favor of per-phase directories under `docs/phase-N/`
- Plan file naming convention: Phase 2's multi-plan slice uses `implementation-<feature>.md` (e.g., `implementation-foundation.md`) to stay consistent with Phase 1's single `implementation.md`
- `.superpowers/` (brainstorming session directory) added to `.gitignore`
- **Pipeline flow (PR #10):** keyword filter is no longer a gate that drops posts; it contributes to scoring via `keyword_match_strength`. All posts now flow through embedding + Ring 1 + Ring 2 + scoring, so semantic matches on posts without exact keyword hits are no longer silently dropped. Workspace `anti_keywords` still act as a spam pre-check. Ring matches and embeddings are persisted before the alert-threshold check so non-alerted posts still record signal hits for analytics.
- **`DeliveryRouter` sender registry is constructor-injected (PR #23, closes #17):** `DeliveryRouter.__init__(senders: dict[str, type] | None = None)` defaults to the module-level `CHANNEL_SENDERS` so production call sites (`pipeline.py:233 → DeliveryRouter()`) are unchanged. Tests now pass `DeliveryRouter(senders={"slack": mock_class})` instead of monkey-patching globals. The sentinel pattern `if senders is not None else CHANNEL_SENDERS` (not `senders or CHANNEL_SENDERS`) preserves the `{}` = "deliberately disable all" semantic. Type annotation tightening (proper `Sender` / `SenderFactory` Protocols) tracked as part of issue #21.

### Security
- **JWT claim enforcement (PR #15, closes #7):** see "Fixed" — `jwt.decode` now requires `exp` and `sub` at decode time, rather than depending on a downstream `KeyError` catch to reject malformed tokens. Explicit > implicit for security-critical contracts.

---

## Pre-changelog commits (for reference — everything before the changelog was introduced)

The commits below predate this changelog. They are summarized for context; future changes will be logged inline under `[Unreleased]` as they happen.

### Phase 2 Foundation — Implementation in progress on `feat/phase-2-foundation-impl`

- `2720f44` — feat(models): add Trend ORM model
- `3b802a2` — feat(models): add CompanySignalSummary ORM model
- `77ae6dd` — feat(models): add PersonSignalSummary ORM model
- `4b05098` — feat(models): add Signal ORM model with pgvector embedding
- `b29afa5` — fix(tests): repair async fixture registration and test db URL parsing (conftest.py made `db_session` unusable under pytest-asyncio 1.x strict mode)
- `15a5e31` — fix(models): sync ORM with migration 002 — Workspace.backfill_used + Post.connection_id FK
- `cd656b0` — feat(db): phase 2 foundation schema migration + pgvector ORM support

### Phase 1 — Shipped

- Ingest pipeline, capability profile extraction, keyword + embedding matching, 3-dimension scorer, context generator (LLM-based outreach drafts), delivery router (Slack, email, WhatsApp, Telegram), Chrome extension, React dashboard, auth (JWT + bcrypt)
- See `docs/phase-1/implementation.md` for the original 4,700-line implementation plan

---

## Changelog maintenance policy

Going forward, every substantive PR or direct-to-main commit adds a line to this file under `[Unreleased]`. When a release is cut, the `[Unreleased]` block becomes a versioned block with a release date. Entries are grouped by `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

**What counts as "substantive":**
- New features
- Bug fixes
- Schema changes
- Dependency additions/swaps
- Security fixes
- Breaking changes
- Notable docs changes (like CLAUDE.md rebuilds)

**What does NOT need a changelog entry:**
- Typo fixes in docs
- Comment-only changes
- Internal-only test additions that don't affect behavior
- Dependency version bumps within a minor range (unless security-relevant)
