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

### Changed
- Docs structure flattened: removed `docs/superpowers/specs/`, `docs/superpowers/plans/`, `docs/archive/` in favor of per-phase directories under `docs/phase-N/`
- Plan file naming convention: Phase 2's multi-plan slice uses `implementation-<feature>.md` (e.g., `implementation-foundation.md`) to stay consistent with Phase 1's single `implementation.md`
- `.superpowers/` (brainstorming session directory) added to `.gitignore`

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
