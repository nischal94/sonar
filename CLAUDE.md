# Sonar — Project Instructions for Claude Code

## Git Safety Rules (MUST FOLLOW)

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
- Documentation updates
- CLAUDE.md or rules updates
- Single-file small fixes

No branch required. No PR required. Commit, push to main, done.

### Complex changes — use a feature branch + PR
Use a feature branch and open a PR for:
- New features (multiple files, new logic)
- Refactors that change behavior or touch many files
- Database schema changes / migrations
- Security-sensitive changes
- Anything touching more than ~50 lines across multiple files
- Anything the user explicitly says to branch

Branch naming: `feat/<scope>-<short-description>`, `fix/<bug>`, `chore/<topic>`, `refactor/<scope>`.

### Merging PRs
- **NEVER merge a PR without the user saying "merge" (or equivalent: "merge it", "go ahead", "yes merge") in their most recent message.** The user's standing consent is not blanket — each merge needs a fresh greenlight.
- When the user says to merge: self-review the diff first, then merge.
- If the PR contains any destructive operations (file deletions, schema drops, dependency downgrades), stop and re-confirm with the user before merging even after they said "merge".

### Before any `git` command that could lose work
- Run `git status` first to verify you understand the current state.
- Prefer additive operations (new commits, new branches) over destructive ones (reset, rm, force push).
- When in doubt, stop and ask.

---

## Nomenclature

### File and directory structure

```
sonar/
├── CLAUDE.md                    # This file
├── README.md                    # Product overview
├── TODO.md                      # Setup checklist
├── docs/
│   ├── phase-1/
│   │   ├── design.md            # Original Phase 1 product design (historical)
│   │   └── implementation.md    # Completed Phase 1 implementation plan (historical)
│   ├── phase-2/
│   │   ├── design.md            # Phase 2 design spec
│   │   ├── foundation.md        # Phase 2 Foundation plan
│   │   ├── wizard.md            # Phase 2 Wizard plan (future)
│   │   ├── dashboard.md         # Phase 2 Dashboard plan (future)
│   │   ├── backfill.md          # Phase 2 Backfill plan (future)
│   │   └── discovery.md         # Phase 2 Discovery + Digest plan (future)
│   └── phase-3/                 # (does not exist yet)
└── ...
```

**Rules:**
- Group docs by phase as directories: `docs/phase-N/`.
- Inside each phase directory: `design.md` is the spec ("what and why"), all other files are implementation plans for features in that phase ("how").
- No date prefixes in filenames — git history has dates, filenames are for humans.
- No `specs/` vs `plans/` subdirectories — the filename (`design.md` vs everything else) carries the distinction.
- No `archive/` directory — old phases are just `phase-N/`, not "archived." They stay tracked and readable.
- No `sonar-` prefix in filenames — we're already in the Sonar repo.
- No `docs/superpowers/` subdirectory — that was internal tooling naming, removed.

### Branch naming

| Prefix | Purpose | Example |
|---|---|---|
| `feat/` | New feature work | `feat/phase-2-foundation` |
| `fix/` | Bug fixes | `fix/axios-lockfile` |
| `chore/` | Tooling/config | `chore/dependabot-config` |
| `docs/` | Docs-only changes | `docs/phase-2-spec` |
| `refactor/` | Non-feature refactors | `refactor/pipeline-structure` |

Feature branches for Phase N work follow `feat/phase-N-<feature>`. Phases are sequential: `feat/phase-2-wizard` branches from main *after* `feat/phase-2-foundation` is merged, not from the Foundation branch itself.

### Commit messages (Conventional Commits)

```
<type>(<scope>): <short description>

<optional body explaining the why, not the what>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`.
Scopes for this repo: `pipeline`, `models`, `services`, `workers`, `frontend`, `extension`, `db`, `scripts`, or omit when it's broad.

### Conversation terminology

| Avoid | Use |
|---|---|
| "Plan 1", "Plan 2 of 5" | "Phase 2 Foundation plan", "the Foundation plan", "Foundation" |
| "Sub-plan", "sub-project" | Just the feature name |
| "the spec" (ambiguous) | "the Phase 2 spec" |
| "the PR" (ambiguous) | "the Foundation PR", "PR #5" |
| "the doc" (ambiguous) | Specific name |

When referencing by number (necessary evil), use the GitHub-assigned PR number, not a hand-assigned "Plan N" number.

---

## Project Structure

- `backend/` — FastAPI + SQLAlchemy (async) + Celery + Postgres/pgvector. Entry: `backend/app/main.py`. Celery: `backend/app/workers/celery_app.py`.
- `frontend/` — Vite + React + TypeScript. Entry: `frontend/src/main.tsx`.
- `extension/` — Chrome MV3 extension. Content scripts in `extension/content/`, popup in `extension/popup/`.
- `docs/phase-N/` — per-phase design spec and implementation plans.

## Tech Stack

Backend: FastAPI, SQLAlchemy 2.x (async), Alembic, Celery, Redis, Postgres + pgvector, OpenAI `text-embedding-3-small` (1536 dim), Groq, Apify.
Frontend: React 18, Vite 6, TypeScript, axios, react-router-dom v6.
Extension: Chrome Manifest V3, plain JS (no bundler).

## Build / Test Commands

- Backend: `cd backend && uv sync && uv run pytest`
- Frontend: `cd frontend && npm install && npm run build`
- Extension: load `extension/` as unpacked extension in Chrome.
- Full stack: `docker compose up` from repo root.

## Phase Context

Sonar is being built in phases. As of 2026-04-11:
- **Phase 1** — ingest pipeline, capability profile, signal matching, alerts, delivery channels. Shipped. Historical docs in `docs/phase-1/`.
- **Phase 2** — Signal Configuration Wizard, Day-One Backfill, Network Intelligence Dashboard, Three-Ring Trending Topics, Weekly Digest Email. Design spec at `docs/phase-2/design.md`. Implementation plans in `docs/phase-2/<feature>.md`.

Read the current phase's `design.md` before starting any work so you understand the in-progress direction.
