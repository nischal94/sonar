# Sonar — TODO

## Resume Here (last updated 2026-04-13, session 2)

**Current state:** clean. `main` HEAD = `520dccb`. 54/54 tests passing. **0 open PRs. 1 open issue (#43 — redis 7 bump blocked upstream on celery+kombu).** Phase 1 + Phase 2 Foundation shipped. Committer leak fully remediated (as before). `.github/` scaffold + CI gates live — `ci.yml`, `codeql.yml`, `pr-title.yml`, `release-please.yml`, `pre-commit-config.yaml`. Releases: `v0.2.0` (2026-04-11), `v0.2.1`, `v0.2.2`, `v0.2.3` (all 2026-04-13, `v0.2.3` latest) — starting with `v0.2.2`, every release attaches SBOM (SPDX ~375KB) + Chrome extension .zip as assets and appends a "Supply-chain transparency" footer to release notes.

**This session (2026-04-13, session 2) shipped 8 PRs across 3 releases:**
- #44 numpy 2.x pin (codify reality)
- #45 CI fixes (alembic DATABASE_URL env override + frontend vite-env.d.ts) — surfaced when #44 triggered CI for the first time after `d4f7837`
- #46 release-please enhancements (emoji-strip, SBOM + extension zip assets, CODEOWNERS/SECURITY.md footer)
- #48 pgvector 0.4.x pin (codify reality)
- #50 Node-24-compatible action bumps across all workflows (checkout v4→v6, setup-node v4→v6, setup-uv v3→v8.0.0, semantic-pr v5→v6, setup-buildx v3→v4, build-push v5→v7); `anchore/sbom-action@v0` and `github/codeql-action/*` deliberately kept on current pins
- #42, #47, #49 — release-please automated release PRs for `v0.2.1`, `v0.2.2`, `v0.2.3`

**Priority 2 is now fully resolved** — redis blocked (#43), numpy + pgvector pinned and released. The frontend-deps bucket under Priority 3 is the only backlog item from the original #40 deferral.

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

### Priority 1 — Wire up CI gates (top tech-debt) — ✅ Shipped 2026-04-13 in `d4f7837`

**Status:** Done. The `.github/workflows/` directory now contains `ci.yml`, `codeql.yml`, `pr-title.yml`, and `release-please.yml`, plus `.pre-commit-config.yaml` at the repo root. `release-please` replaced `release-drafter` (see commit `96b2338`). Below is preserved as the "what shipped" reference — audit against the actual workflow files if verifying coverage.

**What was planned (per original Priority 1 spec):**
- `ruff check` (lint + format check) on every PR
- `mypy` or `pyright` (start permissive, tighten over time per `sonar/CLAUDE.md` Engineering Standards)
- `pytest -q` with coverage reporting (target 70-85% meaningful coverage)
- Backend container build sanity check (`docker compose build api`)
- Frontend `npm run build` sanity check
- Pre-commit hook check (block secrets, trailing whitespace, large files, lint violations)

**Follow-up if gaps found:** diff `ci.yml` against the checklist above; any missing item gets a standalone PR rather than a re-open of this priority.

---

### Priority 2 — Issue #40 backend dep bumps — ✅ Complete 2026-04-13

**Status:** All 3 packages dispositioned. Priority is closed out.

- **`numpy 1.26.0 → 2.4.4`** — ✅ Pinned via [PR #44](https://github.com/nischal94/sonar/pull/44). Investigation showed uv.lock already had 2.4.4 resolved; change was a defensive `>=2.0.0,<3` ceiling in pyproject, not a real version bump. Included in `v0.2.2`.
- **`pgvector 0.3.0 → 0.4.2`** — ✅ Pinned via [PR #48](https://github.com/nischal94/sonar/pull/48). Same pattern as numpy — lock was already at 0.4.2; pinned to `>=0.4.0,<0.5` (SemVer-strict for 0.x minor). Included in `v0.2.2`.
- **`redis 5.0.0 → 7.4.0`** — ❌ Blocked upstream, tracked in [#43](https://github.com/nischal94/sonar/issues/43). Every `celery[redis]` release (5.4.0–5.6.3) transitively requires `kombu[redis]`, which caps `redis<=5.2.1`. Cannot land until celery ships a release with kombu supporting redis>=7. Auto-close future Dependabot redis-7 PRs with a link to #43.

**Process record** (preserved for future dep-audit sessions, per `feedback_dep_audit_split.md`):
1. `git checkout -b chore/deps-<package>`
2. Verify `uv.lock` for the ACTUAL current version — don't trust the pyproject floor alone (both numpy and pgvector were already at target)
3. Bump the pin in `backend/pyproject.toml`; run `uv sync --all-extras`
4. Commit pyproject + uv.lock as TWO atomic commits per `sonar/CLAUDE.md:481`
5. `pytest -q` must stay 54/54
6. Push, open PR, dispatch `superpowers:code-reviewer`
7. Pause for explicit user merge approval per `sonar/CLAUDE.md`

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
- **Type checking** — mypy/pyright in CI starts permissive, tightens over time. (Basic setup shipped with Priority 1 — tighten-over-time work remains.)
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

## Verified state on `main` as of 2026-04-13 (end of session 2)

| | |
|---|---|
| HEAD SHA | `520dccb` (`chore(main): release 0.2.3 (#49)`) |
| Tests | 54/54 passing |
| Open PRs | 0 |
| Open issues | 1 ([#43](https://github.com/nischal94/sonar/issues/43) — redis 7 bump blocked upstream on celery+kombu) |
| CI | `ci.yml` (ruff + mypy + pytest + coverage), `codeql.yml`, `pr-title.yml`, `release-please.yml` all active; `.pre-commit-config.yaml` at repo root. Verified green end-to-end on PRs #44–#50 this session. All non-excluded workflow actions on Node-24-compatible majors. |
| Release pipeline | release-please auto-maintains "next release" PR; on merge it cuts tag + Release + attaches `sonar-extension-<tag>.zip` + `sonar-sbom-<tag>.spdx.json` (SPDX via syft) + appends Supply-chain transparency footer. Verified end-to-end on `v0.2.2` and `v0.2.3`. |
| Committer audit | clean — noreply + GitHub squash-merge only, zero leaked emails |
| Branch protection | `allow_force_pushes: false`, `allow_deletions: false` |
| Active branches on origin | `main` only (release-please branch auto-deleted after #49 merged; recreates on next commit to main) |
| Releases | `v0.2.0` (2026-04-11), `v0.2.1`, `v0.2.2`, `v0.2.3` (all 2026-04-13; `v0.2.3` latest). `v0.2.2` was the first release with SBOM + extension zip + footer. |
| Global git config (this Mac) | `user.email = 10312650+nischal94@users.noreply.github.com`, `user.name = Nischal` |

### Known follow-up tracked for a future session

- **Residual Node 20 on `googleapis/release-please-action@v4`.** PR #50 bumped all other workflow actions to Node-24-compatible majors, but `release-please-action@v4` is already on the latest major and its current v4.x patches still use Node 20. The v0.2.3 release-please run still fires the deprecation annotation specifically for this one action. Deadline: Node 24 forced 2026-06-02, Node 20 removed 2026-09-16. Will resolve when googleapis ships either a v4 patch with Node 24 or a v5. Revisit in May 2026 if still outstanding.

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
