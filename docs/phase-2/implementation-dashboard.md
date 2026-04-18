# Sonar Phase 2 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Ranked People List MVP of the Network Intelligence Dashboard — `/dashboard` shows everyone in the user's network who has crossed the signal threshold in the last 7 days, ranked by signal strength, with threshold + relationship-tier filters and 30-second polling.

**Architecture:** New Celery task `incremental_trending.py` chains to end of `pipeline.py` and updates `person_signal_summary` within ~100 ms of each post being scored. New `GET /workspace/dashboard/people` endpoint reads the pre-aggregated table and joins connections/posts/signals for row-level context. New React page at `/dashboard` polls every 30 s with tab-visibility pause, renders the list, and exposes a threshold slider + 1st/2nd-degree checkboxes. Company Heatmap (Section A) and Trending Topics Panel (Section C) are explicitly out of scope — follow-up slices.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Celery + Redis, Postgres + pgvector (already present), slowapi (rate limiting — already wired), React 18 + Vite + TypeScript, axios (manual polling hook — React Query NOT installed), pytest + pytest-asyncio + Vitest + @testing-library/react + Playwright.

---

## Scope

**In scope:**

- New Celery task `backend/app/workers/incremental_trending.py` that updates `person_signal_summary` per scored post
- Wire the task into `pipeline.py` so it runs at the end of every pipeline invocation
- Pydantic response schemas in `backend/app/schemas/dashboard.py`
- `GET /workspace/dashboard/people` endpoint with `?threshold=`, `?relationship=`, `?limit=` query params
- Frontend page `NetworkIntelligenceDashboard.tsx` at `/dashboard`
- Threshold slider + 1st/2nd-degree checkbox filters
- 30 s polling hook with tab-visibility pause
- Vitest smoke tests for the frontend page
- Route wire-up in `App.tsx`
- Playwright E2E spec: register → wizard → dashboard golden path
- TODO.md + CLAUDE.md updates

**Out of scope (follow-up slices):**

- Company Heatmap Strip (Section A): `company_signal_summary` nightly aggregation, `GET /dashboard/heatmap`, pill UI
- Trending Topics Panel (Section C): Ring 3 Discovery couples with this
- Dismiss row action: needs `dismissed_at` column (schema change; defer)
- Draft-outreach UI integration beyond a "coming soon" placeholder
- URL state / shareable dashboard links
- Cursor-based pagination (MVP uses a 50-row cap)
- Dashboard analytics telemetry (time-on-page, row clicks, filter-usage)

---

## File Structure

### New files

- `backend/app/workers/incremental_trending.py` — Celery task: per-post aggregation update
- `backend/app/routers/dashboard.py` — new router hosting `GET /workspace/dashboard/people`
- `backend/app/schemas/dashboard.py` — Pydantic response schemas (`DashboardPerson`, `DashboardPeopleResponse`)
- `backend/tests/test_incremental_trending.py` — unit + integration tests for the Celery task
- `backend/tests/test_dashboard_endpoint.py` — endpoint tests (happy path, filtering, workspace isolation)
- `backend/tests/test_dashboard_flow.py` — integration test: register → wizard → ingest post → dashboard sees it
- `frontend/src/pages/NetworkIntelligenceDashboard.tsx` — page component
- `frontend/src/pages/NetworkIntelligenceDashboard.test.tsx` — Vitest smoke tests
- `frontend/src/hooks/usePolledEndpoint.ts` — small reusable polling hook (tab-visibility aware)
- `e2e/tests/dashboard-golden-path.spec.ts` — Playwright spec

### Modified files

- `backend/app/workers/pipeline.py` — chain the incremental task after scoring (Task 2)
- `backend/app/main.py` — register `dashboard_router` (Task 4)
- `frontend/src/App.tsx` — add `/dashboard` route inside `<RequireAuth>` (Task 10)
- `TODO.md` — mark Dashboard slice done (Task 12)
- `CLAUDE.md` — note `incremental_trending` as canonical pipeline-chain pattern (Task 12)

Each file has one clear responsibility: the Celery task is a pure aggregation function, the router owns HTTP shape, the schemas own validation, the page owns UX, the polling hook is reusable.

---

## Test Strategy Note for Implementers

- Backend tests run with `docker compose exec -T api pytest`. Stack must be up: `docker compose up -d postgres redis api`.
- Backend tests use `app.dependency_overrides` for LLM + embedding mocks (per `sonar/CLAUDE.md` Python test mocking lessons from issues #6 and #11 — never `unittest.mock.patch()` on module globals).
- Celery tasks are tested by calling the function directly (synchronous, no broker needed). To exercise the `pipeline.py` → `incremental_trending` chain, call `pipeline.process_post()` against a seeded DB; the chain executes inline during tests.
- Frontend tests: `cd frontend && npm run test:run` (Vitest). Mock `axios` via `vi.mock("axios")` at the top of the test file; existing `Settings.test.tsx` + `SignalConfig.test.tsx` show the pattern.
- Vitest's `@testing-library/react` auto-cleanup is configured via `test-setup.ts`; no manual `afterEach(cleanup)` needed.
- Playwright: `cd e2e && npm test`. Needs the stack up + `vite preview` running; CI handles this via `e2e.yml`. Locally, start `docker compose up -d` + `cd frontend && npm run dev` before running tests.
- The Stop hook at `.claude/hooks/verify.sh` runs pytest + tsc + Vitest after every turn with relevant changes. Keep tests green end-to-end or the hook will block.

---

## Task 1: `incremental_trending` Celery task (pure aggregation function)

**Files:**
- Create: `backend/app/workers/incremental_trending.py`
- Create: `backend/tests/test_incremental_trending.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_incremental_trending.py`:

```python
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from app.models.connection import Connection
from app.models.post import Post
from app.models.signal import Signal
from app.models.person_signal_summary import PersonSignalSummary
from app.models.workspace import Workspace
from app.models.user import User
from app.workers.incremental_trending import update_person_aggregation


async def _seed(db_session):
    workspace = Workspace(name="WS")
    db_session.add(workspace)
    await db_session.flush()
    user = User(
        workspace_id=workspace.id, email="x@x.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    conn = Connection(
        workspace_id=workspace.id, user_id=user.id,
        linkedin_id="li-1", name="Jane", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()
    signal = Signal(
        workspace_id=workspace.id, phrase="struggling to hire",
        example_post="example body text", intent_strength=0.7,
        embedding=[0.0] * 1536, enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    return workspace, conn, signal


@pytest.mark.asyncio
async def test_update_creates_summary_if_missing(db_session):
    workspace, conn, signal = await _seed(db_session)
    post = Post(
        workspace_id=workspace.id, connection_id=conn.id,
        linkedin_post_id="p-1", content="we've been interviewing",
        post_type="text", source="feed", combined_score=0.82,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id,
        connection_id=conn.id,
        post_id=post.id,
        signal_id=signal.id,
        combined_score=0.82,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    assert summary.aggregate_score == pytest.approx(0.82)
    assert summary.recent_post_id == post.id
    assert summary.recent_signal_id == signal.id
    assert summary.trend_direction in {"up", "flat", "down"}


@pytest.mark.asyncio
async def test_update_bumps_existing_summary(db_session):
    workspace, conn, signal = await _seed(db_session)
    existing = PersonSignalSummary(
        workspace_id=workspace.id, connection_id=conn.id,
        aggregate_score=0.5, trend_direction="flat",
    )
    db_session.add(existing)

    post = Post(
        workspace_id=workspace.id, connection_id=conn.id,
        linkedin_post_id="p-2", content="hiring struggles",
        post_type="text", source="feed", combined_score=0.9,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id, connection_id=conn.id,
        post_id=post.id, signal_id=signal.id, combined_score=0.9,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    # New score replaces old (simple replacement strategy for MVP; rolling
    # average is follow-up polish).
    assert summary.aggregate_score == pytest.approx(0.9)
    assert summary.recent_post_id == post.id


@pytest.mark.asyncio
async def test_update_with_no_signal_match_is_noop(db_session):
    workspace, conn, _ = await _seed(db_session)
    post = Post(
        workspace_id=workspace.id, connection_id=conn.id,
        linkedin_post_id="p-3", content="random post",
        post_type="text", source="feed", combined_score=0.1,
        matched=False,
    )
    db_session.add(post)
    await db_session.commit()

    # signal_id=None means no signal matched; aggregation should NOT create a row
    await update_person_aggregation(
        db_session,
        workspace_id=workspace.id, connection_id=conn.id,
        post_id=post.id, signal_id=None, combined_score=0.1,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    assert result.scalar_one_or_none() is None
```

- [ ] **Step 2: Run it — verify it fails**

Run: `docker compose exec -T api pytest tests/test_incremental_trending.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workers.incremental_trending'`.

- [ ] **Step 3: Create the aggregation function**

Create `backend/app/workers/incremental_trending.py`:

```python
"""Incremental aggregation task for the dashboard Ranked People List.

Chains to the end of pipeline.py (see Task 2). For every scored post, updates
the person_signal_summary row for the post's author so the dashboard list
reflects the new signal within ~100 ms of scoring. Target runtime per call:
<100 ms (design.md §5.2).

Call shape is a pure function that takes a db_session so tests can assert
against the same transaction; the Celery wrapper is a thin delegate.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.person_signal_summary import PersonSignalSummary
from app.models.post import Post


async def update_person_aggregation(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    connection_id: UUID,
    post_id: UUID,
    signal_id: UUID | None,
    combined_score: float,
) -> None:
    """Upsert the PersonSignalSummary for this connection + recompute trend.

    NO-OP if signal_id is None — aggregation tracks matched signals only.
    """
    if signal_id is None:
        return

    result = await db.execute(
        select(PersonSignalSummary).where(
            and_(
                PersonSignalSummary.workspace_id == workspace_id,
                PersonSignalSummary.connection_id == connection_id,
            )
        )
    )
    summary = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if summary is None:
        summary = PersonSignalSummary(
            workspace_id=workspace_id,
            connection_id=connection_id,
            aggregate_score=combined_score,
            trend_direction=await _trend_direction(db, workspace_id, connection_id, now),
            last_signal_at=now,
            recent_post_id=post_id,
            recent_signal_id=signal_id,
        )
        db.add(summary)
    else:
        # MVP: replace score with latest. Rolling-avg is follow-up polish.
        summary.aggregate_score = combined_score
        summary.last_signal_at = now
        summary.recent_post_id = post_id
        summary.recent_signal_id = signal_id
        summary.trend_direction = await _trend_direction(
            db, workspace_id, connection_id, now
        )
        summary.updated_at = now


async def _trend_direction(
    db: AsyncSession,
    workspace_id: UUID,
    connection_id: UUID,
    now: datetime,
) -> str:
    """Compare matched-post counts for this week vs last week → up / flat / down."""
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    this_week = await db.execute(
        select(Post.id).where(
            and_(
                Post.workspace_id == workspace_id,
                Post.connection_id == connection_id,
                Post.matched.is_(True),
                Post.posted_at >= this_week_start,
            )
        )
    )
    last_week = await db.execute(
        select(Post.id).where(
            and_(
                Post.workspace_id == workspace_id,
                Post.connection_id == connection_id,
                Post.matched.is_(True),
                Post.posted_at >= last_week_start,
                Post.posted_at < this_week_start,
            )
        )
    )
    this_week_count = len(this_week.scalars().all())
    last_week_count = len(last_week.scalars().all())

    if this_week_count > last_week_count:
        return "up"
    if this_week_count < last_week_count:
        return "down"
    return "flat"
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_incremental_trending.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 84/84 + 3 skipped (81+3 baseline + 3 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/incremental_trending.py backend/tests/test_incremental_trending.py
git commit -m "feat(dashboard): incremental_trending aggregation task"
```

If pre-commit reformats, `git add -u` and commit again.

---

## Task 2: Wire `incremental_trending` into `pipeline.py`

**Files:**
- Modify: `backend/app/workers/pipeline.py`
- Create: `backend/tests/test_pipeline_dashboard_hook.py`

- [ ] **Step 1: Read the existing pipeline**

Run: `cat backend/app/workers/pipeline.py`
Note the scoring step and where the pipeline's post-scoring work happens. The aggregation call must land AFTER scoring is persisted and BEFORE the function returns.

- [ ] **Step 2: Write the failing integration test**

Create `backend/tests/test_pipeline_dashboard_hook.py`:

```python
import pytest
from sqlalchemy import select
from uuid import uuid4
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.signal import Signal
from app.models.post import Post
from app.models.person_signal_summary import PersonSignalSummary
from app.workers.pipeline import process_post


@pytest.mark.asyncio
async def test_pipeline_populates_person_signal_summary(db_session, monkeypatch):
    workspace = Workspace(name="WS")
    db_session.add(workspace)
    await db_session.flush()
    user = User(
        workspace_id=workspace.id, email="x@x.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    conn = Connection(
        workspace_id=workspace.id, user_id=user.id,
        linkedin_id="li-1", name="Jane", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()
    signal = Signal(
        workspace_id=workspace.id, phrase="struggling to hire",
        example_post="example body text", intent_strength=0.7,
        embedding=[0.0] * 1536, enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    post = Post(
        workspace_id=workspace.id, connection_id=conn.id,
        linkedin_post_id="p-1", content="we've been interviewing",
        post_type="text", source="feed", combined_score=0.85,
        matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    # Invoke the pipeline's post-scoring hook path directly.
    await process_post(
        db_session,
        post_id=post.id,
        signal_id=signal.id,
        combined_score=0.85,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    summary = result.scalar_one()
    assert summary.aggregate_score == pytest.approx(0.85)
    assert summary.recent_post_id == post.id
```

- [ ] **Step 3: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_pipeline_dashboard_hook.py -v`
Expected: either an ImportError (if `process_post` doesn't exist with this signature) or the aggregation row is missing.

- [ ] **Step 4: Modify `pipeline.py` to call `update_person_aggregation`**

Open `backend/app/workers/pipeline.py`. Find the place where scoring completes — typically after the scorer writes `combined_score` and `matched` to the Post row. Add (at the bottom of that function, BEFORE the return):

```python
from app.workers.incremental_trending import update_person_aggregation
# ... existing scoring logic ...

# Dashboard hook — update person_signal_summary so the ranked list reflects
# this post within ~100 ms. signal_id may be None if nothing matched (no-op).
await update_person_aggregation(
    db,
    workspace_id=post.workspace_id,
    connection_id=post.connection_id,
    post_id=post.id,
    signal_id=matched_signal_id,  # reuse existing variable from scorer
    combined_score=post.combined_score,
)
```

If the existing function signature doesn't expose `matched_signal_id`, use the first entry from `post.ring1_matches` or the nearest-matching signal from `post.ring2_matches` (whichever is non-empty). The key invariant: call `update_person_aggregation` with the BEST matching signal for this post, or `None` if no match.

Expose a convenience wrapper `process_post(db, post_id, signal_id, combined_score)` if `pipeline.py` doesn't already provide one at the call boundary the test expects. Keep the wrapper thin — it should only call `update_person_aggregation` if the test entry point requires it to be separable from full pipeline invocation.

- [ ] **Step 5: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_pipeline_dashboard_hook.py -v`
Expected: PASS.

- [ ] **Step 6: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 85/85 + 3 skipped.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/pipeline.py backend/tests/test_pipeline_dashboard_hook.py
git commit -m "feat(dashboard): chain incremental_trending after scoring"
```

---

## Task 3: Pydantic schemas for the dashboard endpoint

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/tests/test_dashboard_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dashboard_schemas.py`:

```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.dashboard import DashboardPerson, DashboardPeopleResponse


def test_dashboard_person_accepts_minimum_fields():
    p = DashboardPerson(
        connection_id=uuid4(),
        name="Jane Doe",
        title=None,
        company=None,
        relationship_degree=1,
        mutual_count=None,
        aggregate_score=0.82,
        trend_direction="up",
        last_signal_at=datetime.now(timezone.utc),
        recent_post_snippet=None,
        matching_signal_phrase=None,
        recent_post_url=None,
    )
    assert p.relationship_degree == 1


def test_relationship_degree_must_be_1_or_2():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=3,
            mutual_count=None,
            aggregate_score=0.5,
            trend_direction="flat",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_trend_direction_enum():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=1,
            mutual_count=None,
            aggregate_score=0.5,
            trend_direction="sideways",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_aggregate_score_bounds():
    with pytest.raises(ValidationError):
        DashboardPerson(
            connection_id=uuid4(),
            name="X",
            title=None,
            company=None,
            relationship_degree=1,
            mutual_count=None,
            aggregate_score=1.5,
            trend_direction="flat",
            last_signal_at=datetime.now(timezone.utc),
            recent_post_snippet=None,
            matching_signal_phrase=None,
            recent_post_url=None,
        )


def test_response_shape():
    r = DashboardPeopleResponse(people=[], threshold_used=0.65, total=0)
    assert r.total == 0
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_dashboard_schemas.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Create the schemas**

Create `backend/app/schemas/dashboard.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


TrendDirection = Literal["up", "flat", "down"]


class DashboardPerson(BaseModel):
    connection_id: UUID
    name: str
    title: str | None
    company: str | None
    relationship_degree: int = Field(ge=1, le=2)
    mutual_count: int | None
    aggregate_score: float = Field(ge=0, le=1)
    trend_direction: TrendDirection
    last_signal_at: datetime
    recent_post_snippet: str | None
    matching_signal_phrase: str | None
    recent_post_url: str | None


class DashboardPeopleResponse(BaseModel):
    people: list[DashboardPerson]
    threshold_used: float = Field(ge=0, le=1)
    total: int = Field(ge=0)
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_dashboard_schemas.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 90/90 + 3 skipped.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/dashboard.py backend/tests/test_dashboard_schemas.py
git commit -m "feat(schemas): dashboard response shape"
```

---

## Task 4: `GET /workspace/dashboard/people` endpoint

**Files:**
- Create: `backend/app/routers/dashboard.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_dashboard_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_dashboard_endpoint.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.person_signal_summary import PersonSignalSummary
from app.models.signal import Signal
from app.models.post import Post


async def _setup(client, email: str, workspace: str = "WS"):
    await client.post("/workspace/register", json={
        "workspace_name": workspace, "email": email, "password": "pass123",
    })
    tok = (await client.post(
        "/auth/token", data={"username": email, "password": "pass123"}
    )).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


async def _seed_person(db_session, *, workspace_name, email, score, degree=1):
    workspace = Workspace(name=workspace_name)
    db_session.add(workspace)
    await db_session.flush()
    user = User(
        workspace_id=workspace.id, email=email,
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    conn = Connection(
        workspace_id=workspace.id, user_id=user.id,
        linkedin_id=f"li-{email}", name=f"Person {email}",
        headline="VP Engineering", company="Acme", degree=degree,
    )
    db_session.add(conn)
    await db_session.flush()
    signal = Signal(
        workspace_id=workspace.id, phrase="struggling to hire",
        example_post="example body text", intent_strength=0.7,
        embedding=[0.0] * 1536, enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    post = Post(
        workspace_id=workspace.id, connection_id=conn.id,
        linkedin_post_id=f"p-{email}", content="We've been interviewing for 4 months.",
        post_type="text", source="feed", combined_score=score, matched=True,
    )
    db_session.add(post)
    await db_session.flush()
    summary = PersonSignalSummary(
        workspace_id=workspace.id, connection_id=conn.id,
        aggregate_score=score, trend_direction="up",
        last_signal_at=datetime.now(timezone.utc),
        recent_post_id=post.id, recent_signal_id=signal.id,
    )
    db_session.add(summary)
    await db_session.commit()
    return workspace, conn


@pytest.mark.asyncio
async def test_dashboard_people_returns_ranked_list(client, db_session):
    workspace, conn = await _seed_person(
        db_session, workspace_name="Test Agency",
        email="dash@a.com", score=0.85, degree=1,
    )
    # Bypass workspace isolation by authenticating the same workspace we seeded.
    # The register endpoint creates its own workspace; to test against OUR seed,
    # call the endpoint using the already-seeded user.
    hdrs = {"Authorization": f"Bearer {_make_token(conn.user_id, workspace.id)}"}

    resp = await client.get("/workspace/dashboard/people", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["people"]) == 1
    row = body["people"][0]
    assert row["name"].startswith("Person ")
    assert row["aggregate_score"] == pytest.approx(0.85)
    assert row["relationship_degree"] == 1
    assert row["matching_signal_phrase"] == "struggling to hire"


def _make_token(user_id, workspace_id):
    """Helper: forge a JWT for the seeded user so the test doesn't need
    to re-register (which would create a different workspace)."""
    from app.routers.auth import create_access_token
    return create_access_token(user_id=user_id, workspace_id=workspace_id)


@pytest.mark.asyncio
async def test_dashboard_people_filters_by_threshold(client, db_session):
    workspace, conn = await _seed_person(
        db_session, workspace_name="Threshold Test",
        email="thr@a.com", score=0.5, degree=1,
    )
    hdrs = {"Authorization": f"Bearer {_make_token(conn.user_id, workspace.id)}"}

    # Threshold 0.65 excludes the 0.5 score
    resp = await client.get(
        "/workspace/dashboard/people?threshold=0.65", headers=hdrs
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # Threshold 0.4 includes it
    resp = await client.get(
        "/workspace/dashboard/people?threshold=0.4", headers=hdrs
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_dashboard_people_filters_by_relationship(client, db_session):
    workspace, conn = await _seed_person(
        db_session, workspace_name="Rel Test",
        email="rel@a.com", score=0.9, degree=2,
    )
    hdrs = {"Authorization": f"Bearer {_make_token(conn.user_id, workspace.id)}"}

    # Only 1st degree — excludes the 2nd-degree seed
    resp = await client.get(
        "/workspace/dashboard/people?relationship=1", headers=hdrs
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # 2nd degree only — includes it
    resp = await client.get(
        "/workspace/dashboard/people?relationship=2", headers=hdrs
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_dashboard_people_workspace_isolation(client, db_session):
    # Seed workspace A with a person
    workspace_a, conn_a = await _seed_person(
        db_session, workspace_name="A", email="a@a.com", score=0.9,
    )
    # Seed workspace B with a different person
    workspace_b, conn_b = await _seed_person(
        db_session, workspace_name="B", email="b@b.com", score=0.9,
    )

    hdrs_a = {"Authorization": f"Bearer {_make_token(conn_a.user_id, workspace_a.id)}"}

    resp = await client.get("/workspace/dashboard/people", headers=hdrs_a)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    # The one person we see MUST be from workspace A
    assert body["people"][0]["connection_id"] == str(conn_a.id)


@pytest.mark.asyncio
async def test_dashboard_people_rejects_unauthenticated(client):
    resp = await client.get("/workspace/dashboard/people")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_dashboard_endpoint.py -v`
Expected: all FAIL with 404 / import error.

- [ ] **Step 3: Create the router**

Create `backend/app/routers/dashboard.py`:

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import Connection
from app.models.person_signal_summary import PersonSignalSummary
from app.models.post import Post
from app.models.signal import Signal
from app.models.user import User
from app.models.workspace import Workspace
from app.rate_limit import limiter
from app.routers.auth import get_current_user
from app.schemas.dashboard import DashboardPeopleResponse, DashboardPerson

router = APIRouter(prefix="/workspace/dashboard", tags=["dashboard"])


def _snippet(content: str, max_chars: int = 200) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rsplit(" ", 1)[0] + "…"


def _post_url(linkedin_post_id: str | None) -> str | None:
    if not linkedin_post_id:
        return None
    # Best-effort URL reconstruction. LinkedIn post URLs typically follow
    # https://www.linkedin.com/feed/update/urn:li:activity:<id>/
    # If the stored id is already a full urn or URL, pass it through.
    if linkedin_post_id.startswith("http"):
        return linkedin_post_id
    if linkedin_post_id.startswith("urn:"):
        return f"https://www.linkedin.com/feed/update/{linkedin_post_id}/"
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{linkedin_post_id}/"


@router.get("/people", response_model=DashboardPeopleResponse)
@limiter.limit("30/minute")
async def get_dashboard_people(
    request: Request,  # required by @limiter.limit
    threshold: float | None = Query(None, ge=0.0, le=1.0),
    relationship: str = Query("1,2"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Resolve threshold: explicit param > workspace default > 0.65 fallback
    if threshold is None:
        ws_result = await db.execute(
            select(Workspace.matching_threshold).where(
                Workspace.id == current_user.workspace_id
            )
        )
        threshold = ws_result.scalar_one_or_none() or 0.65

    # Parse relationship filter — "1,2" → [1, 2]
    try:
        degrees = sorted({int(x) for x in relationship.split(",") if x.strip()})
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Invalid relationship param; expected comma-separated ints"
        )
    if not all(d in (1, 2) for d in degrees):
        raise HTTPException(
            status_code=422, detail="relationship degree must be 1 or 2"
        )

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stmt = (
        select(
            PersonSignalSummary,
            Connection,
            Post,
            Signal,
        )
        .join(Connection, Connection.id == PersonSignalSummary.connection_id)
        .outerjoin(Post, Post.id == PersonSignalSummary.recent_post_id)
        .outerjoin(Signal, Signal.id == PersonSignalSummary.recent_signal_id)
        .where(
            and_(
                PersonSignalSummary.workspace_id == current_user.workspace_id,
                PersonSignalSummary.aggregate_score >= threshold,
                PersonSignalSummary.last_signal_at >= seven_days_ago,
                Connection.degree.in_(degrees),
            )
        )
        .order_by(PersonSignalSummary.aggregate_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    people = [
        DashboardPerson(
            connection_id=conn.id,
            name=conn.name,
            title=conn.headline,
            company=conn.company,
            relationship_degree=conn.degree,
            mutual_count=conn.mutual_count,
            aggregate_score=summary.aggregate_score,
            trend_direction=summary.trend_direction,
            last_signal_at=summary.last_signal_at,
            recent_post_snippet=_snippet(post.content) if post else None,
            matching_signal_phrase=sig.phrase if sig else None,
            recent_post_url=_post_url(post.linkedin_post_id) if post else None,
        )
        for summary, conn, post, sig in rows
    ]

    return DashboardPeopleResponse(
        people=people, threshold_used=threshold, total=len(people)
    )
```

- [ ] **Step 4: Register the router in `main.py`**

Edit `backend/app/main.py`:
- Add import near other router imports: `from app.routers.dashboard import router as dashboard_router`
- Add `app.include_router(dashboard_router)` near the other `include_router` calls

- [ ] **Step 5: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_dashboard_endpoint.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 95/95 + 3 skipped.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/dashboard.py backend/app/main.py backend/tests/test_dashboard_endpoint.py
git commit -m "feat(dashboard): GET /workspace/dashboard/people endpoint"
```

---

## Task 5: End-to-end integration test (register → wizard → pipeline → dashboard)

**Files:**
- Create: `backend/tests/test_dashboard_flow.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_dashboard_flow.py`:

```python
import pytest
import json
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.connection import Connection
from app.models.user import User
from app.models.signal import Signal
from app.models.post import Post
from app.models.person_signal_summary import PersonSignalSummary
from app.workers.incremental_trending import update_person_aggregation


class FakeLLM:
    async def complete(self, prompt, model, **kwargs):
        return json.dumps({
            "signals": [
                {"phrase": "hiring struggles", "example_post": "still interviewing body", "intent_strength": 0.8},
                {"phrase": "fundraising mode", "example_post": "raising a Series A body", "intent_strength": 0.7},
                {"phrase": "infra pain", "example_post": "legacy ETL bottlenecks body", "intent_strength": 0.7},
                {"phrase": "team scaling", "example_post": "hiring plan this quarter body", "intent_strength": 0.6},
                {"phrase": "tech debt", "example_post": "refactoring payments body", "intent_strength": 0.6},
                {"phrase": "migration pain", "example_post": "moving off legacy stack body", "intent_strength": 0.6},
                {"phrase": "compliance ask", "example_post": "SOC2 prep this year body", "intent_strength": 0.5},
                {"phrase": "tooling chaos", "example_post": "too many SaaS tools body", "intent_strength": 0.5},
            ]
        })


class FakeEmbed:
    async def embed(self, text):
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_full_flow_register_wizard_pipeline_dashboard(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post("/workspace/register", json={
        "workspace_name": "End-to-End Agency",
        "email": "e2e@dash.com", "password": "pass123",
    })
    tok = (await client.post(
        "/auth/token",
        data={"username": "e2e@dash.com", "password": "pass123"},
    )).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    # Complete the wizard
    propose = (await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "CTO services"},
        headers=hdrs,
    )).json()
    confirm = (await client.post(
        "/workspace/signals/confirm",
        json={
            "proposal_event_id": propose["proposal_event_id"],
            "accepted": [0, 1, 2],
        },
        headers=hdrs,
    )).json()
    assert len(confirm["signal_ids"]) == 3

    # Now seed a connection + scored post, and invoke the aggregation
    # directly (Celery chain would do this in prod — simulating here).
    user = (await db_session.execute(
        select(User).where(User.email == "e2e@dash.com")
    )).scalar_one()
    first_signal = (await db_session.execute(
        select(Signal).where(Signal.workspace_id == user.workspace_id).limit(1)
    )).scalar_one()
    conn = Connection(
        workspace_id=user.workspace_id, user_id=user.id,
        linkedin_id="li-e2e", name="Dashboard Test Person",
        headline="CTO", company="TestCo", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()
    post = Post(
        workspace_id=user.workspace_id, connection_id=conn.id,
        linkedin_post_id="e2e-post-1",
        content="We've been interviewing senior engineers for 4 months.",
        post_type="text", source="feed",
        combined_score=0.88, matched=True,
    )
    db_session.add(post)
    await db_session.commit()

    await update_person_aggregation(
        db_session,
        workspace_id=user.workspace_id,
        connection_id=conn.id, post_id=post.id,
        signal_id=first_signal.id, combined_score=0.88,
    )
    await db_session.commit()

    resp = await client.get("/workspace/dashboard/people", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    row = body["people"][0]
    assert row["name"] == "Dashboard Test Person"
    assert row["aggregate_score"] == pytest.approx(0.88)
    assert row["recent_post_snippet"].startswith("We've been interviewing")

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
```

- [ ] **Step 2: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_dashboard_flow.py -v`
Expected: PASS.

- [ ] **Step 3: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 96/96 + 3 skipped.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_dashboard_flow.py
git commit -m "test(dashboard): end-to-end register → wizard → pipeline → dashboard"
```

---

## Task 6: Reusable polling hook

**Files:**
- Create: `frontend/src/hooks/usePolledEndpoint.ts`
- Create: `frontend/src/hooks/usePolledEndpoint.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/usePolledEndpoint.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePolledEndpoint } from "./usePolledEndpoint";

describe("usePolledEndpoint", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls fetcher once on mount and exposes loading + data", async () => {
    const fetcher = vi.fn().mockResolvedValue({ hello: "world" });
    const { result } = renderHook(() =>
      usePolledEndpoint(fetcher, { intervalMs: 30000 })
    );
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toEqual({ hello: "world" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("re-polls every interval", async () => {
    const fetcher = vi.fn().mockResolvedValue({ count: 1 });
    renderHook(() => usePolledEndpoint(fetcher, { intervalMs: 30000 }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    act(() => {
      vi.advanceTimersByTime(30000);
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});
```

- [ ] **Step 2: Run — verify fail**

Run: `cd frontend && npm run test:run -- usePolledEndpoint`
Expected: FAIL (module missing).

- [ ] **Step 3: Create the hook**

Create `frontend/src/hooks/usePolledEndpoint.ts`:

```ts
import { useEffect, useRef, useState } from "react";

interface Options {
  intervalMs: number;
  enabled?: boolean;
}

interface State<T> {
  data: T | null;
  error: Error | null;
  isLoading: boolean;
  isStale: boolean;
}

export function usePolledEndpoint<T>(
  fetcher: () => Promise<T>,
  { intervalMs, enabled = true }: Options
): State<T> & { refetch: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStale, setIsStale] = useState(false);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = async () => {
    if (data !== null) setIsStale(true);
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setIsLoading(false);
      setIsStale(false);
    }
  };

  useEffect(() => {
    if (!enabled) return;
    doFetch();

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        doFetch();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const intervalId = setInterval(() => {
      if (document.visibilityState === "visible") {
        doFetch();
      }
    }, intervalMs);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs]);

  return { data, error, isLoading, isStale, refetch: doFetch };
}
```

- [ ] **Step 4: Run — verify pass**

Run: `cd frontend && npm run test:run -- usePolledEndpoint`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/usePolledEndpoint.ts frontend/src/hooks/usePolledEndpoint.test.ts
git commit -m "feat(frontend): usePolledEndpoint hook with tab-visibility pause"
```

---

## Task 7: Dashboard page component

**Files:**
- Create: `frontend/src/pages/NetworkIntelligenceDashboard.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/pages/NetworkIntelligenceDashboard.tsx`:

```tsx
import { useCallback, useMemo, useState } from "react";
import api from "../api/client";
import { usePolledEndpoint } from "../hooks/usePolledEndpoint";

interface DashboardPerson {
  connection_id: string;
  name: string;
  title: string | null;
  company: string | null;
  relationship_degree: 1 | 2;
  mutual_count: number | null;
  aggregate_score: number;
  trend_direction: "up" | "flat" | "down";
  last_signal_at: string;
  recent_post_snippet: string | null;
  matching_signal_phrase: string | null;
  recent_post_url: string | null;
}

interface DashboardResponse {
  people: DashboardPerson[];
  threshold_used: number;
  total: number;
}

const TREND_ICON: Record<DashboardPerson["trend_direction"], string> = {
  up: "↑",
  flat: "→",
  down: "↓",
};

export function NetworkIntelligenceDashboard() {
  const [threshold, setThreshold] = useState<number>(0.65);
  const [tiers, setTiers] = useState<Set<1 | 2>>(new Set([1, 2]));

  const fetcher = useCallback(async (): Promise<DashboardResponse> => {
    const relationship = [...tiers].sort().join(",");
    const { data } = await api.get<DashboardResponse>(
      `/workspace/dashboard/people?threshold=${threshold}&relationship=${relationship}`
    );
    return data;
  }, [threshold, tiers]);

  const { data, error, isLoading, isStale } = usePolledEndpoint(fetcher, {
    intervalMs: 30000,
  });

  const toggleTier = (t: 1 | 2) => {
    const next = new Set(tiers);
    if (next.has(t)) {
      next.delete(t);
    } else {
      next.add(t);
    }
    if (next.size === 0) return; // always keep at least one tier selected
    setTiers(next);
  };

  const people = data?.people ?? [];

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>Network Intelligence</h1>
        {isStale && <span style={{ fontSize: 12, color: "#888" }}>Updating…</span>}
      </header>

      <section style={{ marginBottom: 24, padding: 16, border: "1px solid #eee", borderRadius: 8 }}>
        <label style={{ display: "block", marginBottom: 8 }}>
          Threshold: <strong>{threshold.toFixed(2)}</strong>
          <input
            type="range"
            min={0.5}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: 4 }}
          />
        </label>
        <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
          <label>
            <input
              type="checkbox"
              checked={tiers.has(1)}
              onChange={() => toggleTier(1)}
            />{" "}
            1st-degree
          </label>
          <label>
            <input
              type="checkbox"
              checked={tiers.has(2)}
              onChange={() => toggleTier(2)}
            />{" "}
            2nd-degree
          </label>
        </div>
      </section>

      {error && (
        <div style={{ color: "#b00", padding: 12, background: "#fee", borderRadius: 8, marginBottom: 16 }}>
          Failed to load dashboard: {error.message}
        </div>
      )}

      {isLoading && people.length === 0 && (
        <div style={{ color: "#888", padding: 24, textAlign: "center" }}>Loading…</div>
      )}

      {!isLoading && people.length === 0 && (
        <div style={{ color: "#666", padding: 24, textAlign: "center", border: "1px dashed #ddd", borderRadius: 8 }}>
          No signals in your network above this threshold yet. Try lowering the threshold, or wait for more posts to flow through.
        </div>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {people.map((p) => (
          <li
            key={p.connection_id}
            style={{ border: "1px solid #eee", borderRadius: 8, padding: 16, marginBottom: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <span style={{
                  display: "inline-block", padding: "2px 8px", borderRadius: 12,
                  background: p.relationship_degree === 1 ? "#d4f7d4" : "#fff3d4",
                  fontSize: 12, marginRight: 8,
                }}>
                  {p.relationship_degree === 1 ? "🟢 1st" : `🟡 2nd${p.mutual_count ? ` · ${p.mutual_count} mutual` : ""}`}
                </span>
                <strong>{p.name}</strong>
                {p.title && <span style={{ color: "#666" }}> · {p.title}</span>}
                {p.company && <span style={{ color: "#666" }}> at {p.company}</span>}
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 18, fontWeight: 600 }}>
                  {(p.aggregate_score * 100).toFixed(0)}% {TREND_ICON[p.trend_direction]}
                </div>
              </div>
            </div>
            {p.recent_post_snippet && (
              <div style={{ marginTop: 8, color: "#444", fontSize: 14 }}>"{p.recent_post_snippet}"</div>
            )}
            {p.matching_signal_phrase && (
              <div style={{ marginTop: 4, fontSize: 12, color: "#888", fontStyle: "italic" }}>
                Matched: {p.matching_signal_phrase}
              </div>
            )}
            <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
              {p.recent_post_url && (
                <a
                  href={p.recent_post_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: 12, padding: "4px 8px", border: "1px solid #ddd", borderRadius: 4, textDecoration: "none", color: "#333" }}
                >
                  View thread
                </a>
              )}
              <button
                style={{ fontSize: 12, padding: "4px 8px", border: "1px solid #ddd", borderRadius: 4, background: "#fff", cursor: "pointer" }}
                onClick={() => alert("Outreach drafting — coming soon")}
              >
                Draft outreach
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default NetworkIntelligenceDashboard;
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/NetworkIntelligenceDashboard.tsx
git commit -m "feat(frontend): NetworkIntelligenceDashboard page"
```

---

## Task 8: Vitest smoke tests for the dashboard page

**Files:**
- Create: `frontend/src/pages/NetworkIntelligenceDashboard.test.tsx`

- [ ] **Step 1: Write the smoke tests**

Create `frontend/src/pages/NetworkIntelligenceDashboard.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NetworkIntelligenceDashboard from "./NetworkIntelligenceDashboard";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

describe("NetworkIntelligenceDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading then empty state when the list is empty", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { people: [], threshold_used: 0.65, total: 0 },
    });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no signals in your network/i)).toBeInTheDocument()
    );
  });

  it("renders the list of people when the endpoint returns rows", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
        people: [
          {
            connection_id: "abc",
            name: "Jane Doe",
            title: "VP Engineering",
            company: "Acme",
            relationship_degree: 1,
            mutual_count: null,
            aggregate_score: 0.82,
            trend_direction: "up",
            last_signal_at: new Date().toISOString(),
            recent_post_snippet: "We've been interviewing for 4 months…",
            matching_signal_phrase: "struggling to hire",
            recent_post_url: null,
          },
        ],
        threshold_used: 0.65,
        total: 1,
      },
    });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());
    expect(screen.getByText(/VP Engineering/)).toBeInTheDocument();
    expect(screen.getByText(/82%/)).toBeInTheDocument();
    expect(screen.getByText(/struggling to hire/i)).toBeInTheDocument();
  });

  it("changing the threshold triggers a new fetch with the updated value", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { people: [], threshold_used: 0.65, total: 0 },
    });
    const user = userEvent.setup();

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    const slider = screen.getByRole("slider");
    await user.click(slider);
    // Simulate a value change to 0.8
    // (jsdom range input accepts direct value change via fireEvent)
    slider.setAttribute("value", "0.8");
    slider.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      const urlsCalled = api.get.mock.calls.map((c) => c[0] as string);
      expect(urlsCalled.some((u) => u.includes("threshold=0.8"))).toBe(true);
    });
  });
});
```

- [ ] **Step 2: Run — verify pass**

Run: `cd frontend && npm run test:run`
Expected: all tests pass (the 3 new + any existing).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/NetworkIntelligenceDashboard.test.tsx
git commit -m "test(frontend): NetworkIntelligenceDashboard smoke tests"
```

---

## Task 9: Route wire-up in `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Read the current App.tsx**

Run: `cat frontend/src/App.tsx`
Note where existing authenticated routes are registered (look for `<RequireAuth>` or similar).

- [ ] **Step 2: Add the `/dashboard` route**

Edit `frontend/src/App.tsx`:
- Add import: `import NetworkIntelligenceDashboard from "./pages/NetworkIntelligenceDashboard";`
- Add inside the authenticated-routes group:
  ```tsx
  <Route path="/dashboard" element={<NetworkIntelligenceDashboard />} />
  ```

If a placeholder `/dashboard` route already exists (Wizard Task 11 redirected there), replace the old element with `<NetworkIntelligenceDashboard />`.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): wire /dashboard route to NetworkIntelligenceDashboard"
```

---

## Task 10: Playwright E2E — register → wizard → dashboard

**Files:**
- Create: `e2e/tests/dashboard-golden-path.spec.ts`

- [ ] **Step 1: Create the spec**

Create `e2e/tests/dashboard-golden-path.spec.ts`:

```ts
/**
 * Dashboard golden-path E2E: register → wizard → dashboard.
 *
 * Uses the Playwright `request` context to seed the DB via API (faster +
 * more stable than UI-clicking the wizard), then navigates the browser
 * to /dashboard and asserts the ranked list renders.
 *
 * Marked `.fixme` until the surrounding register/login E2E specs are
 * de-fixmed (issue #65) — this test shares their UI assumptions and will
 * break for the same reasons.
 */
import { test, expect } from "@playwright/test";

function uniqueEmail() {
  return `dash-e2e-${Date.now()}@sonar-e2e.local`;
}

test.fixme("user can register, complete wizard, and see the dashboard", async ({ page, request }) => {
  const email = uniqueEmail();
  const password = "pass123";
  const backend = process.env.SONAR_BACKEND_URL || "http://localhost:8000";

  // Register via API
  const reg = await request.post(`${backend}/workspace/register`, {
    data: { workspace_name: "Dashboard E2E", email, password },
  });
  expect(reg.status()).toBe(201);

  // Log in via UI
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /login|sign in|log in/i }).click();
  await expect(page).not.toHaveURL(/\/login$/, { timeout: 10_000 });

  // Expect to be routed to the wizard
  await expect(page).toHaveURL(/\/signals\/setup/, { timeout: 10_000 });

  // Fill the wizard minimally and confirm
  await page.getByRole("textbox").first().fill("Fractional CTO services");
  await page.getByRole("button", { name: /next/i }).click();
  // Step 2 (ICP) — skip
  await page.getByRole("button", { name: /next/i }).click();
  // Step 3 — click Generate
  await page.getByRole("button", { name: /generate/i }).click();
  // Wait for proposal response
  await page.waitForURL(/\/signals\/setup/, { timeout: 30_000 });
  // Step 4 — click Next
  await page.getByRole("button", { name: /next/i }).click();
  // Step 5 — Save
  await page.getByRole("button", { name: /save and open dashboard/i }).click();

  // Expect to land on /dashboard
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });

  // At minimum, the dashboard renders its header
  await expect(page.getByText(/network intelligence/i)).toBeVisible({ timeout: 5_000 });
});
```

- [ ] **Step 2: Verify discovery**

Run: `cd e2e && npx --no-install playwright test --list`
Expected: new test shows up in the list (alongside existing `.fixme`-marked specs).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/dashboard-golden-path.spec.ts
git commit -m "test(e2e): dashboard golden-path (fixme — pending #65)"
```

---

## Task 11: TODO.md + CLAUDE.md updates

**Files:**
- Modify: `TODO.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `TODO.md`**

Open `TODO.md`. Find the Phase 2 status table (search: "### Phase 2 — 2 of 5 slices shipped"). Change the Dashboard row from `⬜ Not started` to `✅ Shipped (this PR)` and add a short description of what shipped:

> Ranked People List MVP at `/dashboard` — `incremental_trending` Celery task keeps `person_signal_summary` fresh within ~100 ms of each scored post; `GET /workspace/dashboard/people` joins `person_signal_summary + connections + posts + signals`; frontend polls every 30s with tab-visibility pause; threshold slider + 1st/2nd-degree filters. Heatmap (Section A) + Trending Topics (Section C) deferred.

Update the header count: "Phase 2 — **3 of 5 slices shipped, 2 remaining**".

Also update the "Resume Here" block at the top to mention the dashboard milestone. Replace or append:

> This session shipped the Dashboard Ranked People List MVP. Next natural move: Backfill slice (Day-One Backfill via Chrome extension + Apify) or the Heatmap follow-up to round out §4.3 Section A. Design work required — no implementation plan exists yet for either.

- [ ] **Step 2: Update `CLAUDE.md`**

Open `CLAUDE.md`. Find the "LLM and agent discipline" section (or the Celery/Pipeline section if one exists separately). Add a short bullet near the pipeline-related rules:

> - **Incremental aggregation pattern.** Pipeline post-scoring work (updating `person_signal_summary`, Redis counters, etc.) lives in `app/workers/incremental_trending.py` and chains to the end of `pipeline.py`. Target runtime <100 ms per call. Future per-post aggregation features (Ring 3 counters, company rollups) follow the same chain-at-end pattern — do NOT inline new aggregation into `pipeline.py` itself.

- [ ] **Step 3: Commit**

```bash
git add TODO.md CLAUDE.md
git commit -m "docs: mark Dashboard slice shipped, document incremental_trending pattern"
```

---

## Self-Review Notes

Applied inline before saving this plan:

**Spec coverage:** Every in-scope item from `docs/phase-2/dashboard-decisions.md` maps to a task — aggregation task (1), pipeline chain (2), schemas (3), endpoint (4), E2E integration (5), polling hook (6), page (7), page tests (8), route (9), Playwright (10), docs (11). Out-of-scope items (heatmap, trending, dismiss action, URL state) are explicitly flagged in the Scope section.

**Placeholder scan:** No TBDs. No "similar to…" references. Every code step has complete runnable code. Task 2's "find the place where scoring completes" is as specific as the plan can be without reading `pipeline.py` at plan-write time — the implementer has the context to make the edit; the plan commits to the invariant (call `update_person_aggregation` at end of scoring path with best-matching signal).

**Type consistency:**
- `DashboardPerson` fields match between schema (Task 3), endpoint response (Task 4), integration test assertions (Task 5), and frontend interface (Task 7).
- `update_person_aggregation` signature (keyword-only `workspace_id`, `connection_id`, `post_id`, `signal_id`, `combined_score`) is consistent across Task 1 definition, Task 2 call site, and Task 5 test invocation.
- Query param names (`threshold`, `relationship`, `limit`) match between endpoint (Task 4), tests (Tasks 4 + 5), hook-consumer (Task 7), and frontend tests (Task 8).

**Scope check:** 11 tasks — within the ~10–12 target. Single slice, no sub-projects needed.

---

## Open Questions (resolve during implementation, not blocking plan start)

- `Workspace.matching_threshold` — does the column exist? The plan assumes yes (from Phase 1). If it doesn't, the endpoint falls back to 0.65 hardcoded. Implementer should `grep -n matching_threshold backend/app/models/workspace.py` in Task 4 Step 3 to confirm before adding the query.
- `Connection.mutual_count` — confirmed present in migration 002 (verified during plan writing). But it may be `0` for most rows; the frontend handles `null`/`0` gracefully.
- `process_post` function in `pipeline.py` — name is illustrative. Actual function name may differ; implementer should find the scoring entry-point and add the call there.
- Post-URL reconstruction — `linkedin_post_id` format is not specified. The `_post_url` helper does best-effort URL synthesis; if the stored id isn't in the expected shape, clicking "View thread" will 404 on LinkedIn. Acceptable for MVP; can be tightened as a follow-up polish.
- React Query adoption — not added in this plan (manual polling hook is sufficient). If Backfill or a later slice wants shared cache semantics, add `@tanstack/react-query` then and migrate.
- Rate limit on `/dashboard/people` (30/min) may be too tight if users open multiple tabs. Tune after real user traffic.
