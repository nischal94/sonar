# Sonar Phase 3 — Target-Scoped Intent (Server-Side Ingest, Extension-Optional)

**Status:** Design proposal — awaiting user review
**Date:** 2026-04-21 (session 10 close)
**Supersedes:** the implicit Phase 3 framings in `CLAUDE.md` ("real-time alerts, CRM integrations, team features") — those become sub-features of this phase's architecture rather than its primary goal.
**Builds on:** `docs/phase-2-6/design.md` (Fit × Intent scoring), PR #119 (Phase 2.6 implementation) — the scoring engine is ingest-agnostic and carries forward unchanged.
**Context document:** the Chrome-extension security pivot conversation at session 10's end — transcribed summary in the commit message body.

---

## 1. Problem

Sonar v1 ships a Chrome extension that passively observes the logged-in user's LinkedIn feed. Every post the user scrolls past flows from the extension to the backend, where it's embedded, scored, and alerted on. This architecture made Sonar easy to prototype but carries three structural costs that grow with scale:

1. **Attack surface.** The extension holds permissions to read any DOM on `linkedin.com/*`. A compromise of the extension (supply-chain attack, dev-account hijack, malicious content-script injection) exposes the user's entire LinkedIn session. The session-7 CORS widening to allow `https://www.linkedin.com` (issue [#107](https://github.com/nischal94/sonar/issues/107)) created an additional `/auth/token` response-read exposure. Every new feature on the extension side widens this surface; no hardening makes it narrow.

2. **Product dependency on fragile foreign DOM.** Every LinkedIn DOM revision breaks the extension. Every Chrome Manifest tightening threatens the permission set we rely on. Every Chrome Web Store review cycle can delay a release. The upstream surface is not under our control and drifts constantly.

3. **Enterprise non-starter.** Enterprise IT departments routinely block unknown Chrome extensions. SOC 2 reviews flag passive-observation extensions as high-risk. The extension forecloses on the enterprise motion at exactly the price point where the scoring work of Phase 2.6 becomes most valuable.

Ingest via a browser extension was a shortcut to market for v1. Shipping it as the production architecture through Phase 3+ is increasingly untenable. This phase separates the **ingest mechanism** from the **scoring engine** and moves ingest server-side.

---

## 2. Solution in one paragraph

Replace the extension as the ingest mechanism with server-side public-LinkedIn scraping (Apify) against a user-provided **target list**. Users onboard by pasting 100–500 LinkedIn profile/company URLs representing the accounts they want to sell to; Sonar's backend scrapes those targets' public activity on a daily cadence, runs every post through Phase 2.6's Fit × Intent scoring, and delivers alerts through the existing Slack/Telegram/email channels. The Chrome extension is deprecated from its ingest role; it returns later (v3.2+) as an optional read-only UX overlay that surfaces Sonar's scores on profiles the user visits, with tightly-scoped permissions modeled on Lusha/Apollo. The scoring engine, delivery pipeline, wizard (with the Phase 2.6 ICP review step), and auth layer carry forward unchanged; what changes is the data source and the onboarding shape.

---

## 3. Decisions, with reasoning

Every decision below is the product-shape call that defines this phase. Open questions are flagged where they genuinely remain.

### 3.1 Target list is the onboarding primitive

Workspace owners paste or upload a list of LinkedIn profile URLs (people) and/or company-page URLs. Initial minimum: 100 entries; typical: 200–500; upper bound: 2000. Each target has a type (`person` vs `company`), a normalized LinkedIn URL, and optional metadata (segment tag, priority score, source system).

**Why:** This is the shape every enterprise ABM tool uses (6sense, Demandbase, Clay, Common Room). It matches how B2B sales teams already work — they have a named account list. Pasting that list is a task the user can complete in 5 minutes; the alternative ("install extension, log in, wait for feed to refresh") takes longer and requires more trust.

**Why not "scrape everyone the user interacts with":** moves us back toward feed-observation shape. Defeats the pivot.

**CRM sync (v3.1):** Salesforce / HubSpot / Attio opportunity-list sync — one-click import of opportunities as targets. Follows this phase but uses the same underlying schema.

### 3.2 Daily Apify scrape per workspace

A Celery beat task runs per-workspace daily (configurable: every 4h for high-tier, daily for mid-tier, weekly for free tier). Dispatch is **staggered** across 24 hours via `hash(workspace_id) % 86400` offset so 1000+ workspaces don't thundering-herd the Apify API and our Celery worker pool at 00:00 UTC. For each target, Apify fetches the target's recent public LinkedIn posts (person: ~20 most recent on their profile; company: ~20 most recent on the company page). Posts are inserted into the existing `posts` table with a new `source='target_scrape'` marker; the pipeline processes them exactly as today.

**Why Apify:** already in the stack (used today for day-one connection backfill). Handles rotating proxies + session management + rate limiting. Pricing is predictable (~$0.001/post). Alternative vendors (Bright Data, Harvest API, ScraperAPI) are swap-in if Apify degrades — the integration point is a single Protocol class, matching the existing Apify pattern in `app/services/apify.py`. `target_scraper.py` docstring flags this extensibility so future surfaces (X, job boards, news) plug in at the same seam.

**Why daily:** matches the intent-signal decay window (a post older than 48h is rarely actionable outbound; a post older than 7 days is cold). Faster cadence costs more and adds little value. Slower cadence misses the window. Tunable per workspace if someone wants realtime + pays for it.

**Legal posture:** *HiQ Labs v. LinkedIn* (9th Circuit, 2022) provides a defense for accessing **public profile data**; the Supreme Court declined cert. However, LinkedIn's Terms of Service prohibit automated access at scale, and the 2024 *hiQ* remand addressed breach-of-contract claims separately from CFAA. We are not scraping private feed content, not logged in as the user, not bypassing a paywall — but we are automating access to public data. Apify's proxy-rotation + stealth infrastructure carries most of the operational risk. Enterprise customers who require cleaner posture can run BYO-Apify in their own AWS account (design target for v3.1 enterprise tier). Real legal review is a pre-enterprise-contract gate, not a v3.0 blocker.

### 3.3 Scoring engine unchanged from Phase 2.6

The `fit_scorer` service, `extract_icp_and_seller_mirror` prompt, pipeline hybrid branch, and `/profile/update-icp` endpoint all carry forward 1:1. The only difference is the ingest pathway that feeds posts into the pipeline.

**Why:** Phase 2.6 was deliberately architected to be ingest-agnostic. The `_run_pipeline` function takes a `post_id` and a `workspace_id`; it does not care whether the post was captured by the extension or by an Apify scrape. Every invariant of Phase 2.6 (ICP + seller_mirror embeddings on `capability_profile_versions`, `connection.fit_score` caching, multiplicative `fit × intent` combine, feature-flag rollout) applies identically to target-scraped posts.

**What this lets us do:** ship Phase 3 without rewriting any scoring code. The migration is purely in ingest + onboarding + dashboard.

### 3.4 Targets are a new first-class entity

Introduce a `targets` table keyed by `(workspace_id, linkedin_id)` with a type discriminator. `connections` stays as the user-network model for backwards compatibility during the migration window but is superseded as the primary scoring axis. When the extension ingest path is removed in v3.3 (§6), `connections` becomes a legacy-only read path for historical alerts.

**Why a new entity rather than reusing `connections`:** conceptually different. A connection is "someone the user has a LinkedIn-graph relationship with." A target is "someone the workspace deliberately chose to pursue." The overlap is partial — a target may not be a connection, a connection may not be a target. Separate entities let us keep the scoring pipeline clean and the UI honest.

**Schema sketch:**

```sql
-- Migration 012 — enums for type-safe status + source discriminators
CREATE TYPE target_type AS ENUM ('person', 'company');
CREATE TYPE target_scrape_status AS ENUM ('pending', 'active', 'failed', 'paused');
CREATE TYPE target_scrape_failure_code AS ENUM (
  'rate_limit', 'target_private', 'target_not_found',
  'apify_error', 'network_timeout', 'invalid_url', 'other'
);
CREATE TYPE post_source AS ENUM ('extension', 'target_scrape', 'manual_flag');

-- Migration 013 — targets table
CREATE TABLE targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  type target_type NOT NULL,
  linkedin_url TEXT NOT NULL,           -- canonical form, dedup key
  linkedin_id TEXT,                     -- extracted slug/numeric id if derivable
  name TEXT,                            -- populated after first scrape
  headline TEXT,                        -- for people
  company TEXT,                         -- for people (their employer)
  industry TEXT,                        -- for companies
  segment_tags JSONB NOT NULL DEFAULT '[]'::jsonb,  -- list of user-provided tags
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_scraped_at TIMESTAMPTZ,
  scrape_status target_scrape_status NOT NULL DEFAULT 'pending',
  scrape_failure_code target_scrape_failure_code,   -- machine-readable reason
  scrape_failure_reason TEXT,                       -- free-text debugging detail
  fit_score REAL,                       -- cached fit_score per Phase 2.6 scoring
  fit_score_computed_at TIMESTAMPTZ,    -- invalidation trigger — see below
  UNIQUE (workspace_id, linkedin_url)
);
CREATE INDEX idx_targets_workspace_scrape ON targets (workspace_id, scrape_status, last_scraped_at);
CREATE INDEX idx_targets_fit_stale ON targets (workspace_id, fit_score_computed_at);

-- Migration 014 — posts.source discriminator + posts.target_id
ALTER TABLE posts ADD COLUMN target_id UUID REFERENCES targets(id) ON DELETE SET NULL;
ALTER TABLE posts ADD COLUMN source post_source NOT NULL DEFAULT 'extension';
```

Every ingest path stamps `posts.source`, giving us forever-traceable provenance. Machine-readable `scrape_failure_code` feeds dashboard banners; `scrape_failure_reason` is free-text for debugging specific failures.

**Fit score invalidation:** `fit_score_computed_at` tracks cache freshness. A nightly Celery task flags targets as stale when ANY of:
- The workspace's active `capability_profile_version.created_at > target.fit_score_computed_at` (ICP changed)
- `target.last_scraped_at > target.fit_score_computed_at` (target's headline/company drifted since last score)

Stale targets recompute fit_score on next pipeline pass.

**Dual-entity precedence (target AND connection match same linkedin_id):** targets win. A target representing deliberate user intent beats an incidental connection-graph presence. When a workspace adds a target whose `linkedin_id` matches an existing connection, a migration-trigger copies `connection.fit_score → target.fit_score` and nulls the connection's; the pipeline then reads from `target.fit_score` only. During v3.0/v3.1 coexist (both ingest paths active), pipeline branches on `post.source`: `target_scrape` reads target, `extension` reads connection. Post-v3.2, `connection.fit_score` drops in migration 015.

**Dropped from earlier sketch:** `priority_weight` — underspecified ("is this a multiplier? a sort hint?"). Reintroduce only when a concrete use case appears.

### 3.5 Onboarding redesign — the wizard's shape changes

Current Phase 2.6 wizard (6 steps): what-you-sell → icp-review → generate-signals → review-signals → save.

Phase 3 wizard (7 steps, re-sequenced):

1. **What do you sell?** — unchanged
2. **Review your ICP + seller-mirror** — unchanged (Phase 2.6 Task 7 output)
3. **🆕 Paste your target list** — textarea for URLs, one per line, or CSV upload. Inline validation (is this a valid LinkedIn URL? is it public?). Bulk import buttons: "From Salesforce opportunity list" (v3.1), "From HubSpot deal stage", "From CSV".
4. **🆕 Initial scrape progress** — real-time progress bar showing Apify scrape completion (e.g. "187 / 500 targets scraped"). Estimated time-to-first-alert displayed.
5. **Review generated signals** — same as today but scored against the initial scrape data, not against nothing
6. **Accept/reject signals** — unchanged
7. **Save + go to dashboard** — unchanged

**Why keep the wizard at all:** the ICP + seller_mirror extraction from Phase 2.6 is still the right starting point; target-list onboarding layers on top of it rather than replacing it.

**Time to first value:** with the current extension, TTV is ~24h (backfill + wait for feed to refresh with matched posts). With target-list scraping, TTV is ~1–4h (Apify completes initial scrape, pipeline scores, first alerts deliver). This is a direct user-experience improvement, not just a security improvement.

### 3.6 Dashboard redesign

The Phase 2 dashboard shows a "Ranked People List" from the user's network. Phase 3 dashboard shows a "Ranked Target Activity" feed: targets ordered by their recent highest-scoring post, grouped by segment tag. Drill-in shows the target's full post history with Sonar's score for each.

**Why:** target-scoped, not network-scoped. The user asked Sonar to watch these people; the dashboard's job is to surface what's happening with them.

**Incremental aggregation (Phase 2 Dashboard slice pattern):** `person_signal_summary` gets a sibling `target_signal_summary` keyed by `target_id` instead of `connection_id`. Same ~100ms-per-post refresh budget. Chain-at-end pattern from `incremental_trending.py` applies identically.

### 3.7 Extension deprecation path

- **v3.0 (this phase):** extension still works as-is. `/capture/*` endpoints accept posts from extension AND target-scrape Apify pipeline writes to the same `posts` table. Both sources flow through the same scoring pipeline. Users who've already installed the extension see no degradation.
- **v3.1:** extension put on warn-only mode. It continues to capture, but the frontend shows a banner: "Passive feed capture is being deprecated in favor of target-list tracking. Paste your target list to migrate." Onboarding for new users skips the extension install step.
- **v3.2:** extension capture disabled server-side (CORS tightened, `/capture/*` returns 410 Gone). Extension becomes a read-only UX overlay (Lusha/Apollo shape): user-initiated click to show Sonar's score on a profile they're viewing. No background observation. No `/auth/token` cross-origin access. No linkedin.com in CORS.
- **v3.3:** decide based on usage data whether to maintain the read-only overlay extension or remove entirely. If <20% of active users install it, remove. If >50%, keep and invest in it.

**Why staged, not big-bang:** existing users shouldn't wake up to a broken product. The staged path gives 60–90 days of overlap where both ingest modes work, which is plenty of time for users to paste their target lists.

### 3.8 Issues that close structurally (not through code fixes)

- [#107](https://github.com/nischal94/sonar/issues/107) — CORS service-worker routing. With the extension no longer needing linkedin.com cross-origin access, the CORS widening gets removed entirely.
- [#108](https://github.com/nischal94/sonar/issues/108) — Apify token in URL query param. Moot once target-scrape Apify calls are made server-to-server with Authorization-header auth.

Both close when v3.2 ships. Do not spend engineering time on them before then; the architecture change makes them moot.

---

## 4. Architecture

### Component graph

```
                                    ┌──► Apify (public profile scrape)
User pastes target list ─► targets ─┤
                                    └──► Celery beat (daily per-workspace)
                                              │
                                              ▼
                             Apify response ─► posts (source='target_scrape')
                                              │
                                              ▼
                                  _run_pipeline (unchanged from Phase 2.6)
                                              │
                   ┌──────────────────────────┼──────────────────────────┐
                   ▼                          ▼                          ▼
              Fit × Intent              target_signal_summary       Alerts
           (Phase 2.6 scoring)          (incremental aggregation)   (Slack/Telegram/email)
                   │
                   ▼
                Dashboard (ranked target activity)
```

### New services / files

- `backend/app/models/target.py` — Target ORM model
- `backend/app/routers/targets.py` — CRUD endpoints: `POST /workspace/targets` (bulk), `GET /workspace/targets`, `DELETE /workspace/targets/{id}`, `POST /workspace/targets/csv-upload`
- `backend/app/services/target_scraper.py` — Protocol + RealTargetScraper (Apify-backed) + FakeTargetScraper pattern (mirror `app/services/apify.py`)
- `backend/app/workers/scrape_targets_daily.py` — Celery beat task
- `backend/app/workers/target_signal_aggregator.py` — target-side incremental aggregation
- `backend/scripts/import_targets_from_csv.py` — one-shot CLI for bulk onboarding
- `frontend/src/pages/TargetList.tsx` — target management UI
- `frontend/src/pages/SignalConfig.tsx` — extended with steps 3–4 (target paste + scrape progress)

### Unchanged from Phase 2.6

- Everything in `app/services/fit_scorer.py`
- Everything in `app/prompts/` (including Phase 2.6's `extract_icp_and_seller_mirror`)
- `_run_pipeline` in `app/workers/pipeline.py`
- `/profile/extract`, `/profile/update-icp`
- All delivery channels
- Alert schema and rendering (Phase 2.6's nullable `relationship_score` fix stays; hybrid alerts continue to render correctly)
- Migrations 008–011 (Phase 2.6 schema)

---

## 5. Non-goals (explicitly deferred)

- **Network-scoped signals (1st/2nd/3rd degree).** The user's LinkedIn graph is no longer the scoping primitive. If we want "warm intros through mutual connections," that's a v3.4+ feature built on top of targets (e.g., "among your connections, who can intro to this target?").
- **Real-time feed observation.** No browser-side observation. If the user wants "what's happening RIGHT NOW on LinkedIn," they open LinkedIn; Sonar operates on a daily cadence.
- **User's LinkedIn cookie storage.** Never. The pivot's whole point is eliminating this vector.
- **Team / multi-user workspace mode.** Still single-user-per-workspace for v3.0. Team mode is v4 territory.
- **Multi-surface intent (X/Twitter, job boards, news).** The architecture supports it; the phase scope doesn't include it. Each surface is its own v3.x slice.
- **Outbound automation (draft → send).** Draft generation exists (`context_generator`). Automated sending is v4+.

---

## 6. Migration sequence — what happens to what

| Asset | Today | After Phase 3 v3.0 | After v3.2 |
|---|---|---|---|
| `extension/` (Chrome MV3) | Primary ingest | Still works; deprecation banner | Read-only UX overlay |
| `connections` table | User's network graph | Legacy read path; not written to by new flows | Deprecated, read-only |
| `targets` table | Does not exist | Primary scoring axis | Primary scoring axis |
| `posts.source` | Always 'extension' (implicit) | Explicit: 'extension' \| 'target_scrape' | 'target_scrape' \| 'manual_flag' |
| Day-one backfill | Scrape user's 1st-degrees | Deprecated; replaced by target-list onboarding | Removed |
| `/capture/*` endpoints | Active | Active (both paths coexist) | Returns 410 Gone |
| CORS `allow_origins` | includes linkedin.com | includes linkedin.com | linkedin.com removed |
| `/profile/extract` | Unchanged | Unchanged | Unchanged |
| Fit × Intent scoring | Phase 2.6 | Phase 2.6 | Phase 2.6 |
| Delivery channels | All | All | All |

---

## 7. Risks

1. **Apify rate limits or pricing shift.** ~$0.001/post means 200 targets × 20 posts/day × 30 days = 120k ops/month = ~$120/month per workspace. Manageable at SMB pricing ($99–$499/mo). If Apify changes pricing ≥5×, swap to Bright Data or self-hosted Playwright. 1–2 week migration.

2. **LinkedIn adds CAPTCHA to public profile URLs.** Medium likelihood over 3 years. Mitigations: (a) Apify's rotating-proxy infrastructure is designed to handle this, (b) add secondary surfaces (X, job boards, news) so no single surface is load-bearing, (c) fall back to user-initiated-only extension for affected profiles.

3. **User pastes bad URLs (mistyped, expired, private-only profiles).** Schema enforces unique `(workspace_id, linkedin_url)` and validates URL shape on insert. Scrape status column tracks failures per target. Dashboard surfaces failed targets so the user can fix them. Expected failure rate: ~5%.

4. **User abandons target-list maintenance.** Lists go stale (people change jobs, companies get acquired). Mitigation: weekly digest email includes "X targets haven't posted in 60 days — prune?" prompt. CRM sync (v3.1) automates re-population from opportunity stages.

5. **Target-list size limits for scoring quality.** Below ~50 targets, Fit × Intent thresholds don't tune well (too little signal). Above ~2000, daily scraping costs spike. Enforce 50–2000 as soft bounds in the onboarding UI with explanatory copy.

6. **The "magic" of feed observation is hard to replace marketing-wise.** The pivot's product story is tighter ("paste your targets, get alerts") but less viscerally magical than "we read your feed." Accept this; compensate with a tight demo showing time-to-first-alert under 4h.

7. **Silent workspace-level scrape failure.** If Apify rate-limits or CAPTCHA-breaks an entire workspace's daily run, the product just gets quieter — no alerts, user blames us for noise-free inbox. Mitigations:
   - Dashboard banner: "X targets failed to scrape in the last 24h — review" (red if >50% of workspace's targets failed)
   - Weekly digest email includes: "Y targets have not produced content in 60 days — prune?"
   - Celery task emits a metric per workspace per day (`target_scrape_success_ratio`); alert on-call when workspace ratio drops below 0.5
   - Scrape failures logged with `scrape_failure_code` for aggregate diagnosis

---

## 8. Success criteria

Phase 3 v3.0 is shippable when all hold:

1. **Onboarding completion rate ≥ 75%** from landing → first target list pasted, measured on the first 20 workspace signups after launch.
2. **Time-to-first-alert ≤ 4h** (p95) from target-list save to first delivered alert, on target lists of 100+ entries.
3. **Zero posts delivered from the extension ingest path for workspaces that completed target-list onboarding** (confirms users are actually using the new path).
4. **Fit × Intent DoD re-validated on target-scraped data (HARD GATE before flag flip).** Target-scraped posts are a different distribution than feed-observed ones: pre-filtered for relevance, fewer noise posts, different stylistic mix. Phase 2.6 thresholds tuned on feed data may be too loose OR too strict here. Re-run `scripts/calibrate_matching.py analyze-hybrid` against a freshly labeled 30-post target-scraped dataset for BOTH Dwao and CleverTap workspaces. Pick the winning λ under DoD (P@5 ≥ 0.6, Recall@5 ≥ 0.5, zero top-5 competitors) on both. Document in `eval/calibration/phase-3-target-data-findings.md`. This is the direct analog of Phase 2.6 Task 9 — no flag flip without it.
5. **Weekly Apify cost ≤ $50/workspace** at a 500-target list with daily cadence. If higher, revisit scrape cadence or batch.
6. **Zero new security issues filed against the extension during the v3.0 window** (because it's no longer the primary data path).
7. **Post-embedding retention:** posts older than 90 days have their embedding column nulled (row retained for alert history). Implements via a weekly Celery archival task. Keeps pgvector disk footprint bounded. 1536-dim × 10k posts/workspace/day × 365 days = ~22GB/workspace/year without this.

---

## 9. Implementation sequence (feeder for writing-plans)

Not the full plan — just the slicing shape. Each step ships as its own PR with its own spec + quality review, following the Phase 2.6 discipline.

1. Migration 012 (enums) + 013 (targets table) + 014 (posts.target_id, posts.source) + ORM updates
2. `app/models/target.py` + target CRUD endpoints (`POST/GET/DELETE /workspace/targets`) with staggered-dispatch hash-based scheduling
3. `app/services/target_scraper.py` — Protocol + RealTargetScraper (Apify-backed) + FakeTargetScraper + DI factory. Docstring notes the Protocol is extensible to X/job-boards/news
4. **Batch embedding optimization** — before any scrape-heavy task runs, verify `embedding_provider.embed_batch(texts)` exists and is used in `scrape_targets_daily.py`. 10k posts per workspace per day × 1 API call per post = 10k API calls; batched at 2048/call = 5 calls. ~100× cost + latency win. Do this BEFORE the beat task, not after.
5. `app/workers/scrape_targets_daily.py` — Celery beat task with `hash(workspace_id) % 86400` dispatch offset; processes one workspace at a time; `scrape_failure_code` tracking per target; emits `target_scrape_success_ratio` metric per workspace
6. Pipeline extension — when `posts.source='target_scrape'`, use `target.fit_score`. When `'extension'`, use legacy `connection.fit_score`. Dual-entity precedence rule per §3.4 (target wins over connection on linkedin_id match).
7. `fit_score_computed_at` invalidation Celery task — nightly pass flags targets where `active_profile_version.created_at > fit_score_computed_at` OR `last_scraped_at > fit_score_computed_at`
8. Wizard steps 3 + 4 — target paste/upload UI + scrape progress view
9. Dashboard redesign — ranked target activity + segment-tags drill-in (jsonb `@>` filter) + workspace scrape-health banner (red when >50% targets failed in last 24h)
10. CSV import script + `POST /workspace/targets/csv-upload` endpoint
11. Extension deprecation banner in frontend + onboarding skip-extension flow
12. Post-embedding retention: weekly Celery task nullifies `posts.embedding` for rows older than 90 days, row retained for history
13. Calibration redo (HARD GATE) — generate a labeled target-scraped dataset for Dwao + CleverTap, rerun `analyze-hybrid`, validate DoD holds on the new data distribution. No flag flip without this.
14. v3.0 launch gate: flip `workspace.use_target_based_ingest=TRUE` per workspace after successful onboarding; monitor for 2 weeks before default-on
15. Migration 015 (post-v3.2, after extension capture disabled) — drop `connections.fit_score` column; `targets.fit_score` is the sole source of truth

Then v3.1 (CRM sync, priority queueing tiers), v3.2 (extension deprecation + migration 015), v3.3 (extension-as-overlay or removal).

Each step is scoped to one PR. The full implementation plan (bite-sized TDD tasks, exact code snippets, commit messages) is the output of the `superpowers:writing-plans` invocation that follows this design's approval.

---

## 10. Out-of-band prerequisites before implementation starts

- **Snapshot the dogfood DB** (per CLAUDE.md § Database and migrations): `docker compose exec -T postgres pg_dump -U sonar sonar > snapshots/$(date +%Y-%m-%d)-pre-phase-3.sql`. Phase 2.6's wipe made this rule explicit; it applies doubly here since Phase 3 introduces table-level structural change.
- **Codex-review this design doc** (per CLAUDE.md § Database and migrations): per the post-Phase-2.6 rule that plans touching migrations get adversarial review. `codex review docs/phase-3/design.md` — look specifically for: targets/connections entity boundary correctness, legal risk in §3.2 scraping claims, onboarding UX gaps.
- **Open with `/careful`** on the first implementation session. Migration 012 + 013 are new-table DDL; careful catches DROP TABLE during any downgrade testing.
- **Run `/plan-ceo-review` on this design** before writing-plans. This is a product-shape call more than an engineering call; a CEO-mode review against "is this the right bet given the competition" is cheap insurance before 6–8 weeks of eng.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (after design revisions) | 12 issues found across Architecture (6) + Code Quality (3) + Performance (3); 2 critical failure-mode gaps surfaced; all 12 addressed inline in this revision |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**ENG REVIEW FINDINGS ADDRESSED:**
- 1A/1E: fit_score precedence during coexist + drop `connections.fit_score` post-v3.2 (§3.4 + §9 item 15)
- 1B: staggered dispatch via `hash(workspace_id) % 86400` (§3.2 + §9 item 5)
- 1C: target_scraper.py extensibility note (§3.2 + §9 item 3)
- 1D: tightened legal posture with TOS + 2024 hiQ remand context (§3.2)
- 1F: enum types for `post_source`, `target_type`, `target_scrape_status`, `target_scrape_failure_code` (§3.4 migration 012)
- 2A: `segment_tag TEXT` → `segment_tags JSONB` (§3.4)
- 2B: `priority_weight` dropped (YAGNI)
- 2C: `scrape_failure_code` ENUM + `scrape_failure_reason` TEXT both present (§3.4)
- 4A: batch embedding optimization explicit as §9 item 4 — BEFORE beat task scales
- 4B: `fit_score_computed_at` + nightly invalidation task (§3.4 + §9 item 7)
- 4C: 90-day post embedding retention (§8 success criterion #7 + §9 item 12)

**CRITICAL FAILURE MODES ADDRESSED:**
- Silent workspace-level scrape failure → dashboard banner + weekly digest prompt + on-call metric (§7 risk #7)
- DoD re-validation on target-scraped data distribution → hard gate before flag flip, explicit calibration redo (§8 success criterion #4 + §9 item 13)

**VERDICT:** ENG CLEARED — ready for `/codex review` or `superpowers:writing-plans`. Design doc v2 (post-revision) is the version to review externally.

**UNRESOLVED:** none within eng review scope. Outstanding strategic question (whether Path A is the right pivot at all) is CEO-review territory — explicitly recommended as optional next step.
