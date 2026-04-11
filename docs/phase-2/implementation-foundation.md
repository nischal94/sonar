# Sonar Phase 2 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data model, Ring 1/2 matching logic, and pipeline refactor that the rest of Phase 2 (wizard, dashboard, backfill, Ring 3, digest) will build on.

**Architecture:** Add four new tables (`signals`, `person_signal_summary`, `company_signal_summary`, `trends`) and several columns on `posts`/`workspaces`/`connections`. Refactor `pipeline.py` so the keyword filter becomes a scoring input instead of an early-exit gate. Add `ring1_matcher` (phrase matching) and `ring2_matcher` (pgvector cosine similarity against the new `signals` table). Extend the existing LLM context generator prompt to emit a `themes` field. Roll Phase 1 schema gap fixes (missing `Post.connection_id → connections.id` FK, `connections.mutual_count`) into the Phase 2 migration. Declare `embedding` columns in the Post and CapabilityProfileVersion ORM models (the DB columns already exist from migration 001 but the ORM never declared them, so `Base.metadata.create_all` in tests was missing them — Phase 2 pipeline tests need them). A one-shot script backfills existing `capability_profile_versions.signal_keywords` into the new `signals` table so the migration is production-safe.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (async), Alembic, Postgres + pgvector, OpenAI `text-embedding-3-small` (1536 dim), pytest + pytest-asyncio.

---

## Scope

**In scope:**
- Alembic migration 002 (schema changes)
- New ORM models + additions to existing models
- `ring1_matcher` service (phrase/keyword matching)
- `ring2_matcher` service (pgvector similarity query)
- `context_generator` prompt extension (themes output)
- `scorer` signature update (accept keyword_match_strength input)
- `pipeline.py` refactor (remove keyword filter gate, add Ring 1/2 steps, persist post embedding)
- `backfill_signals_from_keywords.py` one-shot script
- Integration test for end-to-end pipeline

**Out of scope (later Phase 2 plans):**
- Signal configuration wizard backend/frontend (Wizard plan)
- Incremental aggregation task, dashboard endpoints/frontend (Dashboard plan)
- Day-one backfill, extension changes (Backfill plan)
- Ring 3 nightly clustering, weekly digest (Discovery plan)

---

## File Structure

### New files
- `backend/alembic/versions/002_phase2_foundation.py` — schema migration
- `backend/app/models/signal.py` — `Signal` ORM model
- `backend/app/models/person_signal_summary.py` — `PersonSignalSummary` ORM model
- `backend/app/models/company_signal_summary.py` — `CompanySignalSummary` ORM model
- `backend/app/models/trend.py` — `Trend` ORM model
- `backend/app/services/ring1_matcher.py` — keyword-based signal matching
- `backend/app/services/ring2_matcher.py` — vector-similarity-based signal matching
- `backend/scripts/backfill_signals_from_keywords.py` — one-shot data migration
- `backend/tests/test_ring1_matcher.py`
- `backend/tests/test_ring2_matcher.py`
- `backend/tests/test_scorer_phase2.py`
- `backend/tests/test_pipeline_phase2.py`
- `backend/tests/test_context_generator_themes.py`

### Modified files
- `backend/pyproject.toml` — add `pgvector>=0.4.0` dependency (Task 1)
- `backend/app/models/post.py` — add `embedding` column (Task 1) + JSONB additions `ring1_matches`, `ring2_matches`, `themes`, `engagement_counts` (Task 6)
- `backend/app/models/workspace.py` — add `embedding` column on `CapabilityProfileVersion` (Task 1) + `Workspace.backfill_used` (Task 7)
- `backend/app/models/__init__.py` — add `from app.models.<model> import <Model>` for each new Phase 2 model (Tasks 2-5)
- `backend/app/services/context_generator.py` — extend prompt + `AlertContext` with `themes: list[str]` (Task 10)
- `backend/app/services/scorer.py` — accept `keyword_match_strength: float` input (Task 11)
- `backend/app/workers/pipeline.py` — full refactor (Task 12 — biggest change)

Each file has one clear responsibility. Matchers are isolated, services are pure functions that take data and return data, the pipeline orchestrates them, and the models just describe shape.

---

## Test Strategy Note for Implementers

- Backend tests use `pytest` + `pytest-asyncio`. Existing conftest at `backend/tests/conftest.py` provides `db_session` and `test_engine` fixtures that spin up the full schema against a test database. **You do not need to mock the database** — use real postgres with pgvector.
- Tests run with `cd backend && uv run pytest`. A single test is `uv run pytest tests/test_ring1_matcher.py::test_should_match_exact_phrase -v`.
- The test database is `sonar_test` (see `conftest.py:17`). You need postgres running — `docker compose up -d db` from the repo root.
- Follow `test_*` function-style naming consistent with existing tests (see `backend/tests/test_matcher.py` for the reference pattern).
- When a test requires a fresh schema, the `test_engine` fixture calls `Base.metadata.create_all`, which only reflects ORM-declared columns. Phase 1 added two `vector(1536)` columns via raw `op.execute` without declaring them in the ORM, so `create_all` was silently building a test DB that was missing those columns. Task 1 fixes this by installing `pgvector` and declaring `embedding` on the Post and CapabilityProfileVersion models. After Task 1, `create_all` builds the real full schema — including every embedding column — and Phase 2 pipeline tests work against it.
- Each new Phase 2 model must be imported from `backend/app/models/__init__.py` so the SQLAlchemy metadata registry sees it before `create_all` runs. Tasks 2-5 each add their own import line. If you skip this, `create_all` will skip the new tables and every subsequent test will fail with a missing-table error.

---

## Task 1: Alembic migration 002 — schema changes

**Files:**
- Create: `backend/alembic/versions/002_phase2_foundation.py`
- Modify: `backend/pyproject.toml` (add pgvector dependency)
- Modify: `backend/app/models/post.py` (add `embedding` column so `Base.metadata.create_all` in tests builds it — the column already exists in prod via migration 001, but the ORM was never updated)
- Modify: `backend/app/models/workspace.py` (add `embedding` column to `CapabilityProfileVersion` for the same reason)

**Why the model updates are in Task 1:** Phase 1 added `posts.embedding` and `capability_profile_versions.embedding` via raw `op.execute("ALTER TABLE ... vector(1536)")` in migration 001. The ORM models never declared those columns, so `Base.metadata.create_all` (used by `backend/tests/conftest.py:21` to build the test DB) creates those tables *without* the embedding columns. Phase 1 tests got away with this because none of them ran the full pipeline through post embeddings. Phase 2 tests do — so the test DB must have those columns. The fix is to use `pgvector.sqlalchemy.Vector` in the ORM so `create_all` builds the column. Migration 001 does not need to change.

- [ ] **Step 1.0: Add pgvector Python package and update existing ORM models**

Add pgvector to backend dependencies. In `backend/pyproject.toml`, find the `dependencies = [ ... ]` list and add `"pgvector>=0.4.0",` alongside the existing entries (e.g., next to `"numpy>=1.26.0"`).

Then:

```bash
cd backend && uv sync
```

Expected: `pgvector` appears in the resolved dependency tree. No errors.

Update `backend/app/models/post.py` — add the pgvector import and an `embedding` column. This is in addition to the Phase 2 additions that Task 6 will add. Show the final model so Task 6 only needs to layer on top of this:

```python
from sqlalchemy import Column, String, Float, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
import uuid
from app.database import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_post_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True))
    linkedin_post_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    post_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    posted_at = Column(TIMESTAMPTZ)
    ingested_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    relevance_score = Column(Float)
    relationship_score = Column(Float)
    timing_score = Column(Float)
    combined_score = Column(Float)
    matched = Column(Boolean, nullable=False, default=False)
    processed_at = Column(TIMESTAMPTZ)
    extraction_version = Column(String)
    embedding = Column(Vector(1536))
```

Update `backend/app/models/workspace.py` — add the pgvector import and an `embedding` column on `CapabilityProfileVersion`. Append this column after `performance_score`:

```python
# At the top of the file, next to the existing SQLAlchemy imports:
from pgvector.sqlalchemy import Vector

# In the CapabilityProfileVersion class, add after performance_score:
    embedding = Column(Vector(1536))
```

Remove the now-outdated comment `# embedding stored via pgvector — added in migration using Vector type` if it's still present — the column is now declared in the ORM.

Do not commit yet — steps 1.1-1.3 will add the migration and verify the full picture, then step 1.4 commits everything together.

- [ ] **Step 1.1: Write the migration file**

```python
"""Phase 2 foundation: signals, aggregation tables, post columns

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # ── signals ─────────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("example_post", sa.Text()),
        sa.Column("intent_strength", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("embedding", Vector(1536)),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["profile_version_id"], ["capability_profile_versions.id"]),
    )
    op.execute(
        "CREATE INDEX signals_embedding_idx "
        "ON signals USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index(
        "signals_workspace_enabled_idx", "signals", ["workspace_id", "enabled"]
    )

    # ── person_signal_summary ───────────────────────────────────────────
    op.create_table(
        "person_signal_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("trend_direction", sa.String(), nullable=False, server_default="flat"),
        sa.Column("last_signal_at", postgresql.TIMESTAMPTZ()),
        sa.Column("recent_post_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recent_signal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"]),
        sa.ForeignKeyConstraint(["recent_post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["recent_signal_id"], ["signals.id"]),
        sa.UniqueConstraint("workspace_id", "connection_id"),
    )
    op.create_index(
        "person_signal_score_idx",
        "person_signal_summary",
        ["workspace_id", sa.text("aggregate_score DESC")],
    )

    # ── company_signal_summary ──────────────────────────────────────────
    op.create_table(
        "company_signal_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("active_signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "company_name"),
    )
    op.create_index(
        "company_signal_score_idx",
        "company_signal_summary",
        ["workspace_id", sa.text("aggregate_score DESC")],
    )

    # ── trends ──────────────────────────────────────────────────────────
    op.create_table(
        "trends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ring", sa.Integer(), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("cluster_label", sa.Text()),
        sa.Column("cluster_sample_posts", postgresql.JSONB()),
        sa.Column("this_week_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_week_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("velocity_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
    )
    op.create_index(
        "trends_workspace_ring_snapshot_idx",
        "trends",
        ["workspace_id", "ring", sa.text("snapshot_date DESC")],
    )

    # ── posts column additions ──────────────────────────────────────────
    op.add_column("posts", sa.Column("ring1_matches", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("ring2_matches", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("themes", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("engagement_counts", postgresql.JSONB(), server_default="{}"))

    # ── Phase 1 schema gap: posts.connection_id was missing its FK constraint.
    #    Design spec §5.1 says to roll this fix into the Phase 2 migration.
    op.create_foreign_key(
        "posts_connection_id_fkey",
        "posts",
        "connections",
        ["connection_id"],
        ["id"],
    )

    # ── connections column addition (powers 2nd-degree mutual-connection UI later) ──
    op.add_column(
        "connections",
        sa.Column("mutual_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # ── workspaces column addition ──────────────────────────────────────
    op.add_column(
        "workspaces",
        sa.Column("backfill_used", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("workspaces", "backfill_used")
    op.drop_column("connections", "mutual_count")
    op.drop_constraint("posts_connection_id_fkey", "posts", type_="foreignkey")
    op.drop_column("posts", "engagement_counts")
    op.drop_column("posts", "themes")
    op.drop_column("posts", "ring2_matches")
    op.drop_column("posts", "ring1_matches")
    op.drop_index("trends_workspace_ring_snapshot_idx", "trends")
    op.drop_table("trends")
    op.drop_index("company_signal_score_idx", "company_signal_summary")
    op.drop_table("company_signal_summary")
    op.drop_index("person_signal_score_idx", "person_signal_summary")
    op.drop_table("person_signal_summary")
    op.drop_index("signals_workspace_enabled_idx", "signals")
    op.execute("DROP INDEX IF EXISTS signals_embedding_idx")
    op.drop_table("signals")
```

- [ ] **Step 1.2: Run the migration**

```bash
cd backend && uv run alembic upgrade head
```

Expected output: `Running upgrade 001 -> 002, Phase 2 foundation: signals, aggregation tables, post columns`

- [ ] **Step 1.3: Verify the schema**

```bash
cd backend && uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings

async def check():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = :t ORDER BY column_name'), {'t': 'signals'})
        print('signals columns:', sorted(r.scalars().all()))
        r = await conn.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = :t AND column_name LIKE :c'), {'t': 'posts', 'c': 'ring%'})
        print('posts ring columns:', sorted(r.scalars().all()))
    await engine.dispose()

asyncio.run(check())
"
```

Expected to see `signals columns` includes `id, workspace_id, phrase, example_post, intent_strength, enabled, embedding, created_at, updated_at, profile_version_id` and `posts ring columns: ['ring1_matches', 'ring2_matches']`.

- [ ] **Step 1.4: Commit**

```bash
git add backend/alembic/versions/002_phase2_foundation.py \
        backend/pyproject.toml \
        backend/uv.lock \
        backend/app/models/post.py \
        backend/app/models/workspace.py
git commit -m "feat(db): phase 2 foundation schema migration + pgvector ORM support

- Adds migration 002 creating signals, person_signal_summary,
  company_signal_summary, trends tables
- Adds ring1_matches/ring2_matches/themes/engagement_counts to posts
- Adds mutual_count to connections (for 2nd-degree UI in later plan)
- Adds backfill_used to workspaces
- Rolls in Phase 1 schema gap: posts.connection_id FK to connections.id
- Adds pgvector>=0.4.0 dependency and declares embedding columns in
  Post and CapabilityProfileVersion ORM models so Base.metadata.create_all
  builds them in the test database"
```

---

## Task 2: Signal ORM model

**Files:**
- Create: `backend/app/models/signal.py`

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/test_signal_model.py`:

```python
import pytest
import uuid
from sqlalchemy import select
from app.models.signal import Signal
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_signal_row(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test Workspace", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    signal = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="struggling to hire senior engineers",
        example_post="Been interviewing for 3 months and still can't find the right person.",
        intent_strength=0.85,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.commit()

    result = await db_session.execute(
        select(Signal).where(Signal.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.phrase == "struggling to hire senior engineers"
    assert loaded.intent_strength == 0.85
    assert loaded.enabled is True
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_signal_model.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.signal'`

- [ ] **Step 2.3: Implement the model**

Create `backend/app/models/signal.py`:

```python
from sqlalchemy import Column, Float, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from pgvector.sqlalchemy import Vector
import uuid
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    profile_version_id = Column(UUID(as_uuid=True), ForeignKey("capability_profile_versions.id"))
    phrase = Column(Text, nullable=False)
    example_post = Column(Text)
    intent_strength = Column(Float, nullable=False, default=0.7)
    enabled = Column(Boolean, nullable=False, default=True)
    embedding = Column(Vector(1536))
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

Then register the model in `backend/app/models/__init__.py` so `Base.metadata` sees it:

```python
# append to backend/app/models/__init__.py (create the file if empty)
from app.models.signal import Signal  # noqa: F401
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_signal_model.py -v
```

Expected: PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/models/signal.py \
        backend/app/models/__init__.py \
        backend/tests/test_signal_model.py
git commit -m "feat(models): add Signal ORM model with pgvector embedding"
```

---

## Task 3: PersonSignalSummary ORM model

**Files:**
- Create: `backend/app/models/person_signal_summary.py`
- Create: `backend/tests/test_person_signal_summary_model.py`

- [ ] **Step 3.1: Write the failing test**

```python
import pytest
import uuid
from sqlalchemy import select
from app.models.person_signal_summary import PersonSignalSummary
from app.models.workspace import Workspace
from app.models.connection import Connection
from app.models.user import User


@pytest.mark.asyncio
async def test_should_persist_person_signal_summary(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        email="test@example.com",
        hashed_password="hashed",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    conn = Connection(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        linkedin_id="test-person",
        name="Test Person",
        degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    summary = PersonSignalSummary(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        connection_id=conn.id,
        aggregate_score=0.72,
        trend_direction="up",
    )
    db_session.add(summary)
    await db_session.commit()

    result = await db_session.execute(
        select(PersonSignalSummary).where(PersonSignalSummary.connection_id == conn.id)
    )
    loaded = result.scalar_one()
    assert loaded.aggregate_score == 0.72
    assert loaded.trend_direction == "up"
```

- [ ] **Step 3.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_person_signal_summary_model.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3.3: Implement the model**

Create `backend/app/models/person_signal_summary.py`:

```python
from sqlalchemy import Column, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base


class PersonSignalSummary(Base):
    __tablename__ = "person_signal_summary"
    __table_args__ = (UniqueConstraint("workspace_id", "connection_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("connections.id"), nullable=False)
    aggregate_score = Column(Float, nullable=False, default=0.0)
    trend_direction = Column(String, nullable=False, default="flat")
    last_signal_at = Column(TIMESTAMPTZ)
    recent_post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"))
    recent_signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

Then register the model in `backend/app/models/__init__.py`:

```python
# append to backend/app/models/__init__.py
from app.models.person_signal_summary import PersonSignalSummary  # noqa: F401
```

- [ ] **Step 3.4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_person_signal_summary_model.py -v
```

Expected: PASS.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/models/person_signal_summary.py \
        backend/app/models/__init__.py \
        backend/tests/test_person_signal_summary_model.py
git commit -m "feat(models): add PersonSignalSummary ORM model"
```

---

## Task 4: CompanySignalSummary ORM model

**Files:**
- Create: `backend/app/models/company_signal_summary.py`
- Create: `backend/tests/test_company_signal_summary_model.py`

- [ ] **Step 4.1: Write the failing test**

```python
import pytest
import uuid
from sqlalchemy import select
from app.models.company_signal_summary import CompanySignalSummary
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_company_signal_summary(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    summary = CompanySignalSummary(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        company_name="Acme Corp",
        aggregate_score=0.81,
        active_signal_count=3,
    )
    db_session.add(summary)
    await db_session.commit()

    result = await db_session.execute(
        select(CompanySignalSummary).where(
            CompanySignalSummary.workspace_id == workspace.id
        )
    )
    loaded = result.scalar_one()
    assert loaded.company_name == "Acme Corp"
    assert loaded.active_signal_count == 3
```

- [ ] **Step 4.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_company_signal_summary_model.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4.3: Implement the model**

Create `backend/app/models/company_signal_summary.py`:

```python
from sqlalchemy import Column, String, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base


class CompanySignalSummary(Base):
    __tablename__ = "company_signal_summary"
    __table_args__ = (UniqueConstraint("workspace_id", "company_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    company_name = Column(String, nullable=False)
    aggregate_score = Column(Float, nullable=False, default=0.0)
    active_signal_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

Then register the model in `backend/app/models/__init__.py`:

```python
# append to backend/app/models/__init__.py
from app.models.company_signal_summary import CompanySignalSummary  # noqa: F401
```

- [ ] **Step 4.4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_company_signal_summary_model.py -v
```

Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/models/company_signal_summary.py \
        backend/app/models/__init__.py \
        backend/tests/test_company_signal_summary_model.py
git commit -m "feat(models): add CompanySignalSummary ORM model"
```

---

## Task 5: Trend ORM model

**Files:**
- Create: `backend/app/models/trend.py`
- Create: `backend/tests/test_trend_model.py`

- [ ] **Step 5.1: Write the failing test**

```python
import pytest
import uuid
from datetime import date
from sqlalchemy import select
from app.models.trend import Trend
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_should_persist_ring1_trend(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    trend = Trend(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        ring=1,
        signal_id=None,
        this_week_count=12,
        last_week_count=3,
        velocity_delta=9,
        snapshot_date=date.today(),
    )
    db_session.add(trend)
    await db_session.commit()

    result = await db_session.execute(
        select(Trend).where(Trend.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.ring == 1
    assert loaded.velocity_delta == 9


@pytest.mark.asyncio
async def test_should_persist_ring3_trend_with_cluster_label(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test WS 2", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    trend = Trend(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        ring=3,
        cluster_label="migration pain",
        cluster_sample_posts=[{"id": "p1", "text": "our ETL broke"}],
        this_week_count=7,
        last_week_count=1,
        velocity_delta=6,
        snapshot_date=date.today(),
    )
    db_session.add(trend)
    await db_session.commit()

    result = await db_session.execute(
        select(Trend).where(Trend.workspace_id == workspace.id)
    )
    loaded = result.scalar_one()
    assert loaded.ring == 3
    assert loaded.cluster_label == "migration pain"
    assert loaded.cluster_sample_posts[0]["text"] == "our ETL broke"
```

- [ ] **Step 5.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_trend_model.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5.3: Implement the model**

Create `backend/app/models/trend.py`:

```python
from sqlalchemy import Column, Integer, Text, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
import uuid
from app.database import Base


class Trend(Base):
    __tablename__ = "trends"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    ring = Column(Integer, nullable=False)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
    cluster_label = Column(Text)
    cluster_sample_posts = Column(JSONB)
    this_week_count = Column(Integer, nullable=False, default=0)
    last_week_count = Column(Integer, nullable=False, default=0)
    velocity_delta = Column(Integer, nullable=False, default=0)
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

Then register the model in `backend/app/models/__init__.py`:

```python
# append to backend/app/models/__init__.py
from app.models.trend import Trend  # noqa: F401
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_trend_model.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/models/trend.py \
        backend/app/models/__init__.py \
        backend/tests/test_trend_model.py
git commit -m "feat(models): add Trend ORM model"
```

---

## Task 6: Add Phase 2 columns to Post model

**Files:**
- Modify: `backend/app/models/post.py`
- Create: `backend/tests/test_post_model_phase2.py`

- [ ] **Step 6.1: Write the failing test**

```python
import pytest
import uuid
from sqlalchemy import select
from app.models.post import Post
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_post_should_store_ring1_and_ring2_matches(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        linkedin_post_id="lnkd-post-1",
        content="We are struggling to hire senior engineers.",
        post_type="post",
        source="extension",
        ring1_matches=["signal-123"],
        ring2_matches=[{"signal_id": "signal-456", "similarity": 0.82}],
        themes=["engineering hiring", "team scaling"],
        engagement_counts={"likes": 42, "comments": 11, "shares": 3},
    )
    db_session.add(post)
    await db_session.commit()

    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    assert loaded.ring1_matches == ["signal-123"]
    assert loaded.ring2_matches[0]["similarity"] == 0.82
    assert "engineering hiring" in loaded.themes
    assert loaded.engagement_counts["likes"] == 42
```

- [ ] **Step 6.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_post_model_phase2.py -v
```

Expected: FAIL with `TypeError` about unexpected keyword argument `ring1_matches`.

- [ ] **Step 6.3: Update the Post model**

Modify `backend/app/models/post.py` to add the new Phase 2 columns. Task 1 already added the `embedding = Column(Vector(1536))` line and the `pgvector` import; this step layers the JSONB columns on top. Full file contents after this step:

```python
from sqlalchemy import Column, String, Float, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ, JSONB
from pgvector.sqlalchemy import Vector
import uuid
from app.database import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_post_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True))
    linkedin_post_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    post_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    posted_at = Column(TIMESTAMPTZ)
    ingested_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    relevance_score = Column(Float)
    relationship_score = Column(Float)
    timing_score = Column(Float)
    combined_score = Column(Float)
    matched = Column(Boolean, nullable=False, default=False)
    processed_at = Column(TIMESTAMPTZ)
    extraction_version = Column(String)
    embedding = Column(Vector(1536))  # added in Task 1
    # Phase 2 JSONB additions
    ring1_matches = Column(JSONB, default=list)
    ring2_matches = Column(JSONB, default=list)
    themes = Column(JSONB, default=list)
    engagement_counts = Column(JSONB, default=dict)
```

- [ ] **Step 6.4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_post_model_phase2.py -v
```

Expected: PASS.

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/models/post.py backend/tests/test_post_model_phase2.py
git commit -m "feat(models): add Phase 2 columns to Post"
```

---

## Task 7: Add backfill_used column to Workspace model

**Files:**
- Modify: `backend/app/models/workspace.py`

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_workspace_phase2_columns.py`:

```python
import pytest
import uuid
from sqlalchemy import select
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_workspace_default_backfill_used_is_false(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="Test", plan_tier="starter")
    db_session.add(workspace)
    await db_session.commit()

    result = await db_session.execute(select(Workspace).where(Workspace.id == workspace.id))
    loaded = result.scalar_one()
    assert loaded.backfill_used is False


@pytest.mark.asyncio
async def test_workspace_can_set_backfill_used_true(db_session):
    workspace = Workspace(
        id=uuid.uuid4(), name="Test 2", plan_tier="starter", backfill_used=True
    )
    db_session.add(workspace)
    await db_session.commit()

    result = await db_session.execute(select(Workspace).where(Workspace.id == workspace.id))
    loaded = result.scalar_one()
    assert loaded.backfill_used is True
```

- [ ] **Step 7.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_workspace_phase2_columns.py -v
```

Expected: FAIL with `AttributeError` about `backfill_used`.

- [ ] **Step 7.3: Update the Workspace model**

Add one line to `backend/app/models/workspace.py` — after the `created_at` column declaration at line 19, add:

```python
    backfill_used = Column(Boolean, nullable=False, default=False)
```

The final file has `backfill_used` as the last column before `users = relationship(...)`.

- [ ] **Step 7.4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_workspace_phase2_columns.py -v
```

Expected: Both tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/models/workspace.py backend/tests/test_workspace_phase2_columns.py
git commit -m "feat(models): add Workspace.backfill_used for day-one backfill tracking"
```

---

## Task 8: Ring 1 matcher service (keyword/phrase matching)

**Files:**
- Create: `backend/app/services/ring1_matcher.py`
- Create: `backend/tests/test_ring1_matcher.py`

- [ ] **Step 8.1: Write the failing tests**

```python
import pytest
from dataclasses import dataclass
from app.services.ring1_matcher import match_post_to_ring1_signals


@dataclass
class FakeSignal:
    id: str
    phrase: str
    enabled: bool = True


def test_should_match_exact_phrase():
    signals = [FakeSignal(id="s1", phrase="struggling to hire senior engineers")]
    post = "We are struggling to hire senior engineers this quarter."
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s1"]


def test_should_match_case_insensitive():
    signals = [FakeSignal(id="s1", phrase="Series A")]
    post = "Just closed our series a round!"
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s1"]


def test_should_return_multiple_matches():
    signals = [
        FakeSignal(id="s1", phrase="hiring"),
        FakeSignal(id="s2", phrase="engineering"),
    ]
    post = "Hiring across engineering teams."
    result = match_post_to_ring1_signals(post, signals)
    assert set(result) == {"s1", "s2"}


def test_should_skip_disabled_signals():
    signals = [
        FakeSignal(id="s1", phrase="hiring", enabled=False),
        FakeSignal(id="s2", phrase="engineering", enabled=True),
    ]
    post = "Hiring across engineering teams."
    result = match_post_to_ring1_signals(post, signals)
    assert result == ["s2"]


def test_should_return_empty_list_when_no_matches():
    signals = [FakeSignal(id="s1", phrase="quantum computing")]
    post = "We just launched our new coffee blend."
    result = match_post_to_ring1_signals(post, signals)
    assert result == []


def test_should_handle_empty_signal_list():
    result = match_post_to_ring1_signals("any content", [])
    assert result == []
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_ring1_matcher.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ring1_matcher'`.

- [ ] **Step 8.3: Implement the matcher**

Create `backend/app/services/ring1_matcher.py`:

```python
"""Ring 1 matcher — fast literal-phrase matching of a post against configured signals.

Design note: this is intentionally a pure function with no database access or
async dependencies. The caller is responsible for loading the signals. This
keeps the matcher trivially testable and fast enough to run in the hot path
of every ingested post.
"""
from typing import Iterable, Protocol


class SignalLike(Protocol):
    id: object
    phrase: str
    enabled: bool


def match_post_to_ring1_signals(
    post_content: str,
    signals: Iterable[SignalLike],
) -> list[str]:
    """Return the IDs of signals whose phrase appears literally in the post.

    Case-insensitive, substring match. Disabled signals are skipped.
    Returns signal IDs as strings (UUID or str, coerced via str()).
    """
    if not post_content:
        return []

    content_lower = post_content.lower()
    matches: list[str] = []

    for signal in signals:
        if not getattr(signal, "enabled", True):
            continue
        phrase = (signal.phrase or "").strip().lower()
        if not phrase:
            continue
        if phrase in content_lower:
            matches.append(str(signal.id))

    return matches
```

- [ ] **Step 8.4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_ring1_matcher.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 8.5: Commit**

```bash
git add backend/app/services/ring1_matcher.py backend/tests/test_ring1_matcher.py
git commit -m "feat(services): add Ring 1 keyword matcher for post-level signal matching"
```

---

## Task 9: Ring 2 matcher service (pgvector similarity)

**Files:**
- Create: `backend/app/services/ring2_matcher.py`
- Create: `backend/tests/test_ring2_matcher.py`

- [ ] **Step 9.1: Write the failing tests**

```python
import pytest
import uuid
import json
from sqlalchemy import text
from app.models.workspace import Workspace
from app.models.signal import Signal
from app.services.ring2_matcher import match_post_embedding_to_ring2_signals


def _make_embedding(seed: float) -> list[float]:
    """Generate a 1536-dim test embedding seeded to a single value."""
    vec = [seed] * 1536
    # normalize-ish so cosine is meaningful
    return vec


@pytest.mark.asyncio
async def test_should_return_empty_when_no_signals(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter")
    db_session.add(workspace)
    await db_session.commit()

    post_emb = _make_embedding(0.5)
    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, post_emb, cutoff=0.35
    )
    assert result == []


@pytest.mark.asyncio
async def test_should_return_matches_above_cutoff(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS 2", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    # Signal with identical embedding to post -> similarity 1.0 -> distance 0.0
    close_signal = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="close match",
        intent_strength=0.8,
        enabled=True,
    )
    db_session.add(close_signal)
    await db_session.flush()

    # Set embeddings via raw SQL (pgvector)
    emb_vec = _make_embedding(0.5)
    emb_str = "[" + ",".join(str(x) for x in emb_vec) + "]"
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(close_signal.id)},
    )
    await db_session.commit()

    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, emb_vec, cutoff=0.35
    )

    assert len(result) == 1
    assert result[0]["signal_id"] == str(close_signal.id)
    assert result[0]["similarity"] > 0.99


@pytest.mark.asyncio
async def test_should_skip_disabled_signals(db_session):
    workspace = Workspace(id=uuid.uuid4(), name="WS 3", plan_tier="starter")
    db_session.add(workspace)
    await db_session.flush()

    disabled = Signal(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        phrase="disabled",
        intent_strength=0.8,
        enabled=False,
    )
    db_session.add(disabled)
    await db_session.flush()

    emb_vec = _make_embedding(0.5)
    emb_str = "[" + ",".join(str(x) for x in emb_vec) + "]"
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(disabled.id)},
    )
    await db_session.commit()

    result = await match_post_embedding_to_ring2_signals(
        db_session, workspace.id, emb_vec, cutoff=0.35
    )
    assert result == []
```

- [ ] **Step 9.2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_ring2_matcher.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ring2_matcher'`.

- [ ] **Step 9.3: Implement the matcher**

Create `backend/app/services/ring2_matcher.py`:

```python
"""Ring 2 matcher — semantic similarity between a post embedding and the
workspace's active signals via pgvector cosine distance.

Returns a list of {signal_id, similarity} dicts for signals whose cosine
similarity to the post embedding exceeds the cutoff. Similarity is
1 - cosine_distance, converted from pgvector's `<=>` operator.
"""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def match_post_embedding_to_ring2_signals(
    db: AsyncSession,
    workspace_id: UUID,
    post_embedding: list[float],
    cutoff: float = 0.35,
) -> list[dict]:
    """Find signals semantically similar to the given post embedding.

    Args:
        db: active async session
        workspace_id: scope the query to a single workspace
        post_embedding: 1536-dim embedding vector of the post
        cutoff: minimum cosine similarity (0-1). Signals below this are omitted.

    Returns:
        List of dicts: [{"signal_id": "uuid-string", "similarity": 0.87}, ...]
        Sorted by similarity descending.
    """
    if not post_embedding:
        return []

    emb_str = "[" + ",".join(str(x) for x in post_embedding) + "]"

    # pgvector cosine distance operator: <=>  (returns 0 = identical, 2 = opposite)
    # similarity = 1 - distance
    sql = text(
        """
        SELECT
          id::text AS signal_id,
          1 - (embedding <=> CAST(:emb AS vector)) AS similarity
        FROM signals
        WHERE workspace_id = :ws
          AND enabled = TRUE
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> CAST(:emb AS vector)) >= :cutoff
        ORDER BY similarity DESC
        """
    )

    result = await db.execute(
        sql, {"emb": emb_str, "ws": str(workspace_id), "cutoff": cutoff}
    )
    rows = result.mappings().all()

    return [{"signal_id": r["signal_id"], "similarity": float(r["similarity"])} for r in rows]
```

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_ring2_matcher.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 9.5: Commit**

```bash
git add backend/app/services/ring2_matcher.py backend/tests/test_ring2_matcher.py
git commit -m "feat(services): add Ring 2 pgvector similarity matcher"
```

---

## Task 10: Extend context_generator prompt with themes field

**Files:**
- Modify: `backend/app/services/context_generator.py`
- Create: `backend/tests/test_context_generator_themes.py`

- [ ] **Step 10.1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.context_generator import generate_alert_context, AlertContext
from app.services.scorer import Priority


@pytest.mark.asyncio
async def test_alert_context_should_include_themes():
    fake_response = (
        '{"match_reason": "They need data tooling.", '
        '"outreach_draft_a": "Hey — saw your post about pipelines.", '
        '"outreach_draft_b": "Curious: what broke in your stack?", '
        '"opportunity_type": "product_pain", '
        '"urgency_reason": "Active pain right now.", '
        '"themes": ["data pipelines", "migration pain", "tooling gap"]}'
    )

    with patch("app.services.context_generator.openai_provider") as mock_provider:
        mock_provider.complete = AsyncMock(return_value=fake_response)
        context = await generate_alert_context(
            post_content="Our data pipeline broke again.",
            author_name="Alice",
            author_headline="VP Eng at Foo",
            author_company="Foo Inc",
            degree=1,
            enrichment_summary="",
            capability_profile="We sell data tooling.",
            priority=Priority.HIGH,
        )

    assert isinstance(context, AlertContext)
    assert context.themes == ["data pipelines", "migration pain", "tooling gap"]
    assert context.match_reason == "They need data tooling."


@pytest.mark.asyncio
async def test_alert_context_defaults_themes_to_empty_list_when_missing():
    fake_response = (
        '{"match_reason": "They need data tooling.", '
        '"outreach_draft_a": "Hey.", '
        '"outreach_draft_b": "Curious?", '
        '"opportunity_type": "product_pain", '
        '"urgency_reason": "Active."}'
    )

    with patch("app.services.context_generator.openai_provider") as mock_provider:
        mock_provider.complete = AsyncMock(return_value=fake_response)
        context = await generate_alert_context(
            post_content="Our data pipeline broke again.",
            author_name="Alice",
            author_headline="VP Eng",
            author_company="Foo",
            degree=1,
            enrichment_summary="",
            capability_profile="We sell tools.",
            priority=Priority.HIGH,
        )

    assert context.themes == []
```

- [ ] **Step 10.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_context_generator_themes.py -v
```

Expected: FAIL — `AlertContext` has no `themes` field.

- [ ] **Step 10.3: Update context_generator**

Replace the full contents of `backend/app/services/context_generator.py` with:

```python
import json
from dataclasses import dataclass, field
from app.services.llm import openai_provider, groq_provider
from app.services.scorer import Priority

CONTEXT_GENERATION_PROMPT = """
You are a B2B sales intelligence assistant.

COMPANY CAPABILITY PROFILE:
{capability_profile}

LINKEDIN POST:
Author: {author_name}, {author_headline} at {author_company}
Connection degree: {degree}
Company context: {enrichment_summary}
Post content: {post_content}

Return a JSON object with exactly these fields:
- match_reason: 2 sentences max. Why is this post relevant to the company's capabilities? Be specific — reference both the post and what the company does.
- outreach_draft_a: A Direct style LinkedIn message. Max 4 sentences. Reference the specific post. No emojis, no "I hope this finds you well." Sound like a human.
- outreach_draft_b: A Question-led style LinkedIn message. Opens with a curious question about their specific situation. Max 3 sentences.
- opportunity_type: exactly one of: service_need, product_pain, hiring_signal, funding_signal, competitive_mention, general_interest
- urgency_reason: One sentence on why timing matters for this specific signal.
- themes: Array of 3-5 short semantic theme tags describing what this post is about at a concept level. Examples: ["engineering hiring", "team scaling"], ["data pipelines", "ETL", "migration pain"]. These are used for trending topic aggregation, not for the match reason. Keep each theme under 4 words.

Valid JSON only. No preamble, no markdown fences.
"""


@dataclass
class AlertContext:
    match_reason: str
    outreach_draft_a: str
    outreach_draft_b: str
    opportunity_type: str
    urgency_reason: str
    themes: list[str] = field(default_factory=list)


async def generate_alert_context(
    post_content: str,
    author_name: str,
    author_headline: str,
    author_company: str,
    degree: int,
    enrichment_summary: str,
    capability_profile: str,
    priority: Priority,
) -> AlertContext:
    """
    Generate match reason, outreach drafts, and theme tags using LLM.
    Routes to GPT-4o mini for HIGH priority, Groq for MEDIUM/LOW.
    """
    prompt = CONTEXT_GENERATION_PROMPT.format(
        capability_profile=capability_profile,
        author_name=author_name,
        author_headline=author_headline,
        author_company=author_company,
        degree=degree,
        enrichment_summary=enrichment_summary or "No enrichment data available.",
        post_content=post_content[:1000],
    )

    if priority == Priority.HIGH:
        raw = await openai_provider.complete(prompt=prompt, model="gpt-4o-mini")
    else:
        raw = await groq_provider.complete(prompt=prompt, model="llama-3.3-70b-versatile")

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:]).rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"[ContextGenerator] LLM returned unparseable JSON: {exc}. "
            f"Raw (first 200 chars): {raw[:200]}"
        ) from exc

    themes = data.pop("themes", []) or []
    if not isinstance(themes, list):
        themes = []

    try:
        return AlertContext(themes=themes, **data)
    except TypeError as exc:
        raise ValueError(
            f"[ContextGenerator] LLM returned unexpected fields: {exc}. "
            f"Data keys: {list(data.keys())}"
        ) from exc
```

- [ ] **Step 10.4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_context_generator_themes.py -v
```

Expected: Both tests PASS.

- [ ] **Step 10.5: Commit**

```bash
git add backend/app/services/context_generator.py backend/tests/test_context_generator_themes.py
git commit -m "feat(services): extend context_generator prompt with themes output"
```

---

## Task 11: Update scorer to accept keyword match strength as input

**Files:**
- Modify: `backend/app/services/scorer.py`
- Create: `backend/tests/test_scorer_phase2.py`

- [ ] **Step 11.1: Write the failing test**

```python
import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.services.scorer import compute_combined_score, Priority


def _fresh_post_time():
    return datetime.now(timezone.utc) - timedelta(hours=1)


def test_scorer_should_accept_keyword_match_strength_input():
    connection = SimpleNamespace(
        degree=1, relationship_score=0.9, has_interacted=True
    )
    result = compute_combined_score(
        relevance_score=0.75,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=1.0,
    )
    assert isinstance(result.combined_score, float)
    assert 0.0 <= result.combined_score <= 1.0


def test_scorer_boosts_relevance_when_keyword_match_strong():
    connection = SimpleNamespace(
        degree=1, relationship_score=0.9, has_interacted=False
    )
    weak = compute_combined_score(
        relevance_score=0.60,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=0.0,
    )
    strong = compute_combined_score(
        relevance_score=0.60,
        connection=connection,
        posted_at=_fresh_post_time(),
        keyword_match_strength=1.0,
    )
    assert strong.combined_score > weak.combined_score


def test_scorer_keyword_strength_defaults_to_zero_when_not_provided():
    connection = SimpleNamespace(
        degree=2, relationship_score=None, has_interacted=False
    )
    result = compute_combined_score(
        relevance_score=0.50,
        connection=connection,
        posted_at=_fresh_post_time(),
    )
    assert result.combined_score >= 0.0
```

- [ ] **Step 11.2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_scorer_phase2.py -v
```

Expected: FAIL — `keyword_match_strength` is not a parameter of `compute_combined_score`.

- [ ] **Step 11.3: Update the scorer**

Replace `compute_combined_score` in `backend/app/services/scorer.py` with:

```python
def compute_combined_score(
    relevance_score: float,
    connection,
    posted_at: datetime,
    weights: dict | None = None,
    keyword_match_strength: float = 0.0,
) -> ScoringResult:
    """
    Compute 3-dimension combined score for a post+connection pair.

    Dimensions:
      - relevance: semantic match quality (0-1), provided by caller.
        When keyword_match_strength > 0, relevance is boosted by a fraction
        of the keyword match strength to reflect the Ring 1 hit. Capped at 1.0.
      - relationship: warmth of connection (degree + interaction history)
      - timing: urgency decay (linear over 24 hours)

    Args:
      keyword_match_strength: 0.0 (no keyword match) to 1.0 (full match).
        This replaces the old keyword_prefilter hard gate: instead of
        dropping posts that fail the keyword filter, we score all posts
        and let the keyword filter add a boost.
    """
    w = weights or DEFAULT_WEIGHTS

    # Relevance boost from keyword match — up to +0.15
    boosted_relevance = min(1.0, relevance_score + 0.15 * keyword_match_strength)

    # Relationship score
    if connection.relationship_score is not None:
        relationship_score = float(connection.relationship_score)
    else:
        relationship_score = DEGREE_BASE_SCORE.get(connection.degree, 0.15)

    if getattr(connection, "has_interacted", False):
        relationship_score = min(1.0, relationship_score + INTERACTION_BOOST)

    # Timing score — linear decay over 24 hours
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    hours_old = (now - posted_at).total_seconds() / 3600
    timing_score = max(0.0, 1.0 - (hours_old / 24))

    # Combined weighted score
    combined = (
        boosted_relevance   * w["relevance"] +
        relationship_score  * w["relationship"] +
        timing_score        * w["timing"]
    )
    combined = min(1.0, max(0.0, combined))

    if combined >= 0.80:
        priority = Priority.HIGH
    elif combined >= 0.55:
        priority = Priority.MEDIUM
    else:
        priority = Priority.LOW

    return ScoringResult(
        relevance_score=boosted_relevance,
        relationship_score=relationship_score,
        timing_score=timing_score,
        combined_score=combined,
        priority=priority,
    )
```

- [ ] **Step 11.4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_scorer_phase2.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 11.5: Re-run the existing scorer tests to ensure no regressions**

```bash
cd backend && uv run pytest tests/ -v -k scorer
```

Expected: All scorer tests (old and new) pass.

- [ ] **Step 11.6: Commit**

```bash
git add backend/app/services/scorer.py backend/tests/test_scorer_phase2.py
git commit -m "feat(services): accept keyword_match_strength as scorer input, not gate"
```

---

## Task 12: Refactor pipeline.py — keyword filter from gate to input

This is the biggest change. The new pipeline:

1. Embed the post (always — no gate)
2. Run Ring 1 (keyword matching) against active `signals`
3. Run Ring 2 (pgvector similarity) against active `signals`
4. Compute relevance against capability profile embedding
5. Compute `keyword_match_strength` = `len(ring1_matches) / max(len(active_signals), 1)` capped at 1.0
6. Score (scorer now takes `keyword_match_strength`)
7. If `combined_score` passes threshold → generate context → create alert → deliver
8. Persist `posts.embedding`, `posts.ring1_matches`, `posts.ring2_matches`, `posts.themes`

**Files:**
- Modify: `backend/app/workers/pipeline.py`
- Create: `backend/tests/test_pipeline_phase2.py`

- [ ] **Step 12.1: Write the failing integration test**

```python
import pytest
import uuid
from sqlalchemy import text, select
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.user import User
from app.models.connection import Connection
from app.models.post import Post
from app.models.signal import Signal


@pytest.mark.asyncio
async def test_pipeline_persists_embedding_and_ring_matches(db_session, monkeypatch):
    """Integration test: a post with a Ring 1 keyword match flows through
    the refactored pipeline and persists embedding + ring1_matches without
    being dropped by a keyword-filter gate."""
    from app.workers import pipeline as pipeline_module
    from app.services import embedding as emb_module

    # Seed workspace + active profile
    ws = Workspace(id=uuid.uuid4(), name="WS", plan_tier="starter", matching_threshold=0.1)
    db_session.add(ws)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(), workspace_id=ws.id, email="u@t.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=["data pipeline"],
        anti_keywords=[],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    # Raw SQL to set capability_profile_versions.embedding (pgvector)
    dummy_emb = [0.5] * 1536
    emb_str = "[" + ",".join(str(x) for x in dummy_emb) + "]"
    await db_session.execute(
        text("UPDATE capability_profile_versions SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(profile.id)},
    )

    # Signal for Ring 1 match
    signal = Signal(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        profile_version_id=profile.id,
        phrase="data pipeline",
        intent_strength=0.8,
        enabled=True,
    )
    db_session.add(signal)
    await db_session.flush()
    await db_session.execute(
        text("UPDATE signals SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(signal.id)},
    )

    conn = Connection(
        id=uuid.uuid4(), workspace_id=ws.id, user_id=user.id,
        linkedin_id="ln-1", name="Alice", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        connection_id=conn.id,
        linkedin_post_id="ln-p-1",
        content="Our data pipeline broke again and it cost us a day.",
        post_type="post",
        source="extension",
    )
    db_session.add(post)
    await db_session.commit()

    # Monkey-patch the embedding provider to return a deterministic vector
    async def fake_embed(text_in):
        return dummy_emb
    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

    # Monkey-patch context_generator to avoid real LLM calls
    from app.services import context_generator as ctx_mod
    async def fake_ctx(**kwargs):
        return ctx_mod.AlertContext(
            match_reason="test match",
            outreach_draft_a="test a",
            outreach_draft_b="test b",
            opportunity_type="product_pain",
            urgency_reason="test urgency",
            themes=["data tooling"],
        )
    monkeypatch.setattr(ctx_mod, "generate_alert_context", fake_ctx)

    # Monkey-patch DeliveryRouter to be a no-op
    from app.delivery import router as router_mod
    class NoopRouter:
        async def deliver(self, **kwargs): pass
    monkeypatch.setattr(router_mod, "DeliveryRouter", lambda: NoopRouter())

    # Run the pipeline directly (not as celery task)
    await pipeline_module._run_pipeline(post.id, ws.id)

    # Re-fetch post and verify
    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    assert loaded.processed_at is not None
    assert loaded.matched is True
    assert loaded.ring1_matches == [str(signal.id)]
    assert len(loaded.ring2_matches) >= 1
    assert "data tooling" in (loaded.themes or [])
```

- [ ] **Step 12.2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_pipeline_phase2.py -v
```

Expected: FAIL — the current pipeline does not persist `ring1_matches`, `ring2_matches`, or `themes`.

- [ ] **Step 12.3: Refactor the pipeline**

Replace the full contents of `backend/app/workers/pipeline.py`:

```python
import asyncio
from uuid import UUID
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.pipeline.process_post_pipeline", bind=True, max_retries=3)
def process_post_pipeline(self, post_id: str, workspace_id: str):
    """
    Main processing pipeline for a single ingested post.
    Phase 2: no keyword-filter gate. All posts flow through embed →
    Ring 1 (keyword) → Ring 2 (semantic) → scoring → context → alert.
    """
    asyncio.run(_run_pipeline(UUID(post_id), UUID(workspace_id)))


async def _run_pipeline(post_id: UUID, workspace_id: UUID):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, update, text
    from datetime import datetime, timezone
    import json
    from app.config import get_settings
    from app.models.post import Post
    from app.models.connection import Connection
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.signal import Signal
    from app.models.alert import Alert
    from app.models.feedback import SignalEffectiveness
    from app.services.embedding import embedding_provider
    from app.services.matcher import cosine_similarity
    from app.services.ring1_matcher import match_post_to_ring1_signals
    from app.services.ring2_matcher import match_post_embedding_to_ring2_signals
    from app.services.scorer import compute_combined_score
    from app.services.context_generator import generate_alert_context
    from app.services.keyword_filter import DEFAULT_BLOCKLIST
    from app.delivery.router import DeliveryRouter

    engine = create_async_engine(get_settings().database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        post = await db.get(Post, post_id)
        if not post or post.processed_at:
            await engine.dispose()
            return

        result = await db.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active == True)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            await engine.dispose()
            return

        # Hard spam blocklist stays as a pre-check — only posts about birthdays,
        # new jobs, etc. are dropped. This is NOT the keyword filter.
        #
        # Workspace-configured anti_keywords are still honored here so the
        # Phase 1 behavior is preserved — Ring 2 semantic matching should not
        # rescue posts the workspace explicitly told us to ignore.
        content_lower = post.content.lower()
        full_blocklist = DEFAULT_BLOCKLIST + [
            kw.lower() for kw in (profile.anti_keywords or [])
        ]
        if any(term in content_lower for term in full_blocklist):
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        # Stage 1: Embed the post (always)
        post_embedding = await embedding_provider.embed(post.content)

        # Stage 2: Load active signals
        signal_rows = (await db.execute(
            select(Signal).where(
                Signal.workspace_id == workspace_id,
                Signal.enabled == True,
            )
        )).scalars().all()

        # Stage 3: Ring 1 — keyword matches
        ring1_matches = match_post_to_ring1_signals(post.content, signal_rows)

        # Stage 4: Ring 2 — pgvector semantic matches
        ring2_matches = await match_post_embedding_to_ring2_signals(
            db, workspace_id, post_embedding, cutoff=0.35
        )

        # Stage 5: Legacy capability-profile relevance score
        row = await db.execute(
            text("SELECT embedding::text FROM capability_profile_versions WHERE id = :id"),
            {"id": str(profile.id)},
        )
        emb_str = row.scalar_one_or_none()
        capability_embedding = json.loads(emb_str) if emb_str else None

        if capability_embedding is None:
            await engine.dispose()
            return

        relevance_score = cosine_similarity(post_embedding, capability_embedding)

        # Stage 6: Compute keyword_match_strength (0-1)
        active_signal_count = max(len(signal_rows), 1)
        keyword_match_strength = min(1.0, len(ring1_matches) / active_signal_count)

        workspace = await db.get(Workspace, workspace_id)
        connection = await db.get(Connection, post.connection_id)

        # Persist ring matches, themes, embedding immediately — even if we
        # decide below that this post doesn't cross the alert threshold.
        post_emb_str = "[" + ",".join(str(x) for x in post_embedding) + "]"
        await db.execute(
            text("UPDATE posts SET embedding = CAST(:e AS vector) WHERE id = :id"),
            {"e": post_emb_str, "id": str(post_id)},
        )
        await db.execute(
            update(Post).where(Post.id == post_id).values(
                ring1_matches=ring1_matches,
                ring2_matches=ring2_matches,
                relevance_score=relevance_score,
            )
        )

        # Stage 7: Scoring
        if connection is None:
            # Orphan post — can't score relationship dimension, mark processed
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            await engine.dispose()
            return

        scoring = compute_combined_score(
            relevance_score=relevance_score,
            connection=connection,
            posted_at=post.posted_at or post.ingested_at,
            weights=workspace.scoring_weights,
            keyword_match_strength=keyword_match_strength,
        )

        threshold = workspace.matching_threshold or 0.72
        if scoring.combined_score < threshold:
            await db.execute(
                update(Post).where(Post.id == post_id).values(
                    processed_at=datetime.now(timezone.utc),
                    matched=False,
                    relevance_score=scoring.relevance_score,
                    relationship_score=scoring.relationship_score,
                    timing_score=scoring.timing_score,
                    combined_score=scoring.combined_score,
                )
            )
            await db.commit()
            await engine.dispose()
            return

        # Stage 8: Context generation (includes themes)
        context = await generate_alert_context(
            post_content=post.content,
            author_name=connection.name,
            author_headline=connection.headline or "",
            author_company=connection.company or "",
            degree=connection.degree,
            enrichment_summary=str(connection.enrichment_data or ""),
            capability_profile=profile.raw_text,
            priority=scoring.priority,
        )

        # Stage 9: Persist themes + final scores
        await db.execute(
            update(Post).where(Post.id == post_id).values(
                processed_at=datetime.now(timezone.utc),
                matched=True,
                relevance_score=scoring.relevance_score,
                relationship_score=scoring.relationship_score,
                timing_score=scoring.timing_score,
                combined_score=scoring.combined_score,
                themes=context.themes,
            )
        )

        # Stage 10: Create alert
        alert = Alert(
            workspace_id=workspace_id,
            post_id=post_id,
            connection_id=post.connection_id,
            relevance_score=scoring.relevance_score,
            relationship_score=scoring.relationship_score,
            timing_score=scoring.timing_score,
            combined_score=scoring.combined_score,
            priority=scoring.priority.value,
            match_reason=context.match_reason,
            outreach_draft_a=context.outreach_draft_a,
            outreach_draft_b=context.outreach_draft_b,
            opportunity_type=context.opportunity_type,
            urgency_reason=context.urgency_reason,
        )
        db.add(alert)

        effectiveness = SignalEffectiveness(
            workspace_id=workspace_id,
            alert_id=alert.id,
            predicted_score=scoring.combined_score,
        )
        db.add(effectiveness)
        await db.flush()

        await DeliveryRouter().deliver(alert=alert, db=db)
        await db.commit()

    await engine.dispose()
```

- [ ] **Step 12.4: Run the pipeline test to verify it passes**

```bash
cd backend && uv run pytest tests/test_pipeline_phase2.py -v
```

Expected: PASS.

- [ ] **Step 12.5: Run the full test suite to ensure no regressions**

```bash
cd backend && uv run pytest -v
```

Expected: all tests pass. If prior pipeline tests fail because they were asserting the keyword-filter gate behavior, update them to reflect the new "no-gate" behavior (pass-through with lower scores) and commit that fix as part of this task.

- [ ] **Step 12.6: Commit**

```bash
git add backend/app/workers/pipeline.py backend/tests/test_pipeline_phase2.py
git commit -m "refactor(pipeline): promote keyword filter from gate to scoring input

Posts now always flow through embedding, Ring 1 keyword matching, Ring 2
semantic matching, and scoring. Keyword match strength is passed into
the scorer as a relevance boost instead of an early-exit gate. This
unblocks Ring 2's semantic matching value, which would otherwise never
reach the LLM for posts without keyword matches.

Spam blocklist (birthdays, work anniversaries, job changes) is still
pre-checked before embedding to avoid wasted work on obviously
irrelevant content."
```

---

## Task 13: One-shot data backfill script (signal_keywords → signals)

**Files:**
- Create: `backend/scripts/backfill_signals_from_keywords.py`

- [ ] **Step 13.1: Write the script**

```python
"""One-shot backfill: convert existing CapabilityProfileVersion.signal_keywords
into rows in the new signals table.

Run once after migration 002 is applied, before any real Phase 2 traffic.

Usage:
    cd backend && uv run python scripts/backfill_signals_from_keywords.py
"""
import asyncio
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.workspace import CapabilityProfileVersion
from app.models.signal import Signal
from app.services.embedding import embedding_provider


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        result = await db.execute(
            select(CapabilityProfileVersion).where(
                CapabilityProfileVersion.is_active == True
            )
        )
        profiles = result.scalars().all()
        print(f"[backfill] Found {len(profiles)} active capability profiles")

        created = 0
        skipped = 0

        for profile in profiles:
            keywords = profile.signal_keywords or []
            if not keywords:
                skipped += 1
                continue

            # Check if this workspace already has signals — if so, skip
            existing = await db.execute(
                select(Signal).where(Signal.workspace_id == profile.workspace_id).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                print(
                    f"[backfill] workspace {profile.workspace_id} already has "
                    f"signals, skipping"
                )
                skipped += 1
                continue

            for phrase in keywords:
                phrase_stripped = phrase.strip()
                if not phrase_stripped:
                    continue

                embedding = await embedding_provider.embed(phrase_stripped)
                emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

                signal_id = uuid.uuid4()
                await db.execute(
                    text(
                        """
                        INSERT INTO signals
                          (id, workspace_id, profile_version_id, phrase,
                           intent_strength, enabled, embedding, created_at, updated_at)
                        VALUES
                          (:id, :ws, :pv, :phrase, :is_, TRUE,
                           CAST(:emb AS vector), now(), now())
                        """
                    ),
                    {
                        "id": str(signal_id),
                        "ws": str(profile.workspace_id),
                        "pv": str(profile.id),
                        "phrase": phrase_stripped,
                        "is_": 0.7,
                        "emb": emb_str,
                    },
                )
                created += 1
                print(
                    f"[backfill] created signal for workspace "
                    f"{profile.workspace_id}: {phrase_stripped!r}"
                )

        await db.commit()
        print(f"[backfill] done. created={created} skipped_profiles={skipped}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 13.2: Sanity-check the script syntax**

```bash
cd backend && uv run python -c "import ast; ast.parse(open('scripts/backfill_signals_from_keywords.py').read())"
```

Expected: no output (parse succeeds).

- [ ] **Step 13.3: Write a smoke test for the backfill logic**

Create `backend/tests/test_backfill_signals_script.py`:

```python
import pytest
import uuid
from sqlalchemy import select
from unittest.mock import AsyncMock, patch
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.signal import Signal


@pytest.mark.asyncio
async def test_backfill_creates_signals_from_capability_profile_keywords(
    db_session, monkeypatch
):
    """Smoke test: given an active capability profile with signal_keywords,
    the backfill function creates one Signal row per keyword with a stored
    embedding."""
    ws = Workspace(id=uuid.uuid4(), name="WS Backfill", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=["data pipeline", "ETL migration", "ingest bottleneck"],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.commit()

    # Mock the embedding provider so the smoke test doesn't call OpenAI
    fake_embedding = [0.42] * 1536
    from app.services import embedding as emb_module
    monkeypatch.setattr(
        emb_module.embedding_provider,
        "embed",
        AsyncMock(return_value=fake_embedding),
    )

    # Import after monkey-patch so the module uses the patched provider
    from scripts.backfill_signals_from_keywords import main as backfill_main

    # The backfill script creates its own engine/session from settings.
    # For the smoke test we patch create_async_engine to return the test engine.
    from scripts import backfill_signals_from_keywords as backfill_module
    monkeypatch.setattr(
        backfill_module,
        "create_async_engine",
        lambda *args, **kwargs: db_session.bind,
    )
    # Prevent the script from disposing the shared test engine
    monkeypatch.setattr(db_session.bind, "dispose", AsyncMock())

    await backfill_main()

    # Re-query on the same session — signals should now exist for this workspace
    result = await db_session.execute(
        select(Signal).where(Signal.workspace_id == ws.id)
    )
    signals = result.scalars().all()
    phrases = sorted(s.phrase for s in signals)
    assert phrases == ["ETL migration", "data pipeline", "ingest bottleneck"]
```

Run:

```bash
cd backend && uv run pytest tests/test_backfill_signals_script.py -v
```

Expected: PASS. If the patching is tricky (the script owns its own session), it is acceptable to instead refactor `backfill_signals_from_keywords.py` to expose a `async def run(db)` helper that the `main()` wrapper calls with a real session, and test `run(db)` directly. Either approach is fine — the goal is a test that provably exercises the INSERT logic with a mocked embedding provider.

- [ ] **Step 13.4: Run the script against the dev database**

```bash
cd backend && uv run python scripts/backfill_signals_from_keywords.py
```

Expected output: `[backfill] done. created=N skipped_profiles=M` where N and M depend on existing seeded data.

- [ ] **Step 13.5: Verify signals were created**

```bash
cd backend && uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings

async def check():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT count(*) FROM signals'))
        print('signals row count:', r.scalar())
    await engine.dispose()

asyncio.run(check())
"
```

Expected: non-zero count if there were active profiles with `signal_keywords`.

- [ ] **Step 13.6: Commit**

```bash
git add backend/scripts/backfill_signals_from_keywords.py \
        backend/tests/test_backfill_signals_script.py
git commit -m "feat(scripts): add one-shot backfill from signal_keywords to signals table"
```

---

## Task 14: End-to-end smoke test via the full Celery task entry point

**Files:**
- Modify: `backend/tests/test_pipeline_phase2.py` (add one more test)

- [ ] **Step 14.1: Add a smoke test for the non-matched path**

Append to `backend/tests/test_pipeline_phase2.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_does_not_drop_posts_that_miss_keyword_filter(db_session, monkeypatch):
    """Regression test: in Phase 1, posts without any configured keyword
    were dropped at keyword_prefilter. Phase 2 must let these flow through
    the scoring path so Ring 2 semantic matching can still score them."""
    from app.workers import pipeline as pipeline_module
    from app.services import embedding as emb_module

    ws = Workspace(
        id=uuid.uuid4(), name="WS", plan_tier="starter", matching_threshold=0.99
    )
    db_session.add(ws)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(), workspace_id=ws.id, email="u2@t.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=["quantum computing"],  # intentionally won't match
        anti_keywords=[],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    dummy_emb = [0.5] * 1536
    emb_str = "[" + ",".join(str(x) for x in dummy_emb) + "]"
    await db_session.execute(
        text("UPDATE capability_profile_versions SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(profile.id)},
    )

    conn = Connection(
        id=uuid.uuid4(), workspace_id=ws.id, user_id=user.id,
        linkedin_id="ln-2", name="Bob", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        connection_id=conn.id,
        linkedin_post_id="ln-p-2",
        content="Our marketing funnel is leaking prospects like crazy.",
        post_type="post",
        source="extension",
    )
    db_session.add(post)
    await db_session.commit()

    async def fake_embed(text_in):
        return dummy_emb
    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

    await pipeline_module._run_pipeline(post.id, ws.id)

    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    # The post MUST be processed (not left as None), and must have
    # an embedding and relevance score even though it wasn't matched.
    assert loaded.processed_at is not None
    assert loaded.relevance_score is not None
    assert loaded.ring1_matches == []  # no Ring 1 signal match
    # Post should be marked not-matched because score < 0.99 threshold
    assert loaded.matched is False
```

- [ ] **Step 14.2: Add a regression test for workspace `anti_keywords`**

Append to `backend/tests/test_pipeline_phase2.py`:

```python
@pytest.mark.asyncio
async def test_pipeline_respects_workspace_anti_keywords(db_session, monkeypatch):
    """Regression test for Task 12 refactor: workspace-configured anti_keywords
    must still block ingestion after the keyword-filter gate became a scoring
    input. The spam blocklist check should OR in anti_keywords alongside the
    default blocklist."""
    from app.workers import pipeline as pipeline_module
    from app.services import embedding as emb_module

    ws = Workspace(
        id=uuid.uuid4(), name="WS", plan_tier="starter", matching_threshold=0.1
    )
    db_session.add(ws)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(), workspace_id=ws.id, email="u3@t.com",
        hashed_password="x", role="owner",
    )
    db_session.add(user)
    await db_session.flush()

    profile = CapabilityProfileVersion(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        version=1,
        raw_text="We sell data tooling",
        source="manual",
        signal_keywords=[],
        anti_keywords=["NFT", "web3"],
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    dummy_emb = [0.5] * 1536
    emb_str = "[" + ",".join(str(x) for x in dummy_emb) + "]"
    await db_session.execute(
        text("UPDATE capability_profile_versions SET embedding = :e WHERE id = :i"),
        {"e": emb_str, "i": str(profile.id)},
    )

    conn = Connection(
        id=uuid.uuid4(), workspace_id=ws.id, user_id=user.id,
        linkedin_id="ln-3", name="Carol", degree=1,
    )
    db_session.add(conn)
    await db_session.flush()

    post = Post(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        connection_id=conn.id,
        linkedin_post_id="ln-p-3",
        content="Just minted a new NFT collection — join the whitelist!",
        post_type="post",
        source="extension",
    )
    db_session.add(post)
    await db_session.commit()

    async def fake_embed(text_in):
        return dummy_emb
    monkeypatch.setattr(emb_module.embedding_provider, "embed", fake_embed)

    await pipeline_module._run_pipeline(post.id, ws.id)

    result = await db_session.execute(select(Post).where(Post.id == post.id))
    loaded = result.scalar_one()
    # Anti-keyword match: post should be processed but not matched,
    # and no embedding work should have been done (blocklist short-circuits).
    assert loaded.processed_at is not None
    assert loaded.matched is False
    assert loaded.ring1_matches == [] or loaded.ring1_matches is None
```

- [ ] **Step 14.3: Run the full phase 2 pipeline tests**

```bash
cd backend && uv run pytest tests/test_pipeline_phase2.py -v
```

Expected: All tests PASS, including the regression tests from 14.1 and 14.2.

- [ ] **Step 14.4: Run the full backend test suite one last time**

```bash
cd backend && uv run pytest -v
```

Expected: every test passes. No Phase 1 regressions, all new Phase 2 foundation tests green.

- [ ] **Step 14.5: Commit**

```bash
git add backend/tests/test_pipeline_phase2.py
git commit -m "test(pipeline): regression tests for non-keyword-match and anti_keywords paths"
```

---

## Post-implementation verification checklist

Before opening the PR against main, manually verify:

- [ ] `alembic upgrade head` runs cleanly on a fresh database.
- [ ] `alembic downgrade -1` cleanly rolls back migration 002 (schema reverts without errors).
- [ ] `backfill_signals_from_keywords.py` runs without exceptions against the dev database.
- [ ] `uv run pytest` passes with every test green.
- [ ] No new files outside the scope listed in "File Structure" above.
- [ ] Commit messages follow Conventional Commits.
- [ ] No `git rm` or destructive commands were run during this plan.

## Opening the PR

```bash
git push -u origin feat/phase-2-foundation
gh pr create --base main --head feat/phase-2-foundation \
  --title "feat: Phase 2 Foundation — data model, Ring 1/2 matching, pipeline refactor" \
  --body "See docs/phase-2/design.md for design. Implements the Foundation plan at docs/phase-2/implementation-foundation.md."
```

Do not merge without user review.
