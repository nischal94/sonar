# Sonar — Project Instructions for Claude Code

## Git Safety Rules (MUST FOLLOW)

These rules are non-negotiable for any agent working in this repo. They exist because a previous session deleted 5,778 lines of planning docs in one commit by bundling `git rm` with a `.gitignore` change. Do not repeat that failure.

### Destructive operations require explicit confirmation
- NEVER run `git rm` on tracked files without an explicit instruction in the user's most recent message that names the files being removed.
- NEVER commit deletions totaling more than 50 lines of existing tracked content without asking first.
- NEVER run `git reset --hard`, `git push --force`, `git clean -f`, or `git checkout --` on tracked paths without explicit confirmation.
- NEVER rewrite, amend, or squash commits that have already been pushed.

### Never push directly to main
- All changes go on a feature branch (`feat/…`, `fix/…`, `docs/…`, `chore/…`).
- Open a pull request against main. Do not merge without the user's explicit approval.
- `main` is protected by branch protection rules on GitHub — direct pushes will be rejected anyway, but do not try to bypass them.

### Untracking is not deletion
- When the user asks to "stop tracking" a file or directory, use `git rm --cached <path>` — this removes it from the index but keeps the file on disk.
- Do this as a **standalone commit**, never bundled with adding to `.gitignore` or with content changes.
- When adding something to `.gitignore`, never combine that commit with deleting the matching files from the tree.

### Planning docs are user content, not agent content
- Files in `docs/specs/`, `docs/plans/`, `docs/superpowers/`, and `docs/archive/` are the user's planning work. Treat them like source code: never delete, truncate, or mass-rewrite them without explicit instruction.
- If you think a planning doc is outdated, say so and ask what to do. Do not unilaterally remove it.

### Before any `git` command that could lose work
- Run `git status` first to verify you understand the current state.
- Prefer additive operations (new commits, new branches) over destructive ones (reset, rm, force push).
- When in doubt, stop and ask.

## Project Structure

- `backend/` — FastAPI + SQLAlchemy + Celery + Postgres/pgvector. Entry: `backend/app/main.py`. Celery: `backend/app/workers/celery_app.py`.
- `frontend/` — Vite + React + TypeScript. Entry: `frontend/src/main.tsx`.
- `extension/` — Chrome MV3 extension. Content scripts in `extension/content/`, popup in `extension/popup/`.
- `docs/superpowers/specs/` — design specs (tracked).
- `docs/superpowers/plans/` — implementation plans (tracked).
- `docs/archive/` — historical planning docs, restored from git history (tracked).

## Tech Stack

Backend: FastAPI, SQLAlchemy (async), Celery, Redis, Postgres + pgvector, OpenAI / Groq LLM providers, Apify for public scraping.
Frontend: React 18, Vite 6, TypeScript, axios, react-router-dom v6.
Extension: Chrome Manifest V3, plain JS (no bundler).

## Build / Test Commands

- Backend: `cd backend && uv sync && uv run pytest`
- Frontend: `cd frontend && npm install && npm run build`
- Extension: load `extension/` as unpacked extension in Chrome.
- Full stack: `docker compose up` from repo root.

## Phase Context

Sonar is being built in phases. As of 2026-04-11:
- **Phase 1** — ingest pipeline, capability profile, signal matching, alerts, delivery channels. Shipped.
- **Phase 2** — Signal Configuration Wizard, Day-One Backfill, Network Intelligence Dashboard, Three-Ring Trending Topics, Weekly Digest Email. Design spec at `docs/superpowers/specs/2026-04-11-sonar-phase-2-design.md`. Implementation plans in `docs/superpowers/plans/`.

Read the current phase spec before starting any work so you understand the in-progress direction.
