# Sonar Phase 3 — Target-Scoped Intent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Ready to execute (design approved through 4 review skills — see `docs/phase-3/design.md` GSTACK REVIEW REPORT).
**Date:** 2026-04-21 (session 10 close)
**Spec:** `docs/phase-3/design.md` (276 lines, post–plan-eng-review + codex + plan-ceo-review + plan-design-review)

**Goal:** Pivot Sonar's ingest from Chrome-extension feed-observation to server-side target-list scraping, while preserving Phase 2.6's Fit × Intent scoring engine unchanged. Ship v3.0 with people-only targets, CRM sync, warm-intro annotations, and tiered cost/cadence controls.

**Architecture:** Introduce a first-class `targets` table (person-typed for v3.0), a Celery beat task that daily-scrapes each workspace's targets via Apify, and a pipeline branch that scores target-sourced posts using Phase 2.6's hybrid scorer. Deprecate the Chrome extension in three stages (coexist → warn → overlay-only) over v3.0–v3.2. Every ingest path stamps `posts.source`. Alert + context + dashboard paths fork on `posts.source` so `target_scrape` alerts stop trying to load a Connection.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic + Celery + Redis + Postgres + pgvector + OpenAI `text-embedding-3-small` + Apify (target scraping) + Salesforce / HubSpot OAuth (CRM sync). Frontend: React 18 + Vite 6 + TypeScript + React Router v6.

---

## Pre-flight — before ANY Phase 3 task starts

These rules come from CLAUDE.md (hardened after the Phase 2.6 Task 1 alembic wipe scar). They are not optional.

1. **Open the session with `/careful`.** The warn rule on DROP TABLE catches destructive alembic ops before execution. First command of the session.

2. **Snapshot the dogfood DB before the first migration lands:**
   ```bash
   mkdir -p snapshots/
   docker compose exec -T postgres pg_dump -U sonar sonar > snapshots/$(date +%Y-%m-%d)-pre-phase-3.sql
   ```
   `snapshots/*.sql` is gitignored (PII). Local safety only. Without this, an accidental destructive command has no recovery path.

3. **NEVER run `alembic downgrade` below `head` against the `sonar` dev DB.** For round-trip tests, override `sqlalchemy.url` inside the test fixture — see `backend/tests/test_migration_008_009_010.py::alembic_cfg` for the canonical pattern.

4. **Codex-review the design doc before writing this plan** — already done, see design doc §9 out-of-band prerequisites. Codex findings are folded into the design doc v3.

5. **Run `/design-consultation` before the FIRST FRONTEND PR.** Produces `docs/DESIGN.md` capturing color tokens, typography, spacing, layout grid. Phase 2.6 shipped ad-hoc; Phase 3 is the time to codify. Not blocking backend tasks (Task 1–8, 12, 14–17), blocking frontend tasks (Task 9–11, 13).

6. **Every backend command runs inside the `api` container.** `docker compose exec -T api <cmd>`. Never `cd backend && uv run ...`.

7. **Each task = its own feature branch + PR.** Branch prefix: `feat/phase-3-<slice>`. Dispatch `superpowers:code-reviewer` before opening every PR; wait for approval before merge. Same discipline as Phase 2.6.

8. **Two-stage review per task (spec compliance + code quality)** when executing via `superpowers:subagent-driven-development`. Same as Phase 2.6.

---

## File Structure

New files (grouped by phase):

```
backend/alembic/versions/
  012_phase_3_enums.py                        # post_source + target_* enums
  013_targets_table.py                        # targets table (Task 1)
  014_posts_source_and_target_id.py           # posts.target_id + posts.source (Task 1)
  014b_loosen_posts_unique.py                 # (wsid, linkedin_post_id, source) (Task 1)
  015_drop_connection_fit_score.py            # post-v3.2 cleanup (Task 18)

backend/app/models/
  target.py                                   # Target ORM model (Task 1)

backend/app/routers/
  targets.py                                  # target CRUD (Task 2)
  crm_sync.py                                 # Salesforce + HubSpot OAuth + pull (Task 12)

backend/app/services/
  target_scraper.py                           # Apify-backed target scraper Protocol (Task 3)
  batch_embedding.py                          # embed_batch helper (Task 4)
  warm_intro.py                               # degree-1 lookup (Task 7)
  crm/
    salesforce.py                             # SF OAuth + Accounts/Contacts pull (Task 12)
    hubspot.py                                # HubSpot OAuth + Deals/Contacts pull (Task 12)
    common.py                                 # CRM Protocol interface (Task 12)
  url_canonicalizer.py                        # LinkedIn URL canon (Task 2)

backend/app/workers/
  scrape_targets_daily.py                     # Celery beat task (Task 5)
  target_signal_aggregator.py                 # target_signal_summary hook (Task 10)
  fit_score_invalidation.py                   # nightly staleness sweep (Task 8)
  post_embedding_retention.py                 # weekly archival task (Task 14)

backend/scripts/
  import_targets_from_csv.py                  # CSV bulk loader (Task 11)
  backfill_targets_from_connections.py        # one-shot connections→targets migration (Task 6b)

backend/tests/
  test_migration_012_013_014.py               # round-trip (Task 1)
  test_target_model.py                        # ORM sanity (Task 1)
  test_targets_router.py                      # CRUD (Task 2)
  test_url_canonicalizer.py                   # canonicalization edge cases (Task 2)
  test_target_scraper.py                      # Apify Protocol + fakes (Task 3)
  test_batch_embedding.py                     # embed_batch helper (Task 4)
  test_scrape_targets_daily.py                # beat task + dispatch offset (Task 5)
  test_pipeline_target_source.py              # branch on posts.source (Task 6)
  test_warm_intro.py                          # degree-1 lookup (Task 7)
  test_fit_score_invalidation.py              # staleness triggers (Task 8)
  test_post_embedding_retention.py            # 90-day archival (Task 14)
  test_tier_gating.py                         # per-tier caps + cadence (Task 15)
  test_crm_salesforce.py                      # SF OAuth + pull (Task 12)
  test_crm_hubspot.py                         # HubSpot OAuth + pull (Task 12)

frontend/src/pages/
  TargetList.tsx                              # target CRUD UI (Task 9)
  SignalConfig.tsx                            # MODIFIED — add step 3 + 4 (Task 9)
  Dashboard.tsx                               # MODIFIED — rebuild target-activity feed (Task 10)
  CrmConnectCallback.tsx                      # OAuth return handler (Task 12)

frontend/src/components/
  TargetList/TargetListTable.tsx              # dense row layout per design §12.4 (Task 9)
  TargetList/TargetActivityRow.tsx            # dashboard row w/ warm-intro annotation (Task 10)
  TargetList/ScrapeHealthBanner.tsx           # workspace-level scrape status (Task 10)
  TargetList/DeprecationBanner.tsx            # extension sunset notice (Task 13)

docs/
  DESIGN.md                                   # produced by /design-consultation (Pre-flight #5)
  phase-3/
    design.md                                 # this phase's design doc (already written)
    implementation.md                         # this file
```

Modified files (Phase 2.6 code):

```
backend/app/workers/pipeline.py               # branch on posts.source (Task 6)
backend/app/models/post.py                    # add target_id, source (Task 1)
backend/app/models/alert.py                   # add target_id, nullable connection_id (Task 6)
backend/app/services/context_generator.py     # polymorphic Connection|Target input (Task 6)
backend/app/models/workspace.py               # add tier, use_target_based_ingest flag (Task 1)
frontend/src/pages/SignalConfig.tsx           # extend to 7 steps (Task 9)
```

---

## Task 1: Migrations 012+013+014+014b + ORM model updates

Bundles the Phase 3 schema additions in one PR. They're additive (except 014b which loosens an existing unique), all needed before any downstream task.

**Files:**
- Create: `backend/alembic/versions/012_phase_3_enums.py`
- Create: `backend/alembic/versions/013_targets_table.py`
- Create: `backend/alembic/versions/014_posts_source_and_target_id.py`
- Create: `backend/alembic/versions/014b_loosen_posts_unique.py`
- Create: `backend/app/models/target.py`
- Modify: `backend/app/models/post.py` — add `target_id`, `source` columns
- Modify: `backend/app/models/alert.py` — add `target_id`, make `connection_id` nullable
- Modify: `backend/app/models/workspace.py` — add `tier`, `use_target_based_ingest` columns
- Test: `backend/tests/test_migration_012_013_014.py`
- Test: `backend/tests/test_target_model.py`

Branch: `feat/phase-3-migrations`

- [ ] **Step 1: Take pre-phase snapshot of dogfood DB**

```bash
mkdir -p snapshots/
docker compose exec -T postgres pg_dump -U sonar sonar > snapshots/$(date +%Y-%m-%d)-pre-phase-3.sql
```

Expected: `snapshots/2026-04-22-pre-phase-3.sql` created (date varies). File is gitignored.

- [ ] **Step 2: Write failing round-trip migration test**

Create `backend/tests/test_migration_012_013_014.py`:

```python
"""Round-trip test: head → 011 → head for Phase 3 schema additions."""
import pytest
from sqlalchemy import text
from alembic import command
from alembic.config import Config

from app.config import get_settings


@pytest.fixture
def alembic_cfg() -> Config:
    """Alembic config pinned to sonar_test per the Phase 2.6 scar."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    base_url = get_settings().database_url.replace("+asyncpg", "")
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    return cfg


def test_phase_3_migrations_round_trip(alembic_cfg: Config):
    """Upgrade head → downgrade 011 → upgrade head. Must not error."""
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "011")
    command.upgrade(alembic_cfg, "head")


def test_targets_table_shape(alembic_cfg: Config, sync_engine):
    command.upgrade(alembic_cfg, "head")
    with sync_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='targets' AND column_name=:c"
        ), {"c": "type"}).fetchone()
        assert row is not None, "targets.type column missing"
        assert row.data_type == "USER-DEFINED"  # target_type enum

        row = conn.execute(text(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name='targets' AND column_name=:c"
        ), {"c": "segment_tags"}).fetchone()
        assert row is not None
        assert row.udt_name == "jsonb"


def test_posts_source_column(alembic_cfg: Config, sync_engine):
    command.upgrade(alembic_cfg, "head")
    with sync_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT column_name, udt_name FROM information_schema.columns "
            "WHERE table_name='posts' AND column_name=:c"
        ), {"c": "source"}).fetchone()
        assert row is not None
        assert row.udt_name == "post_source"


def test_posts_unique_loosened(alembic_cfg: Config, sync_engine):
    """After 014b, unique is (workspace_id, linkedin_post_id, source)."""
    command.upgrade(alembic_cfg, "head")
    with sync_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT conname FROM pg_constraint "
            "WHERE conname = 'posts_workspace_id_linkedin_post_id_source_key'"
        )).fetchone()
        assert row is not None, "3-column unique missing"
```

- [ ] **Step 3: Run — must fail**

```bash
docker compose exec -T api pytest tests/test_migration_012_013_014.py -v
```

Expected: FAIL — migrations don't exist.

- [ ] **Step 4: Write migration 012 (enums)**

Create `backend/alembic/versions/012_phase_3_enums.py`:

```python
"""Phase 3 enum types — post_source, target_type, target_scrape_status, target_scrape_failure_code.

Defined as a separate migration so subsequent migrations 013 + 014 can reference
them. ENUM types live at the schema level; creating them in their own migration
makes up/down predictable.

Revision ID: 012
Revises: 011
Create Date: 2026-04-22
"""

from alembic import op


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE target_type AS ENUM ('person', 'company')")
    op.execute("CREATE TYPE target_scrape_status AS ENUM ('pending', 'active', 'failed', 'paused')")
    op.execute("""
        CREATE TYPE target_scrape_failure_code AS ENUM (
            'rate_limit', 'target_private', 'target_not_found',
            'apify_error', 'network_timeout', 'invalid_url', 'other'
        )
    """)
    op.execute("CREATE TYPE post_source AS ENUM ('extension', 'target_scrape', 'manual_flag')")


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS post_source")
    op.execute("DROP TYPE IF EXISTS target_scrape_failure_code")
    op.execute("DROP TYPE IF EXISTS target_scrape_status")
    op.execute("DROP TYPE IF EXISTS target_type")
```

- [ ] **Step 5: Write migration 013 (targets table)**

Create `backend/alembic/versions/013_targets_table.py`:

```python
"""targets table — Phase 3 primary scoping entity.

See docs/phase-3/design.md §3.4 for semantics. Person-only in v3.0 (see §11.1);
company type exists in schema for forward-compatibility with v3.1.

Revision ID: 013
Revises: 012
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", postgresql.ENUM(name="target_type", create_type=False), nullable=False),
        sa.Column("linkedin_url", sa.Text(), nullable=False),
        sa.Column("linkedin_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("segment_tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_scraped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("identity_changed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scrape_status", postgresql.ENUM(name="target_scrape_status", create_type=False),
                  server_default="pending", nullable=False),
        sa.Column("scrape_failure_code", postgresql.ENUM(name="target_scrape_failure_code", create_type=False), nullable=True),
        sa.Column("scrape_failure_reason", sa.Text(), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=True),
        sa.Column("fit_score_computed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("workspace_id", "linkedin_url", name="targets_workspace_url_unique"),
    )
    op.create_index("idx_targets_workspace_scrape", "targets", ["workspace_id", "scrape_status", "last_scraped_at"])
    op.create_index("idx_targets_fit_stale", "targets", ["workspace_id", "fit_score_computed_at"])


def downgrade() -> None:
    op.drop_index("idx_targets_fit_stale", table_name="targets")
    op.drop_index("idx_targets_workspace_scrape", table_name="targets")
    op.drop_table("targets")
```

- [ ] **Step 6: Write migration 014 (posts.source + posts.target_id)**

Create `backend/alembic/versions/014_posts_source_and_target_id.py`:

```python
"""Add posts.target_id FK + posts.source discriminator.

Ingest provenance: every post stamps its source. Enables the pipeline to branch
on source (target-sourced uses target.fit_score; extension-sourced uses the
legacy connection.fit_score path).

Revision ID: 014
Revises: 013
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column(
        "target_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("targets.id", ondelete="SET NULL"), nullable=True
    ))
    op.add_column("posts", sa.Column(
        "source", postgresql.ENUM(name="post_source", create_type=False),
        server_default="extension", nullable=False
    ))


def downgrade() -> None:
    op.drop_column("posts", "source")
    op.drop_column("posts", "target_id")
```

- [ ] **Step 7: Write migration 014b (loosen posts unique)**

Create `backend/alembic/versions/014b_loosen_posts_unique.py`:

```python
"""Loosen posts unique to (workspace_id, linkedin_post_id, source) for the v3.0–v3.1
coexist window.

The current 2-column unique blocks the same LinkedIn post being captured by
extension AND target_scrape simultaneously (codex adversarial review finding).
Post-v3.2 when extension writes stop, migration 015 restores the tighter
constraint.

Revision ID: 014b
Revises: 014
Create Date: 2026-04-22
"""

from alembic import op


revision = "014b"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("posts_workspace_id_linkedin_post_id_key", "posts", type_="unique")
    op.create_unique_constraint(
        "posts_workspace_id_linkedin_post_id_source_key",
        "posts", ["workspace_id", "linkedin_post_id", "source"]
    )


def downgrade() -> None:
    op.drop_constraint("posts_workspace_id_linkedin_post_id_source_key", "posts", type_="unique")
    op.create_unique_constraint(
        "posts_workspace_id_linkedin_post_id_key",
        "posts", ["workspace_id", "linkedin_post_id"]
    )
```

- [ ] **Step 8: Update ORM models**

Modify `backend/app/models/post.py` — add columns:

```python
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="SET NULL"), nullable=True)
    source = Column(
        ENUM("extension", "target_scrape", "manual_flag", name="post_source", create_type=False),
        nullable=False, default="extension", server_default="extension"
    )
```

Modify `backend/app/models/alert.py` — add target_id, make connection_id nullable:

```python
    connection_id = Column(UUID(as_uuid=True), ForeignKey("connections.id"), nullable=True)  # was nullable=False
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="SET NULL"), nullable=True)
```

Note: the `alerts.connection_id` nullable change was done in Phase 2.6 migration 011 (null for hybrid-mode legacy alerts). Verify — if already nullable, skip that line.

Modify `backend/app/models/workspace.py` — add tier + use_target_based_ingest:

```python
    tier = Column(
        ENUM("free", "starter", "pro", "enterprise", name="workspace_tier", create_type=True),
        nullable=False, default="free", server_default="free"
    )
    use_target_based_ingest = Column(Boolean, nullable=False, default=False, server_default="false")
```

Wait — `workspace_tier` ENUM wasn't created in migration 012. Fix: add to migration 012:

```python
    op.execute("CREATE TYPE workspace_tier AS ENUM ('free', 'starter', 'pro', 'enterprise')")
```

And in downgrade:

```python
    op.execute("DROP TYPE IF EXISTS workspace_tier")
```

- [ ] **Step 9: Create Target ORM model**

Create `backend/app/models/target.py`:

```python
from __future__ import annotations

import uuid

from sqlalchemy import Column, Float, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from app.database import Base
from app.models._types import TIMESTAMPTZ


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_url", name="targets_workspace_url_unique"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    type = Column(ENUM("person", "company", name="target_type", create_type=False), nullable=False)
    linkedin_url = Column(Text, nullable=False)
    linkedin_id = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    headline = Column(Text, nullable=True)
    company = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    segment_tags = Column(JSONB, nullable=False, default=list, server_default="[]")
    added_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    last_scraped_at = Column(TIMESTAMPTZ, nullable=True)
    identity_changed_at = Column(TIMESTAMPTZ, nullable=True)
    scrape_status = Column(
        ENUM("pending", "active", "failed", "paused", name="target_scrape_status", create_type=False),
        nullable=False, default="pending", server_default="pending"
    )
    scrape_failure_code = Column(
        ENUM(name="target_scrape_failure_code", create_type=False), nullable=True
    )
    scrape_failure_reason = Column(Text, nullable=True)
    fit_score = Column(Float, nullable=True)
    fit_score_computed_at = Column(TIMESTAMPTZ, nullable=True)
```

Register in `backend/app/models/__init__.py`:

```python
from app.models.target import Target  # noqa: F401
```

- [ ] **Step 10: Write model-level sanity test**

Create `backend/tests/test_target_model.py`:

```python
"""Target ORM sanity — insert + query + JSONB segment_tags."""
import pytest
from sqlalchemy import select
from uuid import uuid4

from app.models.target import Target
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_target_insert_and_query(db_session):
    ws = Workspace(name="TestWS", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()

    t = Target(
        workspace_id=ws.id,
        type="person",
        linkedin_url="https://linkedin.com/in/jane-doe",
        name="Jane Doe",
        segment_tags=["enterprise", "icp-1"],
    )
    db_session.add(t)
    await db_session.flush()

    row = (await db_session.execute(
        select(Target).where(Target.workspace_id == ws.id)
    )).scalar_one()

    assert row.name == "Jane Doe"
    assert row.type == "person"
    assert row.segment_tags == ["enterprise", "icp-1"]
    assert row.scrape_status == "pending"
    assert row.fit_score is None


@pytest.mark.asyncio
async def test_target_unique_constraint(db_session):
    ws = Workspace(name="TestWS2", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()

    t1 = Target(workspace_id=ws.id, type="person", linkedin_url="https://linkedin.com/in/jane")
    db_session.add(t1)
    await db_session.flush()

    t2 = Target(workspace_id=ws.id, type="person", linkedin_url="https://linkedin.com/in/jane")
    db_session.add(t2)
    with pytest.raises(Exception):  # IntegrityError from unique constraint
        await db_session.flush()
```

- [ ] **Step 11: Run tests — must pass**

```bash
docker compose exec -T api pytest tests/test_migration_012_013_014.py tests/test_target_model.py -v
```

Expected: 5+ passing.

- [ ] **Step 12: Run full suite — must stay green**

```bash
docker compose exec -T api pytest -q
```

Expected: baseline + new = ~193 passing (was 188 at Phase 2.6 close).

- [ ] **Step 13: Commit + PR**

```bash
git checkout -b feat/phase-3-migrations
git add backend/alembic/versions/012_phase_3_enums.py \
        backend/alembic/versions/013_targets_table.py \
        backend/alembic/versions/014_posts_source_and_target_id.py \
        backend/alembic/versions/014b_loosen_posts_unique.py \
        backend/app/models/target.py \
        backend/app/models/post.py \
        backend/app/models/alert.py \
        backend/app/models/workspace.py \
        backend/app/models/__init__.py \
        backend/tests/test_migration_012_013_014.py \
        backend/tests/test_target_model.py
git commit -m "feat(db): Phase 3 migrations 012–014b + Target model

- Migration 012: post_source + target_type + target_scrape_status +
  target_scrape_failure_code + workspace_tier enums
- Migration 013: targets table (person + company type, per §3.4)
- Migration 014: posts.target_id FK + posts.source discriminator
- Migration 014b: loosen (workspace_id, linkedin_post_id) unique to
  include source for v3.0-v3.1 coexist window; migration 015 restores
  tighter constraint post-v3.2
- Target ORM with JSONB segment_tags, identity_changed_at for scrape-
  driven invalidation, fit_score_computed_at for cache freshness
- Post + Alert + Workspace ORM updates

Per Phase 2.6 scar: all round-trip tests pin sqlalchemy.url to
sonar_test. pg_dump snapshot taken before migration ran."
```

Open PR targeting main. Dispatch `superpowers:code-reviewer` first.

---

## Task 2: Target CRUD endpoints + URL canonicalizer

Enables workspaces to insert, list, delete targets. URL canonicalization is a separate service because it's reused by Task 3 (scraper) and Task 11 (CSV import).

**Files:**
- Create: `backend/app/routers/targets.py`
- Create: `backend/app/services/url_canonicalizer.py`
- Test: `backend/tests/test_targets_router.py`
- Test: `backend/tests/test_url_canonicalizer.py`
- Modify: `backend/app/main.py` — register router

Branch: `feat/phase-3-targets-crud`

- [ ] **Step 1: Write failing canonicalizer test**

Create `backend/tests/test_url_canonicalizer.py`:

```python
"""LinkedIn URL canonicalization — dedup works only if identical inputs produce
identical outputs. Phase 3 design §3.1 makes this a hard requirement."""
import pytest
from app.services.url_canonicalizer import canonicalize_linkedin_url, LinkedInURLError


def test_trailing_slash_ignored():
    assert (canonicalize_linkedin_url("https://linkedin.com/in/jane-doe/")
            == canonicalize_linkedin_url("https://linkedin.com/in/jane-doe"))


def test_www_prefix_ignored():
    assert (canonicalize_linkedin_url("https://www.linkedin.com/in/jane-doe")
            == canonicalize_linkedin_url("https://linkedin.com/in/jane-doe"))


def test_query_params_stripped():
    assert (canonicalize_linkedin_url("https://linkedin.com/in/jane-doe?utm_source=x&locale=de_DE")
            == canonicalize_linkedin_url("https://linkedin.com/in/jane-doe"))


def test_mobile_subdomain_normalized():
    assert (canonicalize_linkedin_url("https://m.linkedin.com/in/jane-doe")
            == canonicalize_linkedin_url("https://linkedin.com/in/jane-doe"))


def test_company_path():
    assert (canonicalize_linkedin_url("https://linkedin.com/company/acme/")
            == "https://linkedin.com/company/acme")


def test_numeric_pub_variant():
    # Legacy /pub/firstname-lastname/ID/ form — rewrite to /in/ if derivable
    result = canonicalize_linkedin_url("https://linkedin.com/pub/jane-doe/12/345/678")
    assert result.startswith("https://linkedin.com/")
    assert "pub/" in result or "in/" in result


def test_rejects_non_linkedin():
    with pytest.raises(LinkedInURLError):
        canonicalize_linkedin_url("https://twitter.com/jane")


def test_rejects_empty():
    with pytest.raises(LinkedInURLError):
        canonicalize_linkedin_url("")


def test_rejects_whitespace_only():
    with pytest.raises(LinkedInURLError):
        canonicalize_linkedin_url("   \n\t ")
```

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T api pytest tests/test_url_canonicalizer.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement canonicalizer**

Create `backend/app/services/url_canonicalizer.py`:

```python
"""Canonicalize LinkedIn URLs to a deterministic form for dedup.

All downstream code (`targets` unique constraint, `target_scrape_1st_degree_cache`
joins, alert→target lookup) depends on identical inputs producing identical
outputs. Edge cases: trailing slashes, www/m subdomains, query params,
locale suffixes, /pub/ legacy paths, /company/ vs /in/.

See docs/phase-3/design.md §3.1.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse


class LinkedInURLError(ValueError):
    """Raised when input is not a valid LinkedIn URL."""


_VALID_PATH_PREFIXES = ("/in/", "/company/", "/pub/", "/school/")


def canonicalize_linkedin_url(raw: str | None) -> str:
    """Return the canonical form: https://linkedin.com/<type>/<slug>, no trailing slash, no query.

    Raises LinkedInURLError on invalid inputs.
    """
    if not raw or not raw.strip():
        raise LinkedInURLError("[url_canonicalizer] empty input")

    url = raw.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "linkedin.com" not in host:
        raise LinkedInURLError(f"[url_canonicalizer] non-LinkedIn host: {host}")

    # Normalize host: drop m./www./ subdomain variants
    host = "linkedin.com"

    # Normalize path: strip trailing slash, validate prefix
    path = parsed.path.rstrip("/")
    if not path or not any(path.startswith(p.rstrip("/")) for p in _VALID_PATH_PREFIXES):
        raise LinkedInURLError(f"[url_canonicalizer] unexpected path shape: {path}")

    # Strip query + fragment
    return urlunparse(("https", host, path, "", "", ""))
```

- [ ] **Step 4: Run test — must pass**

```bash
docker compose exec -T api pytest tests/test_url_canonicalizer.py -v
```

Expected: 9 passing.

- [ ] **Step 5: Write failing targets-router test**

Create `backend/tests/test_targets_router.py`:

```python
"""Targets CRUD endpoint integration tests."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.target import Target


@pytest.mark.asyncio
async def test_create_targets_bulk(client: AsyncClient, db_session, auth_headers, workspace_id):
    resp = await client.post(
        "/workspace/targets",
        json={"urls": [
            "https://linkedin.com/in/jane-doe",
            "https://www.linkedin.com/in/john-smith/",  # canonicalized to same-as-plain
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 2
    assert body["skipped_duplicates"] == 0

    rows = (await db_session.execute(
        select(Target).where(Target.workspace_id == workspace_id)
    )).scalars().all()
    assert len(rows) == 2
    urls = sorted(r.linkedin_url for r in rows)
    assert urls == ["https://linkedin.com/in/jane-doe", "https://linkedin.com/in/john-smith"]


@pytest.mark.asyncio
async def test_create_targets_dedups_within_request(client, auth_headers, workspace_id):
    resp = await client.post(
        "/workspace/targets",
        json={"urls": [
            "https://linkedin.com/in/jane-doe",
            "https://linkedin.com/in/jane-doe/",  # same canonical
            "https://www.linkedin.com/in/jane-doe?utm=foo",  # also same
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1
    assert resp.json()["skipped_duplicates"] == 2


@pytest.mark.asyncio
async def test_create_targets_rejects_invalid_urls(client, auth_headers, workspace_id):
    resp = await client.post(
        "/workspace/targets",
        json={"urls": ["https://twitter.com/jane", "https://linkedin.com/in/good"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert len(body["invalid_urls"]) == 1


@pytest.mark.asyncio
async def test_list_targets(client, auth_headers, workspace_id, seeded_two_targets):
    resp = await client.get("/workspace/targets", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["targets"]) == 2


@pytest.mark.asyncio
async def test_delete_target_auth_scoped(client, auth_headers, another_workspace_target):
    # Target belongs to another workspace; deletion should 404, not 403 (info leak)
    resp = await client.delete(
        f"/workspace/targets/{another_workspace_target}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tier_cap_rejects_over_limit(client, auth_headers, workspace_id, free_tier_workspace):
    """Free tier max 25 targets — 26th insert must fail per §15."""
    # Seed 25 targets, then attempt to add 2 more → expect 1 added, 1 rejected
    urls = [f"https://linkedin.com/in/person-{i}" for i in range(25)]
    await client.post("/workspace/targets", json={"urls": urls}, headers=auth_headers)

    over_limit = [f"https://linkedin.com/in/person-{i}" for i in range(25, 27)]
    resp = await client.post("/workspace/targets", json={"urls": over_limit}, headers=auth_headers)
    body = resp.json()
    assert body["created"] == 0  # all rejected
    assert body["tier_cap_reached"] is True
```

Fixtures needed in `conftest.py`:

```python
@pytest_asyncio.fixture
async def seeded_two_targets(db_session, workspace_id):
    from app.models.target import Target
    for url in ["https://linkedin.com/in/a", "https://linkedin.com/in/b"]:
        db_session.add(Target(workspace_id=workspace_id, type="person", linkedin_url=url))
    await db_session.flush()


@pytest_asyncio.fixture
async def another_workspace_target(db_session):
    from uuid import uuid4
    from app.models.target import Target
    from app.models.workspace import Workspace
    ws = Workspace(name="Other", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()
    t = Target(workspace_id=ws.id, type="person", linkedin_url="https://linkedin.com/in/x")
    db_session.add(t)
    await db_session.flush()
    return t.id


@pytest_asyncio.fixture
async def free_tier_workspace(db_session, workspace_id):
    from sqlalchemy import update
    from app.models.workspace import Workspace
    await db_session.execute(
        update(Workspace).where(Workspace.id == workspace_id).values(tier="free")
    )
    await db_session.flush()
```

- [ ] **Step 6: Run — must fail**

Expected: endpoint doesn't exist.

- [ ] **Step 7: Implement router**

Create `backend/app/routers/targets.py`:

```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.target import Target
from app.models.user import User
from app.models.workspace import Workspace
from app.routers.auth import get_current_user
from app.services.url_canonicalizer import canonicalize_linkedin_url, LinkedInURLError


router = APIRouter(prefix="/workspace/targets", tags=["targets"])


TIER_LIMITS = {"free": 25, "starter": 100, "pro": 500, "enterprise": 100_000}


class CreateTargetsRequest(BaseModel):
    urls: list[str] = Field(..., min_items=1, max_items=2000)


class CreateTargetsResponse(BaseModel):
    created: int
    skipped_duplicates: int
    invalid_urls: list[str]
    tier_cap_reached: bool = False


@router.post("", response_model=CreateTargetsResponse)
async def create_targets(
    body: CreateTargetsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk insert targets. Canonicalizes URLs + dedups against existing rows."""
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == current_user.workspace_id)
    )).scalar_one()

    tier_cap = TIER_LIMITS.get(ws.tier, 25)
    existing_count = (await db.execute(
        select(func.count()).select_from(Target).where(Target.workspace_id == ws.id)
    )).scalar_one()

    if existing_count >= tier_cap:
        return CreateTargetsResponse(
            created=0, skipped_duplicates=0, invalid_urls=[], tier_cap_reached=True
        )

    existing_urls = {
        row[0] for row in (await db.execute(
            select(Target.linkedin_url).where(Target.workspace_id == ws.id)
        )).all()
    }

    canonicalized: dict[str, str] = {}  # canonical_url -> one original input
    invalid: list[str] = []
    for raw in body.urls:
        try:
            canonical = canonicalize_linkedin_url(raw)
            if canonical not in canonicalized:
                canonicalized[canonical] = raw
        except LinkedInURLError:
            invalid.append(raw)

    slots_remaining = tier_cap - existing_count
    to_create: list[str] = []
    skipped = 0
    for canonical in canonicalized:
        if canonical in existing_urls:
            skipped += 1
            continue
        if len(to_create) >= slots_remaining:
            break
        to_create.append(canonical)

    for url in to_create:
        target_type = "company" if "/company/" in url else "person"
        db.add(Target(workspace_id=ws.id, type=target_type, linkedin_url=url))
    await db.commit()

    return CreateTargetsResponse(
        created=len(to_create),
        skipped_duplicates=skipped,
        invalid_urls=invalid,
        tier_cap_reached=len(to_create) < len(canonicalized) - skipped,
    )


class TargetRow(BaseModel):
    id: UUID
    type: str
    linkedin_url: str
    name: str | None
    headline: str | None
    company: str | None
    fit_score: float | None
    scrape_status: str
    last_scraped_at: str | None
    segment_tags: list[str]


class ListTargetsResponse(BaseModel):
    targets: list[TargetRow]


@router.get("", response_model=ListTargetsResponse)
async def list_targets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 500,
    offset: int = 0,
):
    rows = (await db.execute(
        select(Target)
        .where(Target.workspace_id == current_user.workspace_id)
        .order_by(Target.added_at.desc())
        .limit(min(limit, 2000))
        .offset(offset)
    )).scalars().all()
    return ListTargetsResponse(targets=[
        TargetRow(
            id=r.id, type=r.type, linkedin_url=r.linkedin_url,
            name=r.name, headline=r.headline, company=r.company,
            fit_score=r.fit_score, scrape_status=r.scrape_status,
            last_scraped_at=r.last_scraped_at.isoformat() if r.last_scraped_at else None,
            segment_tags=r.segment_tags or [],
        ) for r in rows
    ])


@router.delete("/{target_id}")
async def delete_target(
    target_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(Target).where(
            Target.id == target_id,
            Target.workspace_id == current_user.workspace_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(404, "target not found")
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 8: Register router in `app/main.py`:**

```python
from app.routers import targets
app.include_router(targets.router)
```

- [ ] **Step 9: Run tests — must pass**

```bash
docker compose exec -T api pytest tests/test_targets_router.py tests/test_url_canonicalizer.py -v
```

- [ ] **Step 10: Commit + PR**

```bash
git checkout -b feat/phase-3-targets-crud
git add backend/app/routers/targets.py backend/app/services/url_canonicalizer.py \
        backend/app/main.py backend/tests/test_targets_router.py \
        backend/tests/test_url_canonicalizer.py backend/tests/conftest.py
git commit -m "feat(targets): add CRUD endpoints + URL canonicalizer

POST /workspace/targets (bulk insert with dedup via canonical URL)
GET  /workspace/targets (paginated list)
DELETE /workspace/targets/{id} (auth-scoped to workspace)

Canonicalization handles: trailing slashes, www/m subdomains, query
params, /in/, /company/, /pub/, /school/ path variants. Per §3.1 of
design doc, identical inputs must produce identical canonical output
or targets dedup silently fails.

Tier caps enforced per workspace.tier (free=25, starter=100, pro=500,
enterprise=unlimited). Over-cap requests return tier_cap_reached=true."
```

---

## Task 3: target_scraper service

Apify-backed scraper for person LinkedIn profiles. Protocol pattern matches existing `app/services/apify.py`.

**Files:**
- Create: `backend/app/services/target_scraper.py`
- Test: `backend/tests/test_target_scraper.py`

Branch: `feat/phase-3-target-scraper`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_target_scraper.py`:

```python
"""Target scraper Protocol + fakes + real Apify call shape."""
import pytest
from app.services.target_scraper import (
    TargetScraper, FakeTargetScraper, scrape_person_profile,
    TargetScrapeResult, TargetScrapeFailure,
)


class StubScraper:
    """Minimal stub implementing TargetScraper Protocol."""
    async def scrape_person(self, linkedin_url: str) -> TargetScrapeResult:
        return TargetScrapeResult(
            name="Jane Doe",
            headline="Head of Growth at Acme",
            company="Acme Corp",
            posts=[{
                "linkedin_post_id": "urn:li:activity:123",
                "content": "Looking at CDPs for our D2C stack",
                "posted_at": "2026-04-20T10:00:00Z",
            }],
        )


@pytest.mark.asyncio
async def test_scraper_protocol_returns_posts():
    scraper = StubScraper()
    result = await scraper.scrape_person("https://linkedin.com/in/jane")
    assert result.name == "Jane Doe"
    assert len(result.posts) == 1


@pytest.mark.asyncio
async def test_fake_scraper_returns_deterministic_output():
    scraper = FakeTargetScraper(seed="jane")
    r1 = await scraper.scrape_person("https://linkedin.com/in/jane")
    r2 = await scraper.scrape_person("https://linkedin.com/in/jane")
    assert r1.name == r2.name
    assert r1.posts[0]["content"] == r2.posts[0]["content"]


@pytest.mark.asyncio
async def test_scraper_raises_on_private_profile():
    class PrivateScraper:
        async def scrape_person(self, url):
            raise TargetScrapeFailure("target_private", "Profile is private")
    with pytest.raises(TargetScrapeFailure) as exc:
        await PrivateScraper().scrape_person("https://linkedin.com/in/x")
    assert exc.value.code == "target_private"
```

- [ ] **Step 2: Run — must fail**

- [ ] **Step 3: Implement**

Create `backend/app/services/target_scraper.py`:

```python
"""Target scraper — server-side public LinkedIn profile scraping via Apify.

Protocol-based so we can swap Apify for Bright Data / Harvest API / self-hosted
Playwright without touching scoring code. See design doc §3.2.

The real implementation uses Apify's LinkedIn Profile Scraper actor. Scrape
returns 10 most recent public posts by default (design §11.3 lever B).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.apify import apify_client  # existing singleton


class TargetScrapeFailure(Exception):
    """Scrape failed. `code` matches target_scrape_failure_code ENUM."""
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


@dataclass
class TargetScrapeResult:
    name: str | None
    headline: str | None
    company: str | None
    posts: list[dict[str, Any]]        # linkedin_post_id, content, posted_at, engagement_counts
    first_degree_ids: list[str]         # LinkedIn ids of target's 1st-degree connections (for warm-intro)


class TargetScraper(Protocol):
    async def scrape_person(self, linkedin_url: str) -> TargetScrapeResult: ...


class RealApifyTargetScraper:
    """Production impl. Calls Apify's LinkedIn Profile Scraper actor."""
    async def scrape_person(self, linkedin_url: str) -> TargetScrapeResult:
        try:
            raw = await apify_client.run_actor(
                actor_id="curious_coder/linkedin-profile-scraper",
                input={
                    "profileUrls": [linkedin_url],
                    "maxPosts": 10,
                    "includeConnections": True,
                },
                timeout_s=90,
            )
        except TimeoutError:
            raise TargetScrapeFailure("network_timeout", "Apify actor timed out")
        except Exception as e:
            raise TargetScrapeFailure("apify_error", str(e))

        if not raw:
            raise TargetScrapeFailure("target_not_found", "Apify returned empty result")
        profile = raw[0] if isinstance(raw, list) else raw

        if profile.get("private"):
            raise TargetScrapeFailure("target_private", "Profile is marked private")

        return TargetScrapeResult(
            name=profile.get("name"),
            headline=profile.get("headline"),
            company=profile.get("currentCompany") or profile.get("company"),
            posts=[
                {
                    "linkedin_post_id": p.get("id") or p.get("urn"),
                    "content": p.get("text", ""),
                    "posted_at": p.get("postedAt"),
                } for p in (profile.get("posts") or []) if p.get("text")
            ],
            first_degree_ids=profile.get("connections1stDegree") or [],
        )


class FakeTargetScraper:
    """Deterministic fake for tests. Seeded by profile slug."""
    def __init__(self, seed: str = "default"):
        self._seed = seed

    async def scrape_person(self, linkedin_url: str) -> TargetScrapeResult:
        slug = linkedin_url.rstrip("/").rsplit("/", 1)[-1]
        return TargetScrapeResult(
            name=f"Fake {slug.title()}",
            headline=f"Test headline for {slug}",
            company=f"TestCo {slug}",
            posts=[{
                "linkedin_post_id": f"urn:li:activity:fake-{slug}-1",
                "content": f"Test post content for {slug}",
                "posted_at": "2026-04-21T10:00:00Z",
            }],
            first_degree_ids=[],
        )


_scraper: TargetScraper | None = None


def get_target_scraper() -> TargetScraper:
    """FastAPI Depends() factory."""
    global _scraper
    if _scraper is None:
        _scraper = RealApifyTargetScraper()
    return _scraper


async def scrape_person_profile(url: str, override: TargetScraper | None = None) -> TargetScrapeResult:
    """Convenience wrapper for call sites that don't use Depends."""
    scraper = override or get_target_scraper()
    return await scraper.scrape_person(url)
```

- [ ] **Step 4: Run — must pass**

- [ ] **Step 5: Commit + PR**

```bash
git checkout -b feat/phase-3-target-scraper
git add backend/app/services/target_scraper.py backend/tests/test_target_scraper.py
git commit -m "feat(services): add target_scraper service (Apify-backed)

Protocol + RealApifyTargetScraper + FakeTargetScraper + get_target_scraper
factory. Mirrors the Protocol-Real-Fake-Factory pattern from apify.py.

Scrape returns name/headline/company + up to 10 recent posts + list of
1st-degree connection ids (for warm-intro lookup in Task 7).

Failures raise TargetScrapeFailure with code matching the
target_scrape_failure_code ENUM (rate_limit, target_private,
target_not_found, apify_error, network_timeout, invalid_url, other)."
```

---

## Task 4: Batch embedding optimization

Required BEFORE Task 5's daily scrape can scale. 10k posts/workspace/day × 1 API call each = 10k calls. Batched at 2048 inputs/call = ~5 calls. 100× win.

**Files:**
- Create: `backend/app/services/batch_embedding.py`
- Modify: `backend/app/services/embedding.py` — add `embed_batch` to Protocol + implementations
- Test: `backend/tests/test_batch_embedding.py`

Branch: `feat/phase-3-batch-embedding`

- [ ] **Step 1: Failing test**

Create `backend/tests/test_batch_embedding.py`:

```python
"""Batch embedding — ~100× cost/latency win vs per-call."""
import pytest
from app.services.batch_embedding import embed_texts_batched


class FakeBatchEmbedder:
    def __init__(self):
        self.call_count = 0
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [[0.1] * 1536 for _ in texts]


@pytest.mark.asyncio
async def test_batch_under_limit_one_call():
    fake = FakeBatchEmbedder()
    texts = [f"t{i}" for i in range(100)]
    vecs = await embed_texts_batched(texts, provider=fake, batch_size=2048)
    assert len(vecs) == 100
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_batch_over_limit_multiple_calls():
    fake = FakeBatchEmbedder()
    texts = [f"t{i}" for i in range(5000)]
    vecs = await embed_texts_batched(texts, provider=fake, batch_size=2048)
    assert len(vecs) == 5000
    assert fake.call_count == 3  # 2048 + 2048 + 904


@pytest.mark.asyncio
async def test_batch_empty_input_returns_empty():
    fake = FakeBatchEmbedder()
    vecs = await embed_texts_batched([], provider=fake, batch_size=2048)
    assert vecs == []
    assert fake.call_count == 0


@pytest.mark.asyncio
async def test_batch_skips_empty_strings():
    fake = FakeBatchEmbedder()
    vecs = await embed_texts_batched(["hi", "", "yo"], provider=fake, batch_size=2048)
    assert len(vecs) == 3
    assert vecs[1] == [0.0] * 1536  # zero vector for empty
```

- [ ] **Step 2: Fail → implement**

Modify `backend/app/services/embedding.py` — extend Protocol:

```python
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

Add to `OpenAIEmbeddingProvider`:

```python
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [t[:8000] for t in texts]
        resp = await self._client.embeddings.create(model=self.model, input=cleaned)
        return [d.embedding for d in resp.data]
```

Create `backend/app/services/batch_embedding.py`:

```python
"""Batch embedding helper — chunks inputs into API-safe batches.

text-embedding-3-small accepts up to 2048 inputs per call. At 10k posts/day
per workspace, this is ~5 API calls instead of 10,000. ~100× cost and latency
win. Required before the daily scrape (Task 5) can scale.
"""
from __future__ import annotations

from app.services.embedding import EmbeddingProvider, get_embedding_provider


async def embed_texts_batched(
    texts: list[str], *, provider: EmbeddingProvider | None = None, batch_size: int = 2048
) -> list[list[float]]:
    if not texts:
        return []
    provider = provider or get_embedding_provider()

    # Preserve input ordering; substitute zero-vector for empty strings
    cleaned: list[tuple[int, str]] = []
    results: list[list[float] | None] = [None] * len(texts)
    for i, t in enumerate(texts):
        if t and t.strip():
            cleaned.append((i, t))
        else:
            results[i] = [0.0] * 1536

    for start in range(0, len(cleaned), batch_size):
        chunk = cleaned[start : start + batch_size]
        vectors = await provider.embed_batch([t for _, t in chunk])
        for (i, _), v in zip(chunk, vectors):
            results[i] = v

    return [r for r in results if r is not None]
```

- [ ] **Step 3: Commit**

---

## Task 5: Daily Celery beat task with staggered dispatch

Per-workspace daily scrape. Staggered by `hash(workspace_id) % 86400` to avoid 00:00 UTC thundering herd.

**Files:**
- Create: `backend/app/workers/scrape_targets_daily.py`
- Modify: `backend/app/workers/celery_app.py` — add beat schedule entry
- Test: `backend/tests/test_scrape_targets_daily.py`

Branch: `feat/phase-3-daily-scrape`

- [ ] **Step 1: Failing test**

Create `backend/tests/test_scrape_targets_daily.py`:

```python
"""Daily scrape task — happy path, partial failure, staggered dispatch."""
import pytest
from uuid import uuid4
from sqlalchemy import select

from app.models.target import Target
from app.models.post import Post
from app.workers.scrape_targets_daily import (
    scrape_workspace_targets, compute_dispatch_offset_seconds,
)


def test_dispatch_offset_is_deterministic():
    wid = uuid4()
    assert compute_dispatch_offset_seconds(wid) == compute_dispatch_offset_seconds(wid)


def test_dispatch_offset_in_24h_range():
    for _ in range(100):
        off = compute_dispatch_offset_seconds(uuid4())
        assert 0 <= off < 86400


@pytest.mark.asyncio
async def test_scrape_workspace_happy_path(db_session, workspace_id, seeded_three_targets, fake_target_scraper):
    summary = await scrape_workspace_targets(
        db_session, workspace_id, scraper_override=fake_target_scraper
    )
    assert summary["scraped"] == 3
    assert summary["failed"] == 0
    assert summary["posts_created"] >= 3

    posts = (await db_session.execute(
        select(Post).where(Post.workspace_id == workspace_id, Post.source == "target_scrape")
    )).scalars().all()
    assert len(posts) >= 3


@pytest.mark.asyncio
async def test_scrape_workspace_partial_failure_persists(db_session, workspace_id, mixed_scraper):
    """Some targets fail; the succeeded ones must still be persisted (batch-commit pattern)."""
    from app.models.target import Target
    for url in ["https://linkedin.com/in/a", "https://linkedin.com/in/fail", "https://linkedin.com/in/b"]:
        db_session.add(Target(workspace_id=workspace_id, type="person", linkedin_url=url))
    await db_session.flush()

    summary = await scrape_workspace_targets(db_session, workspace_id, scraper_override=mixed_scraper)
    assert summary["scraped"] == 2
    assert summary["failed"] == 1

    failed = (await db_session.execute(
        select(Target).where(Target.scrape_status == "failed")
    )).scalar_one()
    assert failed.scrape_failure_code is not None
```

- [ ] **Step 2: Implement**

Create `backend/app/workers/scrape_targets_daily.py`:

```python
"""Daily per-workspace target scrape Celery beat task.

Staggered dispatch: hash(workspace_id) % 86400 offset prevents thundering herd.
Each successful scrape creates Post rows stamped source='target_scrape' and
triggers the pipeline for scoring. Failures set target.scrape_status='failed'
with a scrape_failure_code but do NOT roll back already-scraped siblings (per
Phase 2.6 Task 6 lesson — batch commits).

See docs/phase-3/design.md §3.2.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.post import Post
from app.models.target import Target
from app.models.workspace import Workspace
from app.services.target_scraper import (
    TargetScraper, TargetScrapeFailure, get_target_scraper,
)
from app.workers.celery_app import celery_app


COMMIT_BATCH = 25

# Tier → cadence in days (design §11.3)
CADENCE_DAYS = {"free": 2, "starter": 2, "pro": 1, "enterprise": 1}


def compute_dispatch_offset_seconds(workspace_id: UUID) -> int:
    """Deterministic 0–86399 offset within a 24h window."""
    h = hashlib.md5(str(workspace_id).encode()).hexdigest()
    return int(h[:8], 16) % 86400


async def scrape_workspace_targets(
    db: AsyncSession, workspace_id: UUID, *, scraper_override: TargetScraper | None = None
) -> dict:
    """Scrape all due targets for one workspace. Returns summary."""
    scraper = scraper_override or get_target_scraper()

    ws = (await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )).scalar_one()
    cadence = CADENCE_DAYS.get(ws.tier, 2)
    cutoff = datetime.now(timezone.utc).timestamp() - cadence * 86400

    targets = (await db.execute(
        select(Target).where(
            Target.workspace_id == workspace_id,
            Target.type == "person",  # v3.0 person-only (§11.1)
            Target.scrape_status.in_(["pending", "active"]),
        )
    )).scalars().all()

    scraped = failed = posts_created = 0
    now = datetime.now(timezone.utc)
    for i, t in enumerate(targets, 1):
        if t.last_scraped_at and t.last_scraped_at.timestamp() > cutoff:
            continue
        try:
            result = await scraper.scrape_person(t.linkedin_url)
        except TargetScrapeFailure as e:
            t.scrape_status = "failed"
            t.scrape_failure_code = e.code
            t.scrape_failure_reason = e.detail[:1000]
            failed += 1
            if i % COMMIT_BATCH == 0:
                await db.commit()
            continue

        # Detect identity drift (for fit_score invalidation per Task 8)
        if (t.name and result.name and t.name != result.name) or \
           (t.headline and result.headline and t.headline != result.headline) or \
           (t.company and result.company and t.company != result.company):
            t.identity_changed_at = now
        t.name = result.name or t.name
        t.headline = result.headline or t.headline
        t.company = result.company or t.company
        t.last_scraped_at = now
        t.scrape_status = "active"
        t.scrape_failure_code = None
        t.scrape_failure_reason = None

        # Insert posts (ON CONFLICT DO NOTHING on the 3-col unique)
        for p in result.posts:
            db.add(Post(
                workspace_id=workspace_id,
                connection_id=None,         # target-sourced, no connection
                target_id=t.id,
                linkedin_post_id=p["linkedin_post_id"],
                content=p["content"],
                posted_at=datetime.fromisoformat(p["posted_at"].rstrip("Z")).replace(tzinfo=timezone.utc),
                source="target_scrape",
            ))
            posts_created += 1

        scraped += 1
        if i % COMMIT_BATCH == 0:
            await db.commit()

    await db.commit()
    return {
        "scraped": scraped, "failed": failed, "posts_created": posts_created,
        "total_targets": len(targets),
        "success_ratio": scraped / len(targets) if targets else 1.0,
    }


@celery_app.task(name="app.workers.scrape_targets_daily.run_for_workspace")
def run_for_workspace(workspace_id: str):
    """Celery entry point. Creates its own session because Celery tasks run in
    worker processes separate from FastAPI's request scope."""
    async def _run():
        engine = create_async_engine(get_settings().database_url)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with Session() as db:
                return await scrape_workspace_targets(db, UUID(workspace_id))
        finally:
            await engine.dispose()
    return asyncio.run(_run())


@celery_app.task(name="app.workers.scrape_targets_daily.dispatch_all")
def dispatch_all():
    """Runs every minute via beat. Fans out per-workspace tasks based on their
    staggered offset. Called with high-frequency granularity; each workspace
    actually runs at most once per cadence-period."""
    async def _dispatch():
        engine = create_async_engine(get_settings().database_url)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with Session() as db:
                now = datetime.now(timezone.utc)
                seconds_since_midnight = now.hour * 3600 + now.minute * 60 + now.second
                rows = (await db.execute(
                    select(Workspace.id, Workspace.tier)
                    .where(Workspace.use_target_based_ingest.is_(True))
                )).all()
                for ws_id, _tier in rows:
                    off = compute_dispatch_offset_seconds(ws_id)
                    if abs(seconds_since_midnight - off) < 60:
                        run_for_workspace.delay(str(ws_id))
        finally:
            await engine.dispose()
    asyncio.run(_dispatch())
```

Modify `backend/app/workers/celery_app.py` — register beat schedule:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "phase-3-dispatch-target-scrapes": {
        "task": "app.workers.scrape_targets_daily.dispatch_all",
        "schedule": 60.0,  # every minute
    },
}
```

- [ ] **Step 3: Commit**

---

## Task 6: Pipeline branch on posts.source

Modify `_run_pipeline` to read from `target.fit_score` when `posts.source='target_scrape'` and from `connection.fit_score` (legacy) when `source='extension'`. Alert construction gets the same fork.

**Files:**
- Modify: `backend/app/workers/pipeline.py`
- Modify: `backend/app/services/context_generator.py` — polymorphic Connection|Target
- Test: `backend/tests/test_pipeline_target_source.py`

Branch: `feat/phase-3-pipeline-branch`

- [ ] **Step 1: Failing integration test**

Create `backend/tests/test_pipeline_target_source.py`:

```python
"""Pipeline branches on posts.source — target_scrape uses target.fit_score,
extension uses connection.fit_score (legacy)."""
import pytest
from sqlalchemy import select

from app.models.alert import Alert
from app.models.post import Post


@pytest.mark.asyncio
async def test_target_source_uses_target_fit_score(
    db_session, pipeline_setup_target, monkeypatch_pipeline_deps,
):
    ws_id, post_id, target_id = await pipeline_setup_target(fit_score=0.85, intent_high=True)
    from app.workers.pipeline import _run_pipeline
    await _run_pipeline(post_id, ws_id)

    alert = (await db_session.execute(
        select(Alert).where(Alert.post_id == post_id)
    )).scalar_one_or_none()
    assert alert is not None
    assert alert.target_id == target_id
    assert alert.connection_id is None


@pytest.mark.asyncio
async def test_extension_source_still_uses_connection(
    db_session, pipeline_setup_extension, monkeypatch_pipeline_deps,
):
    ws_id, post_id, conn_id = await pipeline_setup_extension()
    from app.workers.pipeline import _run_pipeline
    await _run_pipeline(post_id, ws_id)

    alert = (await db_session.execute(
        select(Alert).where(Alert.post_id == post_id)
    )).scalar_one_or_none()
    assert alert is not None
    assert alert.connection_id == conn_id
    assert alert.target_id is None
```

Fixtures in `conftest.py`: `pipeline_setup_target` (creates ws + target with fit_score + post with source=target_scrape), `pipeline_setup_extension` (legacy path — ws + connection + post with source=extension). Shape mirrors Phase 2.6 `pipeline_setup` fixture.

- [ ] **Step 2: Modify `_run_pipeline`**

In `backend/app/workers/pipeline.py`, at the post-loading step, add:

```python
        from app.models.target import Target

        if post.source == "target_scrape" and post.target_id is not None:
            target = (await db.execute(
                select(Target).where(Target.id == post.target_id)
            )).scalar_one_or_none()
            connection = None
            source_entity = target
        else:
            connection = await db.get(Connection, post.connection_id)
            target = None
            source_entity = connection
```

Replace references to `connection` with branching on `source_entity` where semantics allow. At scoring time:

```python
        if post.source == "target_scrape":
            cached_fit = target.fit_score if target else None
        else:
            cached_fit = connection.fit_score if connection else None
```

Alert construction block:

```python
        alert = Alert(
            workspace_id=workspace_id,
            post_id=post_id,
            connection_id=connection.id if connection else None,
            target_id=target.id if target else None,
            relevance_score=scoring.relevance_score,
            relationship_score=None if workspace.use_hybrid_scoring or post.source == "target_scrape" else scoring.relationship_score,
            timing_score=scoring.timing_score,
            combined_score=scoring.combined_score,
            priority=scoring.priority.value,
            match_reason=context.match_reason,
            outreach_draft_a=context.outreach_draft_a,
            outreach_draft_b=context.outreach_draft_b,
            opportunity_type=context.opportunity_type,
            urgency_reason=context.urgency_reason,
        )
```

Modify `context_generator.py` to accept either a Connection or a Target by extracting common fields (name, headline, company):

```python
async def generate_alert_context(
    *,
    post_content: str,
    author_name: str,
    author_headline: str,
    author_company: str,
    degree: int | None,  # nullable — None for target-sourced
    enrichment_summary: str,
    capability_profile: str,
    priority,
):
    ...
```

Call site in pipeline passes `degree=None` for target-source:

```python
        context = await generate_alert_context(
            post_content=post.content,
            author_name=source_entity.name or "Unknown",
            author_headline=source_entity.headline or "",
            author_company=source_entity.company or "",
            degree=connection.degree if connection else None,
            ...
        )
```

- [ ] **Step 3: Commit**

---

## Task 7: Warm-intro degree-1 lookup (§11.4b)

Alert-time enrichment: "Warm: 2 · Jane Smith, Raj Patel" when the workspace's existing connections include 1st-degree matches of the target.

**Files:**
- Create: `backend/app/services/warm_intro.py`
- Create: `backend/alembic/versions/016_target_first_degree_cache.py` — new table
- Modify: `backend/app/workers/pipeline.py` — call warm_intro.lookup at alert construction
- Modify: `backend/app/models/alert.py` — add `warm_intro_names` JSONB column
- Test: `backend/tests/test_warm_intro.py`

Branch: `feat/phase-3-warm-intro`

- [ ] **Step 1: Migration 016**

```python
"""target_first_degree_cache — LinkedIn ids of each target's 1st-degree network.

Populated as a side-effect of Apify scrape (Task 5). Looked up at alert time
to annotate with warm-intro connections from the workspace's existing
connections table.

Revision ID: 016
Revises: 014b
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016"
down_revision = "014b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_first_degree_cache",
        sa.Column("target_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("targets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("linkedin_ids", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("refreshed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("alerts", sa.Column("warm_intro_names", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "warm_intro_names")
    op.drop_table("target_first_degree_cache")
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_warm_intro.py`:

```python
"""Warm-intro lookup — returns up to 5 names of workspace connections that
appear in the target's 1st-degree list."""
import pytest
from app.services.warm_intro import lookup_warm_intros


@pytest.mark.asyncio
async def test_returns_connection_names_when_intersection(
    db_session, workspace_id, target_with_cache, seeded_connections_with_mutual_ids,
):
    names = await lookup_warm_intros(db_session, workspace_id, target_with_cache)
    assert "Jane Smith" in names
    assert "Raj Patel" in names
    assert len(names) <= 5


@pytest.mark.asyncio
async def test_returns_empty_when_no_cache(db_session, workspace_id, target_without_cache):
    names = await lookup_warm_intros(db_session, workspace_id, target_without_cache)
    assert names == []


@pytest.mark.asyncio
async def test_fail_open_on_query_error(db_session, workspace_id):
    """If DB query fails, return empty list; warm-intro failure never blocks an alert."""
    names = await lookup_warm_intros(db_session, workspace_id, None)  # type: ignore[arg-type]
    assert names == []
```

- [ ] **Step 3: Implement**

Create `backend/app/services/warm_intro.py`:

```python
"""Warm-intro lookup — cheap alert-time enrichment.

Given a target, intersect its 1st-degree connection list (from Apify scrape)
with the workspace's existing connections table. Returns up to 5 names to
annotate the alert with "Warm: 2 · Jane Smith, Raj Patel". Fail-open (empty
list on any error) so warm-intro lookup never blocks alert delivery.

See docs/phase-3/design.md §11.4b.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def lookup_warm_intros(
    db: AsyncSession, workspace_id: UUID, target_id: UUID | None, limit: int = 5
) -> list[str]:
    if target_id is None:
        return []
    try:
        row = (await db.execute(
            text("SELECT linkedin_ids FROM target_first_degree_cache WHERE target_id = :tid"),
            {"tid": str(target_id)},
        )).scalar_one_or_none()
        if not row:
            return []

        names = (await db.execute(
            text(
                "SELECT name FROM connections "
                "WHERE workspace_id = :ws AND linkedin_id = ANY(:ids) "
                "ORDER BY has_interacted DESC, name ASC LIMIT :lim"
            ),
            {"ws": str(workspace_id), "ids": row, "lim": limit},
        )).scalars().all()
        return list(names)
    except Exception as exc:
        logger.warning("[warm_intro] lookup failed — failing open: %s", exc)
        return []
```

Pipeline call site (in alert-construction section): `alert.warm_intro_names = await lookup_warm_intros(db, workspace_id, post.target_id)`.

- [ ] **Step 4: Commit**

---

## Task 8: fit_score invalidation task

Nightly sweep flags stale targets. Trigger conditions per design §3.4.

**Files:**
- Create: `backend/app/workers/fit_score_invalidation.py`
- Modify: `backend/app/workers/celery_app.py` — beat entry
- Test: `backend/tests/test_fit_score_invalidation.py`

Branch: `feat/phase-3-invalidation`

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_invalidation_clears_fit_score_when_profile_newer(db_session, workspace_id):
    from app.workers.fit_score_invalidation import invalidate_stale_targets
    # ... seed: profile_version updated today, target with fit_score_computed_at yesterday
    # assert target.fit_score set to NULL after invalidate call
```

- [ ] **Step 2: Implement**

```python
async def invalidate_stale_targets(db, workspace_id) -> int:
    """Clear fit_score on targets where the active profile version is newer or
    identity_changed_at is after fit_score_computed_at."""
    result = await db.execute(text("""
        UPDATE targets t SET fit_score = NULL, fit_score_computed_at = NULL
        FROM capability_profile_versions p
        WHERE t.workspace_id = p.workspace_id
          AND p.is_active = TRUE
          AND t.workspace_id = :ws
          AND t.fit_score IS NOT NULL
          AND (
            p.created_at > t.fit_score_computed_at
            OR (t.identity_changed_at IS NOT NULL AND t.identity_changed_at > t.fit_score_computed_at)
          )
    """), {"ws": str(workspace_id)})
    await db.commit()
    return result.rowcount
```

Beat entry (daily at 03:00 UTC per workspace):

```python
"phase-3-invalidate-stale-fit-scores": {
    "task": "app.workers.fit_score_invalidation.run",
    "schedule": crontab(hour=3, minute=0),
},
```

- [ ] **Step 3: Commit**

---

## Task 9: Wizard steps 3 + 4 (target paste + scrape progress)

Frontend. Extends Phase 2.6's 6-step wizard to 7 steps per design §3.5.

**Files:**
- Modify: `frontend/src/pages/SignalConfig.tsx` — add steps 3 + 4 (renumber downstream)
- Create: `frontend/src/components/TargetList/TargetPaste.tsx`
- Create: `frontend/src/components/TargetList/ScrapeProgress.tsx`
- Create: `backend/app/routers/targets_progress.py` — GET /workspace/targets/progress endpoint

Branch: `feat/phase-3-wizard-targets`

**PRE-REQ:** Run `/design-consultation` first if `docs/DESIGN.md` doesn't exist (per Pre-flight #5). The design doc has §12 specs for hierarchy, interaction states, and visual language — the implementation must read from that.

- [ ] **Step 1: Add backend endpoint `/workspace/targets/progress`**

Returns `{scraped: int, total: int, pending: int, failed: int, estimated_completion_at: iso8601 | null}` polled every 3s by the frontend during step 4.

- [ ] **Step 2: Extend SignalConfig.tsx**

Current structure is `Step = 1 | 2 | 3 | 4 | 5 | 6`. Extend to 7:

```tsx
type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7;

// After ICP review (step 3 from Phase 2.6), insert new step 3 = target paste,
// new step 4 = scrape progress, shift old steps 4→5, 5→6, 6→7.

// Actually cleaner sequencing per design §3.5:
// 1. What do you sell (unchanged)
// 2. Review ICP (unchanged)
// 3. Paste target list (NEW)
// 4. Scrape progress (NEW)
// 5. Review generated signals (was step 4)
// 6. Accept/reject (was step 5)
// 7. Save (was step 6)
```

Add `TargetPaste` component for step 3:

```tsx
// frontend/src/components/TargetList/TargetPaste.tsx
import { useState } from "react";
import api from "../../api/client";

interface Props {
  onComplete: (count: number) => void;
}

export function TargetPaste({ onComplete }: Props) {
  const [raw, setRaw] = useState("");
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<{ created: number; skipped: number; invalid: string[] } | null>(null);

  const handleSubmit = async () => {
    const urls = raw.split(/\n/).map((l) => l.trim()).filter(Boolean);
    if (urls.length < 10) {
      alert("Please paste at least 10 LinkedIn URLs");
      return;
    }
    setLoading(true);
    const { data } = await api.post("/workspace/targets", { urls });
    setSummary({ created: data.created, skipped: data.skipped_duplicates, invalid: data.invalid_urls });
    setLoading(false);
    if (data.created > 0) onComplete(data.created);
  };

  return (
    <section>
      <h1>Who do you want to sell to?</h1>
      <p>Paste LinkedIn profile URLs, one per line. 10 minimum; 25–100 typical.</p>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder="https://linkedin.com/in/jane-doe&#10;https://linkedin.com/in/john-smith"
        style={{ width: "100%", minHeight: 200, fontFamily: "monospace" }}
      />
      {summary && (
        <div>
          ✓ {summary.created} added · {summary.skipped} duplicates skipped
          {summary.invalid.length > 0 && <div>✗ {summary.invalid.length} invalid URLs (review above)</div>}
        </div>
      )}
      <button disabled={loading} onClick={handleSubmit}>
        {loading ? "Adding..." : "Start watching these targets"}
      </button>
    </section>
  );
}
```

Add `ScrapeProgress` component for step 4:

```tsx
// frontend/src/components/TargetList/ScrapeProgress.tsx
import { useEffect, useState } from "react";
import api from "../../api/client";

interface Props {
  onComplete: () => void;
}

export function ScrapeProgress({ onComplete }: Props) {
  const [progress, setProgress] = useState({ scraped: 0, total: 0 });
  const [recentTargets, setRecentTargets] = useState<string[]>([]);

  useEffect(() => {
    const poll = async () => {
      const { data } = await api.get("/workspace/targets/progress");
      setProgress({ scraped: data.scraped, total: data.total });
      if (data.recent) setRecentTargets((prev) => [...data.recent, ...prev].slice(0, 20));
      if (data.scraped >= data.total && data.total > 0) {
        onComplete();
      }
    };
    const interval = setInterval(poll, 3000);
    poll();
    return () => clearInterval(interval);
  }, [onComplete]);

  const pct = progress.total > 0 ? (progress.scraped / progress.total) * 100 : 0;
  const etaMin = Math.max(1, Math.round((progress.total - progress.scraped) / 50));

  return (
    <section>
      <h1>{progress.scraped} / {progress.total} scraped</h1>
      <p>~{etaMin} min to first alert</p>
      <progress value={progress.scraped} max={progress.total} />
      <ul style={{ fontFamily: "monospace", fontSize: 13 }}>
        {recentTargets.map((t) => <li key={t}>Scraped: {t}</li>)}
      </ul>
    </section>
  );
}
```

- [ ] **Step 3: Commit**

---

## Task 10: Dashboard redesign — Target Activity feed

Rebuild `Dashboard.tsx` from "Ranked People List" to "Ranked Target Activity" table. Per design §12.4: table layout, not cards.

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/components/TargetList/TargetActivityRow.tsx`
- Create: `frontend/src/components/TargetList/ScrapeHealthBanner.tsx`
- Create: `backend/app/routers/target_dashboard.py` — GET /workspace/dashboard/targets
- Create: `backend/app/workers/target_signal_aggregator.py` — incremental aggregation hook
- Create: `backend/alembic/versions/017_target_signal_summary.py` — new aggregation table
- Modify: `backend/app/workers/pipeline.py` — call aggregator after scoring

Branch: `feat/phase-3-dashboard`

- [ ] **Step 1: Migration 017 — `target_signal_summary` table**

Mirrors `person_signal_summary` shape but keyed on `target_id`.

- [ ] **Step 2: Aggregator hook**

Mirrors `incremental_trending.py::update_person_aggregation` — ~100ms/call budget. Chained at end of pipeline (§Phase 2 incremental aggregation pattern).

- [ ] **Step 3: Dashboard endpoint**

Returns ranked targets with last 7d intent sum + 3 most recent scored posts + warm-intro names.

- [ ] **Step 4: Frontend table**

Table layout per §12.4. Expand-on-click rows. Right-rail segment filters. Red/yellow banner when scrape-health <50% / <80% success ratio in last 24h.

- [ ] **Step 5: Commit**

---

## Task 11: CSV import + `/workspace/targets/csv-upload`

**Files:**
- Create: `backend/app/routers/targets_csv.py`
- Create: `backend/scripts/import_targets_from_csv.py` (operator CLI)
- Test: `backend/tests/test_targets_csv_upload.py`

Branch: `feat/phase-3-csv-import`

Expect `file` multipart with columns: `linkedin_url` (required), `segment_tags` (optional, semicolon-separated).

Returns `{created, skipped_duplicates, invalid_rows: [{row_num, reason}]}`.

---

## Task 12: CRM sync (Salesforce + HubSpot) — §11.4a

Promoted to v3.0 from v3.1 per CEO review.

**Files:**
- Create: `backend/app/routers/crm_sync.py` — OAuth callbacks + sync trigger
- Create: `backend/app/services/crm/common.py` — Protocol
- Create: `backend/app/services/crm/salesforce.py`
- Create: `backend/app/services/crm/hubspot.py`
- Create: `backend/app/workers/crm_sync_daily.py` — Celery beat daily resync
- Create: `backend/alembic/versions/018_crm_connections.py` — store OAuth tokens
- Create: `frontend/src/pages/CrmConnectCallback.tsx`

Branch: `feat/phase-3-crm-sync`

OAuth flow:
1. User clicks "Connect Salesforce" in wizard step 3 or target-list page
2. Backend generates authorization URL, redirects user
3. Salesforce/HubSpot calls back with code
4. Backend exchanges code for tokens, stores encrypted in `crm_connections` table
5. Triggers initial pull: Opportunities filtered by `stage IN ('Qualified', 'Proposal', 'Negotiation')` + their key contacts → bulk-insert as targets via existing `/workspace/targets` endpoint
6. Celery beat daily: pull Opportunity delta since last sync, add new contacts as targets

Per §11.4a: ~2 weeks scope. Salesforce REST API + HubSpot CRM API. `simple-salesforce` and `hubspot-api-client` Python packages.

---

## Task 13: Extension deprecation banner + onboarding skip

**Files:**
- Create: `frontend/src/components/TargetList/DeprecationBanner.tsx`
- Modify: `frontend/src/pages/Onboarding.tsx` — skip-extension option

Branch: `feat/phase-3-extension-deprecation-banner`

v3.0 stage 1 per design §3.7: banner shown on dashboard to extension-installed workspaces. "Passive feed capture is being retired. Paste your target list to migrate." Dismissable per session; weekly email nudge.

---

## Task 14: Post-embedding retention — weekly archival

**Files:**
- Create: `backend/app/workers/post_embedding_retention.py`
- Test: `backend/tests/test_post_embedding_retention.py`

Branch: `feat/phase-3-embedding-retention`

Weekly Celery task nullifies `posts.embedding` for rows older than 90 days. Row + scored metadata retained for alert history. Per §8 success criterion #7.

---

## Task 15: Tier gating — caps + cadence

**Files:**
- Modify: `backend/app/routers/targets.py` — enforce tier cap on POST (partially done in Task 2; verify)
- Modify: `backend/app/workers/scrape_targets_daily.py` — use tier cadence (partially done; verify)
- Create: `backend/tests/test_tier_gating.py`

Branch: `feat/phase-3-tier-gating`

Verify all four levers from §11.3 are implemented: cadence, posts-per-target, dormant auto-throttle (if `last_post_at < now - 30d`, cadence becomes weekly), tier caps.

---

## Task 16: Calibration redo (HARD GATE)

Operational, not pure code. Mirror of Phase 2.6 Task 9.

**Files:**
- Modify: `backend/scripts/calibrate_matching.py` — `analyze-hybrid` subcommand already exists from Phase 2.6; verify it works against target-scraped data
- Create: `eval/calibration/phase-3-target-data-findings.md`

Steps:
1. Hand-label 30 target-scraped posts from Dwao workspace (bootstrap from CRM sync)
2. Hand-label 30 target-scraped posts from CleverTap workspace
3. Run `analyze-hybrid` for both
4. Pick winning λ satisfying DoD (P@5 ≥ 0.6, R@5 ≥ 0.5, zero top-5 competitors) on BOTH
5. Document findings
6. **DO NOT flip flag if DoD fails** — diagnose per design §5 step 8

---

## Task 17: v3.0 launch gate

Flip `workspace.use_target_based_ingest=TRUE` for Dwao + CleverTap after successful onboarding. Monitor for 2 weeks.

```bash
docker compose exec -T postgres psql -U sonar -d sonar -c \
  "UPDATE workspaces SET use_target_based_ingest=TRUE, tier='pro' WHERE id='<dwao_uuid>';"
```

Watch `target_scrape_success_ratio` metric, alert delivery rate, any dashboard regressions.

---

## Task 18: Migration 015 — drop `connections.fit_score`

Post-v3.2, after extension capture is disabled. `targets.fit_score` becomes sole source of truth.

**Files:**
- Create: `backend/alembic/versions/015_drop_connection_fit_score.py`

```python
def upgrade():
    op.drop_column("connections", "fit_score")

def downgrade():
    op.add_column("connections", sa.Column("fit_score", sa.Float(), nullable=True))
```

Branch: `feat/phase-3-drop-connection-fit-score`. Last task of the phase.

---

## Self-review

**Spec coverage (design doc §9 → plan tasks):**
- §9 item 1 (migrations) → Task 1 ✅
- §9 item 2 (target CRUD) → Task 2 ✅
- §9 item 3 (scraper service) → Task 3 ✅
- §9 item 4 (batch embedding) → Task 4 ✅
- §9 item 5 (daily scrape) → Task 5 ✅
- §9 item 6 (pipeline branch) → Task 6 ✅
- §9 item 7 (warm-intro) → Task 7 ✅
- §9 item 8 (invalidation) → Task 8 ✅
- §9 item 9 (wizard steps) → Task 9 ✅
- §9 item 10 (dashboard) → Task 10 ✅
- §9 item 11 (CSV) → Task 11 ✅
- §9 item 12 (CRM sync) → Task 12 ✅
- §9 item 13 (deprecation banner) → Task 13 ✅
- §9 item 14 (retention) → Task 14 ✅
- §9 item 15 (tier gating) → Task 15 ✅
- §9 item 16 (calibration) → Task 16 ✅
- §9 item 17 (launch gate) → Task 17 ✅
- §9 item 18 (migration 015) → Task 18 ✅

**Placeholder scan:** Tasks 10 (dashboard), 11 (CSV), 12 (CRM), 13 (deprecation), 14 (retention), 15 (tier gating) are abbreviated — they have all required structural information (files, branch, approach, expected shape) but don't expand every TDD step into full code. Rationale: these follow patterns already established earlier in the plan (Phase 2.6 + Tasks 1–9 establish the shape), and expanding each to Phase 2.6-level detail would double the file size without adding clarity. An executor using `superpowers:subagent-driven-development` can ask for expansion on any task that needs it.

**Type consistency:** `TargetScrapeResult` in Task 3 → used in Task 5 with matching fields (name, headline, company, posts, first_degree_ids). `compute_dispatch_offset_seconds` in Task 5 → same signature in tests. `canonicalize_linkedin_url` in Task 2 → used in Task 2 routes and Task 11 CSV import. `lookup_warm_intros` in Task 7 → called from Task 6's pipeline modifications.

**Known plan gaps the executor should surface during subagent dispatch:**
- Task 10 `target_signal_summary` schema — mirror `person_signal_summary` structurally; exact column set can be finalized during Task 10 implementation.
- Task 12 CRM token encryption — design doc doesn't mandate a specific approach; `cryptography.fernet` with `SECRET_KEY`-derived key is a sane default.
- Task 13 deprecation banner copy — design doc §3.7 has the messaging; Task 13 puts it in the component.

**Pre-merge gates before first frontend task (9, 10, 11, 13):**
- `/design-consultation` must have produced `docs/DESIGN.md`
- `/plan-design-review` was already run on the design doc; its §12 specs are the implementation spec for the UI tasks

**Operational gates between tasks:**
- After Task 1 lands: run `alembic upgrade head` on dogfood; verify `targets` table empty + no orphan FKs
- After Task 5 lands: run `dispatch_all` manually once against a test workspace with 3 targets; verify posts created + scored
- Before Task 17 (flag flip): Task 16 calibration DoD must pass on BOTH Dwao and CleverTap

---

## Execution handoff

Plan complete and saved to `docs/phase-3/implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — orchestrator dispatches a fresh subagent per task with two-stage review between tasks (spec compliance + code quality). Matches the Phase 2.6 execution pattern.

**2. Inline Execution** — tasks execute in a single session using `superpowers:executing-plans`. Batched with manual checkpoints.

Phase 3 is larger than Phase 2.6 (18 tasks vs. 9, estimated 8–12 weeks vs. 1–2 sessions). Subagent-driven is strongly recommended.

**Before the first task starts:** confirm the Pre-flight checklist is complete:
1. `/careful` on
2. `pg_dump` dogfood DB snapshot
3. `docs/DESIGN.md` created via `/design-consultation` (required for frontend tasks)

Which approach?
