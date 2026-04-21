# Sonar — Project Status & Plan

> **This is the single source of truth for the project.** Read top-to-bottom to resume. Sections below follow a fixed order: Next Session Action Plan → Phase status → Reference processes → Open issues → Orthogonal cleanup → Session log → Resume / setup commands. Older session forensics (`docs/session-notes/`) are preserved as historical artifacts but new session records go in the Session log section below, not there.

---

## Next Session Action Plan (last rewritten 2026-04-21, end of session 10)

**State at resume:** Branch `feat/phase-2-6-migrations` HEAD = `583154b`. Tests: 186 backend pass. Working tree clean. **PR [#119](https://github.com/nischal94/sonar/pull/119) open** with 17 commits implementing Phase 2.6 Tasks 1–8 plus the #120 blocker fix. Task 9 (operational) is the only pending piece.

### 1. 🔬 Manual browser walkthrough of the 6-step wizard

**What:** `docker compose up -d frontend && open http://localhost:5173/signals/setup`. Walk all 6 steps: enter "What do you sell?" → **new ICP review step 3** appears showing extracted ICP + seller_mirror → edit each field → proceed to signal generation → accept/reject signals → save. Check browser devtools network tab for `/profile/extract` (returns icp + seller_mirror) and `/profile/update-icp` (fires only if user edited). Take a screenshot for the PR merge record.
**Why now:** Per CLAUDE.md lessons learned, frontend changes require a human in the browser; `npm run build` proves the bundle compiles, not that React rendering works at runtime. This is the last gate before Task 9's calibration run.
**Blocks:** Item 2 (calibration run needs confirmed working ICP extraction flow) and item 3 (PR merge).
**Effort:** 10–15 min.

### 2. 🎯 Task 9 — run Phase 2.6 calibration + decide flag flip

**What:** For both Dwao and CleverTap workspaces: extract ICP via `/profile/extract`, run `python scripts/backfill_fit_scores.py --workspace-id <uuid>`, then `python scripts/calibrate_matching.py analyze-hybrid --workspace-id <uuid> --labels eval/calibration/<dataset>.md --lambdas 0.0,0.1,0.2,0.3,0.5,0.7,1.0`. For CleverTap, re-label the same 30-post dogfood dataset under the CleverTap lens first (~15 min). Pick the winning λ that satisfies DoD on BOTH workspaces: P@5 ≥ 0.6, Recall@5 ≥ 0.5, zero top-5 competitors. Document findings at `eval/calibration/phase-2-6-findings.md`.
**Why now:** This is the ship/don't-ship gate for Phase 2.6. The implementation is shippable code; whether it actually improves matching is an empirical question only calibration answers. If DoD fails, see design.md §5 step 8 for diagnostic paths (encoder upgrade, prompt tightening, retrieval-model swap).
**Blocks:** flag flip on dogfood workspace. PR #119 can merge independently of calibration outcome, but the flag flip is the operational goal.
**Effort:** 1–2 hours (ICP extraction × 2 workspaces, backfill × 2, analyze-hybrid × 2, CleverTap re-label, write findings).

### 3. 🚀 Merge PR #119 + flip the flag for dogfood workspace

**What:** After items 1 + 2 pass, merge PR #119 to main. Then `UPDATE workspaces SET use_hybrid_scoring = TRUE WHERE id = '<Dwao_uuid>';`. Monitor `/dashboard` output and delivered alerts for 1–2 weeks against the session-8 calibration baseline.
**Why now:** The Phase 2.6 code is inert until the flag flips. The rollout design is per-workspace so rollback is a single SQL flip.
**Effort:** 5 min to merge + flip. 1–2 weeks monitoring.

### 4. 🛠 Address Phase 2.6 follow-up issues (any time, low-to-medium effort)

- [#121](https://github.com/nischal94/sonar/issues/121) — log `PROMPT_VERSION` on every LLM call. Systemic tech debt; also affects the existing `extract_capability_profile`.
- [#122](https://github.com/nischal94/sonar/issues/122) — wizard: split `icpEdited` into per-field dirty flags (avoid redundant re-embed on unchanged field). UX polish.
- [#123](https://github.com/nischal94/sonar/issues/123) — pipeline race on `connection.fit_score` cache. Idempotent outcome; low priority until traffic scales.
- [#124](https://github.com/nischal94/sonar/issues/124) — add `workspace.hybrid_lambda` column if Task 9 picks λ ≠ 0.3. Close as "no action needed" if Task 9 picks 0.3.

Also deferred from session 8: [#107](https://github.com/nischal94/sonar/issues/107) CORS service-worker routing, [#108](https://github.com/nischal94/sonar/issues/108) Apify token to Authorization header, [#110](https://github.com/nischal94/sonar/issues/110) Ring 1 dead, [#111](https://github.com/nischal94/sonar/issues/111) dashboard slider default. None block Phase 2.6.

### 5. 🧭 Phase 2 Discovery (DEFERRED until Phase 2.6 DoD passes)

**What:** Ring 3 nightly HDBSCAN clustering for emerging topics + Weekly Digest Email. Per `docs/phase-2/design.md §4.4`.
**When to revisit:** After Task 9 DoD passes AND the flag has been stable for 2+ weeks on the dogfood workspace. Clustering the current matching signal clusters noise; Discovery is building on sand until 2.6 lands.
**Effort:** Multi-session when it's time.

### 6. 🚧 Pre-launch tier (gates before first external paying customer — NOT next-session work)

Tracked so they don't surprise:
- **PII/GDPR:** data retention policy + export + deletion endpoints. Not started.
- **Observability:** structlog + Sentry + Prometheus + split `/health/live` vs `/ready` + DB backup/restore drill. Not started.
- **LLM eval harness:** activates once `signal_proposal_events` has ~100+ real completions.
- **Frontend dep bumps:** React 18→19, Vite 6→8, react-router-dom 6→7. Tracked in [#40](https://github.com/nischal94/sonar/issues/40). Requires human in browser — plan a dedicated half-day.

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

### Phase 3 — ⬜ TBD (no design yet)

Three rough directions in `CLAUDE.md`: real-time alerts, CRM integrations, team features. Deprioritized vs Phase 2.6. Run `superpowers:brainstorming` to scope when 2.6 ships.

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

### Session 10 — 2026-04-21 — Phase 2.6 implementation shipped (Tasks 1–8) + #120 blocker fix

- **Open:** [PR #119](https://github.com/nischal94/sonar/pull/119) — 17 commits on `feat/phase-2-6-migrations`, 186 tests green. Implements all 8 code tasks from `docs/phase-2-6/implementation.md`: 3 migrations + ORM updates, ICP + seller_mirror prompt module, fit_scorer service, extended `/profile/extract`, pipeline branch on `use_hybrid_scoring`, one-shot backfill script, wizard ICP review step + `/profile/update-icp`, `analyze-hybrid` calibration subcommand.
- **Discipline:** every task through `superpowers:subagent-driven-development` with two-stage review (spec + quality). Reviews caught 1 blocking (Task 1 SQL injection in test), 6 important findings, multiple nice-to-haves — all addressed inline or deferred with rationale.
- **Closed:** [#120](https://github.com/nischal94/sonar/issues/120) — Phase 2.6 merge blocker (delivery formatters rendering `relationship_score=0.0` as "Relationship: 0%"). Migration 011 makes the column nullable; hybrid pipeline path passes None; Slack/Telegram/email render "Relationship: N/A (hybrid scoring)".
- **Filed for follow-up:** [#121](https://github.com/nischal94/sonar/issues/121) PROMPT_VERSION logging systemic gap, [#122](https://github.com/nischal94/sonar/issues/122) wizard per-field dirty flags, [#123](https://github.com/nischal94/sonar/issues/123) pipeline fit_score race (idempotent), [#124](https://github.com/nischal94/sonar/issues/124) lambda storage pending Task 9 calibration.
- **Task 9 still pending** — operational: run `analyze-hybrid` for Dwao + CleverTap against the session-8 labeled dataset, pick winning λ, flip `use_hybrid_scoring=True` only if DoD passes on both workspaces. Manual browser walkthrough of the 6-step wizard also required before merge.

### Session 9 — 2026-04-20/21 — Phase 2.6 design doc written + first review

- **Merged:** [PR #114](https://github.com/nischal94/sonar/pull/114) — calibration harness + findings + Phase 2.6 evidence pool. Closed [#106](https://github.com/nischal94/sonar/issues/106) as superseded by [#113](https://github.com/nischal94/sonar/issues/113).
- **Committed:** `14cc237` Phase 2.6 design proposal (Fit × Intent hybrid scoring), `0d390e7` revision after first review. `docs/phase-2-6/design.md` covers contrastive ICP phrasing with explicit anti-examples, a subtractive seller-mirror term with λ sweep (promoted from Plan B to v1 after review), multiplicative `fit × intent` combine, three DoD constraints (P@5 ≥ 0.6, Recall ≥ 0.5, zero top-5 competitor leakage), feature-flag rollout.
- **Design retractions from first review:** Dropped the earlier concern that CleverTap calibration would be weaker because the labeler doesn't work there. That was confused product thinking — the labeler's domain knowledge is what matters, employment is irrelevant. CleverTap remains a full dual-profile DoD.
- **Implementation plan written:** `docs/phase-2-6/implementation.md` — 9 tasks with bite-sized TDD steps, exact code snippets, commit messages. Task 9 is operational (flag flip + retire legacy).

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
