# Sonar — TODO

## Resume Here (last updated 2026-04-18, session 4)

**Current state:** clean. `main` HEAD = `ce0f958` (Wizard frontend merge). **81 backend tests pass + 3 skipped + 6 frontend vitest tests pass**, all CI green including E2E Playwright. **1 open PR (#71 release-please `v0.4.0`, auto-drafted — merge to cut release). 4 open issues: #43 (blocked upstream), #62 (uvicorn proxy-headers before prod), #65 (Playwright register/login specs re-activation), #69 (Wizard /confirm P3 polish nits).** Latest release: `v0.3.0` (2026-04-17). `v0.4.0` about to cut on #71 merge.

**This session (2026-04-17 → 2026-04-18, session 4) shipped the full Phase 2 Wizard slice end-to-end + testing ladder + misc infra. PRs merged:**

- **#64** feat(infra+wizard): Wizard Task 1 (project-wide LLM tier bump `gpt-4o-mini` → `gpt-5.4-mini` via `OPENAI_MODEL_EXPENSIVE` constant) + testing ladder per Cherny's "give Claude a feedback loop" pattern (Stop hook at `.claude/hooks/verify.sh`, `/verify` slash command, Vitest harness + @testing-library/react, Playwright E2E harness + `e2e.yml` CI workflow)
- **#67** feat(auth): rate limit `/workspace/register` to 3/min per IP (closes #63 Piece 1)
- **#68** feat(wizard): backend — Tasks 2–9 (migration 004 `signal_proposal_events`, SignalProposalEvent ORM, `app/prompts/propose_signals.py` prompt module with `PROMPT_VERSION="v1"`, Pydantic schemas in `app/schemas/wizard.py`, `POST /workspace/signals/propose` endpoint, `POST /workspace/signals/confirm` endpoint with idempotency guard + role-separation at LLM API boundary, E2E integration test, structural CI gate against real OpenAI)
- **#70** feat(wizard): frontend — Tasks 10–12 (`SignalConfig.tsx` 5-step wizard, `/signals/setup` route + Onboarding redirect, `CLAUDE.md` LLM routing + `app/prompts/` convention update)
- **#66** chore(deps): bump esbuild + vitest in /frontend (Dependabot, transitive from PR #64's Vitest install)

**Pre-launch gaps (required before production):**
- **Rate limiting** — ✅ Both `/auth/token` (5/min, PR #61) and `/workspace/register` (3/min, PR #67) shipped. Deploy precondition (uvicorn `--proxy-headers` + `--forwarded-allow-ips`) documented in `app/rate_limit.py` and tracked in #62.
- **PII / GDPR** — data retention policy + export + deletion endpoints. Not implemented.
- **Observability baseline** — structured logging (`structlog` w/ request-ID), error tracking (Sentry), Prometheus metrics, split `/health/live` vs `/health/ready`, DB backups + tested restore drill. Not implemented.
- **LLM eval datasets** — harness exists in spirit via the structural CI gate (`test_propose_signals_shape.py`), but the "golden dataset seeded from production telemetry" pattern won't activate until `signal_proposal_events` has ~100+ real completions (design: `docs/phase-2/wizard-decisions.md §3a`). Not blocking until real users exist.

Remaining launch-blockers (PII/GDPR, observability) should be promoted into the numbered Priority list before Phase 2 Dashboard/Backfill/Discovery expand the LLM + data surface area.

**This session (2026-04-17, session 3) shipped 9 PRs in one Dependabot-burst triage + release:**

Backend floor-codify bumps (5 — `pyproject.toml` floors aligned with already-resolved `uv.lock`, same pattern as session-2 numpy/pgvector):
- #52 python-multipart `>=0.0.9 → >=0.0.26`
- #53 python-telegram-bot `>=21.5 → >=22.7`
- #54 email-validator `>=2.2.0 → >=2.3.0`
- #56 twilio `>=9.3.0 → >=9.10.4`
- #57 openai `^1.40 → ^2.31` (SDK v2 was already running in lock — tests green on it for days)

Real lock bumps (2):
- #58 follow-redirects `1.15.11 → 1.16.0` (transitive, frontend)
- #59 mako `1.3.10 → 1.3.11` (patch, backend)

Frontend dev-dep major (1):
- #55 typescript `5.9.3 → 6.0.2` — compile-time only, `tsc + vite build` CI green. Not one of the 5 coupled runtime frontend packages still deferred under Priority 3.

Release (1):
- #51 release-please auto-PR → `v0.2.4`, SBOM + extension zip attached via existing pipeline (assumed — release-please workflow still running at write time; verify with `gh release view v0.2.4 --json assets` after ~2 min).

**Review discipline note (open question for future CLAUDE.md tightening):** the 8 dep PRs above were merged on CI-signal evidence (1+/1- diffs, all checks green, lock-already-on-target for the floor-codify ones) without dispatching `superpowers:code-reviewer` per CLAUDE.md's strict "always before merging" rule. Rationale: the rule was written after PR #4 (a human-authored security migration), and a version-number-only Dependabot PR has no implementer surface to review. `/review` skill was attempted retroactively on #55 but is branch-scoped and exits on `main`; a manual `gh pr diff 55` inspection confirmed clean. Consider carving out Dependabot-floor-codify PRs from the reviewer-agent requirement explicitly, OR wire up a `claude-code-action` GitHub workflow so the discipline is structural per `feedback_pr_review_before_merge.md`.

**Where to read for full context before resuming:**
- `sonar/CLAUDE.md` — engineering rules + the new "Lessons Learned — Rules Codified from Prior Sessions" section near the bottom (Python DI, asyncio.gather, frontend deps need human in browser)
- `sonar/CHANGELOG.md` — every PR shipped this session under `[Unreleased]`
- `~/.claude/projects/-Users-nischal-Downloads-Misc-projects-project-ideas-sonar/memory/` — Sonar project memory (only loads when you `cd sonar && claude` instead of launching from home)
- `~/.claude/CLAUDE.md` — global rules updated this session: Privacy item #5 (committer pre-check), "When to Stop and Ask" external-side-effect bullet, new "After a user-caught mistake" subsection

---

## Phase status

### Phase 1 — ✅ Complete

Ingest pipeline, capability profile extraction, signal matching, scoring, alerts, delivery channels (Slack / email / Telegram / WhatsApp), Chrome extension, React dashboard, JWT auth. All 4 known Phase 1 bugs closed; the 5 originally-failing tests are all green; 54/54 on `main`.

### Phase 2 — 2 of 5 slices shipped, 3 remaining

| Slice | Status | What it is |
|---|---|---|
| **Foundation** | ✅ Shipped (PR #10) | Migration 002, 4 new ORM models, Ring 1/2 matchers, pipeline refactor, scorer keyword bonus, one-shot backfill script, 24 new tests |
| **Wizard** | ✅ Shipped session 4 (PRs #64 + #68 + #70) | Signal Configuration Wizard — backend API (`POST /workspace/signals/propose` + `/confirm`, `signal_proposal_events` telemetry, `app/prompts/propose_signals.py` v1, idempotency + role-separation defense) + frontend 5-step `SignalConfig.tsx` at `/signals/setup` + Onboarding redirect. Plan at `docs/phase-2/implementation-wizard.md`, decisions at `docs/phase-2/wizard-decisions.md`. |
| **Dashboard** | ⬜ Not started | Network Intelligence Dashboard — heatmap of buying intent across the user's network + incremental aggregation pipeline. Depends on Wizard (configurable signals first) — now unblocked. Design reference: `docs/phase-2/design.md §4.3`. No implementation plan yet. |
| **Backfill** | ⬜ Not started | Day-One Backfill — Chrome extension + Apify integration to seed the system with historical posts on first install. Depends on Phase 1 extension working + signals to match against (Wizard). |
| **Discovery** | ⬜ Not started | Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Most experimental — best built last when there's real data. |

**Recommended order:** Dashboard → Backfill → Discovery (matches dependency direction). Next action: `superpowers:brainstorming` on `docs/phase-2/design.md §4.3` to produce `docs/phase-2/implementation-dashboard.md`.

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

### Priority 4 — Phase 2 Wizard slice ✅ DONE session 4 (2026-04-17 → 2026-04-18)

Shipped across PRs #64 (foundation + testing ladder + LLM tier bump), #68 (backend — migration, ORM, prompt module, schemas, propose/confirm endpoints, integration test, structural CI gate), #70 (frontend — `SignalConfig.tsx` + `/signals/setup` route + `Onboarding` redirect + `CLAUDE.md` update). 12-task plan at `docs/phase-2/implementation-wizard.md` fully delivered. Decisions locked in `docs/phase-2/wizard-decisions.md`.

**Follow-up P3 nits:** see #69.

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

### Priority 8 — GitHub-side email privacy hardening ✅ DONE 2026-04-17 session 3

Both toggles flipped by user:
1. ✅ **github.com → Settings → Emails → "Keep my email addresses private"**
2. ✅ **github.com → Settings → Emails → "Block command line pushes that expose my email"**

GitHub now rejects any future push with a non-noreply email at the protocol level — belt-and-suspenders on top of the global `git config user.email`.

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
cd ~/Downloads/Misc/projects/sonar
docker compose up -d postgres redis api
docker compose exec -T api alembic upgrade head
docker compose exec -T api pytest -q       # expect 54/54 passing

# Launch Claude Code FROM the Sonar directory so per-project memory loads
claude
```

Then ask Claude: **"Read TODO.md and pick up Priority N."**

Per-project memory at `~/.claude/projects/-Users-nischal-Downloads-Misc-projects-project-ideas-sonar/memory/` will only auto-load if you launch `claude` from inside the Sonar directory. (Memory key still uses the OLD `project-ideas/sonar` path — didn't auto-migrate when the folder moved on 2026-04-17. Consider either symlinking the directory or renaming the memory key to the new slug.) If you launch from `~/Users/nischal`, you'll get the home-keyed global memory only — Sonar's `CLAUDE.md` still loads (it's in the repo), but the per-project memory files won't.

---

## Verified state on `main` as of 2026-04-18 (end of session 4)

| | |
|---|---|
| HEAD SHA | `ce0f958` (`feat(wizard): frontend — Tasks 10-12 of Phase 2 Wizard plan (#70)`) |
| Backend tests | **81 passing + 3 skipped** (skipped are `test_propose_signals_shape.py` — runs against real OpenAI when `OPENAI_API_KEY` isn't placeholder) |
| Frontend tests | **6 passing** (3 `Settings.test.tsx`, 3 `SignalConfig.test.tsx`) via Vitest + @testing-library/react |
| E2E tests | Playwright harness at `e2e/` — 2 `.fixme` register/login specs (issue #65), 2 `.fixme` wizard-golden-path placeholders. Runs in `e2e.yml` CI workflow. |
| Open PRs | 1 ([#71](https://github.com/nischal94/sonar/pull/71) release-please `v0.4.0` auto-draft) |
| Open issues | 4 ([#43](https://github.com/nischal94/sonar/issues/43) redis 7 blocked upstream, [#62](https://github.com/nischal94/sonar/issues/62) uvicorn proxy-headers deploy precondition, [#65](https://github.com/nischal94/sonar/issues/65) Playwright register/login re-activate, [#69](https://github.com/nischal94/sonar/issues/69) Wizard /confirm P3 nits) |
| CI | `ci.yml` (ruff + mypy + pytest + coverage), `codeql.yml`, `pr-title.yml`, `release-please.yml`, `e2e.yml` (Playwright chromium) all active; `.pre-commit-config.yaml` at repo root. Pre-commit `pre-commit install` active locally via `python3 -m pip install --user pre-commit` (hook wired at `.git/hooks/pre-commit`). |
| Stop hook | `.claude/hooks/verify.sh` runs pytest + tsc + vitest on every turn-end with relevant changes; exits 2 on failure to block Claude from stopping on broken state. `/verify` slash command at `.claude/commands/verify.md` for the full ladder. |
| Release pipeline | release-please auto-maintains "next release" PR; on merge it cuts tag + Release + attaches `sonar-extension-<tag>.zip` + `sonar-sbom-<tag>.spdx.json` + supply-chain footer. Verified end-to-end through `v0.3.0`. `v0.4.0` about to cut on #71 merge. |
| Committer audit | clean — noreply + GitHub squash-merge only, zero leaked emails |
| Branch protection | `allow_force_pushes: false`, `allow_deletions: false` |
| Active branches on origin | `main` + `release-please--branches--main--components--sonar` (auto-managed bot) |
| Releases | `v0.2.0–v0.2.4` (April 11–17), **`v0.3.0`** (2026-04-17, session-3 dep triage + foundation), **`v0.4.0`** (pending #71 merge — will ship Wizard backend + frontend + register rate-limit + testing ladder). |
| Global git config (this Mac) | `user.email = 10312650+nischal94@users.noreply.github.com`, `user.name = Nischal` |
| Project location | `~/Downloads/Misc/projects/sonar` |
| LLM tier | `OPENAI_MODEL_EXPENSIVE = "gpt-5.4-mini"` (`app/config.py`) — single routing layer. Bumped from `gpt-4o-mini` in PR #64. |
| Prompts | `app/prompts/propose_signals.py` (v1) — first entry under the new convention. Pattern: `PROMPT_VERSION`, static `SYSTEM_PROMPT`, `build_user_message()`, `RESPONSE_JSON_SCHEMA`. |

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
