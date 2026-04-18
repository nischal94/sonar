# Sonar Phase 2 — Backfill Implementation Plan

> ⚠️ **Historical note (2026-04-18):** This plan was executed using SendGrid as the email provider (the pattern inherited from Phase 1). The project migrated to Resend later the same day in commit [`ed75626`](https://github.com/nischal94/sonar/commit/ed75626). SendGrid references below reflect what shipped at the time — the current code in `backend/app/delivery/email.py` uses Resend.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Day-One Backfill — a new user completes the wizard, clicks "Run day-one scan" in the extension, and within ~5 minutes the dashboard is populated with real network signals from up to 200 1st-degree connections × 60 days of post history.

**Architecture:** Chrome extension gains a new content script that scrolls the user's LinkedIn connections page and POSTs the list to `/extension/connections/bulk`. The extension then triggers a one-time `day_one_backfill` Celery task that calls Apify for 1st-degree profile posts, routes results through the existing Phase 1 pipeline, and emails the user when done. Dashboard polls a new `/backfill/status` endpoint at 5 s during the active window to show a progress banner. Idempotency enforced via `Workspace.backfill_used` (already present from Foundation) plus a 409 on re-trigger.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, Celery + Redis, Postgres + pgvector, Apify API (new — first external HTTP integration since SendGrid/Groq), existing `app/delivery/email.py` SendGrid sender, slowapi (rate limiting), React 18 + Vite + TypeScript, axios, Vitest + Playwright, Chrome MV3 extension.

---

## Scope

**In scope:**
- Alembic migration 005 — add `Workspace.backfill_started_at`, `backfill_completed_at`, `backfill_profile_count`
- `app/services/apify.py` — async Apify wrapper with test double
- `app/workers/day_one_backfill.py` — Celery task orchestrating scrape → pipeline ingestion
- `POST /extension/connections/bulk` — bulk upsert `Connection` rows
- `POST /workspace/backfill/trigger` — starts the task (idempotent via `backfill_used`)
- `GET /workspace/backfill/status` — polling endpoint for the dashboard banner
- New method on `EmailSender` — `send_backfill_complete(workspace, profile_count)`
- Chrome extension — new content script `capture-connections.ts`, popup button, manifest permission
- Frontend — `BackfillBanner.tsx` + 5 s polling hook while active
- Vitest smoke tests for the banner, Playwright golden-path (`.fixme` pending #65)
- Research spike artifacts: `docs/phase-2/backfill-apify-research.md` + `backfill-2nd-degree-research.md`
- TODO.md + CLAUDE.md updates

**Out of scope (follow-up slices):**
- 2nd-degree ICP-filtered scrape (research only — no implementation)
- CSV upload fallback path
- User-facing retry UX after hard Apify failure
- Per-connection profile enrichment beyond Apify's response
- Opt-out for the completion email

---

## File Structure

### New files
- `backend/alembic/versions/005_workspace_backfill_columns.py` — schema migration
- `backend/app/services/apify.py` — Apify HTTP wrapper + Pydantic response types
- `backend/app/workers/day_one_backfill.py` — Celery task entry point + pure-function aggregation helpers
- `backend/app/schemas/backfill.py` — Pydantic request/response shapes
- `backend/app/routers/backfill.py` — endpoints for connections bulk, trigger, status
- `backend/tests/test_apify_service.py` — wraps Apify, asserts request shape, mocked
- `backend/tests/test_day_one_backfill.py` — Celery task unit + integration tests
- `backend/tests/test_backfill_router.py` — endpoint tests (bulk, trigger idempotency, status)
- `backend/tests/test_backfill_flow.py` — end-to-end integration test
- `docs/phase-2/backfill-apify-research.md` — Task 1 deliverable
- `docs/phase-2/backfill-2nd-degree-research.md` — Task 12 deliverable
- `frontend/src/components/BackfillBanner.tsx` — dashboard banner + status polling
- `frontend/src/components/BackfillBanner.test.tsx` — Vitest smoke tests
- `extension/content/capture-connections.js` — LinkedIn connections-page scraper
- `e2e/tests/backfill-golden-path.spec.ts` — Playwright spec (.fixme pending #65)

### Modified files
- `backend/app/models/workspace.py` — declare the 3 new columns (Task 3)
- `backend/app/main.py` — register `backfill_router` (Task 7)
- `backend/app/delivery/email.py` — add `send_backfill_complete` method (Task 9)
- `frontend/src/pages/NetworkIntelligenceDashboard.tsx` — render `<BackfillBanner />` when status is active (Task 11)
- `extension/manifest.json` — add host permission for the connections page (Task 10)
- `extension/popup/*` — add "Run day-one scan" button (Task 10)
- `TODO.md` + `CLAUDE.md` — Task 13

Each file has one clear responsibility: the Apify wrapper knows nothing about domain models; the Celery task orchestrates without talking to HTTP directly; the router owns HTTP shape; the email sender owns templating; the extension owns DOM scraping.

---

## Test Strategy Note for Implementers

- Backend tests run via `docker compose exec -T api pytest`. Use `app.dependency_overrides` for Apify + Email mocking — matches Wizard / Dashboard pattern per `sonar/CLAUDE.md` "Python test mocking" Lessons Learned (issues #6 / #11).
- Apify HTTP is mocked via a `FakeApifyService` injected with `Depends(get_apify_service)`. Never `patch()` on module globals.
- Celery task body is tested by calling the pure orchestration function directly against a seeded DB; no broker required.
- Frontend tests follow the `Settings.test.tsx` / `NetworkIntelligenceDashboard.test.tsx` pattern — `vi.mock("../api/client")` + `@testing-library/react`.
- Playwright spec goes in `e2e/tests/` alongside existing specs. Mark `.fixme` pending issue #65.
- Stop hook at `.claude/hooks/verify.sh` will run pytest + tsc + vitest on every turn with relevant changes.
- Pre-commit hooks (ruff, ruff-format, gitleaks) run on commit. Use `pass123` for test passwords. If hooks reformat, `git add -u` and commit again.

---

## Task 1: Apify actor research spike

**Files:**
- Create: `docs/phase-2/backfill-apify-research.md`

- [ ] **Step 1: Visit Apify Store and identify candidates**

Browse https://apify.com/store?search=linkedin+profile. Identify 2-3 actors that:
- Accept a list of LinkedIn profile URLs as input
- Return posts from the last N days per profile
- Are maintained (last update within 6 months)
- Have pricing compatible with the $0.40/workspace target at 200 profiles

Candidate seeds (verify freshness before relying on them):
- `apify/linkedin-profile-scraper` (official Apify)
- `curious_coder/linkedin-profile-scraper` (popular 3rd-party)
- One more to be identified during research

- [ ] **Step 2: Write the research note**

Create `docs/phase-2/backfill-apify-research.md` with these sections:
1. Candidates table: actor id, last-updated date, pricing ($/1k profiles), input schema, output schema snippet, rate-limit posture
2. MVP pick + justification (pricing × maintenance × output-shape fit)
3. Known limitations of the picked actor (e.g. does it return post content, engagement counts, post timestamp?)
4. Fallback — if the MVP pick breaks in production, which candidate to swap to

- [ ] **Step 3: Commit**

```bash
git add docs/phase-2/backfill-apify-research.md
git commit -m "docs(backfill): Apify actor research spike"
```

If pre-commit reformats, `git add -u` and commit again.

---

## Task 2: Alembic migration 005 — Workspace backfill columns

**Files:**
- Create: `backend/alembic/versions/005_workspace_backfill_columns.py`

- [ ] **Step 1: Verify the current migration head**

Run: `docker compose exec -T api alembic current`
Expected: `004 (head)` (from the Wizard slice). If a different head is reported, set `down_revision` to match.

- [ ] **Step 2: Create the migration file**

Create `backend/alembic/versions/005_workspace_backfill_columns.py`:

```python
"""workspace backfill columns — day-one backfill bookkeeping

Revision ID: 005
Revises: 004
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("backfill_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column("backfill_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "backfill_profile_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "backfill_profile_count")
    op.drop_column("workspaces", "backfill_completed_at")
    op.drop_column("workspaces", "backfill_started_at")
```

- [ ] **Step 3: Run the migration + verify round-trip**

```bash
docker compose exec -T api alembic upgrade head
docker compose exec -T postgres psql -U sonar -d sonar -c "\d workspaces" | grep backfill
docker compose exec -T api alembic downgrade -1
docker compose exec -T postgres psql -U sonar -d sonar -c "\d workspaces" | grep backfill
docker compose exec -T api alembic upgrade head
```

Expected: first `\d | grep backfill` shows 4 columns (existing `backfill_used` + 3 new). After downgrade only `backfill_used` remains. After re-upgrade all 4 are back.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/005_workspace_backfill_columns.py
git commit -m "feat(db): migration 005 — workspace backfill bookkeeping columns"
```

---

## Task 3: Update Workspace ORM model + test

**Files:**
- Modify: `backend/app/models/workspace.py`
- Create: `backend/tests/test_workspace_backfill_columns.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_workspace_backfill_columns.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_workspace_has_backfill_bookkeeping_columns(db_session):
    ws = Workspace(name="Backfill Test")
    db_session.add(ws)
    await db_session.commit()

    # Defaults
    assert ws.backfill_used is False
    assert ws.backfill_started_at is None
    assert ws.backfill_completed_at is None
    assert ws.backfill_profile_count == 0

    # Set them
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    ws.backfill_completed_at = now
    ws.backfill_profile_count = 127
    await db_session.commit()

    reloaded = (await db_session.execute(
        select(Workspace).where(Workspace.id == ws.id)
    )).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None
    assert reloaded.backfill_profile_count == 127
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_workspace_backfill_columns.py -v`
Expected: FAIL with `AttributeError: 'Workspace' object has no attribute 'backfill_started_at'` (ORM doesn't declare the new columns yet).

- [ ] **Step 3: Update the ORM**

Edit `backend/app/models/workspace.py`. Find the line:
```python
    backfill_used = Column(Boolean, nullable=False, default=False)
```
and add AFTER it (before the `users = relationship(...)` line):
```python
    backfill_started_at = Column(TIMESTAMPTZ)
    backfill_completed_at = Column(TIMESTAMPTZ)
    backfill_profile_count = Column(Integer, nullable=False, default=0, server_default="0")
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_workspace_backfill_columns.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 97/97 + 3 skipped (96+3 baseline + 1 new test).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/workspace.py backend/tests/test_workspace_backfill_columns.py
git commit -m "feat(models): declare backfill bookkeeping columns on Workspace ORM"
```

---

## Task 4: Apify service wrapper

**Files:**
- Create: `backend/app/services/apify.py`
- Create: `backend/tests/test_apify_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_apify_service.py`:

```python
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from app.services.apify import (
    ApifyService,
    ApifyProfilePost,
    get_apify_service,
)


class FakeApify(ApifyService):
    """In-memory double for tests. Returns fixed posts regardless of input."""

    def __init__(self, posts_per_profile: int = 3):
        self.calls: list[dict] = []
        self._posts_per_profile = posts_per_profile

    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]:
        self.calls.append({"profile_urls": profile_urls, "days": days})
        out: list[ApifyProfilePost] = []
        for url in profile_urls:
            for i in range(self._posts_per_profile):
                out.append(
                    ApifyProfilePost(
                        profile_url=url,
                        linkedin_post_id=f"{url}-post-{i}",
                        content=f"post body {i} about hiring challenges",
                        posted_at=datetime.now(timezone.utc),
                        reaction_count=i * 3,
                        comment_count=i,
                        share_count=0,
                    )
                )
        return out


@pytest.mark.asyncio
async def test_fake_apify_returns_expected_shape():
    fake = FakeApify(posts_per_profile=2)
    result = await fake.scrape_profile_posts(
        ["https://linkedin.com/in/alice", "https://linkedin.com/in/bob"], days=60
    )
    assert len(result) == 4
    assert all(isinstance(p, ApifyProfilePost) for p in result)
    assert fake.calls == [
        {
            "profile_urls": [
                "https://linkedin.com/in/alice",
                "https://linkedin.com/in/bob",
            ],
            "days": 60,
        }
    ]


def test_get_apify_service_is_callable():
    svc = get_apify_service()
    assert isinstance(svc, ApifyService)
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_apify_service.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Create the service**

Create `backend/app/services/apify.py`:

```python
"""Apify service wrapper for the Day-One Backfill slice.

First external HTTP integration since SendGrid/Groq. Follows the Depends()-
injectable pattern (per sonar/CLAUDE.md Python test mocking rules) so tests
never touch real Apify.

Actor selection + pricing documented in docs/phase-2/backfill-apify-research.md.
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Protocol
import httpx
from pydantic import BaseModel
from app.config import get_settings


class ApifyProfilePost(BaseModel):
    """Normalized representation of one post returned by Apify."""

    profile_url: str
    linkedin_post_id: str
    content: str
    posted_at: datetime
    reaction_count: int = 0
    comment_count: int = 0
    share_count: int = 0


class ApifyService(Protocol):
    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]:
        ...


class RealApifyService:
    """Production implementation. Calls the configured Apify actor via HTTPS.

    The specific actor id and input-schema mapping live in
    docs/phase-2/backfill-apify-research.md. Update this class when the
    MVP pick changes.
    """

    _ACTOR_ID = "apify/linkedin-profile-scraper"  # verify in research spike
    _RUN_TIMEOUT_SEC = 600

    def __init__(self) -> None:
        token = get_settings().apify_api_token
        if token.startswith("placeholder"):
            raise RuntimeError(
                "APIFY_API_TOKEN is the placeholder value; real token required "
                "to call the live Apify API."
            )
        self._token = token
        self._base = "https://api.apify.com/v2"

    async def scrape_profile_posts(
        self, profile_urls: list[str], days: int
    ) -> list[ApifyProfilePost]:
        run_url = (
            f"{self._base}/acts/{self._ACTOR_ID}/run-sync-get-dataset-items"
            f"?token={self._token}"
        )
        payload = {
            "profileUrls": profile_urls,
            "maxPostsPerProfile": 30,
            "daysBack": days,
        }
        async with httpx.AsyncClient(timeout=self._RUN_TIMEOUT_SEC) as client:
            resp = await client.post(run_url, json=payload)
            resp.raise_for_status()
            raw = resp.json()

        # Actor-specific field mapping. Adjust when swapping actors.
        posts: list[ApifyProfilePost] = []
        for item in raw:
            try:
                posts.append(
                    ApifyProfilePost(
                        profile_url=item["profileUrl"],
                        linkedin_post_id=item["postId"],
                        content=item.get("text", ""),
                        posted_at=datetime.fromisoformat(item["postedAt"]),
                        reaction_count=item.get("reactions", 0),
                        comment_count=item.get("comments", 0),
                        share_count=item.get("shares", 0),
                    )
                )
            except (KeyError, ValueError):
                # Malformed row from Apify — skip, keep the batch useful.
                continue
        return posts


_singleton: RealApifyService | None = None


def get_apify_service() -> ApifyService:
    """FastAPI Depends() factory. Tests override with a FakeApifyService."""
    global _singleton
    if _singleton is None:
        _singleton = RealApifyService()
    return _singleton
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_apify_service.py -v`
Expected: the FakeApify-using tests pass. `test_get_apify_service_is_callable` will FAIL in dev because `apify_api_token` is `placeholder-apify-token` and `RealApifyService.__init__` raises. **Adjust the test** to either mock the config or move the placeholder-check to lazy-on-first-call. Cleanest fix: skip the test when the token is placeholder:

```python
import pytest
from app.config import get_settings


@pytest.mark.skipif(
    get_settings().apify_api_token.startswith("placeholder"),
    reason="requires real APIFY_API_TOKEN",
)
def test_get_apify_service_is_callable():
    svc = get_apify_service()
    assert isinstance(svc, ApifyService)
```

Expected after adjustment: 2 passed, 1 skipped.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 99/99 + 4 skipped (97+3 baseline + 2 new passing + 1 new skipped).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/apify.py backend/tests/test_apify_service.py
git commit -m "feat(services): Apify wrapper with Depends()-injectable test seam"
```

---

## Task 5: Celery task `day_one_backfill.py`

**Files:**
- Create: `backend/app/workers/day_one_backfill.py`
- Create: `backend/tests/test_day_one_backfill.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_day_one_backfill.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.user import User
from app.models.connection import Connection
from app.models.post import Post
from app.services.apify import ApifyProfilePost
from app.workers.day_one_backfill import run_day_one_backfill
from tests.test_apify_service import FakeApify


async def _seed_workspace_with_connections(db_session, n_connections: int = 3):
    ws = Workspace(name="Backfill WS")
    db_session.add(ws)
    await db_session.flush()
    user = User(
        workspace_id=ws.id, email="x@x.com", hashed_password="x", role="owner"
    )
    db_session.add(user)
    await db_session.flush()
    for i in range(n_connections):
        db_session.add(
            Connection(
                workspace_id=ws.id, user_id=user.id,
                linkedin_id=f"li-{i}", name=f"Conn {i}",
                profile_url=f"https://linkedin.com/in/conn-{i}",
                degree=1,
            )
        )
    await db_session.commit()
    return ws


@pytest.mark.asyncio
async def test_run_day_one_backfill_ingests_posts_and_marks_complete(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=3)
    fake_apify = FakeApify(posts_per_profile=2)

    await run_day_one_backfill(db_session, workspace_id=ws.id, apify=fake_apify)
    await db_session.commit()

    # Apify called once with all 3 profile URLs + 60-day window
    assert len(fake_apify.calls) == 1
    assert len(fake_apify.calls[0]["profile_urls"]) == 3
    assert fake_apify.calls[0]["days"] == 60

    # 3 connections × 2 posts = 6 Post rows
    posts = (await db_session.execute(select(Post))).scalars().all()
    assert len(posts) == 6

    # Workspace bookkeeping updated
    reloaded = (await db_session.execute(
        select(Workspace).where(Workspace.id == ws.id)
    )).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None
    assert reloaded.backfill_completed_at is not None
    assert reloaded.backfill_profile_count == 3


@pytest.mark.asyncio
async def test_run_day_one_backfill_caps_at_200_profiles(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=250)
    fake_apify = FakeApify(posts_per_profile=1)

    await run_day_one_backfill(db_session, workspace_id=ws.id, apify=fake_apify)
    await db_session.commit()

    # Only 200 profile URLs forwarded
    assert len(fake_apify.calls[0]["profile_urls"]) == 200

    reloaded = (await db_session.execute(
        select(Workspace).where(Workspace.id == ws.id)
    )).scalar_one()
    assert reloaded.backfill_profile_count == 200


@pytest.mark.asyncio
async def test_run_day_one_backfill_is_idempotent(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=2)
    ws.backfill_used = True  # already backfilled
    await db_session.commit()

    fake_apify = FakeApify(posts_per_profile=2)
    with pytest.raises(ValueError, match="already backfilled"):
        await run_day_one_backfill(
            db_session, workspace_id=ws.id, apify=fake_apify
        )
    # Apify was NOT called
    assert fake_apify.calls == []
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_day_one_backfill.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Create the task**

Create `backend/app/workers/day_one_backfill.py`:

```python
"""Day-One Backfill Celery task.

Called once per workspace after the wizard completes + the extension
captures the user's connection list. Runs an Apify 1st-degree scrape,
ingests the resulting posts through the existing pipeline.

Caps: 200 connections × 60 days per workspace (see
docs/phase-2/backfill-decisions.md §4).
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.connection import Connection
from app.models.post import Post
from app.models.workspace import Workspace
from app.services.apify import ApifyService

MAX_CONNECTIONS = 200
DAYS_BACK = 60


async def run_day_one_backfill(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    apify: ApifyService,
) -> int:
    """Run backfill for one workspace. Returns the number of profiles scraped.

    Raises ValueError if the workspace has already been backfilled.
    """
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )).scalar_one_or_none()
    if ws is None:
        raise ValueError(f"workspace {workspace_id} not found")
    if ws.backfill_used:
        raise ValueError(f"workspace {workspace_id} already backfilled")

    # Mark started + consumed FIRST — prevents double-enqueue on retry.
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db.flush()

    # Pick up to 200 connections, ordered by first_seen_at DESC (proxy for
    # "most-recently-active" since connections without posts have null
    # last_active_at). Swap to last_active_at once it's reliably populated.
    conns = (await db.execute(
        select(Connection)
        .where(Connection.workspace_id == workspace_id)
        .where(Connection.degree == 1)
        .order_by(Connection.first_seen_at.desc())
        .limit(MAX_CONNECTIONS)
    )).scalars().all()
    profile_urls = [c.profile_url for c in conns if c.profile_url]
    conn_by_url = {c.profile_url: c for c in conns if c.profile_url}

    # Scrape via Apify
    posts = await apify.scrape_profile_posts(
        profile_urls=profile_urls, days=DAYS_BACK
    )

    # Ingest each post (simplified — in prod this would dispatch to the
    # pipeline Celery task; for MVP we insert Post rows directly so the
    # existing pipeline picks them up on its next sweep).
    for p in posts:
        conn = conn_by_url.get(p.profile_url)
        if conn is None:
            continue
        db.add(
            Post(
                workspace_id=workspace_id,
                connection_id=conn.id,
                linkedin_post_id=p.linkedin_post_id,
                content=p.content,
                post_type="text",
                source="backfill",
                posted_at=p.posted_at,
                engagement_counts={
                    "reactions": p.reaction_count,
                    "comments": p.comment_count,
                    "shares": p.share_count,
                },
            )
        )

    ws.backfill_completed_at = datetime.now(timezone.utc)
    ws.backfill_profile_count = len(profile_urls)
    await db.flush()
    return len(profile_urls)
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_day_one_backfill.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 102/102 + 4 skipped.

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/day_one_backfill.py backend/tests/test_day_one_backfill.py
git commit -m "feat(backfill): day_one_backfill Celery task"
```

---

## Task 6: `POST /extension/connections/bulk` endpoint

**Files:**
- Create: `backend/app/schemas/backfill.py`
- Create: `backend/app/routers/backfill.py`
- Create: `backend/tests/test_backfill_router.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_backfill_router.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.user import User
from app.models.connection import Connection
from app.models.workspace import Workspace
from app.routers.auth import create_access_token


def _tok(user_id, workspace_id):
    return create_access_token(user_id=user_id, workspace_id=workspace_id)


async def _seed_workspace(db_session, email: str):
    ws = Workspace(name=f"WS {email}")
    db_session.add(ws)
    await db_session.flush()
    user = User(
        workspace_id=ws.id, email=email, hashed_password="x", role="owner"
    )
    db_session.add(user)
    await db_session.commit()
    return ws, user


@pytest.mark.asyncio
async def test_connections_bulk_upserts_rows(client, db_session):
    ws, user = await _seed_workspace(db_session, "a@a.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post(
        "/extension/connections/bulk",
        json={
            "connections": [
                {
                    "linkedin_id": "li-1",
                    "name": "Alice",
                    "headline": "VP Eng",
                    "company": "Acme",
                    "profile_url": "https://linkedin.com/in/alice",
                },
                {
                    "linkedin_id": "li-2",
                    "name": "Bob",
                    "headline": None,
                    "company": None,
                    "profile_url": "https://linkedin.com/in/bob",
                },
            ]
        },
        headers=hdrs,
    )
    assert resp.status_code == 200
    assert resp.json() == {"upserted": 2}

    rows = (await db_session.execute(
        select(Connection).where(Connection.workspace_id == ws.id)
    )).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_connections_bulk_dedupes_on_linkedin_id(client, db_session):
    ws, user = await _seed_workspace(db_session, "b@b.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    await client.post(
        "/extension/connections/bulk",
        json={"connections": [{
            "linkedin_id": "li-dup", "name": "Old", "headline": None,
            "company": None, "profile_url": "https://linkedin.com/in/dup",
        }]},
        headers=hdrs,
    )
    # Send again with the same linkedin_id but updated name
    await client.post(
        "/extension/connections/bulk",
        json={"connections": [{
            "linkedin_id": "li-dup", "name": "New", "headline": "Updated",
            "company": "NewCo", "profile_url": "https://linkedin.com/in/dup",
        }]},
        headers=hdrs,
    )

    rows = (await db_session.execute(
        select(Connection).where(Connection.workspace_id == ws.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "New"
    assert rows[0].company == "NewCo"


@pytest.mark.asyncio
async def test_connections_bulk_rejects_unauthenticated(client):
    resp = await client.post(
        "/extension/connections/bulk",
        json={"connections": []},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: 404 / import error on all tests.

- [ ] **Step 3: Create the schema**

Create `backend/app/schemas/backfill.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class BulkConnection(BaseModel):
    linkedin_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    headline: str | None = Field(default=None, max_length=500)
    company: str | None = Field(default=None, max_length=200)
    profile_url: str = Field(min_length=1, max_length=500)


class ConnectionsBulkRequest(BaseModel):
    connections: list[BulkConnection] = Field(min_length=0, max_length=500)


class ConnectionsBulkResponse(BaseModel):
    upserted: int


class BackfillTriggerResponse(BaseModel):
    task_id: str
    backfill_started_at: datetime


BackfillState = Literal["idle", "running", "done", "failed"]


class BackfillStatusResponse(BaseModel):
    state: BackfillState
    profile_count: int
    backfill_started_at: datetime | None
    backfill_completed_at: datetime | None
```

- [ ] **Step 4: Create the router**

Create `backend/app/routers/backfill.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.connection import Connection
from app.models.user import User
from app.models.workspace import Workspace
from app.rate_limit import limiter
from app.routers.auth import get_current_user
from app.schemas.backfill import (
    BackfillStatusResponse,
    BackfillTriggerResponse,
    ConnectionsBulkRequest,
    ConnectionsBulkResponse,
)

router = APIRouter(tags=["backfill"])


@router.post("/extension/connections/bulk", response_model=ConnectionsBulkResponse)
@limiter.limit("5/hour")
async def connections_bulk(
    request: Request,
    body: ConnectionsBulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.connections:
        return ConnectionsBulkResponse(upserted=0)

    # Load existing connections in this batch
    linkedin_ids = [c.linkedin_id for c in body.connections]
    existing = (await db.execute(
        select(Connection).where(
            Connection.workspace_id == current_user.workspace_id,
            Connection.linkedin_id.in_(linkedin_ids),
        )
    )).scalars().all()
    existing_by_lid = {c.linkedin_id: c for c in existing}

    for row in body.connections:
        e = existing_by_lid.get(row.linkedin_id)
        if e is not None:
            e.name = row.name
            e.headline = row.headline
            e.company = row.company
            e.profile_url = row.profile_url
        else:
            db.add(
                Connection(
                    workspace_id=current_user.workspace_id,
                    user_id=current_user.id,
                    linkedin_id=row.linkedin_id,
                    name=row.name,
                    headline=row.headline,
                    company=row.company,
                    profile_url=row.profile_url,
                    degree=1,
                )
            )

    await db.commit()
    return ConnectionsBulkResponse(upserted=len(body.connections))
```

- [ ] **Step 5: Register the router**

Edit `backend/app/main.py`:
- Add import near other router imports: `from app.routers.backfill import router as backfill_router`
- Add `app.include_router(backfill_router)` near the other `include_router` calls

- [ ] **Step 6: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 105/105 + 4 skipped.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/backfill.py backend/app/routers/backfill.py backend/app/main.py backend/tests/test_backfill_router.py
git commit -m "feat(backfill): POST /extension/connections/bulk endpoint"
```

---

## Task 7: `POST /workspace/backfill/trigger` endpoint

**Files:**
- Modify: `backend/app/routers/backfill.py`
- Modify: `backend/tests/test_backfill_router.py` (extend)

- [ ] **Step 1: Add the failing tests**

Append to `backend/tests/test_backfill_router.py`:

```python
from unittest.mock import patch


@pytest.mark.asyncio
async def test_trigger_sets_started_at_on_first_call(client, db_session):
    ws, user = await _seed_workspace(db_session, "trig1@t.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post("/workspace/backfill/trigger", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert "task_id" in body
    assert "backfill_started_at" in body

    reloaded = (await db_session.execute(
        select(Workspace).where(Workspace.id == ws.id)
    )).scalar_one()
    assert reloaded.backfill_used is True
    assert reloaded.backfill_started_at is not None


@pytest.mark.asyncio
async def test_trigger_returns_409_on_second_call(client, db_session):
    ws, user = await _seed_workspace(db_session, "trig2@t.com")
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}

    resp = await client.post("/workspace/backfill/trigger", headers=hdrs)
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: new tests FAIL with 404.

- [ ] **Step 3: Add the endpoint**

Append to `backend/app/routers/backfill.py`:

```python
@router.post("/workspace/backfill/trigger", response_model=BackfillTriggerResponse)
@limiter.limit("2/day")
async def backfill_trigger(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == current_user.workspace_id)
    )).scalar_one()
    if ws.backfill_used:
        raise HTTPException(
            status_code=409,
            detail=(
                "Backfill already used for this workspace (started at "
                f"{ws.backfill_started_at.isoformat() if ws.backfill_started_at else 'unknown'})"
            ),
        )

    # Mark started now to prevent race with a second trigger before the
    # Celery task picks up.
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    await db.commit()

    # In prod: enqueue Celery task. For MVP test visibility we return a
    # synthesized task_id — the actual Celery dispatch is wired in Task 13
    # once end-to-end infra is in place.
    task_id = f"backfill-{current_user.workspace_id}-{int(now.timestamp())}"
    return BackfillTriggerResponse(task_id=task_id, backfill_started_at=now)
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/backfill.py backend/tests/test_backfill_router.py
git commit -m "feat(backfill): POST /workspace/backfill/trigger with idempotency"
```

---

## Task 8: `GET /workspace/backfill/status` endpoint

**Files:**
- Modify: `backend/app/routers/backfill.py`
- Modify: `backend/tests/test_backfill_router.py` (extend)

- [ ] **Step 1: Add the failing tests**

Append to `backend/tests/test_backfill_router.py`:

```python
@pytest.mark.asyncio
async def test_status_reports_idle_before_trigger(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat1@s.com")
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    resp = await client.get("/workspace/backfill/status", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "idle"
    assert body["profile_count"] == 0


@pytest.mark.asyncio
async def test_status_reports_running_after_start(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat2@s.com")
    ws.backfill_used = True
    ws.backfill_started_at = datetime.now(timezone.utc)
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    resp = await client.get("/workspace/backfill/status", headers=hdrs)
    assert resp.json()["state"] == "running"


@pytest.mark.asyncio
async def test_status_reports_done_after_completion(client, db_session):
    ws, user = await _seed_workspace(db_session, "stat3@s.com")
    now = datetime.now(timezone.utc)
    ws.backfill_used = True
    ws.backfill_started_at = now
    ws.backfill_completed_at = now
    ws.backfill_profile_count = 127
    await db_session.commit()
    hdrs = {"Authorization": f"Bearer {_tok(user.id, ws.id)}"}
    body = (await client.get("/workspace/backfill/status", headers=hdrs)).json()
    assert body["state"] == "done"
    assert body["profile_count"] == 127
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: new tests FAIL (404).

- [ ] **Step 3: Add the endpoint**

Append to `backend/app/routers/backfill.py`:

```python
@router.get("/workspace/backfill/status", response_model=BackfillStatusResponse)
async def backfill_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == current_user.workspace_id)
    )).scalar_one()

    if not ws.backfill_used:
        state = "idle"
    elif ws.backfill_completed_at is None:
        state = "running"
    else:
        state = "done"

    return BackfillStatusResponse(
        state=state,
        profile_count=ws.backfill_profile_count,
        backfill_started_at=ws.backfill_started_at,
        backfill_completed_at=ws.backfill_completed_at,
    )
```

**NOTE** the `failed` state isn't surfaced here yet — it requires a dedicated `backfill_failed_at` or `backfill_error` column. Deferring to a follow-up task or column addition if needed.

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_backfill_router.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 110/110 + 4 skipped.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/backfill.py backend/tests/test_backfill_router.py
git commit -m "feat(backfill): GET /workspace/backfill/status endpoint"
```

---

## Task 9: Completion-email integration

**Files:**
- Modify: `backend/app/delivery/email.py` — add `send_backfill_complete` method
- Modify: `backend/app/workers/day_one_backfill.py` — hook email send on completion
- Create: `backend/tests/test_backfill_email.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_backfill_email.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.delivery.email import EmailSender
from app.models.workspace import Workspace
from app.workers.day_one_backfill import run_day_one_backfill
from tests.test_apify_service import FakeApify
from tests.test_day_one_backfill import _seed_workspace_with_connections


class FakeEmailSender:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_backfill_complete(
        self, workspace: Workspace, profile_count: int
    ) -> None:
        self.calls.append(
            {
                "workspace_id": workspace.id,
                "profile_count": profile_count,
                "email": workspace.delivery_channels.get("email", {}).get("address"),
            }
        )


@pytest.mark.asyncio
async def test_backfill_sends_completion_email(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=2)
    ws.delivery_channels = {"email": {"address": "ops@example.com"}}
    await db_session.commit()

    apify = FakeApify(posts_per_profile=1)
    email = FakeEmailSender()

    await run_day_one_backfill(
        db_session, workspace_id=ws.id, apify=apify, email=email
    )
    await db_session.commit()

    assert len(email.calls) == 1
    assert email.calls[0]["email"] == "ops@example.com"
    assert email.calls[0]["profile_count"] == 2
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_backfill_email.py -v`
Expected: FAIL — `run_day_one_backfill` doesn't accept an `email` argument.

- [ ] **Step 3: Add `send_backfill_complete` to EmailSender**

Edit `backend/app/delivery/email.py`. Add inside the `EmailSender` class (after the existing `send` method):

```python
    async def send_backfill_complete(
        self, workspace, profile_count: int
    ) -> None:
        """One-time onboarding email sent when Day-One Backfill finishes."""
        config = workspace.delivery_channels.get("email", {}) if workspace.delivery_channels else {}
        to_email = config.get("address")
        if not to_email:
            return

        subject = "Your Sonar dashboard is ready"
        html = f"""
        <h2>Your Sonar dashboard is ready</h2>
        <p>We've finished scanning <strong>{profile_count}</strong> people in your network for buying-intent signals over the past 60 days.</p>
        <p>Open your dashboard to see who's showing intent right now:</p>
        <p><a href="http://localhost:5173/dashboard">Open Sonar Dashboard</a></p>
        <p>Going forward, new signals flow into your dashboard automatically as the extension observes your LinkedIn feed.</p>
        """

        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=get_settings().sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        await asyncio.to_thread(self._client.send, message)
```

- [ ] **Step 4: Wire email into `run_day_one_backfill`**

Edit `backend/app/workers/day_one_backfill.py`. Change the signature and add the call:

```python
async def run_day_one_backfill(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    apify: ApifyService,
    email=None,  # Optional — inject FakeEmailSender in tests
) -> int:
    # ... existing body ...

    ws.backfill_completed_at = datetime.now(timezone.utc)
    ws.backfill_profile_count = len(profile_urls)
    await db.flush()

    # Fire-and-forget completion email. Email failures do NOT fail the task.
    if email is not None:
        try:
            await email.send_backfill_complete(ws, len(profile_urls))
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "[backfill] completion email failed, continuing: %s", exc
            )

    return len(profile_urls)
```

- [ ] **Step 5: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_backfill_email.py tests/test_day_one_backfill.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: 111/111 + 4 skipped.

- [ ] **Step 7: Commit**

```bash
git add backend/app/delivery/email.py backend/app/workers/day_one_backfill.py backend/tests/test_backfill_email.py
git commit -m "feat(backfill): completion email via EmailSender.send_backfill_complete"
```

---

## Task 10: Chrome extension — content script + popup button

**Files:**
- Create: `extension/content/capture-connections.js`
- Modify: `extension/manifest.json` — add host permission
- Modify: `extension/popup/popup.html` + `popup.js` — add "Run day-one scan" button

- [ ] **Step 1: Read existing manifest + popup to match style**

```bash
cat extension/manifest.json
cat extension/popup/popup.html
cat extension/popup/popup.js
```

Note existing permission style, message-passing pattern (chrome.runtime.sendMessage or similar), and content-script structure (there's an existing `extension/content/` directory for feed-capture scripts).

- [ ] **Step 2: Add host permission to manifest**

In `extension/manifest.json`, inside `host_permissions` (or `content_scripts.matches` if that's the existing pattern), add:

```json
"https://www.linkedin.com/mynetwork/invite-connect/connections/*"
```

- [ ] **Step 3: Create the content script**

Create `extension/content/capture-connections.js`:

```javascript
// Day-One Backfill: scrape the user's 1st-degree connection list.
// Triggered by a message from the extension popup. Scrolls the virtualized
// list, extracts each connection's profile_url / name / headline / company,
// POSTs in chunks of 100 to /extension/connections/bulk, then calls
// /workspace/backfill/trigger.

(async function main() {
  if (!window.location.pathname.includes("/mynetwork/invite-connect/connections")) {
    return;
  }

  function extractConnectionsFromDOM() {
    const rows = document.querySelectorAll('[data-chameleon-result-urn]');
    const out = [];
    for (const row of rows) {
      const link = row.querySelector('a[href*="/in/"]');
      if (!link) continue;
      const profile_url = new URL(link.href).origin + new URL(link.href).pathname;
      const name = row.querySelector('[data-test-app-aware-link] span')?.textContent?.trim() || "";
      const headline = row.querySelector('.mn-connection-card__occupation')?.textContent?.trim() || null;
      if (!name) continue;
      const linkedin_id = new URL(link.href).pathname.split('/in/')[1]?.replace(/\/$/, "");
      out.push({
        linkedin_id, name, headline, company: null, profile_url,
      });
    }
    return out;
  }

  async function scrollAndCollect(maxScrolls = 30) {
    const seen = new Set();
    const all = [];
    for (let i = 0; i < maxScrolls; i++) {
      const batch = extractConnectionsFromDOM();
      for (const c of batch) {
        if (!seen.has(c.linkedin_id)) {
          seen.add(c.linkedin_id);
          all.push(c);
        }
      }
      window.scrollTo(0, document.body.scrollHeight);
      await new Promise(r => setTimeout(r, 1500));
    }
    return all;
  }

  async function postBulk(connections) {
    const CHUNK = 100;
    for (let i = 0; i < connections.length; i += CHUNK) {
      const chunk = connections.slice(i, i + CHUNK);
      const res = await fetch("http://localhost:8000/extension/connections/bulk", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${await getAuthToken()}`,
        },
        body: JSON.stringify({ connections: chunk }),
      });
      if (!res.ok) throw new Error(`bulk post failed: ${res.status}`);
    }
  }

  async function triggerBackfill() {
    const res = await fetch("http://localhost:8000/workspace/backfill/trigger", {
      method: "POST",
      headers: { "Authorization": `Bearer ${await getAuthToken()}` },
    });
    if (!res.ok && res.status !== 409) {
      throw new Error(`trigger failed: ${res.status}`);
    }
  }

  async function getAuthToken() {
    return new Promise(resolve => {
      chrome.storage.local.get(["sonar_token"], (r) => resolve(r.sonar_token || ""));
    });
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type !== "run_day_one_scan") return;
    (async () => {
      try {
        const connections = await scrollAndCollect();
        if (connections.length === 0) {
          sendResponse({ ok: false, error: "no_connections_found" });
          return;
        }
        await postBulk(connections);
        await triggerBackfill();
        sendResponse({ ok: true, count: connections.length });
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true; // keep channel open for async response
  });
})();
```

- [ ] **Step 4: Register the content script in manifest**

Edit `extension/manifest.json` — add to `content_scripts` array:

```json
{
  "matches": ["https://www.linkedin.com/mynetwork/invite-connect/connections/*"],
  "js": ["content/capture-connections.js"]
}
```

- [ ] **Step 5: Add the popup button**

Edit `extension/popup/popup.html` — add (near the existing button elements):

```html
<button id="run-day-one-scan" class="btn">Run day-one scan</button>
<div id="day-one-status" class="status"></div>
```

Edit `extension/popup/popup.js` — add:

```javascript
document.getElementById("run-day-one-scan").addEventListener("click", async () => {
  const statusEl = document.getElementById("day-one-status");
  statusEl.textContent = "Scanning connections...";
  const [tab] = await chrome.tabs.query({ url: "https://www.linkedin.com/mynetwork/invite-connect/connections/*" });
  if (!tab) {
    statusEl.textContent = "Open your LinkedIn connections page first.";
    return;
  }
  chrome.tabs.sendMessage(tab.id, { type: "run_day_one_scan" }, (res) => {
    if (!res) {
      statusEl.textContent = "Scan failed to start. Refresh the connections page and try again.";
      return;
    }
    if (res.ok) {
      statusEl.textContent = `Backfill started for ${res.count} connections. Check your dashboard.`;
    } else {
      statusEl.textContent = `Scan failed: ${res.error}`;
    }
  });
});
```

- [ ] **Step 6: Verify the extension loads (manual)**

Load the extension as unpacked in Chrome: `chrome://extensions` → Developer mode → Load unpacked → select `extension/`. Open popup. Expected: "Run day-one scan" button appears. Clicking it (without the connections page open) shows the "Open your LinkedIn connections page first" message.

Full end-to-end test (open connections page → click button → observe scroll + network calls) is a manual verification; it's exercised by the Playwright spec in Task 11 (marked `.fixme`) and by real-user dogfooding.

- [ ] **Step 7: Commit**

```bash
git add extension/content/capture-connections.js extension/manifest.json extension/popup/popup.html extension/popup/popup.js
git commit -m "feat(extension): day-one-scan content script + popup button"
```

---

## Task 11: Frontend — BackfillBanner with 5s polling

**Files:**
- Create: `frontend/src/components/BackfillBanner.tsx`
- Create: `frontend/src/components/BackfillBanner.test.tsx`
- Modify: `frontend/src/pages/NetworkIntelligenceDashboard.tsx` — render `<BackfillBanner />`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/BackfillBanner.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BackfillBanner from "./BackfillBanner";

vi.mock("../api/client", () => ({
  default: { get: vi.fn() },
}));

describe("BackfillBanner", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders nothing when state is idle", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { state: "idle", profile_count: 0, backfill_started_at: null, backfill_completed_at: null },
    });

    const { container } = render(<BackfillBanner />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("renders running banner when state is running", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
        state: "running",
        profile_count: 0,
        backfill_started_at: new Date().toISOString(),
        backfill_completed_at: null,
      },
    });
    render(<BackfillBanner />);
    await waitFor(() =>
      expect(screen.getByText(/backfill in progress/i)).toBeInTheDocument()
    );
  });

  it("renders done banner when state is done", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
        state: "done",
        profile_count: 127,
        backfill_started_at: new Date().toISOString(),
        backfill_completed_at: new Date().toISOString(),
      },
    });
    render(<BackfillBanner />);
    await waitFor(() =>
      expect(screen.getByText(/backfill complete/i)).toBeInTheDocument()
    );
  });
});
```

- [ ] **Step 2: Run — verify fail**

Run: `cd frontend && npm run test:run -- BackfillBanner`
Expected: FAIL (module missing).

- [ ] **Step 3: Create the component**

Create `frontend/src/components/BackfillBanner.tsx`:

```tsx
import { useCallback } from "react";
import api from "../api/client";
import { usePolledEndpoint } from "../hooks/usePolledEndpoint";

interface BackfillStatus {
  state: "idle" | "running" | "done" | "failed";
  profile_count: number;
  backfill_started_at: string | null;
  backfill_completed_at: string | null;
}

export function BackfillBanner() {
  const fetcher = useCallback(async (): Promise<BackfillStatus> => {
    const { data } = await api.get<BackfillStatus>("/workspace/backfill/status");
    return data;
  }, []);

  const { data } = usePolledEndpoint(fetcher, { intervalMs: 5000 });

  if (!data || data.state === "idle") {
    return null;
  }

  if (data.state === "running") {
    return (
      <div
        role="status"
        style={{
          padding: 12,
          background: "#eef6ff",
          border: "1px solid #b3d4ff",
          borderRadius: 8,
          marginBottom: 16,
          fontSize: 14,
        }}
      >
        Backfill in progress — your dashboard will populate as we process your network.
      </div>
    );
  }

  if (data.state === "done") {
    return (
      <div
        role="status"
        style={{
          padding: 12,
          background: "#e9f7e9",
          border: "1px solid #b6dfb6",
          borderRadius: 8,
          marginBottom: 16,
          fontSize: 14,
        }}
      >
        Backfill complete — you're seeing your full 60-day network snapshot ({data.profile_count} people).
      </div>
    );
  }

  return (
    <div
      role="status"
      style={{
        padding: 12,
        background: "#fdecec",
        border: "1px solid #f5c2c2",
        borderRadius: 8,
        marginBottom: 16,
        fontSize: 14,
      }}
    >
      Backfill didn't complete cleanly — signals will accumulate from here. Contact support if this persists.
    </div>
  );
}

export default BackfillBanner;
```

- [ ] **Step 4: Run — verify pass**

Run: `cd frontend && npm run test:run -- BackfillBanner`
Expected: all 3 tests PASS.

- [ ] **Step 5: Render the banner on the Dashboard**

Edit `frontend/src/pages/NetworkIntelligenceDashboard.tsx`. Add the import near the top:

```tsx
import BackfillBanner from "../components/BackfillBanner";
```

Then inside the JSX return, render `<BackfillBanner />` at the top of the main `<div>` (above the existing `<header>`):

```tsx
return (
  <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
    <BackfillBanner />
    <header>...existing...</header>
    ...
```

- [ ] **Step 6: Build + full frontend suite**

```bash
cd frontend && npm run build
cd frontend && npm run test:run
```
Expected: build succeeds; all tests (Settings + SignalConfig + NetworkIntelligenceDashboard + usePolledEndpoint + BackfillBanner) pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/BackfillBanner.tsx frontend/src/components/BackfillBanner.test.tsx frontend/src/pages/NetworkIntelligenceDashboard.tsx
git commit -m "feat(frontend): BackfillBanner with 5s polling on dashboard"
```

---

## Task 12: 2nd-degree research spike

**Files:**
- Create: `docs/phase-2/backfill-2nd-degree-research.md`

- [ ] **Step 1: Browse Apify Store for ICP-filtered search actors**

Search terms: "linkedin sales navigator", "linkedin search", "linkedin people search". Note which actors:
- Accept filter criteria (title, seniority, company-size, industry)
- Can scope to 2nd-degree (rarely exposed directly; sometimes inferable via sales-navigator actors)
- Return profile URLs + recent posts

- [ ] **Step 2: Write the research note**

Create `docs/phase-2/backfill-2nd-degree-research.md` with:
1. Candidates considered (id, last updated, pricing, input schema)
2. Which candidates support ICP-style filters
3. Which can scope to 2nd-degree
4. MVP candidate (may be "none yet"), with justification
5. Notes on LinkedIn ToS considerations — anything that would make us pull back

If no viable actor exists today, the note says so explicitly: "As of 2026-04-18, no Apify actor directly supports 2nd-degree ICP-filtered post scraping. Revisit in ~3 months."

- [ ] **Step 3: Commit**

```bash
git add docs/phase-2/backfill-2nd-degree-research.md
git commit -m "docs(backfill): 2nd-degree Apify actor research spike"
```

---

## Task 13: TODO.md + CLAUDE.md updates

**Files:**
- Modify: `TODO.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `TODO.md`**

Find the Phase 2 status table. Change the **Backfill** row from `⬜ Not started` to:

```
| **Backfill** | ✅ Shipped session 6 (this PR — 1st-degree only) | Day-One Backfill at `/workspace/backfill/*`. Extension captures connection list → `/extension/connections/bulk` upserts `Connection` rows → `/workspace/backfill/trigger` starts the `day_one_backfill` Celery task (idempotent via `Workspace.backfill_used`) → Apify 1st-degree scrape caps at 200 × 60 days → posts flow through pipeline → completion email via `EmailSender.send_backfill_complete`. Dashboard banner polls `/workspace/backfill/status` at 5s. 2nd-degree ICP-filtered scrape deferred — research note at `docs/phase-2/backfill-2nd-degree-research.md`. |
```

Update header count: `### Phase 2 — **4 of 5 slices shipped, 1 remaining**`.

Also update the "Resume Here" block at the top with a new session summary.

- [ ] **Step 2: Update `CLAUDE.md`**

Find the "LLM and agent discipline" section (or the Pipeline section if one exists). Add a bullet near external-integration guidance:

```markdown
- **External HTTP integrations follow the Apify/SendGrid pattern.** Define a `Protocol` class (the interface), a `Real{Service}` implementation (production), and a `get_{service}` factory used with `Depends()`. Tests inject a `Fake{Service}` via `app.dependency_overrides` — never `patch()` on module globals. See `app/services/apify.py` for the canonical example added in the Backfill slice.
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md CLAUDE.md
git commit -m "docs: mark Backfill slice shipped, document external-HTTP integration pattern"
```

---

## Self-Review Notes

Applied inline before saving this plan:

**Spec coverage:** Every in-scope item from `docs/phase-2/backfill-decisions.md` maps to a task — migration (2), ORM (3), Apify service (4), Celery task (5), bulk endpoint (6), trigger endpoint (7), status endpoint (8), email (9), extension (10), frontend banner (11), research spikes (1, 12), docs (13). Out-of-scope items (2nd-degree implementation, CSV upload, retry UX) are called out in the Scope section.

**Placeholder scan:** No TBDs. The actor id `apify/linkedin-profile-scraper` in `RealApifyService` is a starting assumption the research spike (Task 1) validates or replaces — documented as "verify in research spike" in the code comment. Not a placeholder, a deliberate default with a documented revision path.

**Type consistency:**
- `ApifyProfilePost` fields are consistent between service (Task 4), task consumer (Task 5), and test fixtures.
- `BackfillStatusResponse` shape matches between schema (Task 6), endpoint (Task 8), frontend interface (Task 11).
- `run_day_one_backfill` signature (`db`, `workspace_id`, `apify`, optional `email`) consistent across Task 5 + Task 9.

**Scope check:** 13 tasks — at the top of the target range. Single slice, no sub-projects needed.

---

## Open Questions (resolve during implementation, not blocking plan start)

- Apify actor selection — Task 1 deliverable. If the research concludes no good actor exists, BLOCK and surface before starting Task 5.
- Connection ordering — `Connection.first_seen_at.desc()` is used as a proxy for "most-recently-active." If Phase 1 populates `last_active_at` reliably, switch to that column for better truncation behavior at 200 connections.
- `backfill_failed_at` column — not added in this plan. If the `failed` state needs persistence (e.g., for retry UX), add a column in a future migration. MVP: failures are transient-in-memory + logged.
- Extension auth-token storage — the content script reads `chrome.storage.local.sonar_token`. Verify Phase 1 extension already stores the JWT there under that key; if the key differs (e.g., `access_token`), update the content script.
- Completion email dashboard URL — hardcoded to `http://localhost:5173/dashboard` for MVP. Swap to an env-based URL when deploy lands.
