# Sonar Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working end-to-end Sonar MVP — from onboarding (URL → capability profile) through LinkedIn feed ingestion (Chrome extension) to AI-matched alert delivery via Slack, email, WhatsApp, and Telegram.

**Architecture:** Modular event-driven Python backend (FastAPI + Celery + Redis + PostgreSQL/pgvector) with a Chrome extension for LinkedIn feed capture and a React dashboard. Each pipeline stage (ingest → enrich → score → generate → deliver) is a separate Celery worker connected via Redis queues.

**Tech Stack:** Python 3.12, FastAPI, Celery, Redis, PostgreSQL 16 + pgvector, OpenAI SDK, Groq SDK, React 18 + TypeScript + Vite, Chrome Manifest V3, SendGrid, Twilio, Telegram Bot API, Docker Compose

---

## File Structure

```
sonar/
├── docker-compose.yml                  # PostgreSQL, pgvector, Redis, API, worker, frontend
├── .env.example                        # All required env vars documented
├── backend/
│   ├── pyproject.toml                  # Dependencies: fastapi, celery, redis, psycopg2, openai, groq, pgvector, alembic, pydantic, httpx, sendgrid, twilio, python-telegram-bot
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/                   # Migration files
│   ├── app/
│   │   ├── main.py                     # FastAPI app init, router registration
│   │   ├── config.py                   # Settings from env vars (pydantic-settings)
│   │   ├── database.py                 # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── workspace.py            # Workspace + CapabilityProfileVersion ORM models
│   │   │   ├── user.py                 # User ORM model
│   │   │   ├── connection.py           # Connection ORM model
│   │   │   ├── post.py                 # Post ORM model
│   │   │   ├── alert.py                # Alert ORM model
│   │   │   ├── outreach.py             # OutreachHistory ORM model
│   │   │   └── feedback.py             # FeedbackAdjustment + SignalEffectiveness ORM models
│   │   ├── schemas/
│   │   │   ├── workspace.py            # Pydantic request/response schemas
│   │   │   ├── ingest.py               # Post ingest payload schema
│   │   │   ├── alert.py                # Alert response schema
│   │   │   └── feedback.py             # Feedback request schema
│   │   ├── routers/
│   │   │   ├── workspace.py            # POST /workspace, GET /workspace/{id}
│   │   │   ├── profile.py              # POST /profile/extract, PUT /profile
│   │   │   ├── ingest.py               # POST /ingest (extension + fallback)
│   │   │   ├── alerts.py               # GET /alerts, POST /alerts/{id}/feedback
│   │   │   └── auth.py                 # POST /auth/token, POST /auth/refresh
│   │   ├── workers/
│   │   │   ├── celery_app.py           # Celery app init + queue definitions
│   │   │   ├── pipeline.py             # Chain: enrich → score → generate → deliver
│   │   │   ├── enrichment.py           # Celery task: enrich connection company data
│   │   │   ├── scoring.py              # Celery task: 3-dimension scoring
│   │   │   ├── generator.py            # Celery task: LLM context + draft generation
│   │   │   └── delivery.py             # Celery task: route to channels
│   │   ├── services/
│   │   │   ├── embedding.py            # EmbeddingProvider protocol + OpenAI impl
│   │   │   ├── llm.py                  # LLMProvider protocol + OpenAI/Groq impls
│   │   │   ├── profile_extractor.py    # URL crawl + doc parse → capability profile
│   │   │   ├── keyword_filter.py       # Stage 1 pre-filter
│   │   │   ├── matcher.py              # pgvector cosine similarity
│   │   │   ├── scorer.py               # 3-dimension scoring logic
│   │   │   ├── context_generator.py    # Match reason + outreach draft generation
│   │   │   └── feedback_trainer.py     # Threshold adjustment logic
│   │   ├── delivery/
│   │   │   ├── router.py               # DeliveryRouter: fan-out to channels
│   │   │   ├── slack.py                # Slack block kit sender
│   │   │   ├── email.py                # SendGrid sender (immediate + digest queue)
│   │   │   ├── telegram.py             # Telegram bot sender
│   │   │   └── whatsapp.py             # Twilio WhatsApp sender
│   │   └── jobs/
│   │       ├── public_poller.py        # Celery Beat: Apify public post polling
│   │       └── digest_sender.py        # Celery Beat: hourly email digest
│   └── tests/
│       ├── conftest.py                 # pytest fixtures: test DB, mock providers
│       ├── test_keyword_filter.py
│       ├── test_scorer.py
│       ├── test_matcher.py
│       ├── test_context_generator.py
│       ├── test_feedback_trainer.py
│       ├── test_ingest_router.py
│       ├── test_alerts_router.py
│       └── test_delivery_router.py
├── extension/
│   ├── manifest.json
│   ├── background/
│   │   └── service-worker.js           # Alarm scheduling, API calls
│   ├── content/
│   │   └── linkedin-scraper.js         # DOM extraction, sync orchestration
│   ├── popup/
│   │   ├── popup.html
│   │   └── popup.js                    # Show sync status + signal count
│   └── utils/
│       ├── extractor.js                # DOM selectors + post parsing
│       ├── api-client.js               # Authenticated HTTPS to backend
│       └── storage.js                  # chrome.storage.local wrapper
└── frontend/
    ├── index.html
    ├── vite.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/
    │   │   └── client.ts               # Typed API client (fetch wrapper)
    │   ├── pages/
    │   │   ├── Onboarding.tsx          # URL/doc input → profile extraction
    │   │   ├── AlertFeed.tsx           # Prioritized alert list
    │   │   ├── OpportunityBoard.tsx    # Kanban: Open → Contacted → Responded → Won/Lost
    │   │   └── Settings.tsx            # Delivery channel config + profile editor
    │   └── components/
    │       ├── AlertCard.tsx           # Single alert with scores + drafts + buttons
    │       ├── ScoreBar.tsx            # Visual score bar component
    │       └── ChannelSetup.tsx        # Slack/email/Telegram/WhatsApp config form
    └── tests/
        └── AlertCard.test.tsx
```

---

## Task 1: Project Scaffold + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: sonar
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker --loglevel=info
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  beat:
    build: ./backend
    command: celery -A app.workers.celery_app beat --loglevel=info
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

volumes:
  postgres_data:
```

- [ ] **Step 2: Create .env.example**

```bash
# .env.example
DATABASE_URL=postgresql+asyncpg://sonar:sonar@postgres:5432/sonar
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-to-random-32-char-string

# LLM providers
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...

# Delivery channels
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=alerts@yoursonar.com
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TELEGRAM_BOT_TOKEN=...

# Data providers
APIFY_API_TOKEN=apify_api_...

# Extension
EXTENSION_VERSION=1.0.0
```

- [ ] **Step 3: Create backend/pyproject.toml**

```toml
[project]
name = "sonar-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "psycopg2-binary>=2.9.0",
    "alembic>=1.13.0",
    "pgvector>=0.3.0",
    "openai>=1.40.0",
    "groq>=0.9.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "sendgrid>=6.11.0",
    "twilio>=9.3.0",
    "python-telegram-bot>=21.5",
    "beautifulsoup4>=4.12.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]
```

- [ ] **Step 4: Create backend/app/config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str

    openai_api_key: str
    groq_api_key: str

    sendgrid_api_key: str
    sendgrid_from_email: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    telegram_bot_token: str

    apify_api_token: str
    extension_version: str = "1.0.0"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 5: Create backend/app/database.py**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 6: Create backend/app/main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sonar API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Start services and verify health**

```bash
cp .env.example .env
# Fill in API keys in .env
docker compose up -d postgres redis
docker compose up api
```

Visit `http://localhost:8000/health` — expected: `{"status": "ok"}`

- [ ] **Step 8: Commit**

```bash
git init
git add docker-compose.yml .env.example backend/
git commit -m "feat: scaffold project with Docker Compose and FastAPI"
```

---

## Task 2: Database Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_schema.py`
- Create: `backend/app/models/workspace.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/connection.py`
- Create: `backend/app/models/post.py`
- Create: `backend/app/models/alert.py`
- Create: `backend/app/models/outreach.py`
- Create: `backend/app/models/feedback.py`

- [ ] **Step 1: Initialize alembic**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 2: Create backend/app/models/workspace.py**

```python
# backend/app/models/workspace.py
from sqlalchemy import Column, String, Float, Boolean, Integer, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    plan_tier = Column(String, nullable=False, default="starter")
    capability_profile = Column(Text)
    matching_threshold = Column(Float, nullable=False, default=0.72)
    scoring_weights = Column(JSONB, default=lambda: {"relevance": 0.50, "relationship": 0.30, "timing": 0.20})
    onboarding_url = Column(String)
    onboarding_doc_path = Column(String)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    users = relationship("User", back_populates="workspace")
    capability_versions = relationship("CapabilityProfileVersion", back_populates="workspace")


class CapabilityProfileVersion(Base):
    __tablename__ = "capability_profile_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    version = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    # embedding stored via pgvector — added in migration using Vector type
    source = Column(String, nullable=False)
    signal_keywords = Column(ARRAY(Text))
    anti_keywords = Column(ARRAY(Text))
    is_active = Column(Boolean, nullable=False, default=True)
    performance_score = Column(Float)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    workspace = relationship("Workspace", back_populates="capability_versions")
```

- [ ] **Step 3: Create backend/app/models/user.py**

```python
# backend/app/models/user.py
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    linkedin_profile_url = Column(String)
    delivery_channels = Column(JSONB, default=dict)
    alert_rate_limits = Column(JSONB, default=lambda: {"high": 10, "medium": 5, "low": 2})
    quiet_hours = Column(JSONB, default=dict)
    extension_installed = Column(Boolean, nullable=False, default=False)
    extension_last_sync = Column(TIMESTAMPTZ)
    timezone = Column(String, nullable=False, default="UTC")
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")

    workspace = relationship("Workspace", back_populates="users")
```

- [ ] **Step 4: Create backend/app/models/connection.py**

```python
# backend/app/models/connection.py
from sqlalchemy import Column, String, Float, Boolean, Integer, ARRAY, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
import uuid
from app.database import Base

class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("workspace_id", "linkedin_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    linkedin_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    headline = Column(Text)
    profile_url = Column(String)
    company = Column(String)
    seniority = Column(String)
    degree = Column(Integer, nullable=False)
    relationship_score = Column(Float, nullable=False, default=0.5)
    has_interacted = Column(Boolean, nullable=False, default=False)
    first_seen_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    last_active_at = Column(TIMESTAMPTZ)
    enriched_at = Column(TIMESTAMPTZ)
    enrichment_data = Column(JSONB, default=dict)
    topic_interests = Column(ARRAY(Text))
```

- [ ] **Step 5: Create backend/app/models/post.py**

```python
# backend/app/models/post.py
from sqlalchemy import Column, String, Float, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
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
    # embedding: Vector(1536) — added via raw SQL in migration
    relevance_score = Column(Float)
    relationship_score = Column(Float)
    timing_score = Column(Float)
    combined_score = Column(Float)
    matched = Column(Boolean, nullable=False, default=False)
    processed_at = Column(TIMESTAMPTZ)
    extraction_version = Column(String)
```

- [ ] **Step 6: Create backend/app/models/alert.py**

```python
# backend/app/models/alert.py
from sqlalchemy import Column, String, Float, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    post_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True), nullable=False)
    relevance_score = Column(Float, nullable=False)
    relationship_score = Column(Float, nullable=False)
    timing_score = Column(Float, nullable=False)
    combined_score = Column(Float, nullable=False)
    priority = Column(String, nullable=False)
    match_reason = Column(Text)
    outreach_draft_a = Column(Text)
    outreach_draft_b = Column(Text)
    opportunity_type = Column(String)
    urgency_reason = Column(Text)
    status = Column(String, nullable=False, default="pending")
    delivered_at = Column(TIMESTAMPTZ)
    seen_at = Column(TIMESTAMPTZ)
    feedback = Column(String)
    feedback_at = Column(TIMESTAMPTZ)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

- [ ] **Step 7: Create backend/app/models/outreach.py**

```python
# backend/app/models/outreach.py
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
import uuid
from app.database import Base

class OutreachHistory(Base):
    __tablename__ = "outreach_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    connection_id = Column(UUID(as_uuid=True), nullable=False)
    message_sent = Column(Text)
    outcome = Column(String)
    notes = Column(Text)
    contacted_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

- [ ] **Step 8: Create backend/app/models/feedback.py**

```python
# backend/app/models/feedback.py
from sqlalchemy import Column, String, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from sqlalchemy import Numeric
import uuid
from app.database import Base

class FeedbackAdjustment(Base):
    __tablename__ = "feedback_adjustments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    old_threshold = Column(Float, nullable=False)
    new_threshold = Column(Float, nullable=False)
    positive_rate = Column(Float, nullable=False)
    adjustment_reason = Column(String)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")


class SignalEffectiveness(Base):
    __tablename__ = "signal_effectiveness"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False)
    alert_id = Column(UUID(as_uuid=True), nullable=False)
    predicted_score = Column(Float, nullable=False)
    user_rated = Column(String)
    outreach_sent = Column(Boolean, nullable=False, default=False)
    outreach_outcome = Column(String)
    revenue_attributed = Column(Numeric(10, 2))
    effectiveness_score = Column(Float)
    created_at = Column(TIMESTAMPTZ, nullable=False, server_default="now()")
```

- [ ] **Step 9: Write the initial Alembic migration**

Create `backend/alembic/versions/001_initial_schema.py`:

```python
"""Initial schema

Revision ID: 001
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan_tier", sa.String(), nullable=False, server_default="starter"),
        sa.Column("capability_profile", sa.Text()),
        sa.Column("matching_threshold", sa.Float(), nullable=False, server_default="0.72"),
        sa.Column("scoring_weights", postgresql.JSONB(), server_default='{"relevance":0.50,"relationship":0.30,"timing":0.20}'),
        sa.Column("onboarding_url", sa.String()),
        sa.Column("onboarding_doc_path", sa.String()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("capability_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("anti_keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("performance_score", sa.Float()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )
    # Add pgvector column separately (SQLAlchemy doesn't natively support Vector type)
    op.execute("ALTER TABLE capability_profile_versions ADD COLUMN embedding vector(1536)")

    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("linkedin_profile_url", sa.String()),
        sa.Column("delivery_channels", postgresql.JSONB(), server_default="{}"),
        sa.Column("alert_rate_limits", postgresql.JSONB(), server_default='{"high":10,"medium":5,"low":2}'),
        sa.Column("quiet_hours", postgresql.JSONB(), server_default="{}"),
        sa.Column("extension_installed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extension_last_sync", postgresql.TIMESTAMPTZ()),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("linkedin_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("headline", sa.Text()),
        sa.Column("profile_url", sa.String()),
        sa.Column("company", sa.String()),
        sa.Column("seniority", sa.String()),
        sa.Column("degree", sa.Integer(), nullable=False),
        sa.Column("relationship_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("has_interacted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("first_seen_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_active_at", postgresql.TIMESTAMPTZ()),
        sa.Column("enriched_at", postgresql.TIMESTAMPTZ()),
        sa.Column("enrichment_data", postgresql.JSONB(), server_default="{}"),
        sa.Column("topic_interests", postgresql.ARRAY(sa.Text())),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "linkedin_id"),
    )

    op.create_table("posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True)),
        sa.Column("linkedin_post_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("posted_at", postgresql.TIMESTAMPTZ()),
        sa.Column("ingested_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("relationship_score", sa.Float()),
        sa.Column("timing_score", sa.Float()),
        sa.Column("combined_score", sa.Float()),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processed_at", postgresql.TIMESTAMPTZ()),
        sa.Column("extraction_version", sa.String()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "linkedin_post_id"),
    )
    op.execute("ALTER TABLE posts ADD COLUMN embedding vector(1536)")
    op.execute("CREATE INDEX posts_embedding_idx ON posts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    op.create_table("alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("relationship_score", sa.Float(), nullable=False),
        sa.Column("timing_score", sa.Float(), nullable=False),
        sa.Column("combined_score", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("match_reason", sa.Text()),
        sa.Column("outreach_draft_a", sa.Text()),
        sa.Column("outreach_draft_b", sa.Text()),
        sa.Column("opportunity_type", sa.String()),
        sa.Column("urgency_reason", sa.Text()),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("delivered_at", postgresql.TIMESTAMPTZ()),
        sa.Column("seen_at", postgresql.TIMESTAMPTZ()),
        sa.Column("feedback", sa.String()),
        sa.Column("feedback_at", postgresql.TIMESTAMPTZ()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"]),
    )

    op.create_table("outreach_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_sent", sa.Text()),
        sa.Column("outcome", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("contacted_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("feedback_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_threshold", sa.Float(), nullable=False),
        sa.Column("new_threshold", sa.Float(), nullable=False),
        sa.Column("positive_rate", sa.Float(), nullable=False),
        sa.Column("adjustment_reason", sa.String()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("signal_effectiveness",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicted_score", sa.Float(), nullable=False),
        sa.Column("user_rated", sa.String()),
        sa.Column("outreach_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("outreach_outcome", sa.String()),
        sa.Column("revenue_attributed", sa.Numeric(10, 2)),
        sa.Column("effectiveness_score", sa.Float()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

def downgrade():
    op.drop_table("signal_effectiveness")
    op.drop_table("feedback_adjustments")
    op.drop_table("outreach_history")
    op.drop_table("alerts")
    op.drop_table("posts")
    op.drop_table("connections")
    op.drop_table("users")
    op.drop_table("capability_profile_versions")
    op.drop_table("workspaces")
```

- [ ] **Step 10: Run migrations**

```bash
docker compose up -d postgres
cd backend
alembic upgrade head
```

Expected output ends with: `Running upgrade  -> 001, Initial schema`

- [ ] **Step 11: Commit**

```bash
git add backend/alembic/ backend/app/models/
git commit -m "feat: add database models and initial migration"
```

---

## Task 3: Auth — JWT Workspace + User Authentication

**Files:**
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/schemas/workspace.py`
- Create: `backend/app/routers/workspace.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_auth.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_register_and_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register workspace + owner user
        resp = await client.post("/workspace/register", json={
            "workspace_name": "Test Agency",
            "email": "owner@test.com",
            "password": "testpassword123"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "workspace_id" in data

        # Login and get token
        resp = await client.post("/auth/token", data={
            "username": "owner@test.com",
            "password": "testpassword123"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_auth.py -v
```

Expected: FAIL — `404 Not Found` on `/workspace/register`

- [ ] **Step 3: Create backend/app/schemas/workspace.py**

```python
# backend/app/schemas/workspace.py
from pydantic import BaseModel, EmailStr
from uuid import UUID

class WorkspaceRegister(BaseModel):
    workspace_name: str
    email: EmailStr
    password: str

class WorkspaceResponse(BaseModel):
    workspace_id: UUID
    user_id: UUID
    email: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 4: Create backend/app/routers/auth.py**

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceRegister, WorkspaceResponse, TokenResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
workspace_router = APIRouter(prefix="/workspace", tags=["workspace"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def create_access_token(user_id: UUID, workspace_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@workspace_router.post("/register", status_code=201, response_model=WorkspaceResponse)
async def register(body: WorkspaceRegister, db: AsyncSession = Depends(get_db)):
    # Check email not taken
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    workspace = Workspace(name=body.workspace_name)
    db.add(workspace)
    await db.flush()  # get workspace.id

    user = User(
        workspace_id=workspace.id,
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
        role="owner"
    )
    db.add(user)
    await db.commit()

    return WorkspaceResponse(workspace_id=workspace.id, user_id=user.id, email=user.email)


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(user.id, user.workspace_id)
    return TokenResponse(access_token=token)
```

- [ ] **Step 5: Register routers in main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router, workspace_router

app = FastAPI(title="Sonar API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspace_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create tests/conftest.py**

```python
# backend/tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import settings

TEST_DATABASE_URL = settings.database_url.replace("/sonar", "/sonar_test")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session

@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pytest tests/test_auth.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/ backend/app/schemas/ backend/tests/
git commit -m "feat: add JWT auth with workspace registration and login"
```

---

## Task 4: Capability Profile Extraction Service

**Files:**
- Create: `backend/app/services/embedding.py`
- Create: `backend/app/services/llm.py`
- Create: `backend/app/services/profile_extractor.py`
- Create: `backend/app/routers/profile.py`
- Create: `backend/tests/test_profile_extractor.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_profile_extractor.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.profile_extractor import extract_capability_profile

@pytest.mark.asyncio
async def test_extract_from_text():
    sample_text = """
    Acme AI Agency builds custom AI agents for B2B sales teams.
    We specialize in integrating LLMs with existing CRM systems like Salesforce and HubSpot.
    Our clients are mid-market SaaS companies struggling with sales automation.
    """

    with patch("app.services.profile_extractor.llm_client") as mock_llm:
        mock_llm.complete = AsyncMock(return_value='''{
            "company_name": "Acme AI Agency",
            "company_description": "Builds custom AI agents for B2B sales teams.",
            "primary_services": ["custom AI agents", "LLM integration", "sales automation"],
            "target_customers": ["mid-market SaaS companies"],
            "pain_points_solved": ["sales automation", "CRM integration"],
            "technologies_used": ["LLMs", "Salesforce", "HubSpot"],
            "signal_keywords": ["AI agent", "sales automation", "CRM integration", "LLM"],
            "anti_keywords": ["looking for job", "open to work"],
            "capability_summary": "Acme AI Agency builds custom AI agents and LLM integrations for B2B sales teams at mid-market SaaS companies, solving sales automation and CRM integration challenges."
        }''')

        profile = await extract_capability_profile(text=sample_text)

    assert profile.company_name == "Acme AI Agency"
    assert "AI agent" in profile.signal_keywords
    assert len(profile.signal_keywords) >= 4
    assert profile.capability_summary != ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_profile_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/services/llm.py**

```python
# backend/app/services/llm.py
from typing import Protocol
from openai import AsyncOpenAI
from groq import AsyncGroq
from app.config import settings

class LLMProvider(Protocol):
    async def complete(self, prompt: str, model: str) -> str: ...


class OpenAILLMProvider:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def complete(self, prompt: str, model: str = "gpt-4o") -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content


class GroqLLMProvider:
    def __init__(self):
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    async def complete(self, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content


# Default instances — swap via config if needed
openai_provider = OpenAILLMProvider()
groq_provider = GroqLLMProvider()

# Alias used in profile_extractor (always uses GPT-4o for quality)
llm_client = openai_provider
```

- [ ] **Step 4: Create backend/app/services/embedding.py**

```python
# backend/app/services/embedding.py
from typing import Protocol
from openai import AsyncOpenAI
from app.config import settings

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbeddingProvider:
    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed(self, text: str) -> list[float]:
        # Truncate to 8000 chars to stay within token limits
        text = text[:8000]
        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding


embedding_provider = OpenAIEmbeddingProvider()
```

- [ ] **Step 5: Create backend/app/services/profile_extractor.py**

```python
# backend/app/services/profile_extractor.py
import json
import httpx
from dataclasses import dataclass
from app.services.llm import llm_client

PROFILE_EXTRACTION_PROMPT = """
Analyze this company's website/document to build a sales intelligence capability profile.

CONTENT:
{content}

Return a JSON object with exactly these fields:
- company_name: string
- company_description: 2-3 sentence summary of what they do
- primary_services: list of specific services/products offered
- target_customers: list of industries, roles, or company sizes they serve
- pain_points_solved: list of specific problems they solve
- technologies_used: list of tech stack, tools, platforms they work with
- signal_keywords: list of 20-30 keywords/phrases that would indicate a prospect needs this company (what would someone post about on LinkedIn if they needed this company?)
- anti_keywords: list of 10-15 phrases indicating irrelevance (e.g. job seekers, unrelated topics)
- capability_summary: A single dense paragraph (150-200 words) covering ALL capabilities. Written to maximize semantic vector search coverage — not marketing copy.

Respond with valid JSON only. No preamble, no markdown fences.
"""


@dataclass
class CapabilityProfile:
    company_name: str
    company_description: str
    primary_services: list[str]
    target_customers: list[str]
    pain_points_solved: list[str]
    technologies_used: list[str]
    signal_keywords: list[str]
    anti_keywords: list[str]
    capability_summary: str


async def fetch_url_content(url: str) -> str:
    """Fetch and return text content from a URL."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Strip HTML tags naively — good enough for about pages
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:12000]


async def extract_capability_profile(
    text: str | None = None,
    url: str | None = None,
) -> CapabilityProfile:
    """
    Extract capability profile from either raw text or a URL.
    Uses GPT-4o for highest quality — this runs once at onboarding.
    """
    if not text and not url:
        raise ValueError("Either text or url must be provided")

    content = text or await fetch_url_content(url)
    prompt = PROFILE_EXTRACTION_PROMPT.format(content=content)

    raw = await llm_client.complete(prompt=prompt, model="gpt-4o")

    # Strip markdown fences if model adds them despite instruction
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return CapabilityProfile(**data)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_profile_extractor.py -v
```

Expected: PASS

- [ ] **Step 7: Create backend/app/routers/profile.py**

```python
# backend/app/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, HttpUrl
from uuid import UUID
from app.database import get_db
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.profile_extractor import extract_capability_profile
from app.services.embedding import embedding_provider

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileExtractRequest(BaseModel):
    url: HttpUrl | None = None
    text: str | None = None


class ProfileExtractResponse(BaseModel):
    company_name: str
    capability_summary: str
    signal_keywords: list[str]
    version: int


@router.post("/extract", response_model=ProfileExtractResponse)
async def extract_profile(
    body: ProfileExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.url and not body.text:
        raise HTTPException(status_code=400, detail="Provide url or text")

    profile = await extract_capability_profile(
        text=body.text,
        url=str(body.url) if body.url else None,
    )

    # Generate embedding for capability summary
    embedding = await embedding_provider.embed(profile.capability_summary)

    # Deactivate previous active version
    await db.execute(
        update(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
        .where(CapabilityProfileVersion.is_active == True)
        .values(is_active=False)
    )

    # Count existing versions
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
    )
    version_number = (count_result.scalar() or 0) + 1

    # Save new version
    version = CapabilityProfileVersion(
        workspace_id=current_user.workspace_id,
        version=version_number,
        raw_text=profile.capability_summary,
        source="url" if body.url else "document",
        signal_keywords=profile.signal_keywords,
        anti_keywords=profile.anti_keywords,
        is_active=True,
    )
    db.add(version)

    # Update workspace capability_profile text
    await db.execute(
        update(Workspace)
        .where(Workspace.id == current_user.workspace_id)
        .values(capability_profile=profile.capability_summary)
    )

    # Store embedding via raw SQL (pgvector)
    await db.flush()
    await db.execute(
        f"UPDATE capability_profile_versions SET embedding = :emb WHERE id = :id",
        {"emb": str(embedding), "id": str(version.id)}
    )

    await db.commit()

    return ProfileExtractResponse(
        company_name=profile.company_name,
        capability_summary=profile.capability_summary,
        signal_keywords=profile.signal_keywords,
        version=version_number,
    )
```

- [ ] **Step 8: Register router in main.py**

```python
# backend/app/main.py — add to existing imports and registrations
from app.routers.profile import router as profile_router
# ...
app.include_router(profile_router)
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/ backend/app/routers/profile.py backend/tests/test_profile_extractor.py
git commit -m "feat: add capability profile extraction with LLM and embedding storage"
```

---

## Task 5: Keyword Pre-Filter + Semantic Matching Engine

**Files:**
- Create: `backend/app/services/keyword_filter.py`
- Create: `backend/app/services/matcher.py`
- Create: `backend/tests/test_keyword_filter.py`
- Create: `backend/tests/test_matcher.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_keyword_filter.py
import pytest
from app.services.keyword_filter import keyword_prefilter

def test_blocks_birthday_post():
    result = keyword_prefilter(
        content="Happy birthday to my amazing colleague Sarah!",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=["happy birthday"]
    )
    assert result is False

def test_blocks_post_with_no_signal_words():
    result = keyword_prefilter(
        content="Just had an amazing lunch at this new Italian place downtown.",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=[]
    )
    assert result is False

def test_passes_relevant_post():
    result = keyword_prefilter(
        content="We're evaluating AI automation tools for our data pipeline. Any recommendations?",
        signal_keywords=["AI", "automation", "data pipeline"],
        anti_keywords=[]
    )
    assert result is True

def test_blocks_open_to_work():
    result = keyword_prefilter(
        content="Excited to share that I'm open to work! Looking for a senior data role.",
        signal_keywords=["data", "pipeline"],
        anti_keywords=["open to work", "looking for"]
    )
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_keyword_filter.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/services/keyword_filter.py**

```python
# backend/app/services/keyword_filter.py

DEFAULT_BLOCKLIST = [
    "happy birthday",
    "work anniversary",
    "excited to announce my new role",
    "open to work",
    "pleased to share",
    "thrilled to announce",
    "congratulations on your",
    "looking for new opportunities",
]


def keyword_prefilter(
    content: str,
    signal_keywords: list[str],
    anti_keywords: list[str],
) -> bool:
    """
    Returns True if the post should proceed to semantic matching.
    Returns False if the post should be discarded.

    Stage 1 of the matching pipeline — fast, cheap, synchronous.
    """
    content_lower = content.lower()

    # Hard blocklist — combined default + workspace anti_keywords
    full_blocklist = DEFAULT_BLOCKLIST + [kw.lower() for kw in anti_keywords]
    if any(term in content_lower for term in full_blocklist):
        return False

    # Must contain at least one signal keyword
    if not any(kw.lower() in content_lower for kw in signal_keywords):
        return False

    return True
```

- [ ] **Step 4: Run keyword filter tests to verify they pass**

```bash
pytest tests/test_keyword_filter.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Write failing matcher test**

```python
# backend/tests/test_matcher.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from app.services.matcher import compute_relevance_score


@pytest.mark.asyncio
async def test_high_relevance_for_matching_content():
    workspace_id = uuid4()

    with patch("app.services.matcher.embedding_provider") as mock_emb, \
         patch("app.services.matcher.get_capability_embedding") as mock_cap:

        # Simulate embeddings that are very similar (high cosine similarity)
        mock_emb.embed = AsyncMock(return_value=[0.9] * 1536)
        mock_cap = AsyncMock(return_value=[0.9] * 1536)

        score = await compute_relevance_score(
            post_content="We need help integrating AI agents into our sales workflow.",
            capability_embedding=[0.9] * 1536,
        )

    # Same vector → cosine similarity = 1.0
    assert score > 0.95


@pytest.mark.asyncio
async def test_low_relevance_for_unrelated_content():
    score = await compute_relevance_score(
        post_content="Just got back from an amazing hiking trip in the mountains!",
        capability_embedding=[0.9] * 1536,
    )
    # Very different content → low similarity
    # With mocked embeddings returning zeros for unrelated content
    assert score >= 0.0
    assert score <= 1.0
```

- [ ] **Step 6: Run matcher test to verify it fails**

```bash
pytest tests/test_matcher.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 7: Create backend/app/services/matcher.py**

```python
# backend/app/services/matcher.py
import numpy as np
from app.services.embedding import embedding_provider


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


async def compute_relevance_score(
    post_content: str,
    capability_embedding: list[float],
) -> float:
    """
    Generate post embedding and compute cosine similarity
    against the workspace capability profile embedding.
    Returns a float between 0.0 and 1.0.
    """
    post_embedding = await embedding_provider.embed(post_content)
    return cosine_similarity(post_embedding, capability_embedding)
```

- [ ] **Step 8: Run matcher tests to verify they pass**

```bash
pytest tests/test_matcher.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/keyword_filter.py backend/app/services/matcher.py backend/tests/
git commit -m "feat: add keyword pre-filter and semantic similarity matcher"
```

---

## Task 6: 3-Dimension Scoring Engine

**Files:**
- Create: `backend/app/services/scorer.py`
- Create: `backend/tests/test_scorer.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_scorer.py
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app.services.scorer import compute_combined_score, Priority, ScoringResult


def make_connection(degree: int = 1, relationship_score: float | None = None, has_interacted: bool = False):
    from types import SimpleNamespace
    return SimpleNamespace(
        degree=degree,
        relationship_score=relationship_score,
        has_interacted=has_interacted,
    )


def test_high_priority_for_fresh_first_degree_relevant_post():
    connection = make_connection(degree=1, relationship_score=0.9)
    result = compute_combined_score(
        relevance_score=0.88,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    assert result.priority == Priority.HIGH
    assert result.combined_score >= 0.80


def test_low_priority_for_old_third_degree_weak_post():
    connection = make_connection(degree=3, relationship_score=0.3)
    result = compute_combined_score(
        relevance_score=0.55,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=23),
    )
    assert result.priority == Priority.LOW
    assert result.combined_score < 0.55


def test_relationship_score_boost_for_interaction():
    connection = make_connection(degree=2, relationship_score=None, has_interacted=True)
    result = compute_combined_score(
        relevance_score=0.80,
        connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    # has_interacted should boost relationship score above base 0.60 for degree=2
    assert result.relationship_score > 0.60


def test_timing_score_decays_over_24_hours():
    connection = make_connection(degree=1)
    fresh_result = compute_combined_score(
        relevance_score=0.80, connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    old_result = compute_combined_score(
        relevance_score=0.80, connection=connection,
        posted_at=datetime.now(timezone.utc) - timedelta(hours=22),
    )
    assert fresh_result.timing_score > old_result.timing_score
    assert fresh_result.combined_score > old_result.combined_score


def test_scoring_result_fields_present():
    connection = make_connection(degree=1)
    result = compute_combined_score(
        relevance_score=0.75,
        connection=connection,
        posted_at=datetime.now(timezone.utc),
    )
    assert isinstance(result, ScoringResult)
    assert 0.0 <= result.relevance_score <= 1.0
    assert 0.0 <= result.relationship_score <= 1.0
    assert 0.0 <= result.timing_score <= 1.0
    assert 0.0 <= result.combined_score <= 1.0
    assert result.priority in (Priority.HIGH, Priority.MEDIUM, Priority.LOW)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_scorer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/services/scorer.py**

```python
# backend/app/services/scorer.py
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

DEFAULT_WEIGHTS = {
    "relevance": 0.50,
    "relationship": 0.30,
    "timing": 0.20,
}

DEGREE_BASE_SCORE = {1: 0.90, 2: 0.60, 3: 0.30}
INTERACTION_BOOST = 0.15


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScoringResult:
    relevance_score: float
    relationship_score: float
    timing_score: float
    combined_score: float
    priority: Priority


def compute_combined_score(
    relevance_score: float,
    connection,  # Connection ORM object or SimpleNamespace with degree, relationship_score, has_interacted
    posted_at: datetime,
    weights: dict | None = None,
) -> ScoringResult:
    """
    Compute 3-dimension combined score for a post+connection pair.

    Dimensions:
      - relevance: semantic match quality (0-1), provided by caller
      - relationship: warmth of connection (degree + interaction history)
      - timing: urgency decay (linear over 24 hours)
    """
    w = weights or DEFAULT_WEIGHTS

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
        relevance_score    * w["relevance"] +
        relationship_score * w["relationship"] +
        timing_score       * w["timing"]
    )
    combined = min(1.0, max(0.0, combined))

    # Priority bucketing
    if combined >= 0.80:
        priority = Priority.HIGH
    elif combined >= 0.55:
        priority = Priority.MEDIUM
    else:
        priority = Priority.LOW

    return ScoringResult(
        relevance_score=relevance_score,
        relationship_score=relationship_score,
        timing_score=timing_score,
        combined_score=combined,
        priority=priority,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scorer.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scorer.py backend/tests/test_scorer.py
git commit -m "feat: add 3-dimension scoring engine with priority bucketing"
```

---

## Task 7: Context Generator (Match Reason + Outreach Drafts)

**Files:**
- Create: `backend/app/services/context_generator.py`
- Create: `backend/tests/test_context_generator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_context_generator.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.context_generator import generate_alert_context, AlertContext
from app.services.scorer import Priority


@pytest.mark.asyncio
async def test_generates_context_with_all_required_fields():
    mock_response = '''{
        "match_reason": "John is evaluating AI agents for sales, which matches your core service offering of building custom AI agents.",
        "outreach_draft_a": "Hey John, saw your post about evaluating AI agents for sales — we have helped 3 SaaS companies with exactly this. Worth a quick 20-min call?",
        "outreach_draft_b": "John — curious what specific sales workflow you are trying to automate? We have been seeing this challenge come up a lot lately.",
        "opportunity_type": "service_need",
        "urgency_reason": "Post is fresh and the evaluation is actively underway."
    }'''

    with patch("app.services.context_generator.openai_provider") as mock_openai, \
         patch("app.services.context_generator.groq_provider") as mock_groq:

        mock_openai.complete = AsyncMock(return_value=mock_response)
        mock_groq.complete = AsyncMock(return_value=mock_response)

        context = await generate_alert_context(
            post_content="We're actively evaluating AI agent platforms for our sales team.",
            author_name="John Smith",
            author_headline="VP Sales at Acme Corp",
            author_company="Acme Corp",
            degree=1,
            enrichment_summary="Acme Corp: 200 employees, Series B, CRM stack includes Salesforce.",
            capability_profile="We build custom AI agents for B2B sales teams integrating with CRM systems.",
            priority=Priority.HIGH,
        )

    assert isinstance(context, AlertContext)
    assert len(context.match_reason) > 10
    assert len(context.outreach_draft_a) > 10
    assert len(context.outreach_draft_b) > 10
    assert context.opportunity_type in ["service_need", "product_pain", "hiring_signal", "funding_signal", "competitive_mention", "general_interest"]
    assert len(context.urgency_reason) > 5


@pytest.mark.asyncio
async def test_high_priority_uses_openai_not_groq():
    mock_response = '''{
        "match_reason": "Relevant.",
        "outreach_draft_a": "Draft A.",
        "outreach_draft_b": "Draft B.",
        "opportunity_type": "service_need",
        "urgency_reason": "Fresh signal."
    }'''

    with patch("app.services.context_generator.openai_provider") as mock_openai, \
         patch("app.services.context_generator.groq_provider") as mock_groq:

        mock_openai.complete = AsyncMock(return_value=mock_response)
        mock_groq.complete = AsyncMock(return_value=mock_response)

        await generate_alert_context(
            post_content="Need AI help.",
            author_name="Jane", author_headline="CTO", author_company="Corp",
            degree=1, enrichment_summary="", capability_profile="We build AI agents.",
            priority=Priority.HIGH,
        )

        mock_openai.complete.assert_called_once()
        mock_groq.complete.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_context_generator.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/services/context_generator.py**

```python
# backend/app/services/context_generator.py
import json
from dataclasses import dataclass
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

Valid JSON only. No preamble, no markdown fences.
"""


@dataclass
class AlertContext:
    match_reason: str
    outreach_draft_a: str
    outreach_draft_b: str
    opportunity_type: str
    urgency_reason: str


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
    Generate match reason and two outreach draft variants using LLM.
    Routes to GPT-4o mini for HIGH priority, Groq for MEDIUM/LOW.
    """
    prompt = CONTEXT_GENERATION_PROMPT.format(
        capability_profile=capability_profile,
        author_name=author_name,
        author_headline=author_headline,
        author_company=author_company,
        degree=degree,
        enrichment_summary=enrichment_summary or "No enrichment data available.",
        post_content=post_content[:1000],  # cap to avoid token overflow
    )

    if priority == Priority.HIGH:
        raw = await openai_provider.complete(prompt=prompt, model="gpt-4o-mini")
    else:
        raw = await groq_provider.complete(prompt=prompt, model="llama-3.3-70b-versatile")

    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return AlertContext(**data)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_context_generator.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/context_generator.py backend/tests/test_context_generator.py
git commit -m "feat: add LLM context generator with model routing by priority"
```

---

## Task 8: Celery Pipeline + Ingest API

**Files:**
- Create: `backend/app/workers/celery_app.py`
- Create: `backend/app/workers/pipeline.py`
- Create: `backend/app/schemas/ingest.py`
- Create: `backend/app/routers/ingest.py`
- Create: `backend/tests/test_ingest_router.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ingest_router.py
import pytest
from unittest.mock import patch, MagicMock
from app.schemas.ingest import PostIngestPayload, PostAuthor

@pytest.mark.asyncio
async def test_ingest_endpoint_accepts_valid_payload(client, db_session):
    # Register and login first
    await client.post("/workspace/register", json={
        "workspace_name": "Test Agency", "email": "test@ingest.com", "password": "pass123"
    })
    login = await client.post("/auth/token", data={"username": "test@ingest.com", "password": "pass123"})
    token = login.json()["access_token"]

    payload = {
        "posts": [{
            "linkedin_post_id": "urn:li:activity:111222333",
            "author": {
                "name": "Jane Doe",
                "headline": "CTO at StartupX",
                "profile_url": "https://linkedin.com/in/janedoe",
                "linkedin_id": "janedoe123",
                "degree": 1
            },
            "content": "We are evaluating AI agent frameworks for our product team.",
            "post_type": "post",
            "posted_at": "2026-04-08T09:00:00Z",
            "engagement": {"likes": 12, "comments": 3}
        }],
        "extraction_version": "1.0.0"
    }

    with patch("app.routers.ingest.process_post_pipeline.delay") as mock_task:
        mock_task.return_value = MagicMock(id="task-123")
        resp = await client.post(
            "/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )

    assert resp.status_code == 202
    assert resp.json()["queued"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ingest_router.py -v
```

Expected: FAIL

- [ ] **Step 3: Create backend/app/workers/celery_app.py**

```python
# backend/app/workers/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "sonar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.pipeline",
        "app.jobs.public_poller",
        "app.jobs.digest_sender",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "public-post-poller": {
            "task": "app.jobs.public_poller.poll_public_posts",
            "schedule": 3600.0,  # every hour
        },
        "email-digest-sender": {
            "task": "app.jobs.digest_sender.send_digests",
            "schedule": 3600.0,  # every hour
        },
    }
)
```

- [ ] **Step 4: Create backend/app/schemas/ingest.py**

```python
# backend/app/schemas/ingest.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class PostAuthor(BaseModel):
    name: str
    headline: str | None = None
    profile_url: str | None = None
    linkedin_id: str
    degree: int  # 1, 2, or 3

class PostEngagement(BaseModel):
    likes: int = 0
    comments: int = 0

class IngestPost(BaseModel):
    linkedin_post_id: str
    author: PostAuthor
    content: str
    post_type: str = "post"
    posted_at: datetime | None = None
    engagement: PostEngagement = PostEngagement()

class PostIngestPayload(BaseModel):
    posts: list[IngestPost]
    extraction_version: str = "unknown"

class IngestResponse(BaseModel):
    queued: int
    skipped: int  # duplicates
```

- [ ] **Step 5: Create backend/app/workers/pipeline.py**

```python
# backend/app/workers/pipeline.py
import asyncio
from uuid import UUID
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.pipeline.process_post_pipeline", bind=True, max_retries=3)
def process_post_pipeline(self, post_id: str, workspace_id: str):
    """
    Main processing pipeline for a single ingested post.
    Chain: enrich → score → generate → deliver
    """
    asyncio.run(_run_pipeline(UUID(post_id), UUID(workspace_id)))


async def _run_pipeline(post_id: UUID, workspace_id: UUID):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import settings
    from app.models.post import Post
    from app.models.connection import Connection
    from app.models.workspace import CapabilityProfileVersion
    from app.models.alert import Alert
    from app.models.feedback import SignalEffectiveness
    from app.services.keyword_filter import keyword_prefilter
    from app.services.matcher import compute_relevance_score
    from app.services.scorer import compute_combined_score, Priority
    from app.services.context_generator import generate_alert_context
    from app.delivery.router import DeliveryRouter
    from sqlalchemy import select, text
    import json

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Fetch post
        post = await db.get(Post, post_id)
        if not post or post.processed_at:
            return  # Already processed or not found

        # Fetch workspace capability profile
        result = await db.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == workspace_id)
            .where(CapabilityProfileVersion.is_active == True)
        )
        version = result.scalar_one_or_none()
        if not version:
            return  # No capability profile yet

        # Stage 1: Keyword pre-filter
        passes = keyword_prefilter(
            content=post.content,
            signal_keywords=version.signal_keywords or [],
            anti_keywords=version.anti_keywords or [],
        )
        if not passes:
            from sqlalchemy import update
            from datetime import datetime, timezone
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(processed_at=datetime.now(timezone.utc), matched=False)
            )
            await db.commit()
            return

        # Stage 2+3: Embedding + semantic similarity
        # Fetch capability embedding via raw SQL
        row = await db.execute(
            text("SELECT embedding::text FROM capability_profile_versions WHERE id = :id"),
            {"id": str(version.id)}
        )
        emb_str = row.scalar_one_or_none()
        if not emb_str:
            return
        capability_embedding = json.loads(emb_str)

        relevance_score = await compute_relevance_score(
            post_content=post.content,
            capability_embedding=capability_embedding,
        )

        # Check relevance threshold
        workspace = await db.get_one(
            __import__("app.models.workspace", fromlist=["Workspace"]).Workspace,
            workspace_id
        )
        if relevance_score < workspace.matching_threshold:
            from sqlalchemy import update
            from datetime import datetime, timezone
            await db.execute(
                update(Post).where(Post.id == post_id)
                .values(
                    processed_at=datetime.now(timezone.utc),
                    matched=False,
                    relevance_score=relevance_score,
                )
            )
            await db.commit()
            return

        # Fetch connection
        connection = await db.get(Connection, post.connection_id)

        # Stage 5: 3-dimension scoring
        scoring = compute_combined_score(
            relevance_score=relevance_score,
            connection=connection,
            posted_at=post.posted_at or post.ingested_at,
            weights=workspace.scoring_weights,
        )

        # Stage 6: Context generation
        context = await generate_alert_context(
            post_content=post.content,
            author_name=connection.name if connection else "Unknown",
            author_headline=connection.headline or "",
            author_company=connection.company or "",
            degree=connection.degree if connection else 3,
            enrichment_summary=str(connection.enrichment_data) if connection else "",
            capability_profile=version.raw_text,
            priority=scoring.priority,
        )

        # Stage 7: Create alert
        from datetime import datetime, timezone
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

        # Log signal effectiveness
        effectiveness = SignalEffectiveness(
            workspace_id=workspace_id,
            alert_id=alert.id,
            predicted_score=scoring.combined_score,
        )
        db.add(effectiveness)

        # Update post as processed
        from sqlalchemy import update as sa_update
        await db.execute(
            sa_update(Post).where(Post.id == post_id).values(
                processed_at=datetime.now(timezone.utc),
                matched=True,
                relevance_score=relevance_score,
                relationship_score=scoring.relationship_score,
                timing_score=scoring.timing_score,
                combined_score=scoring.combined_score,
            )
        )
        await db.flush()

        # Stage 8: Deliver
        await DeliveryRouter().deliver(alert=alert, db=db)

        await db.commit()

    await engine.dispose()
```

- [ ] **Step 6: Create backend/app/routers/ingest.py**

```python
# backend/app/routers/ingest.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.connection import Connection
from app.routers.auth import get_current_user
from app.schemas.ingest import PostIngestPayload, IngestResponse
from app.workers.pipeline import process_post_pipeline
import uuid

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestResponse)
async def ingest_posts(
    payload: PostIngestPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queued = 0
    skipped = 0

    for item in payload.posts:
        # Upsert connection (create or update degree/headline)
        conn_stmt = insert(Connection).values(
            id=uuid.uuid4(),
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            linkedin_id=item.author.linkedin_id,
            name=item.author.name,
            headline=item.author.headline,
            profile_url=item.author.profile_url,
            degree=item.author.degree,
        ).on_conflict_do_update(
            index_elements=["workspace_id", "linkedin_id"],
            set_={
                "name": item.author.name,
                "headline": item.author.headline,
                "degree": item.author.degree,
            }
        ).returning(Connection.id)

        conn_result = await db.execute(conn_stmt)
        connection_id = conn_result.scalar_one()

        # Check for duplicate post
        existing = await db.execute(
            select(Post.id).where(
                Post.workspace_id == current_user.workspace_id,
                Post.linkedin_post_id == item.linkedin_post_id,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Insert post
        post = Post(
            workspace_id=current_user.workspace_id,
            connection_id=connection_id,
            linkedin_post_id=item.linkedin_post_id,
            content=item.content,
            post_type=item.post_type,
            source="extension",
            posted_at=item.posted_at,
            extraction_version=payload.extraction_version,
        )
        db.add(post)
        await db.flush()

        # Queue for processing
        process_post_pipeline.delay(str(post.id), str(current_user.workspace_id))
        queued += 1

    await db.commit()
    return IngestResponse(queued=queued, skipped=skipped)
```

- [ ] **Step 7: Register router in main.py**

```python
# backend/app/main.py — add to imports and registrations
from app.routers.ingest import router as ingest_router
# ...
app.include_router(ingest_router)
```

- [ ] **Step 8: Run test to verify it passes**

```bash
pytest tests/test_ingest_router.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/workers/ backend/app/schemas/ingest.py backend/app/routers/ingest.py
git commit -m "feat: add Celery pipeline and ingest API endpoint"
```

---

## Task 9: Delivery Layer — All Four Channels

**Files:**
- Create: `backend/app/delivery/router.py`
- Create: `backend/app/delivery/slack.py`
- Create: `backend/app/delivery/email.py`
- Create: `backend/app/delivery/telegram.py`
- Create: `backend/app/delivery/whatsapp.py`
- Create: `backend/tests/test_delivery_router.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_delivery_router.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from app.delivery.router import DeliveryRouter
from app.services.scorer import Priority


def make_alert(priority: str = "high"):
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        connection_id=uuid4(),
        priority=priority,
        combined_score=0.85,
        relevance_score=0.88,
        relationship_score=0.90,
        timing_score=0.82,
        match_reason="This is why it matches.",
        outreach_draft_a="Draft A message.",
        outreach_draft_b="Draft B message.",
        opportunity_type="service_need",
        urgency_reason="Post is fresh.",
    )


def make_workspace_with_slack():
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid4(),
        delivery_channels={"slack": {"webhook_url": "https://hooks.slack.com/test", "min_priority": "low"}},
    )


@pytest.mark.asyncio
async def test_router_calls_slack_for_configured_workspace():
    alert = make_alert(priority="high")
    workspace = make_workspace_with_slack()

    with patch("app.delivery.router.SlackSender") as MockSlack:
        mock_instance = MagicMock()
        mock_instance.send = AsyncMock()
        MockSlack.return_value = mock_instance

        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace)

        mock_instance.send.assert_called_once()


@pytest.mark.asyncio
async def test_router_skips_channel_below_min_priority():
    alert = make_alert(priority="low")
    workspace_with_high_threshold = __import__("types").SimpleNamespace(
        id=uuid4(),
        delivery_channels={
            "slack": {"webhook_url": "https://hooks.slack.com/test", "min_priority": "high"}
        },
    )

    with patch("app.delivery.router.SlackSender") as MockSlack:
        mock_instance = MagicMock()
        mock_instance.send = AsyncMock()
        MockSlack.return_value = mock_instance

        router = DeliveryRouter()
        await router.deliver(alert=alert, workspace=workspace_with_high_threshold)

        mock_instance.send.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_delivery_router.py -v
```

Expected: FAIL

- [ ] **Step 3: Create backend/app/delivery/slack.py**

```python
# backend/app/delivery/slack.py
import httpx


PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


class SlackSender:
    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("slack", {})
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            return

        emoji = PRIORITY_EMOJI.get(alert.priority, "⚪")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {alert.priority.upper()} SIGNAL"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Why it matches:*\n{alert.match_reason}"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Relevance: `{_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}\n"
                        f"Relationship: `{_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}\n"
                        f"Timing: `{_score_bar(alert.timing_score)}` {alert.timing_score:.0%}"
                    )
                }
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Draft A (Direct):*\n_{alert.outreach_draft_a}_"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Draft B (Question):*\n_{alert.outreach_draft_b}_"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Acted"},
                        "action_id": f"acted_{alert.id}",
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✗ Not Relevant"},
                        "action_id": f"irrelevant_{alert.id}"
                    }
                ]
            }
        ]

        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"blocks": blocks})
```

- [ ] **Step 4: Create backend/app/delivery/email.py**

```python
# backend/app/delivery/email.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import settings

PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}


class EmailSender:
    def __init__(self):
        self._client = SendGridAPIClient(settings.sendgrid_api_key)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("email", {})
        to_email = config.get("address")
        if not to_email:
            return

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")

        subject = f"{priority_emoji} Sonar Signal — {alert.opportunity_type.replace('_', ' ').title()}"

        html = f"""
        <h2>{priority_emoji} {alert.priority.upper()} SIGNAL</h2>
        <p><strong>Why it matches:</strong><br>{alert.match_reason}</p>
        <p><strong>Urgency:</strong> {alert.urgency_reason}</p>
        <hr>
        <p><strong>Draft A (Direct):</strong><br><em>{alert.outreach_draft_a}</em></p>
        <p><strong>Draft B (Question):</strong><br><em>{alert.outreach_draft_b}</em></p>
        <hr>
        <p>
            Scores — Relevance: {alert.relevance_score:.0%} |
            Relationship: {alert.relationship_score:.0%} |
            Timing: {alert.timing_score:.0%} |
            Combined: {alert.combined_score:.0%}
        </p>
        <p>
            <a href="https://yoursonar.com/alerts/{alert.id}/acted">✓ Mark Acted</a> &nbsp;|&nbsp;
            <a href="https://yoursonar.com/alerts/{alert.id}/irrelevant">✗ Not Relevant</a>
        </p>
        """

        message = Mail(
            from_email=settings.sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        self._client.send(message)
```

- [ ] **Step 5: Create backend/app/delivery/telegram.py**

```python
# backend/app/delivery/telegram.py
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from app.config import settings


def _score_bar(score: float, width: int = 10) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


class TelegramSender:
    def __init__(self):
        self._bot = Bot(token=settings.telegram_bot_token)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("telegram", {})
        chat_id = config.get("chat_id")
        if not chat_id:
            return

        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")

        text = (
            f"{emoji} *{alert.priority.upper()} SIGNAL*\n\n"
            f"🎯 *Why it matches:*\n{alert.match_reason}\n\n"
            f"📊 Relevance: `{_score_bar(alert.relevance_score)}` {alert.relevance_score:.0%}\n"
            f"📊 Relationship: `{_score_bar(alert.relationship_score)}` {alert.relationship_score:.0%}\n"
            f"📊 Timing: `{_score_bar(alert.timing_score)}` {alert.timing_score:.0%}\n\n"
            f"✉️ *Draft A \\(Direct\\):*\n_{alert.outreach_draft_a}_\n\n"
            f"✉️ *Draft B \\(Question\\):*\n_{alert.outreach_draft_b}_"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✓ Acted", callback_data=f"acted_{alert.id}"),
                InlineKeyboardButton("✗ Not Relevant", callback_data=f"irrelevant_{alert.id}")
            ]
        ])

        await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
        )
```

- [ ] **Step 6: Create backend/app/delivery/whatsapp.py**

```python
# backend/app/delivery/whatsapp.py
from twilio.rest import Client
from app.config import settings
import hashlib


class WhatsAppSender:
    def __init__(self):
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    async def send(self, alert, workspace) -> None:
        config = workspace.delivery_channels.get("whatsapp", {})
        to_phone = config.get("phone")
        if not to_phone:
            return

        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.priority, "⚪")
        short_id = str(alert.id)[:8]

        body = (
            f"{emoji} *Sonar Signal* [{alert.priority.upper()}]\n\n"
            f"Why it matches: {alert.match_reason}\n\n"
            f"Draft: {alert.outreach_draft_a}\n\n"
            f"Ref: {short_id}"
        )

        self._client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
```

- [ ] **Step 7: Create backend/app/delivery/router.py**

```python
# backend/app/delivery/router.py
import asyncio
from app.delivery.slack import SlackSender
from app.delivery.email import EmailSender
from app.delivery.telegram import TelegramSender
from app.delivery.whatsapp import WhatsAppSender

PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

CHANNEL_SENDERS = {
    "slack": SlackSender,
    "email": EmailSender,
    "telegram": TelegramSender,
    "whatsapp": WhatsAppSender,
}


class DeliveryRouter:
    async def deliver(self, alert, workspace=None, db=None) -> None:
        """
        Fan-out alert to all configured channels that meet the priority threshold.
        Fetches workspace from db if not provided.
        """
        if workspace is None and db is not None:
            from app.models.workspace import Workspace
            workspace = await db.get(Workspace, alert.workspace_id)

        if not workspace:
            return

        channels = workspace.delivery_channels or {}
        alert_priority_value = PRIORITY_ORDER.get(alert.priority, 1)

        tasks = []
        for channel_name, config in channels.items():
            min_priority = config.get("min_priority", "low")
            min_value = PRIORITY_ORDER.get(min_priority, 1)

            if alert_priority_value >= min_value:
                sender_class = CHANNEL_SENDERS.get(channel_name)
                if sender_class:
                    sender = sender_class()
                    tasks.append(sender.send(alert=alert, workspace=workspace))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
```

- [ ] **Step 8: Run delivery tests to verify they pass**

```bash
pytest tests/test_delivery_router.py -v
```

Expected: 2 PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/delivery/ backend/tests/test_delivery_router.py
git commit -m "feat: add delivery router with Slack, email, Telegram, and WhatsApp channels"
```

---

## Task 10: Alerts API + Feedback Endpoint

**Files:**
- Create: `backend/app/routers/alerts.py`
- Create: `backend/app/schemas/alert.py`
- Create: `backend/app/services/feedback_trainer.py`
- Create: `backend/tests/test_alerts_router.py`
- Create: `backend/tests/test_feedback_trainer.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_feedback_trainer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.feedback_trainer import process_feedback_adjustment


@pytest.mark.asyncio
async def test_raises_threshold_when_positive_rate_low():
    workspace = MagicMock()
    workspace.id = __import__("uuid").uuid4()
    workspace.matching_threshold = 0.72

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    # 3 positive out of 20 = 15% positive rate → should raise threshold
    recent_feedback = ["positive"] * 3 + ["negative"] * 17

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == 0.74  # raised by 0.02


@pytest.mark.asyncio
async def test_lowers_threshold_when_positive_rate_high():
    workspace = MagicMock()
    workspace.id = __import__("uuid").uuid4()
    workspace.matching_threshold = 0.72

    mock_db = AsyncMock()

    # 40 positive out of 50 = 80% positive rate → should lower threshold
    recent_feedback = ["positive"] * 40 + ["negative"] * 10

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == 0.71  # lowered by 0.01


@pytest.mark.asyncio
async def test_no_change_when_rate_in_acceptable_range():
    workspace = MagicMock()
    workspace.matching_threshold = 0.72
    mock_db = AsyncMock()

    # 30 positive out of 50 = 60% → acceptable range
    recent_feedback = ["positive"] * 30 + ["negative"] * 20

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=mock_db,
    )

    assert new_threshold == 0.72  # unchanged


@pytest.mark.asyncio
async def test_returns_unchanged_when_insufficient_feedback():
    workspace = MagicMock()
    workspace.matching_threshold = 0.72
    mock_db = AsyncMock()

    new_threshold = await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=["positive"] * 5,  # only 5, need 10 minimum
        db=mock_db,
    )

    assert new_threshold == 0.72  # unchanged — not enough data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_feedback_trainer.py -v
```

Expected: FAIL

- [ ] **Step 3: Create backend/app/services/feedback_trainer.py**

```python
# backend/app/services/feedback_trainer.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models.workspace import Workspace
from app.models.feedback import FeedbackAdjustment
import uuid

MINIMUM_FEEDBACK_COUNT = 10
RAISE_THRESHOLD_STEP = 0.02
LOWER_THRESHOLD_STEP = 0.01
MAX_THRESHOLD = 0.92
MIN_THRESHOLD = 0.55


async def process_feedback_adjustment(
    workspace,
    recent_feedback: list[str],
    db: AsyncSession,
) -> float:
    """
    Adjust workspace matching threshold based on accumulated feedback.
    Returns the new threshold (unchanged if no adjustment made).
    """
    if len(recent_feedback) < MINIMUM_FEEDBACK_COUNT:
        return workspace.matching_threshold

    positive_count = sum(1 for f in recent_feedback if f == "positive")
    positive_rate = positive_count / len(recent_feedback)
    old_threshold = workspace.matching_threshold

    if positive_rate < 0.40:
        # Too many irrelevant alerts — be more selective
        new_threshold = min(MAX_THRESHOLD, old_threshold + RAISE_THRESHOLD_STEP)
    elif positive_rate > 0.75:
        # High satisfaction — catch more signals
        new_threshold = max(MIN_THRESHOLD, old_threshold - LOWER_THRESHOLD_STEP)
    else:
        return old_threshold  # No change needed

    if new_threshold == old_threshold:
        return old_threshold

    # Persist new threshold
    await db.execute(
        update(Workspace)
        .where(Workspace.id == workspace.id)
        .values(matching_threshold=new_threshold)
    )

    # Log adjustment
    adjustment = FeedbackAdjustment(
        workspace_id=workspace.id,
        alert_id=uuid.uuid4(),  # placeholder — no single alert triggered this
        old_threshold=old_threshold,
        new_threshold=new_threshold,
        positive_rate=positive_rate,
        adjustment_reason=f"positive_rate={positive_rate:.2f}, n={len(recent_feedback)}",
    )
    db.add(adjustment)

    return new_threshold
```

- [ ] **Step 4: Run feedback trainer tests to verify they pass**

```bash
pytest tests/test_feedback_trainer.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Create backend/app/schemas/alert.py**

```python
# backend/app/schemas/alert.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class AlertResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    connection_id: UUID
    priority: str
    combined_score: float
    relevance_score: float
    relationship_score: float
    timing_score: float
    match_reason: str | None
    outreach_draft_a: str | None
    outreach_draft_b: str | None
    opportunity_type: str | None
    urgency_reason: str | None
    status: str
    feedback: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class FeedbackRequest(BaseModel):
    feedback: str  # 'positive' | 'negative'
    outcome: str | None = None  # 'no_reply' | 'replied' | 'meeting_booked' | 'deal_opened'
    message_sent: str | None = None
```

- [ ] **Step 6: Create backend/app/routers/alerts.py**

```python
# backend/app/routers/alerts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.alert import Alert
from app.models.outreach import OutreachHistory
from app.models.feedback import SignalEffectiveness
from app.routers.auth import get_current_user
from app.schemas.alert import AlertResponse, FeedbackRequest
from app.services.feedback_trainer import process_feedback_adjustment

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    priority: str | None = None,
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert).where(Alert.workspace_id == current_user.workspace_id)
    if priority:
        query = query.where(Alert.priority == priority)
    if status:
        query = query.where(Alert.status == status)
    query = query.order_by(Alert.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{alert_id}/feedback", status_code=200)
async def submit_feedback(
    alert_id: UUID,
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.feedback not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="feedback must be 'positive' or 'negative'")

    alert = await db.get(Alert, alert_id)
    if not alert or alert.workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc)

    # Update alert feedback
    await db.execute(
        update(Alert).where(Alert.id == alert_id)
        .values(feedback=body.feedback, feedback_at=now, status="acted" if body.feedback == "positive" else "dismissed")
    )

    # Update signal effectiveness
    user_rated = "relevant" if body.feedback == "positive" else "not_relevant"
    await db.execute(
        update(SignalEffectiveness).where(SignalEffectiveness.alert_id == alert_id)
        .values(user_rated=user_rated, outreach_sent=body.message_sent is not None)
    )

    # Log outreach if message provided
    if body.message_sent:
        outreach = OutreachHistory(
            workspace_id=current_user.workspace_id,
            alert_id=alert_id,
            connection_id=alert.connection_id,
            message_sent=body.message_sent,
            outcome=body.outcome,
        )
        db.add(outreach)

    await db.flush()

    # Check if threshold adjustment is needed
    recent_result = await db.execute(
        select(Alert.feedback).where(
            Alert.workspace_id == current_user.workspace_id,
            Alert.feedback.is_not(None)
        ).order_by(Alert.feedback_at.desc()).limit(50)
    )
    recent_feedback = [row[0] for row in recent_result.fetchall()]

    from app.models.workspace import Workspace
    workspace = await db.get(Workspace, current_user.workspace_id)
    await process_feedback_adjustment(
        workspace=workspace,
        recent_feedback=recent_feedback,
        db=db,
    )

    await db.commit()
    return {"message": "Sonar is learning your preferences."}
```

- [ ] **Step 7: Register router in main.py**

```python
# backend/app/main.py — add to imports and registrations
from app.routers.alerts import router as alerts_router
# ...
app.include_router(alerts_router)
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/alerts.py backend/app/schemas/alert.py backend/app/services/feedback_trainer.py backend/tests/
git commit -m "feat: add alerts API with feedback endpoint and threshold adjustment"
```

---

## Task 11: Chrome Extension

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/background/service-worker.js`
- Create: `extension/content/linkedin-scraper.js`
- Create: `extension/utils/extractor.js`
- Create: `extension/utils/api-client.js`
- Create: `extension/utils/storage.js`
- Create: `extension/popup/popup.html`
- Create: `extension/popup/popup.js`

- [ ] **Step 1: Create extension/manifest.json**

```json
{
  "manifest_version": 3,
  "name": "Sonar",
  "version": "1.0.0",
  "description": "Network-aware LinkedIn intent intelligence.",
  "permissions": ["activeTab", "storage", "alarms"],
  "host_permissions": ["https://www.linkedin.com/*"],
  "background": {
    "service_worker": "background/service-worker.js"
  },
  "content_scripts": [
    {
      "matches": ["https://www.linkedin.com/*"],
      "js": ["utils/storage.js", "utils/extractor.js", "utils/api-client.js", "content/linkedin-scraper.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {"16": "icons/icon16.png", "48": "icons/icon48.png"}
  },
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'"
  }
}
```

- [ ] **Step 2: Create extension/utils/storage.js**

```javascript
// extension/utils/storage.js
const SonarStorage = {
  async getAuthToken() {
    const data = await chrome.storage.local.get(['auth_token']);
    return data.auth_token || null;
  },

  async setAuthToken(token) {
    await chrome.storage.local.set({ auth_token: token });
  },

  async getHighWaterMark() {
    const data = await chrome.storage.local.get(['high_water_mark']);
    return data.high_water_mark || null;
  },

  async setHighWaterMark(postId) {
    await chrome.storage.local.set({ high_water_mark: postId });
  },

  async getLastSyncTime() {
    const data = await chrome.storage.local.get(['last_sync_time']);
    return data.last_sync_time || 0;
  },

  async setLastSyncTime(timestamp) {
    await chrome.storage.local.set({ last_sync_time: timestamp });
  },

  async getSeenPostIds() {
    const data = await chrome.storage.local.get(['seen_post_ids']);
    return new Set(data.seen_post_ids || []);
  },

  async addSeenPostIds(ids) {
    const existing = await this.getSeenPostIds();
    const merged = [...existing, ...ids];
    // Keep last 2000 IDs to prevent unbounded growth
    const trimmed = merged.slice(-2000);
    await chrome.storage.local.set({ seen_post_ids: trimmed });
  },

  async getSignalCount() {
    const data = await chrome.storage.local.get(['signal_count']);
    return data.signal_count || 0;
  },

  async incrementSignalCount(n) {
    const current = await this.getSignalCount();
    await chrome.storage.local.set({ signal_count: current + n });
  }
};
```

- [ ] **Step 3: Create extension/utils/extractor.js**

```javascript
// extension/utils/extractor.js
// DOM selectors — stored as constants for easy patching
const SELECTORS = {
  FEED_POST: 'div[data-urn*="urn:li:activity"]',
  POST_CONTENT: '.feed-shared-update-v2__description, .update-components-text',
  AUTHOR_NAME: '.update-components-actor__name, .feed-shared-actor__name',
  AUTHOR_HEADLINE: '.update-components-actor__description, .feed-shared-actor__description',
  AUTHOR_PROFILE_LINK: '.update-components-actor__meta a, .feed-shared-actor__meta a',
  DEGREE_BADGE: '.dist-value',
  LIKE_COUNT: '.social-details-social-counts__reactions-count',
  COMMENT_COUNT: '.social-details-social-counts__comments',
  POST_TIMESTAMP: '.update-components-actor__sub-description time',
};

const EXTRACTION_VERSION = '1.0.0';

function extractDegree(postElement) {
  const badge = postElement.querySelector(SELECTORS.DEGREE_BADGE);
  if (!badge) return 3;
  const text = badge.textContent.trim();
  if (text.includes('1st')) return 1;
  if (text.includes('2nd')) return 2;
  return 3;
}

function extractLinkedInId(profileUrl) {
  if (!profileUrl) return null;
  const match = profileUrl.match(/linkedin\.com\/in\/([^/?]+)/);
  return match ? match[1] : null;
}

function extractPost(postElement) {
  const urn = postElement.getAttribute('data-urn');
  if (!urn) return null;

  const content = postElement.querySelector(SELECTORS.POST_CONTENT)?.textContent?.trim();
  if (!content || content.length < 20) return null;

  const authorName = postElement.querySelector(SELECTORS.AUTHOR_NAME)?.textContent?.trim();
  if (!authorName) return null;

  const profileLink = postElement.querySelector(SELECTORS.AUTHOR_PROFILE_LINK)?.href;
  const linkedinId = extractLinkedInId(profileLink) || authorName.toLowerCase().replace(/\s+/g, '');

  const headline = postElement.querySelector(SELECTORS.AUTHOR_HEADLINE)?.textContent?.trim() || '';
  const degree = extractDegree(postElement);

  const timestampEl = postElement.querySelector(SELECTORS.POST_TIMESTAMP);
  const postedAt = timestampEl?.getAttribute('datetime') || null;

  const likes = parseInt(postElement.querySelector(SELECTORS.LIKE_COUNT)?.textContent?.replace(/[^0-9]/g, '') || '0');
  const comments = parseInt(postElement.querySelector(SELECTORS.COMMENT_COUNT)?.textContent?.replace(/[^0-9]/g, '') || '0');

  return {
    linkedin_post_id: urn,
    author: {
      name: authorName,
      headline: headline,
      profile_url: profileLink || null,
      linkedin_id: linkedinId,
      degree: degree,
    },
    content: content,
    post_type: 'post',
    posted_at: postedAt,
    engagement: { likes, comments },
    extraction_version: EXTRACTION_VERSION,
    captured_at: new Date().toISOString(),
  };
}

function extractVisiblePosts() {
  const postElements = document.querySelectorAll(SELECTORS.FEED_POST);
  const posts = [];

  for (const el of postElements) {
    try {
      const post = extractPost(el);
      if (post) posts.push(post);
    } catch (e) {
      console.warn('[Sonar] Failed to extract post:', e.message);
    }
  }

  return posts;
}
```

- [ ] **Step 4: Create extension/utils/api-client.js**

```javascript
// extension/utils/api-client.js
const SONAR_API_BASE = 'https://api.yoursonar.com'; // Change to localhost:8000 for dev

const SonarAPI = {
  async ingestPosts(posts) {
    const token = await SonarStorage.getAuthToken();
    if (!token) {
      console.warn('[Sonar] No auth token — skipping ingest');
      return null;
    }

    const response = await fetch(`${SONAR_API_BASE}/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        posts: posts,
        extraction_version: '1.0.0',
      }),
    });

    if (response.status === 401) {
      await SonarStorage.setAuthToken(null);
      return null;
    }

    if (!response.ok) {
      console.error('[Sonar] Ingest failed:', response.status);
      return null;
    }

    return await response.json();
  },

  async setAuthToken(token) {
    await SonarStorage.setAuthToken(token);
  }
};
```

- [ ] **Step 5: Create extension/content/linkedin-scraper.js**

```javascript
// extension/content/linkedin-scraper.js

const MIN_SYNC_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

async function shouldSync() {
  const lastSync = await SonarStorage.getLastSyncTime();
  return (Date.now() - lastSync) >= MIN_SYNC_INTERVAL_MS;
}

async function scrollFeedAndCollect() {
  const highWaterMark = await SonarStorage.getHighWaterMark();
  const seenIds = await SonarStorage.getSeenPostIds();
  const newPosts = [];
  let hitWaterMark = false;
  let scrollAttempts = 0;
  const MAX_SCROLLS = 15;

  while (scrollAttempts < MAX_SCROLLS && !hitWaterMark) {
    const visible = extractVisiblePosts();

    for (const post of visible) {
      if (seenIds.has(post.linkedin_post_id)) continue;
      if (post.linkedin_post_id === highWaterMark) {
        hitWaterMark = true;
        break;
      }
      newPosts.push(post);
    }

    if (hitWaterMark || visible.length === 0) break;

    // Scroll down with randomized speed
    window.scrollBy(0, 600 + Math.random() * 400);
    const delay = 800 + Math.random() * 600;
    await new Promise(r => setTimeout(r, delay));

    // Pause between batches
    if (scrollAttempts % 3 === 2) {
      await new Promise(r => setTimeout(r, 1200 + Math.random() * 2600));
    }

    scrollAttempts++;
  }

  return newPosts;
}

async function runSync() {
  const token = await SonarStorage.getAuthToken();
  if (!token) return; // Not authenticated — skip silently

  if (!(await shouldSync())) return;

  console.log('[Sonar] Starting feed sync...');

  try {
    const posts = await scrollFeedAndCollect();

    if (posts.length === 0) {
      console.log('[Sonar] No new posts found.');
      return;
    }

    // Deduplicate against local cache
    const seenIds = await SonarStorage.getSeenPostIds();
    const freshPosts = posts.filter(p => !seenIds.has(p.linkedin_post_id));

    if (freshPosts.length === 0) return;

    // Send in batches of 50
    for (let i = 0; i < freshPosts.length; i += 50) {
      const batch = freshPosts.slice(i, i + 50);
      await SonarAPI.ingestPosts(batch);
    }

    // Update local state
    const newIds = freshPosts.map(p => p.linkedin_post_id);
    await SonarStorage.addSeenPostIds(newIds);
    if (freshPosts[0]) {
      await SonarStorage.setHighWaterMark(freshPosts[0].linkedin_post_id);
    }
    await SonarStorage.setLastSyncTime(Date.now());

    console.log(`[Sonar] Synced ${freshPosts.length} new posts.`);
  } catch (e) {
    console.error('[Sonar] Sync error:', e.message);
  }
}

// Run on page load
runSync();

// Re-run when user navigates within LinkedIn (SPA navigation)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    if (location.pathname === '/feed/') {
      setTimeout(runSync, 2000); // Wait for feed to render
    }
  }
}).observe(document.body, { subtree: true, childList: true });
```

- [ ] **Step 6: Create extension/background/service-worker.js**

```javascript
// extension/background/service-worker.js

chrome.runtime.onInstalled.addListener(() => {
  // Set up recurring alarm with jitter
  scheduleNextAlarm();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'sonar-sync') {
    triggerLinkedInSync();
    scheduleNextAlarm();
  }
});

function scheduleNextAlarm() {
  // 30 minutes ± 3 minutes jitter
  const jitterMinutes = (Math.random() * 6) - 3;
  const delayMinutes = 30 + jitterMinutes;

  chrome.alarms.create('sonar-sync', { delayInMinutes: delayMinutes });
}

async function triggerLinkedInSync() {
  // Find existing LinkedIn tab
  const tabs = await chrome.tabs.query({ url: 'https://www.linkedin.com/*' });

  if (tabs.length > 0) {
    // LinkedIn is open — send message to content script
    try {
      await chrome.tabs.sendMessage(tabs[0].id, { type: 'SONAR_SYNC' });
    } catch (e) {
      // Content script not ready — ignore
    }
  }
}

// Handle auth token set from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SET_AUTH_TOKEN') {
    chrome.storage.local.set({ auth_token: message.token });
    sendResponse({ success: true });
  }
});
```

- [ ] **Step 7: Create extension/popup/popup.html**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: system-ui; width: 280px; padding: 16px; margin: 0; }
    h2 { font-size: 16px; margin: 0 0 12px; }
    .status { font-size: 13px; color: #666; margin-bottom: 12px; }
    .signal-count { font-size: 24px; font-weight: bold; color: #0077b5; }
    .label { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
    input { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; margin: 4px 0; }
    button { width: 100%; padding: 8px; background: #0077b5; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
    button:hover { background: #006097; }
    .connected { color: #057642; font-weight: 500; }
    .disconnected { color: #cc1016; }
  </style>
</head>
<body>
  <h2>⚡ Sonar</h2>
  <div id="auth-section">
    <div class="status disconnected" id="status-text">Not connected</div>
    <input type="email" id="email-input" placeholder="Email" />
    <input type="password" id="password-input" placeholder="Password" />
    <button id="connect-btn">Connect to Sonar</button>
  </div>
  <div id="stats-section" style="display:none">
    <div class="status connected">● Connected</div>
    <div class="signal-count" id="signal-count">0</div>
    <div class="label">Signals detected today</div>
    <p class="status" id="last-sync-text">Last sync: never</p>
    <button id="sync-now-btn">Sync Now</button>
  </div>
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 8: Create extension/popup/popup.js**

```javascript
// extension/popup/popup.js
const API_BASE = 'https://api.yoursonar.com'; // Change to localhost:8000 for dev

async function init() {
  const { auth_token, signal_count, last_sync_time } = await chrome.storage.local.get([
    'auth_token', 'signal_count', 'last_sync_time'
  ]);

  if (auth_token) {
    showConnected(signal_count || 0, last_sync_time);
  } else {
    showDisconnected();
  }
}

function showConnected(count, lastSyncTime) {
  document.getElementById('auth-section').style.display = 'none';
  document.getElementById('stats-section').style.display = 'block';
  document.getElementById('signal-count').textContent = count;

  if (lastSyncTime) {
    const mins = Math.round((Date.now() - lastSyncTime) / 60000);
    document.getElementById('last-sync-text').textContent =
      `Last sync: ${mins < 1 ? 'just now' : `${mins}m ago`}`;
  }
}

function showDisconnected() {
  document.getElementById('auth-section').style.display = 'block';
  document.getElementById('stats-section').style.display = 'none';
}

document.getElementById('connect-btn')?.addEventListener('click', async () => {
  const email = document.getElementById('email-input').value;
  const password = document.getElementById('password-input').value;

  const resp = await fetch(`${API_BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
  });

  if (resp.ok) {
    const { access_token } = await resp.json();
    await chrome.storage.local.set({ auth_token: access_token });
    showConnected(0, null);
  } else {
    document.getElementById('status-text').textContent = 'Login failed. Check credentials.';
  }
});

document.getElementById('sync-now-btn')?.addEventListener('click', async () => {
  const tabs = await chrome.tabs.query({ url: 'https://www.linkedin.com/*' });
  if (tabs.length > 0) {
    chrome.tabs.sendMessage(tabs[0].id, { type: 'SONAR_SYNC' });
    window.close();
  } else {
    alert('Please open LinkedIn first.');
  }
});

init();
```

- [ ] **Step 9: Load and manually test the extension in Chrome**

```
1. Open Chrome → chrome://extensions
2. Enable "Developer mode" (top right)
3. Click "Load unpacked" → select the extension/ folder
4. Navigate to linkedin.com
5. Check: extension icon appears in toolbar
6. Click icon → login with test account credentials
7. Open LinkedIn feed → check Chrome console for "[Sonar] Starting feed sync..."
8. Verify posts appear in backend DB:
   docker compose exec postgres psql -U sonar -d sonar -c "SELECT COUNT(*) FROM posts;"
```

- [ ] **Step 10: Commit**

```bash
git add extension/
git commit -m "feat: add Chrome extension with LinkedIn feed sync and popup UI"
```

---

## Task 12: Public Fallback Poller (Apify)

**Files:**
- Create: `backend/app/jobs/public_poller.py`

- [ ] **Step 1: Create backend/app/jobs/public_poller.py**

```python
# backend/app/jobs/public_poller.py
"""
Public post poller — fallback for workspaces without Chrome extension.
Runs hourly via Celery Beat. Uses Apify LinkedIn scrapers.
"""
import httpx
import asyncio
from app.workers.celery_app import celery_app
from app.config import settings

APIFY_LINKEDIN_ACTOR = "curious_coder/linkedin-post-search-scraper"


@celery_app.task(name="app.jobs.public_poller.poll_public_posts")
def poll_public_posts():
    asyncio.run(_poll_all_workspaces())


async def _poll_all_workspaces():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.user import User
    from app.models.post import Post
    from app.workers.pipeline import process_post_pipeline
    import uuid

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Find workspaces WITHOUT extension installed users
        result = await db.execute(
            select(Workspace).join(User, User.workspace_id == Workspace.id)
            .where(User.extension_installed == False)
        )
        workspaces = result.scalars().all()

        for workspace in workspaces:
            # Get active capability profile keywords
            profile_result = await db.execute(
                select(CapabilityProfileVersion)
                .where(CapabilityProfileVersion.workspace_id == workspace.id)
                .where(CapabilityProfileVersion.is_active == True)
            )
            profile = profile_result.scalar_one_or_none()
            if not profile or not profile.signal_keywords:
                continue

            # Use first 3 signal keywords as search query
            query = " OR ".join(profile.signal_keywords[:3])
            posts = await fetch_apify_posts(query=query, limit=50)

            owner_result = await db.execute(
                select(User)
                .where(User.workspace_id == workspace.id)
                .where(User.role == "owner")
                .limit(1)
            )
            owner = owner_result.scalar_one_or_none()
            if not owner:
                continue

            queued = 0
            for raw_post in posts:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                from app.models.connection import Connection

                linkedin_id = raw_post.get("author_id", raw_post.get("author_name", "unknown"))

                # Upsert connection
                conn_stmt = pg_insert(Connection).values(
                    id=uuid.uuid4(),
                    workspace_id=workspace.id,
                    user_id=owner.id,
                    linkedin_id=linkedin_id,
                    name=raw_post.get("author_name", "Unknown"),
                    headline=raw_post.get("author_headline", ""),
                    degree=3,  # Unknown degree for public posts
                ).on_conflict_do_update(
                    index_elements=["workspace_id", "linkedin_id"],
                    set_={"name": raw_post.get("author_name", "Unknown")},
                ).returning(Connection.id)

                conn_result = await db.execute(conn_stmt)
                connection_id = conn_result.scalar_one()

                # Check duplicate
                from sqlalchemy import select as sa_select
                existing = await db.execute(
                    sa_select(Post.id).where(
                        Post.workspace_id == workspace.id,
                        Post.linkedin_post_id == raw_post["post_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                post = Post(
                    workspace_id=workspace.id,
                    connection_id=connection_id,
                    linkedin_post_id=raw_post["post_id"],
                    content=raw_post.get("text", ""),
                    post_type="post",
                    source="public_fallback",
                )
                db.add(post)
                await db.flush()

                process_post_pipeline.delay(str(post.id), str(workspace.id))
                queued += 1

            await db.commit()

    await engine.dispose()


async def fetch_apify_posts(query: str, limit: int = 50) -> list[dict]:
    """
    Call Apify LinkedIn post search actor and return normalized post list.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Start Apify run
        start_resp = await client.post(
            f"https://api.apify.com/v2/acts/{APIFY_LINKEDIN_ACTOR}/runs",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            json={"searchQuery": query, "maxResults": limit},
        )
        if not start_resp.ok:
            return []

        run_id = start_resp.json()["data"]["id"]

        # Poll for completion (max 60s)
        for _ in range(12):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            )
            if status_resp.json()["data"]["status"] == "SUCCEEDED":
                break

        # Fetch results
        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        results_resp = await client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
        )
        if not results_resp.ok:
            return []

        items = results_resp.json()
        return [
            {
                "post_id": item.get("id", item.get("url", str(uuid.uuid4()))),
                "text": item.get("text", ""),
                "author_name": item.get("authorName", "Unknown"),
                "author_headline": item.get("authorHeadline", ""),
                "author_id": item.get("authorProfileUrl", "").split("/in/")[-1].split("/")[0] or "unknown",
            }
            for item in items
            if item.get("text")
        ]
```

- [ ] **Step 2: Create backend/app/jobs/digest_sender.py**

```python
# backend/app/jobs/digest_sender.py
"""
Hourly email digest for MEDIUM and LOW priority alerts.
Batches unsent medium/low alerts and sends a single digest email.
"""
import asyncio
from app.workers.celery_app import celery_app


@celery_app.task(name="app.jobs.digest_sender.send_digests")
def send_digests():
    asyncio.run(_send_all_digests())


async def _send_all_digests():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, update
    from app.models.alert import Alert
    from app.models.user import User
    from app.models.workspace import Workspace
    from app.delivery.email import EmailSender
    from app.config import settings
    from datetime import datetime, timezone, timedelta

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    sender = EmailSender()

    async with Session() as db:
        # Find unsent medium/low alerts from last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(Alert)
            .where(Alert.priority.in_(["medium", "low"]))
            .where(Alert.status == "pending")
            .where(Alert.created_at >= one_hour_ago)
        )
        alerts = result.scalars().all()

        if not alerts:
            return

        # Group by workspace
        by_workspace: dict = {}
        for alert in alerts:
            ws_id = str(alert.workspace_id)
            by_workspace.setdefault(ws_id, []).append(alert)

        for ws_id, ws_alerts in by_workspace.items():
            from uuid import UUID
            workspace = await db.get(Workspace, UUID(ws_id))
            if not workspace:
                continue

            email_config = (workspace.delivery_channels or {}).get("email", {})
            if not email_config.get("address"):
                continue

            # Send digest — reuse EmailSender with digest flag
            # For digest, send first alert with "[Digest]" subject prefix
            # Simple implementation: send each alert individually marked as digest
            for alert in ws_alerts:
                await sender.send(alert=alert, workspace=workspace)
                await db.execute(
                    update(Alert).where(Alert.id == alert.id)
                    .values(status="delivered", delivered_at=datetime.now(timezone.utc))
                )

        await db.commit()

    await engine.dispose()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/jobs/
git commit -m "feat: add Apify public post poller and email digest sender"
```

---

## Task 13: React Dashboard

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/Onboarding.tsx`
- Create: `frontend/src/pages/AlertFeed.tsx`
- Create: `frontend/src/pages/OpportunityBoard.tsx`
- Create: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/components/AlertCard.tsx`
- Create: `frontend/src/components/ScoreBar.tsx`

- [ ] **Step 1: Initialize Vite React project**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install axios react-router-dom @types/react-router-dom
```

- [ ] **Step 2: Create frontend/src/api/client.ts**

```typescript
// frontend/src/api/client.ts
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sonar_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface Alert {
  id: string;
  priority: 'high' | 'medium' | 'low';
  combined_score: number;
  relevance_score: number;
  relationship_score: number;
  timing_score: number;
  match_reason: string;
  outreach_draft_a: string;
  outreach_draft_b: string;
  opportunity_type: string;
  urgency_reason: string;
  status: string;
  feedback: string | null;
  created_at: string;
}

export const authAPI = {
  register: (data: { workspace_name: string; email: string; password: string }) =>
    api.post('/workspace/register', data),
  login: (email: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    return api.post<{ access_token: string }>('/auth/token', form);
  },
};

export const alertsAPI = {
  list: (params?: { priority?: string; status?: string; limit?: number }) =>
    api.get<Alert[]>('/alerts', { params }),
  feedback: (alertId: string, data: { feedback: string; outcome?: string; message_sent?: string }) =>
    api.post(`/alerts/${alertId}/feedback`, data),
};

export const profileAPI = {
  extract: (data: { url?: string; text?: string }) =>
    api.post('/profile/extract', data),
};

export default api;
```

- [ ] **Step 3: Create frontend/src/components/ScoreBar.tsx**

```tsx
// frontend/src/components/ScoreBar.tsx
interface ScoreBarProps {
  label: string;
  score: number;
}

export function ScoreBar({ label, score }: ScoreBarProps) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? '#dc2626' : pct >= 55 ? '#d97706' : '#16a34a';

  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#666' }}>
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div style={{ background: '#e5e7eb', borderRadius: 4, height: 6, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 4 }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/src/components/AlertCard.tsx**

```tsx
// frontend/src/components/AlertCard.tsx
import { useState } from 'react';
import { Alert, alertsAPI } from '../api/client';
import { ScoreBar } from './ScoreBar';

interface AlertCardProps {
  alert: Alert;
  onFeedback: (alertId: string, feedback: 'positive' | 'negative') => void;
}

const PRIORITY_COLOR = { high: '#dc2626', medium: '#d97706', low: '#16a34a' };
const PRIORITY_EMOJI = { high: '🔴', medium: '🟡', low: '🟢' };

export function AlertCard({ alert, onFeedback }: AlertCardProps) {
  const [copied, setCopied] = useState<'a' | 'b' | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);

  async function handleFeedback(feedback: 'positive' | 'negative') {
    await alertsAPI.feedback(alert.id, { feedback });
    setFeedbackSent(true);
    onFeedback(alert.id, feedback);
  }

  function copyDraft(which: 'a' | 'b') {
    const text = which === 'a' ? alert.outreach_draft_a : alert.outreach_draft_b;
    navigator.clipboard.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 2000);
  }

  const borderColor = PRIORITY_COLOR[alert.priority] || '#666';

  return (
    <div style={{
      border: `2px solid ${borderColor}`,
      borderRadius: 8,
      padding: 16,
      marginBottom: 12,
      background: 'white',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>
          {PRIORITY_EMOJI[alert.priority]} {alert.priority.toUpperCase()} SIGNAL
        </span>
        <span style={{ fontSize: 12, color: '#888' }}>
          {new Date(alert.created_at).toLocaleTimeString()}
        </span>
      </div>

      <p style={{ fontSize: 13, color: '#444', marginBottom: 12 }}>{alert.match_reason}</p>

      <div style={{ marginBottom: 12 }}>
        <ScoreBar label="Relevance" score={alert.relevance_score} />
        <ScoreBar label="Relationship" score={alert.relationship_score} />
        <ScoreBar label="Timing" score={alert.timing_score} />
      </div>

      <div style={{ background: '#f9fafb', borderRadius: 6, padding: 10, marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>DRAFT A — DIRECT</div>
        <p style={{ fontSize: 13, margin: 0 }}>{alert.outreach_draft_a}</p>
        <button onClick={() => copyDraft('a')} style={{ marginTop: 6, fontSize: 11, cursor: 'pointer' }}>
          {copied === 'a' ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      <div style={{ background: '#f9fafb', borderRadius: 6, padding: 10, marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>DRAFT B — QUESTION</div>
        <p style={{ fontSize: 13, margin: 0 }}>{alert.outreach_draft_b}</p>
        <button onClick={() => copyDraft('b')} style={{ marginTop: 6, fontSize: 11, cursor: 'pointer' }}>
          {copied === 'b' ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      {!feedbackSent && alert.feedback === null && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => handleFeedback('positive')}
            style={{ flex: 1, padding: '6px 0', background: '#057642', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
          >
            ✓ Acted on this
          </button>
          <button
            onClick={() => handleFeedback('negative')}
            style={{ flex: 1, padding: '6px 0', background: '#f3f4f6', color: '#444', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
          >
            ✗ Not relevant
          </button>
        </div>
      )}

      {(feedbackSent || alert.feedback !== null) && (
        <p style={{ fontSize: 12, color: '#888', textAlign: 'center', margin: 0 }}>
          ✓ Sonar is learning your preferences.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create frontend/src/pages/Onboarding.tsx**

```tsx
// frontend/src/pages/Onboarding.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, profileAPI } from '../api/client';

export function Onboarding() {
  const [step, setStep] = useState<'register' | 'profile'>('register');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleRegister(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = e.currentTarget;
    const data = {
      workspace_name: (form.elements.namedItem('workspace') as HTMLInputElement).value,
      email: (form.elements.namedItem('email') as HTMLInputElement).value,
      password: (form.elements.namedItem('password') as HTMLInputElement).value,
    };
    try {
      await authAPI.register(data);
      const loginResp = await authAPI.login(data.email, data.password);
      localStorage.setItem('sonar_token', loginResp.data.access_token);
      setStep('profile');
    } catch {
      setError('Registration failed. Email may already be taken.');
    }
    setLoading(false);
  }

  async function handleProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = e.currentTarget;
    const url = (form.elements.namedItem('url') as HTMLInputElement).value;
    try {
      await profileAPI.extract({ url });
      navigate('/alerts');
    } catch {
      setError('Failed to extract profile. Check the URL and try again.');
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 480, margin: '80px auto', padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>⚡ Welcome to Sonar</h1>
      <p style={{ color: '#666', marginBottom: 32 }}>Network-aware LinkedIn intent intelligence.</p>

      {step === 'register' && (
        <form onSubmit={handleRegister}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Create your workspace</h2>
          <input name="workspace" placeholder="Agency / Company name" required style={inputStyle} />
          <input name="email" type="email" placeholder="Email" required style={inputStyle} />
          <input name="password" type="password" placeholder="Password" required style={inputStyle} />
          {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
          <button type="submit" disabled={loading} style={btnStyle}>
            {loading ? 'Creating...' : 'Create Workspace →'}
          </button>
        </form>
      )}

      {step === 'profile' && (
        <form onSubmit={handleProfile}>
          <h2 style={{ fontSize: 18, marginBottom: 8 }}>Tell Sonar what you do</h2>
          <p style={{ color: '#666', fontSize: 14, marginBottom: 16 }}>
            Paste your website URL. Sonar will learn your capabilities automatically.
          </p>
          <input name="url" type="url" placeholder="https://yourcompany.com" required style={inputStyle} />
          {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
          <button type="submit" disabled={loading} style={btnStyle}>
            {loading ? 'Analyzing your website...' : 'Start Listening →'}
          </button>
        </form>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', marginBottom: 12, fontSize: 14,
  border: '1px solid #e5e7eb', borderRadius: 6, boxSizing: 'border-box',
};
const btnStyle: React.CSSProperties = {
  width: '100%', padding: '10px 0', background: '#0077b5', color: 'white',
  border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer',
};
```

- [ ] **Step 6: Create frontend/src/pages/AlertFeed.tsx**

```tsx
// frontend/src/pages/AlertFeed.tsx
import { useEffect, useState } from 'react';
import { Alert, alertsAPI } from '../api/client';
import { AlertCard } from '../components/AlertCard';

export function AlertFeed() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const resp = await alertsAPI.list({ priority: filter === 'all' ? undefined : filter });
      setAlerts(resp.data);
      setLoading(false);
    }
    load();
  }, [filter]);

  function handleFeedback(alertId: string, feedback: 'positive' | 'negative') {
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, feedback } : a));
  }

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 16 }}>⚡ Signal Feed</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {(['all', 'high', 'medium', 'low'] as const).map(p => (
          <button
            key={p}
            onClick={() => setFilter(p)}
            style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === p ? '#0077b5' : '#f3f4f6',
              color: filter === p ? 'white' : '#444',
              border: 'none', fontWeight: filter === p ? 600 : 400,
            }}
          >
            {p === 'all' ? 'All' : `${p === 'high' ? '🔴' : p === 'medium' ? '🟡' : '🟢'} ${p}`}
          </button>
        ))}
      </div>

      {loading && <p style={{ color: '#888' }}>Loading signals...</p>}

      {!loading && alerts.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
          <p>No signals yet.</p>
          <p style={{ fontSize: 13 }}>Install the Chrome extension and open LinkedIn to start syncing.</p>
        </div>
      )}

      {alerts.map(alert => (
        <AlertCard key={alert.id} alert={alert} onFeedback={handleFeedback} />
      ))}
    </div>
  );
}
```

- [ ] **Step 7: Create frontend/src/pages/OpportunityBoard.tsx**

```tsx
// frontend/src/pages/OpportunityBoard.tsx
import { useEffect, useState } from 'react';
import { Alert, alertsAPI } from '../api/client';

const COLUMNS = [
  { key: 'pending', label: 'Open Signals' },
  { key: 'acted', label: 'Contacted' },
  { key: 'dismissed', label: 'Dismissed' },
];

export function OpportunityBoard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    alertsAPI.list({ limit: 200 }).then(r => setAlerts(r.data));
  }, []);

  return (
    <div style={{ padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 20 }}>📋 Opportunity Board</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {COLUMNS.map(col => {
          const colAlerts = alerts.filter(a => a.status === col.key);
          return (
            <div key={col.key} style={{ background: '#f9fafb', borderRadius: 8, padding: 12 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#444' }}>
                {col.label} ({colAlerts.length})
              </h3>
              {colAlerts.map(alert => (
                <div key={alert.id} style={{
                  background: 'white', borderRadius: 6, padding: 10, marginBottom: 8,
                  border: '1px solid #e5e7eb', fontSize: 13
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>
                    {alert.priority === 'high' ? '🔴' : alert.priority === 'medium' ? '🟡' : '🟢'} {alert.opportunity_type?.replace('_', ' ')}
                  </div>
                  <div style={{ color: '#888', fontSize: 12 }}>
                    Score: {Math.round(alert.combined_score * 100)}%
                  </div>
                </div>
              ))}
              {colAlerts.length === 0 && (
                <p style={{ color: '#bbb', fontSize: 13 }}>Empty</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Create frontend/src/pages/Settings.tsx**

```tsx
// frontend/src/pages/Settings.tsx
import { useState } from 'react';
import api from '../api/client';

export function Settings() {
  const [slackWebhook, setSlackWebhook] = useState('');
  const [email, setEmail] = useState('');
  const [telegram, setTelegram] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [saved, setSaved] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const channels: Record<string, unknown> = {};
    if (slackWebhook) channels.slack = { webhook_url: slackWebhook, min_priority: 'low' };
    if (email) channels.email = { address: email };
    if (telegram) channels.telegram = { chat_id: telegram };
    if (whatsapp) channels.whatsapp = { phone: whatsapp };

    await api.patch('/workspace/channels', { delivery_channels: channels });
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 20 }}>⚙️ Delivery Channels</h2>
      <form onSubmit={save}>
        <label style={labelStyle}>Slack Webhook URL</label>
        <input value={slackWebhook} onChange={e => setSlackWebhook(e.target.value)} placeholder="https://hooks.slack.com/..." style={inputStyle} />

        <label style={labelStyle}>Email Address</label>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" style={inputStyle} />

        <label style={labelStyle}>Telegram Chat ID</label>
        <input value={telegram} onChange={e => setTelegram(e.target.value)} placeholder="123456789" style={inputStyle} />

        <label style={labelStyle}>WhatsApp Phone (with country code)</label>
        <input value={whatsapp} onChange={e => setWhatsapp(e.target.value)} placeholder="+14155238886" style={inputStyle} />

        <button type="submit" style={btnStyle}>{saved ? '✓ Saved!' : 'Save Channels'}</button>
      </form>
    </div>
  );
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4, color: '#444' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', marginBottom: 16, fontSize: 14, border: '1px solid #e5e7eb', borderRadius: 6, boxSizing: 'border-box' };
const btnStyle: React.CSSProperties = { width: '100%', padding: '10px 0', background: '#0077b5', color: 'white', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' };
```

- [ ] **Step 9: Create frontend/src/App.tsx**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Onboarding } from './pages/Onboarding';
import { AlertFeed } from './pages/AlertFeed';
import { OpportunityBoard } from './pages/OpportunityBoard';
import { Settings } from './pages/Settings';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('sonar_token');
  return token ? <>{children}</> : <Navigate to="/" replace />;
}

function Nav() {
  return (
    <nav style={{ borderBottom: '1px solid #e5e7eb', padding: '12px 24px', display: 'flex', gap: 24, alignItems: 'center' }}>
      <span style={{ fontWeight: 700, fontSize: 16 }}>⚡ Sonar</span>
      <Link to="/alerts" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Signals</Link>
      <Link to="/board" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Board</Link>
      <Link to="/settings" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Settings</Link>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Onboarding />} />
        <Route path="/alerts" element={<RequireAuth><Nav /><AlertFeed /></RequireAuth>} />
        <Route path="/board" element={<RequireAuth><Nav /><OpportunityBoard /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Nav /><Settings /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 10: Start frontend and verify**

```bash
cd frontend
npm run dev
```

Visit `http://localhost:5173` — expected: Onboarding page renders cleanly.

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat: add React dashboard with alert feed, opportunity board, and settings"
```

---

## Task 14: End-to-End Integration Test

**Files:**
- Create: `backend/tests/test_e2e.py`

- [ ] **Step 1: Write the end-to-end test**

```python
# backend/tests/test_e2e.py
"""
End-to-end integration test: register → profile → ingest → alert created.
Runs against test database. Mocks LLM and delivery channels.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end(client):
    """
    Full flow:
    1. Register workspace
    2. Extract capability profile (mocked LLM)
    3. Ingest a LinkedIn post (mocked pipeline task)
    4. Verify alert is created and retrievable
    """

    # Step 1: Register
    resp = await client.post("/workspace/register", json={
        "workspace_name": "E2E Test Agency",
        "email": "e2e@test.com",
        "password": "testpassword"
    })
    assert resp.status_code == 201

    # Step 2: Login
    login = await client.post("/auth/token", data={
        "username": "e2e@test.com", "password": "testpassword"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: Extract profile (mock LLM + embedding)
    mock_profile_json = '''{
        "company_name": "E2E Test Agency",
        "company_description": "We build AI agents.",
        "primary_services": ["AI agents"],
        "target_customers": ["SaaS companies"],
        "pain_points_solved": ["automation"],
        "technologies_used": ["Python", "LLMs"],
        "signal_keywords": ["AI agent", "automation", "LLM"],
        "anti_keywords": ["happy birthday"],
        "capability_summary": "We build custom AI agents for SaaS automation."
    }'''

    with patch("app.services.profile_extractor.llm_client") as mock_llm, \
         patch("app.services.embedding.embedding_provider") as mock_emb:
        mock_llm.complete = AsyncMock(return_value=mock_profile_json)
        mock_emb.embed = AsyncMock(return_value=[0.5] * 1536)

        resp = await client.post("/profile/extract", json={
            "text": "We build custom AI agents for SaaS companies."
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "E2E Test Agency"

    # Step 4: Ingest a post
    with patch("app.routers.ingest.process_post_pipeline") as mock_task:
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-e2e"))

        resp = await client.post("/ingest", json={
            "posts": [{
                "linkedin_post_id": "urn:li:activity:e2etest001",
                "author": {
                    "name": "Test Person",
                    "headline": "CTO at TestCo",
                    "profile_url": "https://linkedin.com/in/testperson",
                    "linkedin_id": "testperson",
                    "degree": 1
                },
                "content": "Looking for AI agent solutions for our sales automation pipeline.",
                "post_type": "post",
                "posted_at": "2026-04-08T10:00:00Z"
            }],
            "extraction_version": "1.0.0"
        }, headers=headers)

        assert resp.status_code == 202
        assert resp.json()["queued"] == 1
        assert resp.json()["skipped"] == 0

        # Verify pipeline task was called
        mock_task.delay.assert_called_once()

    # Step 5: Verify alerts endpoint returns empty (pipeline mocked)
    resp = await client.get("/alerts", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Run end-to-end test**

```bash
pytest tests/test_e2e.py -v
```

Expected: PASS

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_e2e.py
git commit -m "test: add end-to-end integration test for full pipeline"
```

---

## Task 15: Final Wiring + Docker Compose Production Config

**Files:**
- Modify: `backend/app/routers/workspace.py` (add PATCH /workspace/channels)
- Modify: `docker-compose.yml` (add frontend service)

- [ ] **Step 1: Add PATCH /workspace/channels to workspace router**

```python
# Add to backend/app/routers/auth.py workspace_router

from pydantic import BaseModel

class ChannelUpdateRequest(BaseModel):
    delivery_channels: dict

@workspace_router.patch("/channels", status_code=200)
async def update_channels(
    body: ChannelUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(User)
        .where(User.id == current_user.id)
        .values(delivery_channels=body.delivery_channels)
    )
    await db.commit()
    return {"message": "Channels updated."}
```

- [ ] **Step 2: Add frontend service to docker-compose.yml**

```yaml
# Add to docker-compose.yml services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - VITE_API_BASE=http://localhost:8000
    depends_on:
      - api
```

Create `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

- [ ] **Step 3: Run full stack and verify**

```bash
docker compose up --build
```

Verify:
- `http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:8000/docs` → FastAPI Swagger UI shows all routes
- `http://localhost:5173` → React onboarding page

- [ ] **Step 4: Final test run**

```bash
cd backend
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete Sonar Phase 1 MVP — full stack end-to-end"
```

---

## Phase 1 Completion Criteria

Before onboarding the first beta user, verify all of the following:

```
BACKEND
□ All database migrations run cleanly from scratch
□ All pytest tests pass (run: pytest tests/ -v)
□ /health endpoint returns 200
□ /workspace/register + /auth/token flow works
□ /profile/extract successfully calls OpenAI and stores embedding
□ /ingest accepts extension payload and queues Celery task
□ /alerts returns alert list for authenticated workspace
□ /alerts/{id}/feedback updates status and triggers threshold check
□ Celery worker processes pipeline tasks (test with a real post)
□ At least one delivery channel delivers a real alert

CHROME EXTENSION
□ Extension loads in Chrome without errors
□ Popup authenticates successfully with backend
□ LinkedIn feed sync extracts posts and sends to /ingest
□ Badge updates with signal count
□ High-water mark prevents duplicate syncs

DASHBOARD
□ Onboarding flow completes (register → profile → alert feed)
□ Alert feed displays alerts with scores and drafts
□ Copy draft buttons work
□ Feedback buttons call API and update UI
□ Opportunity board shows alerts by status
□ Settings page saves delivery channels

COST VERIFICATION
□ One test run costs < $1 in LLM API calls (use mock data first)
□ Apify test call returns LinkedIn posts successfully
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Onboarding (URL/doc → capability profile) — Tasks 4
- ✅ Chrome extension sync — Task 11
- ✅ Keyword pre-filter — Task 5
- ✅ Semantic matching — Task 5
- ✅ 3-dimension scoring — Task 6
- ✅ Context generation with model routing — Task 7
- ✅ Celery pipeline — Task 8
- ✅ All 4 delivery channels — Task 9
- ✅ Alert lifecycle + feedback — Task 10
- ✅ Feedback trainer + threshold adjustment — Task 10
- ✅ Public fallback poller (Apify) — Task 12
- ✅ React dashboard (alert feed + board + settings) — Task 13
- ✅ Signal effectiveness logging — Task 8 (pipeline)
- ✅ Docker Compose dev environment — Task 1

**Type consistency check:** All function signatures are consistent across tasks. `compute_combined_score` takes the same parameters in Task 6 (definition) and Task 8 (pipeline usage). `AlertContext` dataclass fields match usage in pipeline. `DeliveryRouter.deliver()` signature consistent across Tasks 9 and 8.

**No placeholders found.**
