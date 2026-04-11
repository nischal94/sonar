# Sonar Phase 2 — Network Intelligence Design Spec

**Date:** 2026-04-11
**Status:** Design approved, ready for implementation planning
**Builds on:** Phase 1 ingest pipeline (`backend/app/workers/pipeline.py`), Chrome extension (`extension/`), React dashboard (`frontend/`)

---

## 1. Overview

Phase 2 transforms Sonar from a raw post-ingest pipeline into a network-aware buying-intent intelligence product. It sits on top of Phase 1's ingest infrastructure and adds four user-facing capabilities:

1. A **Signal Configuration Wizard** that turns "what you sell" into structured, embeddable buying signals
2. A **Day-One Backfill** that gives users an immediately populated dashboard on first use
3. A **Network Intelligence Dashboard** with a ranked people list, company heatmap, and trending topics panel
4. A **Weekly Digest Email** with a market brief, ranked people, and blind-spot discoveries

All four features serve one job: **given a description of what the user sells, surface the people in their LinkedIn network who are showing intent to buy that specific thing, ranked by signal strength, with the context needed to reach out intelligently.**

---

## 2. Core Thesis & Competitive Positioning

**Thesis:** A product company or agency sells a specific thing. They want to catch buying intent for that thing *in their own network*, on LinkedIn, in real time.

**Positioning vs Sales Navigator:** Sonar is not a replacement for LinkedIn Sales Navigator. Sales Navigator is stronger at advanced search, account tracking, job change alerts, contact reveal, and CRM integration — we do not compete with those features and will not build them.

Sonar's differentiation surface is what Sales Navigator does *not* do well:

- Network-aware intent from the user's actual LinkedIn feed
- Post-level signals (not just account-level events)
- Personalized semantic signal matching tuned to what *you* specifically sell
- Week-over-week trend velocity across the user's network
- Semantic theme matching that catches intent even without keyword matches
- Contextualized outreach drafts tied to specific post content
- Affordability — targeting a price point well below Sales Navigator

**One-line positioning:** *"Sales Navigator tells you who to hunt. Sonar tells you who's raising their hand in your network right now."*

**Out of scope — explicit non-goals for Phase 2:**

- Real-time alerts / push notifications (Phase 3)
- CRM integrations (Phase 3)
- Multi-user workspaces / team features (Phase 3)
- Lead list management, advanced search, contact info reveal (not on roadmap — Sales Navigator territory)
- Mobile app

---

## 3. User Journey

1. **Sign up** → user creates a workspace and account
2. **Install the Chrome extension** (mandatory — no extension, no product)
3. **Complete Signal Configuration Wizard** → describes what they sell, LLM proposes signals, user confirms/edits
4. **Extension captures 1st-degree connection list** from LinkedIn connections page
5. **Day-One Backfill runs** → scrapes 90 days of 1st-degree posts + 30 days of ICP-filtered 2nd-degree posts via Apify
6. **Dashboard opens with real signals already present** — user sees 15-30+ pre-populated signals from day one
7. **Ongoing use:** extension syncs passively as the user uses LinkedIn; new posts flow through the pipeline; the people leaderboard updates within minutes
8. **Weekly digest** arrives in the user's inbox every Monday with a market brief, ranked people, and Ring 3 blind spots

---

## 4. Feature Specifications

### 4.1 Signal Configuration Wizard

**Purpose:** Turn a free-form description of what the user sells into a structured set of embeddable buying signals that power Rings 1 and 2 of the trending-topics system.

**Flow (target: 60 seconds end to end):**

1. **Step 1 — "What do you sell?"** — single textarea. Example: *"Fractional CTO services for Series A-B SaaS startups with small engineering teams."*
2. **Step 2 — "Who's your ICP?"** — optional one-liner. Example: *"CEOs and VPs Eng at 20-50 person startups."*
3. **Step 3 — LLM proposes signals** — server-side LLM call generates 8-10 candidate signals. Each candidate has:
   - `phrase` — short human-readable label ("struggling to hire senior engineers")
   - `example_post` — a realistic LinkedIn post example matching this signal
   - `intent_strength` — LLM confidence (0-1) that this signal indicates real buying intent
4. **Step 4 — User reviews and edits** — accept / reject / edit buttons per signal. User can add custom signals.
5. **Step 5 — Save** — for each confirmed signal, compute a 1536-dim embedding and persist. Active capability profile is marked. Dashboard opens.

**Important: signals must stay editable over time.** A dedicated `/signals` settings page allows the user to add, edit, disable, or remove signals at any time. Ring 3 "blind spot" discoveries have a one-click "Add as a signal" button that routes through the same code path.

**LLM prompt structure:**

- System prompt: static description of the task ("You are a sales intelligence analyst helping the user define buying signals for their product.")
- User message: the user's free-form "what you sell" + "ICP" text — **never interpolated into the system prompt**
- Output: structured JSON with a `signals` array matching the schema above
- `max_tokens`: 1500
- Output parsing: markdown fence-stripping logic already exists in `context_generator.py`; reuse it

**Data model:** see Section 5.1 (new `signals` table with `vector(1536)` column).

**New endpoints:**

- `POST /workspace/signals/propose` — body `{ what_you_sell, icp }` → returns proposed signals (LLM call, no DB write)
- `POST /workspace/signals/confirm` — body `{ accepted_signals: [...] }` → computes embeddings, persists rows, marks profile active
- `GET /workspace/signals` — returns current active signals
- `PATCH /workspace/signals/{signal_id}` — edit a single signal, triggers re-embedding
- `DELETE /workspace/signals/{signal_id}` — soft-disable
- `POST /workspace/signals/from-discovery` — promote a Ring 3 discovered cluster to a confirmed signal

**New frontend:** `frontend/src/pages/SignalConfig.tsx` — multi-step wizard. Routes: `/signals/setup` for first-time users, `/signals` for ongoing editing.

---

### 4.2 Day-One Backfill

**Purpose:** Solve the "empty dashboard on day one" problem. Give users immediate value instead of waiting a week for organic feed sync to accumulate signals.

**Replaces:** The current `public_poller.py` (which does generic keyword search against LinkedIn via Apify and is removed as part of this phase).

**Flow:**

1. User completes the Signal Configuration Wizard
2. Extension is prompted to capture the user's full 1st-degree connection list from `https://www.linkedin.com/mynetwork/invite-connect/connections/` (new extension capability — see Section 7)
3. Extension POSTs the connection list to a new endpoint: `POST /extension/connections/bulk`
4. Backend enqueues a one-time `day_one_backfill` Celery task
5. Task runs two Apify jobs:
   - **1st-degree scrape** — scrape up to 500 1st-degree connection profile URLs via an Apify profile-scraping actor. 90 days of post history. (Free tier: cap at 200.)
   - **ICP-filtered 2nd-degree scrape** — LLM generates an ICP filter from the capability profile (title keywords, seniority levels, company size range, industries). Apify actor runs a filtered 2nd-degree search. Up to 500 profiles, 30 days of history. (Free tier: cap at 100.)
6. Resulting posts flow through the standard Phase 1 pipeline
7. `Workspace.backfill_used` is marked true so the backfill cannot be triggered twice

**Fallback behavior:** If no suitable Apify actor exists for ICP-filtered 2nd-degree search, the backfill degrades gracefully to 1st-degree-only. This is a known unknown to validate during implementation — Apify actor availability changes over time. The backfill task must not fail outright if one of the two scrapes is unavailable.

**Cost model:** ~1,000 profiles per workspace × ~$0.002/profile ≈ $2 per workspace per backfill. One-time per workspace. Capped. Absorbed as user acquisition cost (free tier lower caps), included in pricing for paid tiers.

**Relationship-tier labeling:** All posts from the backfill are tagged with the correct `Connection.degree` (1 or 2) at ingest time. This drives the relationship badges shown on the dashboard ranked list.

---

### 4.3 Network Intelligence Dashboard

**Purpose:** A single page where the user sees everything that matters — who in their network is showing intent right now, where that activity is concentrated, and what topics are rising.

**Layout (three stacked sections, in order of priority):**

**Section A — Company Heatmap Strip (top)**
- Horizontal row of company "pills" showing where signal activity is concentrated
- Each pill: company name + activity indicator (e.g., three dots filled = high activity)
- Ranked left-to-right by aggregate signal strength within that company in the last 7 days
- Click a pill → filters the ranked list below to that company
- Data source: `company_signal_summary` table (new — see Section 5.1)

**Section B — Ranked People List (primary)**
- The core of the dashboard. Every person in the user's network who has crossed the signal threshold in the last 7 days, ranked by signal strength.
- No artificial cap on count — shows everyone above threshold. (Threshold is a user-adjustable setting with defaults.)
- Each row:
  - Relationship badge (🟢 1st-degree / 🟡 2nd-degree with N mutual connections)
  - Name + title + company
  - Aggregate signal score + trend arrow (↑ rising this week, → stable, ↓ falling)
  - Most recent matching post snippet (2-line preview)
  - Matching signal label ("struggling to hire senior engineers")
  - Quick actions: "View full thread" / "Draft outreach" / "Dismiss"
- Data source: `person_signal_summary` table (new — see Section 5.1)

**Section C — Trending Topics Panel**
- Three tabs: Ring 1 (exact signal matches), Ring 2 (semantic matches), Ring 3 (domain-adjacent discoveries)
- Each tab shows the top N trending topics ranked by week-over-week velocity delta
- Each topic shows: label, velocity (e.g., "+12 posts vs. last week"), list of people posting about it
- Ring 3 tab has "Add as a signal" button per topic
- Data source: `trends` table (new — see Section 5.1)

**New frontend page:** `frontend/src/pages/NetworkIntelligenceDashboard.tsx` at `/dashboard`

**New endpoints:**

- `GET /dashboard/people?threshold=0.65&company=<optional>` — ranked list
- `GET /dashboard/heatmap` — company heatmap data
- `GET /dashboard/trending?ring=1|2|3` — trending topics for a specific ring

---

### 4.4 Three-Ring Trending Topics System

This is the most structurally complex feature in Phase 2. **The three rings are two distinct subsystems that share one UI panel. They run at different times, on different data, with different outputs. The spec treats them as separate subsystems to avoid implementation confusion.**

#### Ring 1 — Exact Configured Signal Matches (post-level)

**What it does:** Matches incoming posts against the user's configured signal phrases via keyword/phrase matching.

**How:** During the Phase 1 pipeline, after embedding, each post is checked against the user's active signal list for literal phrase matches (case-insensitive, simple tokenization). A match sets `post.ring1_matches` to an array of signal IDs.

**Aggregation:** The incremental task (triggered at the end of the pipeline) increments Redis counters of the form `ring1:{workspace_id}:{signal_id}` with a 14-day rolling window. Nightly job snapshots these counters into the `trends` table and computes week-over-week deltas.

**Output:** Ring 1 tab on the dashboard shows each configured signal's velocity this week vs last week.

#### Ring 2 — LLM Semantic Matches (post-level)

**What it does:** Catches posts whose intent matches a signal semantically but not literally. E.g., a post about "we've been interviewing forever" matches the "struggling to hire senior engineers" signal even without the exact phrase.

**How:** Two layers of semantic matching, both post-level:

1. **Vector similarity matching (query-time):** After a post is embedded, the pipeline runs a pgvector cosine similarity query against the new `signals` table (not JSONB — see Section 5.1 for why). For each signal where `cosine_distance < 0.35` (tunable), the post is tagged with `post.ring2_matches[{signal_id, similarity}]`.

2. **LLM theme extraction (reused call):** The existing `context_generator.py` LLM call is extended with a new output field `themes: list[str]` — 3-5 semantic themes the LLM extracts from the post. This piggybacks on the existing call, so cost is essentially zero. Themes are stored on the post and cross-referenced against signals for secondary tagging.

**Aggregation:** Same model as Ring 1 — Redis counters of the form `ring2:{workspace_id}:{signal_id}` incremented by the incremental task, snapshotted nightly, velocity delta computed.

**Output:** Ring 2 tab on the dashboard shows signals ranked by semantic-match velocity. Same UI shape as Ring 1, different data source.

**CRITICAL: Pipeline branching change.**
The current Phase 1 pipeline has `keyword_filter.py` as an early exit — posts that fail the keyword filter never reach the LLM. **This must change.** The new pipeline flow:

1. Ingest
2. Embed (always — no early exit)
3. Compute Ring 1 keyword matches (doesn't gate pipeline)
4. Compute Ring 2 vector similarity against signals table (doesn't gate pipeline)
5. LLM call (context_generator with extended themes output)
6. Scoring — the existing `scorer.py` now takes keyword match as *one input* rather than a gate
7. Alert creation if `combined_score > threshold`
8. Incremental task — update person aggregation + Redis counters

The keyword filter is not removed — it's demoted from a gate to a scoring input. High keyword match adds score; no keyword match doesn't block the pipeline.

#### Ring 3 — Domain-Adjacent Discovery (aggregate-level)

**What it does:** Discovers topics that are rising in the user's network but are *not* covered by any existing configured signal. Filtered by semantic proximity to the capability profile so it never surfaces random noise.

**How (nightly batch only — this is NOT a post-level operation):**

1. Nightly Celery job pulls all posts from the last 14 days for the workspace
2. Runs HDBSCAN clustering on post embeddings (`hdbscan` Python library, `min_cluster_size=3`, tunable)
3. For each cluster:
   - Compute cluster centroid embedding
   - Filter out clusters where `cosine_similarity(centroid, capability_profile_embedding) < 0.25` — keeps the discovery bounded to the user's domain
   - Filter out clusters that significantly overlap with existing configured signals (`cosine_similarity(centroid, any_existing_signal) > 0.80`) — no redundancy with Rings 1/2
4. For each remaining cluster, call a cheap LLM with the 5 closest posts to the centroid and ask for a short label + summary
5. Persist discovered clusters to `trends` table with `ring=3`
6. Compare to previous week's discovered clusters and compute velocity delta

**Scale consideration:** HDBSCAN on ~10,000-50,000 post embeddings per workspace is feasible on reasonable hardware in a few seconds to a minute. Only becomes a problem above ~500K posts per workspace, which is out of Phase 2 scope.

**Fallback:** If HDBSCAN produces zero valid clusters (e.g., small networks, early days after onboarding), Ring 3 tab shows an empty state rather than failing. The UI should say: *"Ring 3 discoveries appear as your network generates more activity — check back in a few days."*

**Output:** Ring 3 tab on the dashboard shows the discovered cluster labels, velocity, and posts-in-cluster. Each has "Add as a signal" button → routes to `POST /workspace/signals/from-discovery`.

---

### 4.5 Weekly Digest Email

**Purpose:** Drive habitual re-engagement with the product by delivering curated intelligence on a fixed cadence.

**Cadence:** Every Monday morning at 7am in the user's timezone. Generated by the nightly Celery job on Sunday night.

**Structure (in order):**

1. **Market Brief (3 sentences)** — LLM-generated narrative summary of what moved in the user's network this week. Inputs: top 3 Ring 1/2 signals by velocity, top 1 Ring 3 discovery. Example: *"Your network had a spike in posts about data pipeline migration pain this week — 7 people mentioned legacy ETL bottlenecks, up from 2 last week. Fundraising activity in B2B SaaS also picked up, with 3 VPs of Engineering sharing team-scaling plans."*
2. **Top Signals (up to 15 people)** — ranked list of people who crossed the signal threshold this week, capped at 15 for email readability. Each entry: name, title, company, matching signal, 2-line post snippet, single best outreach draft. The person's full details and more outreach variants are accessible via a "Open in Dashboard" link.
3. **Blind Spots (up to 3)** — Ring 3 discoveries with rising velocity that the user has not yet added as signals. Each entry: cluster label, sample post, "Add as a signal" CTA that deep-links to the signals page with the cluster pre-filled.

**Display cap on email vs backend storage:** The backend stores *everyone* who crossed the threshold. The email truncates to 15 for readability. The "Open in Dashboard" link takes the user to the full list.

**Email service:** Reuse `backend/app/delivery/email.py` from Phase 1. No new delivery infrastructure needed.

**Digest opt-out:** Per-workspace setting, stored in `Workspace.delivery_channels`.

---

## 5. Architecture

### 5.1 Data Model Changes

**New tables:**

```
signals
  id                    UUID PK
  workspace_id          UUID FK → workspaces.id
  profile_version_id    UUID FK → capability_profile_versions.id
  phrase                TEXT
  example_post          TEXT
  intent_strength       FLOAT
  embedding             vector(1536)
  enabled               BOOLEAN DEFAULT true
  created_at            TIMESTAMPTZ
  updated_at            TIMESTAMPTZ

  INDEX ON (workspace_id, enabled)
  HNSW INDEX ON embedding vector_cosine_ops
```

Rationale: proper pgvector column (not JSONB) so Ring 2 can do `ORDER BY embedding <=> post_embedding` in SQL.

```
person_signal_summary
  id                    UUID PK
  workspace_id          UUID FK → workspaces.id
  connection_id         UUID FK → connections.id
  aggregate_score       FLOAT
  trend_direction       TEXT    -- 'up' | 'flat' | 'down'
  last_signal_at        TIMESTAMPTZ
  recent_post_id        UUID FK → posts.id
  recent_signal_id      UUID FK → signals.id
  updated_at            TIMESTAMPTZ

  UNIQUE (workspace_id, connection_id)
  INDEX ON (workspace_id, aggregate_score DESC)
```

Rationale: the incremental task updates this table on every pipeline completion. The dashboard ranked list reads from here (fast, pre-aggregated).

```
company_signal_summary
  id                    UUID PK
  workspace_id          UUID FK → workspaces.id
  company_name          TEXT
  aggregate_score       FLOAT
  active_signal_count   INT
  updated_at            TIMESTAMPTZ

  UNIQUE (workspace_id, company_name)
  INDEX ON (workspace_id, aggregate_score DESC)
```

Rationale: powers the company heatmap strip. Updated by the nightly job, not the incremental task (acceptable 24h staleness for the heatmap).

```
trends
  id                    UUID PK
  workspace_id          UUID FK → workspaces.id
  ring                  INT     -- 1, 2, or 3
  signal_id             UUID FK → signals.id NULL  -- ring 1/2 only
  cluster_label         TEXT                        -- ring 3 only
  cluster_sample_posts  JSONB                       -- ring 3 only
  this_week_count       INT
  last_week_count       INT
  velocity_delta        INT
  snapshot_date         DATE
  created_at            TIMESTAMPTZ

  INDEX ON (workspace_id, ring, snapshot_date DESC)
```

Rationale: one table serves all three rings, disambiguated by the `ring` column. Nightly job writes one row per signal or cluster per snapshot.

**Column additions to existing tables:**

- `posts.embedding vector(1536)` — persisted, not recomputed. HNSW index for Ring 3 clustering queries.
- `posts.ring1_matches JSONB` — list of signal IDs that matched via keyword
- `posts.ring2_matches JSONB` — list of `{signal_id, similarity}` that matched via vector similarity
- `posts.themes JSONB` — list of theme strings extracted by the LLM
- `posts.engagement_counts JSONB` — `{likes, comments, shares}` captured by the extension
- `connections.mutual_count INT` — for 2nd-degree mutual-connection display
- `workspaces.backfill_used BOOLEAN DEFAULT false`
- `users.extension_installed BOOLEAN DEFAULT false` (may already exist — verify in migration)

**Column changes to existing tables:**

- `capability_profile_versions.signal_keywords` → deprecated, replaced by the new `signals` table. Kept for migration compatibility, unused after Phase 2.

**Phase 1 gap fixes rolled into Phase 2 migration:**

- Add missing `ForeignKey` constraint on `Post.connection_id → connections.id`
- Clarify semantics of `SignalEffectiveness` vs feedback model (may collapse into one table)
- Update pipeline's keyword filter from gate to scoring input (code change, not schema)

### 5.2 Celery Architecture

**Existing:** `pipeline.py` processes each post through the ingest pipeline.

**Modified `pipeline.py` flow:**

1. Ingest raw post
2. Embed (always runs — no keyword-filter gate)
3. Compute Ring 1 keyword matches → write to `posts.ring1_matches`
4. Compute Ring 2 vector similarity against `signals` table → write to `posts.ring2_matches`
5. LLM call (existing `context_generator.py`, extended with `themes` output) → write to `posts.themes`
6. Scoring (existing `scorer.py`, modified to treat keyword filter as input not gate)
7. Create alert if `combined_score > threshold`
8. **Chain to incremental task** (new)

**New task: `incremental_trending.py`**

- Triggered at the end of every `pipeline.py` run
- Updates `person_signal_summary.aggregate_score` for the post's author
- Increments Redis counters: `ring1:{workspace_id}:{signal_id}` and `ring2:{workspace_id}:{signal_id}` with 14-day TTL
- Computes the person's trend direction (comparing this week's matches to last week's)
- Target runtime: <100ms per invocation

**New task: `day_one_backfill.py`**

- Triggered once per workspace after wizard completion + connection sync
- Runs two Apify calls (1st-degree profile scrape, 2nd-degree ICP-filtered scrape)
- Dispatches each resulting post to `pipeline.py`
- Marks `Workspace.backfill_used = true`
- Fallback: if 2nd-degree actor unavailable, logs a warning and degrades to 1st-degree-only

**New nightly task: `nightly_trending.py`**

- Scheduled via Celery Beat at 2am workspace-local time (or UTC for simplicity in Phase 2)
- For each active workspace:
  1. Snapshot Ring 1 and Ring 2 counters from Redis into the `trends` table
  2. Compute week-over-week deltas for Ring 1/2
  3. Run HDBSCAN clustering on last-14-days post embeddings → Ring 3 discovery
  4. LLM-label each valid cluster
  5. Write Ring 3 rows to `trends` table
  6. Update `company_signal_summary` aggregation
  7. If today is Sunday, generate the weekly digest draft → schedule email send for Monday 7am
- Target runtime: under 5 minutes per workspace

**Removed task: `public_poller.py`**

- Completely deleted (file + Beat schedule entry + Celery task include list)

### 5.3 Pipeline Flow Diagram

```
Extension                         Backend                              User
---------                         -------                              ----
  |                                  |                                   |
  | POST /ingest (posts)             |                                   |
  |--------------------------------->|                                   |
  |                                  | pipeline.py:                      |
  |                                  |   embed                           |
  |                                  |   ring1 keyword match             |
  |                                  |   ring2 vector similarity         |
  |                                  |   LLM (context + themes)          |
  |                                  |   scoring                         |
  |                                  |   alert create                    |
  |                                  |                                   |
  |                                  | incremental_trending.py:          |
  |                                  |   update person_signal_summary    |
  |                                  |   increment Redis counters        |
  |                                  |                                   |
  |                                  | [ongoing]                         |
  |                                  |                                   |
  |                                  | nightly_trending.py (2am):        |
  |                                  |   snapshot counters → trends      |
  |                                  |   HDBSCAN → Ring 3 discovery      |
  |                                  |   update company_signal_summary   |
  |                                  |   [Sunday] generate digest draft  |
  |                                  |                                   |
  |                                  |                     [Monday 7am]  |
  |                                  |----- send weekly digest --------->|
```

---

## 6. API Surface Summary

**New endpoints (grouped by feature):**

*Signal config:*
- `POST /workspace/signals/propose`
- `POST /workspace/signals/confirm`
- `GET /workspace/signals`
- `PATCH /workspace/signals/{signal_id}`
- `DELETE /workspace/signals/{signal_id}`
- `POST /workspace/signals/from-discovery`

*Dashboard:*
- `GET /dashboard/people?threshold&company&limit`
- `GET /dashboard/heatmap`
- `GET /dashboard/trending?ring=1|2|3`

*Extension integration:*
- `POST /extension/connections/bulk` — ingest 1st-degree connection list
- `POST /extension/engagement/{post_id}` — update engagement counts on existing post

*Backfill:*
- `POST /workspace/backfill/trigger` — manual trigger (auto-called after wizard)
- `GET /workspace/backfill/status` — polling endpoint for backfill progress

**Authentication:** all endpoints use the existing JWT bearer auth from Phase 1.

---

## 7. Chrome Extension Changes

Two new capabilities required in the extension beyond what Phase 1 has:

1. **Connection list capture** — a new content script that runs on `https://www.linkedin.com/mynetwork/invite-connect/connections/`, scrolls the list, extracts each connection's profile URL, name, headline, and company, and POSTs the batch to `/extension/connections/bulk`. This is triggered once by the popup "Run day-one scan" button, not passively.

2. **Engagement metrics capture** — when a post is captured during passive feed sync, the extraction logic also grabs reaction count, comment count, and share count. These flow through to the backend as part of the existing ingest payload, stored on `posts.engagement_counts`.

No other extension changes in Phase 2.

---

## 8. Frontend Changes

**New pages:**

- `SignalConfig.tsx` (wizard + ongoing editing) — routes `/signals/setup`, `/signals`
- `NetworkIntelligenceDashboard.tsx` — route `/dashboard`

**Modified pages:**

- `App.tsx` — add new routes, update navigation
- `Onboarding.tsx` — redirect to `/signals/setup` on first login instead of the existing path

**State management:** continue using existing patterns (no new libraries).

**Styling:** continue using existing Tailwind/plain CSS conventions from Phase 1.

---

## 9. Open Decisions to Validate During Implementation

The following items are intentionally called out as unresolved and must be validated during the implementation phase:

1. **2nd-degree ICP-filtered Apify actor availability.** The design assumes such an actor exists. If it doesn't, the backfill degrades to 1st-degree-only. This is a known unknown.
2. **HDBSCAN clustering parameters.** `min_cluster_size=3` is a starting guess; real tuning requires real data.
3. **Signal threshold defaults.** The `combined_score > threshold` value for alert creation needs calibration against real data. Phase 2 ships with a default and a settings UI for user adjustment.
4. **Ring 2 cosine similarity cutoff.** Starting at `0.35` for "matches" but may need tuning.
5. **Ring 3 proximity filter.** Starting at `0.25` minimum cosine similarity to capability profile but may need tuning.
6. **Nightly job runtime.** If clustering exceeds 5 minutes per workspace, will need to split across workers or switch clustering algorithm.

---

## 10. Testing Strategy

- **Unit tests:** signal matching logic, Ring 1 keyword matcher, Ring 2 vector query wrapper, scorer with new inputs, aggregation logic
- **Integration tests:** end-to-end pipeline with a real post going through all three rings, backfill task with mocked Apify responses, nightly task against a seeded database
- **Frontend tests:** wizard flow, dashboard rendering with seeded API responses
- **Manual smoke tests before ship:**
  - Complete wizard end-to-end
  - Verify day-one backfill populates dashboard
  - Verify ranked list updates within 2 minutes of a new post being synced
  - Verify weekly digest email renders correctly on desktop and mobile clients
  - Verify "Add as a signal" from Ring 3 works end-to-end

---

## 11. Security Considerations

- User-supplied text (wizard "what you sell", ICP) goes only in the user message of LLM calls, never interpolated into the system prompt
- All LLM calls have `max_tokens` caps (context_generator: 2000, wizard proposal: 1500, digest brief: 500)
- LLM outputs are never passed directly to SQL, shell, or file paths — all outputs are JSON-parsed and type-validated
- Apify API token is read from environment variable, never committed or logged
- Email rendering uses templating (not string concatenation) to prevent HTML injection in the digest
- All new endpoints require authenticated workspace context; no cross-workspace data leakage

---

## 12. Success Criteria

Phase 2 is "done" when:

1. A new user can sign up, install the extension, complete the wizard, trigger the backfill, and see their first 15+ signals on the dashboard within 5 minutes end-to-end
2. The ranked people list updates within 2 minutes of a new post being synced through the extension
3. The three-ring trending topics panel shows non-empty data after 7 days of ingest
4. The weekly digest email sends successfully and renders correctly on Gmail desktop and iOS Mail
5. Phase 1 regression tests still pass, plus new Phase 2 tests
6. No fabricated Apify actors or data — all external integrations verified working during implementation
