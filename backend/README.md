# Sonar Backend

FastAPI + Celery + PostgreSQL/pgvector backend for the Sonar intent intelligence platform.

---

## Services

| Service | Command | Port |
|---|---|---|
| API | `uvicorn app.main:app --reload` | 8000 |
| Worker | `celery -A app.workers.celery_app worker` | — |
| Beat | `celery -A app.workers.celery_app beat` | — |

All three run inside Docker. See the root `docker-compose.yml`.

---

## Local Development

### With Docker (recommended)

```bash
# From repo root
docker compose up --build

# Run migrations (first time or after schema changes)
docker compose exec api alembic upgrade head

# Tail logs for the worker
docker compose logs -f worker
```

### Running Tests

```bash
docker compose exec api pytest tests/ -v --tb=short
```

Tests run against a separate `sonar_test` database (created automatically). The conftest sets up and tears down tables per session. LLM calls and external HTTP are mocked.

```bash
# Run a single test file
docker compose exec api pytest tests/test_scorer.py -v

# Run the end-to-end test
docker compose exec api pytest tests/test_e2e.py -v
```

---

## Database Migrations

```bash
# Apply all pending migrations
docker compose exec api alembic upgrade head

# Create a new migration after changing models
docker compose exec api alembic revision --autogenerate -m "description"

# Downgrade one step
docker compose exec api alembic downgrade -1

# Show current migration state
docker compose exec api alembic current
```

The initial migration (`001_initial_schema.py`) creates 9 tables and installs the pgvector extension. The `embedding vector(1536)` column on the `posts` table uses a raw `ALTER TABLE` statement because SQLAlchemy's `autogenerate` doesn't know the `vector` type — this is intentional.

---

## Pipeline Walkthrough

When the Chrome extension submits posts to `POST /ingest`, each post is stored and a Celery task is queued. The pipeline runs asynchronously:

```
process_post_pipeline (Celery task)
│
├── 1. keyword_filter
│   Checks post content against the workspace's anti_keywords list.
│   Posts matching any anti-keyword are discarded immediately (no LLM cost).
│
├── 2. embedding
│   Calls OpenAI text-embedding-3-small to produce a 1536-dim vector.
│   The vector is stored on the post row for future reuse.
│
├── 3. matcher
│   Computes cosine similarity between the post embedding and the
│   workspace's capability profile embedding. Posts below the workspace's
│   match_threshold are discarded.
│
├── 4. scorer
│   Computes the 3-dimension combined score:
│     combined = relevance×0.50 + relationship×0.30 + timing×0.20
│   Classifies into HIGH (≥0.80), MEDIUM (≥0.55), or LOW (<0.55).
│
├── 5. context_generator
│   Routes to LLM based on priority:
│     HIGH  → GPT-4o mini (faster, more reliable)
│     MED/LOW → Groq Llama 3.3 70B (free tier)
│   Produces: match_reason, outreach_draft_a (direct), outreach_draft_b (question)
│
├── 6. Alert record created in database
│
└── 7. delivery_router
    Fan-out to all configured channels in parallel (asyncio.gather):
      - Slack (webhook)
      - Email (SendGrid)
      - Telegram (bot)
      - WhatsApp (Twilio)
    Each channel checks the alert's priority against its min_priority setting.
```

---

## Configuration

Settings are loaded via pydantic-settings v2. The `@lru_cache` pattern on `get_settings()` avoids module-level instantiation — critical for test isolation.

```python
from app.config import get_settings
settings = get_settings()
```

Never import `settings` as a module-level object. Always call `get_settings()`.

---

## Key Design Decisions

**`@lru_cache` + `get_settings()`** — prevents eager instantiation at import time, which would break alembic migrations and test fixtures that need to override settings.

**`asyncio.run()` in Celery tasks** — Celery workers are synchronous; `asyncio.run()` is the standard pattern for bridging sync Celery and async SQLAlchemy/httpx code.

**`sqlalchemy.text()` for raw SQL** — all raw SQL (pgvector ALTER TABLE, embedding updates) uses parameterized `text()` calls to prevent SQL injection, never f-strings.

**Pydantic v2 schemas** — all schemas use `model_config = {"from_attributes": True}` (not the v1 `class Config` inner class).

---

## Project Structure

```
backend/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models/
│   │   ├── workspace.py    # Workspace, CapabilityProfileVersion
│   │   ├── user.py         # User
│   │   ├── connection.py   # Connection (unique: workspace_id + linkedin_id)
│   │   ├── post.py         # Post (unique: workspace_id + linkedin_post_id)
│   │   ├── alert.py        # Alert
│   │   ├── outreach.py     # OutreachHistory
│   │   └── feedback.py     # FeedbackAdjustment, SignalEffectiveness
│   ├── schemas/
│   │   ├── workspace.py
│   │   ├── ingest.py
│   │   └── alert.py
│   ├── routers/
│   │   ├── auth.py         # /auth/token, /workspace/register, /workspace/channels
│   │   ├── profile.py      # /profile/extract
│   │   ├── ingest.py       # /ingest
│   │   └── alerts.py       # /alerts, /alerts/{id}/feedback
│   ├── services/
│   │   ├── profile_extractor.py
│   │   ├── keyword_filter.py
│   │   ├── embedding.py
│   │   ├── matcher.py
│   │   ├── scorer.py
│   │   ├── context_generator.py
│   │   ├── llm.py          # LLM provider abstraction (OpenAI + Groq)
│   │   └── feedback_trainer.py
│   ├── delivery/
│   │   ├── router.py
│   │   ├── slack.py
│   │   ├── email.py
│   │   ├── telegram.py
│   │   └── whatsapp.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── pipeline.py
│   └── jobs/
│       ├── public_poller.py
│       └── digest_sender.py
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── conftest.py          # Async test client + test DB fixtures
│   ├── test_auth.py
│   ├── test_profile_extractor.py
│   ├── test_keyword_filter.py
│   ├── test_matcher.py
│   ├── test_scorer.py
│   ├── test_context_generator.py
│   ├── test_ingest_router.py
│   ├── test_alerts_router.py
│   ├── test_delivery_router.py
│   ├── test_feedback_trainer.py
│   └── test_e2e.py
└── pyproject.toml
```
