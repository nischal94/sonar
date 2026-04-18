# Sonar Phase 2 Dashboard — Implementation Decisions

**Date:** 2026-04-18
**Status:** Decisions locked, ready for implementation-plan generation
**Slice:** Phase 2 — Dashboard (Ranked People List MVP)
**Builds on:** Phase 2 Foundation (`person_signal_summary` table shipped PR #10) + Wizard (configurable signals shipped PRs #64, #68, #70)
**Design spec:** `docs/phase-2/design.md §4.3` — Section B Ranked People List only; A (Heatmap) and C (Trending Topics) deferred to follow-up slices

This doc captures the implementation-level decisions made during the 2026-04-18 brainstorming session. Companion to `docs/phase-2/design.md`, not a replacement. `writing-plans` should treat both as input when generating the task-level `docs/phase-2/implementation-dashboard.md`.

---

## 1. Scope (Option B — ranked list only)

**In scope:**

- `/dashboard` page rendering a ranked list of people above signal threshold in the last 7 days, ordered by `person_signal_summary.aggregate_score DESC`
- Per-row content (from design.md §4.3 Section B):
  - Relationship badge (🟢 1st-degree / 🟡 2nd-degree + mutual-connection count)
  - Name + title + company
  - Aggregate score + trend arrow (↑ rising / → stable / ↓ falling)
  - Most-recent matching post snippet (2-line preview)
  - Matching signal phrase
  - Quick actions: View thread / Draft outreach / Dismiss
- Threshold slider at top of list (defaults to `workspaces.matching_threshold`, in-session override)
- Relationship-tier checkbox toggles (`[x] 1st-degree  [x] 2nd-degree`)
- 30-second polling with stale-while-revalidate (tab-visibility pause)
- New Celery task `incremental_trending.py` that updates `person_signal_summary` on every pipeline completion
- New endpoint `GET /workspace/dashboard/people`
- `/dashboard` route + wire-up

**Out of scope (explicitly deferred to follow-up slices):**

- Company Heatmap Strip (Section A) — requires `company_signal_summary` nightly aggregation + heatmap endpoint + pill UI
- Trending Topics Panel (Section C) — couples with Discovery slice (Ring 3 clustering populates the `trends` table)
- Click-a-pill-to-filter-by-company (depends on Heatmap)
- Company search / date range / free-text filter
- `Dismiss` row action (requires `dismissed_at` column on `person_signal_summary` — not in Foundation schema)
- URL state for filters (React-component state only in MVP)
- `/dashboard/heatmap` and `/dashboard/trending?ring=N` endpoints

**Rationale:**
The Ranked People List is the "primary" surface per the design spec. Shipping it first gets the critical product hypothesis — *"does a network-scoped ranked list of buying-intent signals actually drive outreach decisions?"* — in front of users within one slice instead of three. Heatmap + Trending Topics answer secondary questions that are only worth investing in once the primary surface has validated signal. This mirrors the Scope-B pattern the Wizard slice used successfully.

---

## 2. Data Refresh (Option B — 30s polling)

**Decision:** 30-second polling with stale-while-revalidate, tab-visibility pause.

**Frontend:**

- Uses React Query (preferred, if already in `frontend/package.json`) OR a manual `useEffect` + `setInterval` hook if React Query isn't already a dep
- Poll target: `GET /workspace/dashboard/people` (with current filter query params)
- Poll interval: 30 seconds
- `document.visibilityState === "hidden"` pauses polling; resuming tab triggers an immediate refetch + resumes the interval
- Stale-while-revalidate: old list stays on screen while new data loads; atomic swap on response
- Loading state only for the initial fetch; subsequent polls update silently

**Backend freshness contract:**

- Celery task `incremental_trending.py` chains to end of `pipeline.py` (one-line `.apply_async()` or Celery `chain()` addition after scoring)
- Per post scored, updates `person_signal_summary` row for the post's author:
  - Bumps `aggregate_score` (7-day rolling window logic per design.md §5.2)
  - Updates `last_signal_at`, `recent_post_id`, `recent_signal_id`
  - Recomputes `trend_direction` by comparing this-week count vs last-week count for the same person
- Target runtime: <100ms per invocation (per design.md §5.2)
- User-visible staleness bound: poll interval (30s) + aggregation lag (<100ms) ≈ 30s. Sufficient for sales-intelligence use case.

**Not built:**

- No WebSocket endpoint
- No Server-Sent Events
- No Redis pub/sub between worker and frontend

Those live in a future "real-time updates" slice when we have signal (pun intended) that users care about sub-30s latency. Pre-launch with no users = premature infrastructure.

---

## 3. Filters (Option C — threshold + relationship)

**Threshold slider:**

- Default value loaded from `workspaces.matching_threshold` (per-workspace DB column, already populated from Phase 1)
- Range: 0.50–0.95, 0.05 increments
- In-session only — changes do NOT persist back to the workspace row in MVP
- Query param: `?threshold=0.65`

**Relationship-tier checkboxes:**

- Two checkboxes labeled `1st-degree` and `2nd-degree`
- Both checked by default
- Unchecking excludes that tier
- Query param: `?relationship=1,2` (defaults to `1,2` when omitted)

**Why these two and not more:**

The threshold and relationship dimensions are the two knobs the product already exposes at the data layer:
- Threshold → `person_signal_summary.aggregate_score >= ?`
- Relationship → `connections.degree IN (?)`

Adding a company-search filter or date-range filter would require either new indexes or per-query joins that haven't been validated against real traffic. YAGNI. Revisit after MVP ships and we see which filters users actually ask for.

**No URL state in MVP.** Filters are React-component state. Browser refresh resets to defaults. URL-encoded filters (shareable dashboard links, bookmarking) is a follow-up polish task.

---

## 4. Data Volume Caveat (2nd-degree sparse until Backfill ships)

2nd-degree connections only populate densely after the Backfill slice ships (Apify pulls 2nd-degree profiles during Day-One Backfill — design.md §4.2). Until Backfill lands, 2nd-degree rows in the list will be whatever the Chrome extension observed passively from the user's feed.

The 2nd-degree filter is still correct to ship now — it just has less to filter. Users will perceive the list as "mostly 1st-degree" which matches early-product reality.

---

## 5. API Design

**Single new endpoint:**

```
GET /workspace/dashboard/people
  ?threshold=0.65           (optional; defaults to workspaces.matching_threshold)
  ?relationship=1,2         (optional; defaults to "1,2"; comma-separated)
  ?limit=50                 (optional; default 50; no cursor pagination in MVP)

Response 200:
{
  "people": [
    {
      "connection_id": "uuid",
      "name": "Jane Doe",
      "title": "VP Engineering",
      "company": "Acme",
      "relationship_degree": 1,
      "mutual_count": null,
      "aggregate_score": 0.82,
      "trend_direction": "up",
      "last_signal_at": "2026-04-18T09:15:00Z",
      "recent_post_snippet": "We've been interviewing for 4 months...",
      "matching_signal_phrase": "struggling to hire senior engineers",
      "recent_post_url": "https://www.linkedin.com/posts/..."
    }
  ],
  "threshold_used": 0.65,
  "total": 47
}
```

**Security:**

- Requires `Depends(get_current_user)` — workspace-scoped by `current_user.workspace_id`
- Rate-limited via slowapi: `30/minute per IP` (30s polling × 1 user = 2 req/min; 30/min leaves plenty of headroom for multiple-tab / page-navigation bursts)
- Response must NEVER include `connection_id`s or signals from a different workspace — query MUST filter on `person_signal_summary.workspace_id`

**Query shape (reference for implementer):**

```sql
SELECT pss.*, c.name, c.title, c.company, c.degree, c.mutual_count,
       p.content_snippet, p.linkedin_url,
       s.phrase
FROM person_signal_summary pss
JOIN connections c ON c.id = pss.connection_id
LEFT JOIN posts p ON p.id = pss.recent_post_id
LEFT JOIN signals s ON s.id = pss.recent_signal_id
WHERE pss.workspace_id = :workspace_id
  AND pss.aggregate_score >= :threshold
  AND c.degree = ANY(:degrees)
  AND pss.last_signal_at > now() - interval '7 days'
ORDER BY pss.aggregate_score DESC
LIMIT :limit
```

Implementer should verify schema-level join keys match Foundation migration 002's actual column names.

---

## 6. Frontend

**New page:**

`frontend/src/pages/NetworkIntelligenceDashboard.tsx` — single component, step-state-free (unlike Wizard).

**State:**

```tsx
const [threshold, setThreshold] = useState<number>(workspaceDefault);
const [relationshipTiers, setRelationshipTiers] = useState<Set<1 | 2>>(new Set([1, 2]));
const { data, isLoading, isStale } = usePolledDashboard({ threshold, relationship: [...relationshipTiers] });
```

**Row rendering:**

- Relationship badge: colored dot or pill; shows mutual-count only for `degree === 2`
- Score: displayed as a percentage (e.g., "82%") or 0–1 float — implementer's judgment
- Trend arrow: ↑ ↓ → based on `trend_direction` enum
- Post snippet: 2-line max, fade-out or ellipsis
- Signal phrase: italic label
- Quick actions:
  - **View thread** → opens `recent_post_url` in new tab
  - **Draft outreach** → placeholder `onClick` that shows a "coming soon" toast (Phase 1 outreach-drafts exist but UI integration is out-of-scope)
  - **Dismiss** → deferred (missing schema support)

**Styling:** inline styles matching `Settings.tsx` and `SignalConfig.tsx` conventions. No Tailwind.

**Loading/empty/error states:**

- Initial load: skeleton rows (3-5 placeholder cards)
- Empty (0 people above threshold): friendly message — "No signals in your network above this threshold yet. Try lowering the threshold, or wait for more posts to flow through."
- Error: red banner with retry button
- Stale (during poll): subtle "Updating…" pill in the header; list stays interactive

---

## 7. Telemetry

**No new telemetry tables in this slice.** `person_signal_summary` is itself the source of truth for what the user saw.

Dashboard analytics (time-on-page, rows-clicked, filter-used) deferred to follow-up. YAGNI until we have users and a question to answer.

---

## 8. Task Outline (~10-12 tasks, subject to `writing-plans` refinement)

1. New Celery task `backend/app/workers/incremental_trending.py` — pure aggregation function + unit tests
2. Wire `incremental_trending` into `backend/app/workers/pipeline.py` chain + integration test
3. Pydantic response schemas in `backend/app/schemas/dashboard.py`
4. `GET /workspace/dashboard/people` endpoint in new router `backend/app/routers/dashboard.py` + 3-4 endpoint tests (happy path, filtering, workspace isolation, empty state)
5. Integration test: seed workspace + connections + posts + signals → pipeline → assert endpoint returns expected rows
6. Frontend `NetworkIntelligenceDashboard.tsx` — list rendering + skeleton + empty + error states
7. Frontend: threshold slider + relationship checkboxes wired to the fetch
8. Frontend: 30-second polling hook with tab-visibility pause
9. Frontend: Vitest smoke tests (renders empty state, renders list, filter changes re-fetch)
10. Route wire-up in `App.tsx` — add `/dashboard` route inside `<RequireAuth>`
11. E2E Playwright spec: register → wizard → dashboard golden path
12. TODO.md + CLAUDE.md updates (mention `incremental_trending` as the canonical pipeline-chain pattern)

---

## 9. Success Criteria

1. A user who completed the wizard lands on `/dashboard` and sees their current ranked list within one page-load
2. New signals flowing through `pipeline.py` appear in the list within 30 seconds (poll interval + aggregation lag)
3. Threshold slider updates the list in under 500ms (no page reload, filtered via query param)
4. Relationship-tier toggles filter correctly (test: uncheck 2nd-degree → only 1st-degree rows remain)
5. All existing tests still pass; new tests deterministic
6. Playwright E2E walks register → wizard → dashboard without `.fixme` markers

---

## 10. Open Questions (to resolve during implementation, not blocking plan generation)

- Does `frontend/package.json` already include `@tanstack/react-query` or similar? If not, whether to add it or use a manual polling hook is an implementer call. Vote: manual hook — one fewer dep.
- `connections.mutual_count` — is it actually populated on real 1st-degree rows? Not guaranteed. Frontend should gracefully handle `null`.
- `posts.content_snippet` — if the post model stores the full content without a pre-truncated snippet, the endpoint should truncate server-side (first 200 chars or first 2 lines) rather than dump full post bodies over the wire.
- Rate-limit value (30/min per IP) may need to be higher if multiple tabs are common; tune after real user traffic.
- What renders at `/dashboard` today? Onboarding navigates there after wizard completion (Task 11 redirect). Implementer must check if there's a placeholder page to replace vs. an empty route.
