# Sonar

**Network-aware LinkedIn intent intelligence for B2B revenue teams.**

Sonar monitors your LinkedIn network in real time, detects intent signals the moment they surface, and delivers prioritized alerts with AI-drafted outreach — so you spend zero time finding opportunities and 100% of your time closing them.

> The key insight: every existing tool (Trigify, Octolens, Intently) monitors the public LinkedIn feed — millions of strangers. Sonar monitors *your* network. A warm signal from someone who already knows you is worth 10× a cold signal from a stranger.

---

## How It Works

```
You describe what you do (URL or text)
        ↓
Sonar learns your capability profile (LLM + embeddings)
        ↓
Chrome extension monitors your LinkedIn network's posts
        ↓
AI matches posts against your capability profile
        ↓
Real-time alert: who posted, why it's relevant, what to say
        ↓
You reach out — warm, timely, relevant
        ↓
Deal starts
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Chrome Extension (MV3)                                 │
│  LinkedIn feed → DOM extraction → POST /ingest          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI (port 8000)                                    │
│  /workspace  /auth  /profile  /ingest  /alerts          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Celery Workers                                         │
│                                                         │
│  process_post_pipeline                                  │
│  ├── keyword_filter      (anti-keyword early exit)      │
│  ├── embedding           (OpenAI text-embedding-3-small)│
│  ├── matcher             (cosine similarity vs profile) │
│  ├── scorer              (relevance × relationship ×    │
│  │                        timing → combined score)      │
│  ├── context_generator   (match reason + 2 drafts)      │
│  │   ├── HIGH  → GPT-4o mini                           │
│  │   └── MED/LOW → Groq Llama 3.3 70B (free)           │
│  └── delivery_router     (Slack / email / Telegram /    │
│                            WhatsApp — fan-out)          │
│                                                         │
│  Celery Beat jobs (hourly)                              │
│  ├── public_poller       (Apify fallback for non-ext.)  │
│  └── digest_sender       (batch medium/low via email)   │
└──────────────┬──────────────────┬───────────────────────┘
               │                  │
┌──────────────▼──────┐  ┌────────▼────────────────────────┐
│  PostgreSQL + pgvect│  │  Redis (broker + result backend) │
│  9 tables, 1536-dim │  └─────────────────────────────────┘
│  vector embeddings  │
└─────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  React Dashboard (port 5173)                            │
│  Onboarding → Alert Feed → Opportunity Board → Settings │
└─────────────────────────────────────────────────────────┘
```

---

## Scoring Model

Each post is scored across three dimensions and combined into a single priority:

| Dimension | Weight | Signal |
|---|---|---|
| **Relevance** | 50% | Cosine similarity between post embedding and capability profile embedding |
| **Relationship** | 30% | Connection degree (1st=0.90, 2nd=0.60, 3rd=0.30) + interaction boost (+0.15) |
| **Timing** | 20% | Linear decay over 24 hours (fresh post = 1.0, 24h old = 0.0) |

| Priority | Combined Score | Routing |
|---|---|---|
| 🔴 HIGH | ≥ 0.80 | Instant alert via all configured channels + GPT-4o mini drafts |
| 🟡 MEDIUM | ≥ 0.55 | Alert + hourly email digest + Groq Llama drafts |
| 🟢 LOW | < 0.55 | Queued for digest only |

Thresholds auto-adjust based on your feedback: if fewer than 40% of recent alerts are acted on, the threshold rises by 0.02. If more than 75% are acted on, it lowers by 0.01.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115, Python 3.12 |
| Task queue | Celery 5.4 + Redis 7 |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| LLM (high priority) | OpenAI GPT-4o mini |
| LLM (med/low) | Groq Llama 3.3 70B (free tier) |
| Email | SendGrid |
| WhatsApp | Twilio |
| Telegram | python-telegram-bot |
| Public fallback | Apify LinkedIn post scraper |
| Frontend | React 18, Vite, TypeScript |
| Extension | Chrome MV3 |
| Auth | JWT (python-jose, bcrypt) |
| ORM | SQLAlchemy 2.0 (async) |

---

## Quickstart

### Prerequisites

- Docker and Docker Compose
- API keys for: OpenAI, Groq, SendGrid, Twilio, Telegram, Apify (only configure the channels you need)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/sonar.git
cd sonar
cp .env.example .env
```

Edit `.env` and fill in your credentials. At minimum, you need:

```env
DATABASE_URL=postgresql+asyncpg://sonar:sonar@postgres:5432/sonar
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-to-a-random-32-char-string
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
```

### 2. Start the stack

```bash
docker compose up --build
```

This starts:
- `postgres` — PostgreSQL 16 with pgvector on port 5432
- `redis` — Redis 7 on port 6379
- `api` — FastAPI on port 8000 (auto-reload)
- `worker` — Celery worker
- `beat` — Celery Beat (hourly jobs)
- `frontend` — Vite React dev server on port 5173

### 3. Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Verify

```
http://localhost:8000/health   → {"status": "ok"}
http://localhost:8000/docs     → Swagger UI (all routes)
http://localhost:5173          → React onboarding page
```

### 5. Install the Chrome extension

See [extension/README.md](extension/README.md).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✓ | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | ✓ | Redis URL (`redis://redis:6379/0`) |
| `SECRET_KEY` | ✓ | JWT signing secret (min 32 chars, random) |
| `OPENAI_API_KEY` | ✓ | OpenAI key for embeddings + GPT-4o mini |
| `GROQ_API_KEY` | ✓ | Groq key for Llama 3.3 70B (free tier available) |
| `SENDGRID_API_KEY` | Email alerts | SendGrid API key |
| `SENDGRID_FROM_EMAIL` | Email alerts | Verified sender address |
| `TWILIO_ACCOUNT_SID` | WhatsApp alerts | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | WhatsApp alerts | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | WhatsApp alerts | WhatsApp sender number (`whatsapp:+14155238886`) |
| `TELEGRAM_BOT_TOKEN` | Telegram alerts | Bot token from @BotFather |
| `APIFY_API_TOKEN` | Public fallback poller | Apify API token |
| `EXTENSION_VERSION` | | Current extension version (default: `1.0.0`) |

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`.

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/workspace/register` | Create workspace + owner user |
| `POST` | `/auth/token` | Login, returns JWT |
| `PATCH` | `/workspace/channels` | Update delivery channel config |

### Profile

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/profile/extract` | Extract capability profile from URL or text (LLM) |

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` | Submit posts from Chrome extension (batch) |

### Alerts

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/alerts` | List alerts (filterable by `priority`, `status`) |
| `POST` | `/alerts/{id}/feedback` | Submit positive/negative feedback |

---

## Project Structure

```
sonar/
├── backend/
│   ├── app/
│   │   ├── config.py            # Settings (pydantic-settings v2, @lru_cache)
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── main.py              # FastAPI app + router registration
│   │   ├── models/              # SQLAlchemy ORM models (7 files)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # FastAPI route handlers
│   │   │   ├── auth.py          # /auth + /workspace
│   │   │   ├── profile.py       # /profile
│   │   │   ├── ingest.py        # /ingest
│   │   │   └── alerts.py        # /alerts
│   │   ├── services/
│   │   │   ├── profile_extractor.py   # LLM capability profile extraction
│   │   │   ├── keyword_filter.py      # Fast anti-keyword pre-filter
│   │   │   ├── embedding.py           # OpenAI embedding provider
│   │   │   ├── matcher.py             # Cosine similarity matching
│   │   │   ├── scorer.py              # 3-dimension scoring engine
│   │   │   ├── context_generator.py   # LLM match reason + outreach drafts
│   │   │   └── feedback_trainer.py    # Threshold auto-adjustment
│   │   ├── delivery/
│   │   │   ├── router.py        # Fan-out to all configured channels
│   │   │   ├── slack.py
│   │   │   ├── email.py
│   │   │   ├── telegram.py
│   │   │   └── whatsapp.py
│   │   ├── workers/
│   │   │   ├── celery_app.py    # Celery config + Beat schedule
│   │   │   └── pipeline.py      # Full post → alert pipeline task
│   │   └── jobs/
│   │       ├── public_poller.py # Hourly Apify scraper fallback
│   │       └── digest_sender.py # Hourly medium/low email digest
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # 11 unit tests + 1 e2e test
│   └── pyproject.toml
├── extension/                   # Chrome MV3 extension
├── frontend/                    # React 18 + Vite dashboard
├── docs/
│   ├── specs/                   # Product design spec
│   └── plans/                   # Phase 1 implementation plan
├── docker-compose.yml
└── .env.example
```

---

## Running Tests

```bash
# From repo root — runs against a test database (sonar_test)
docker compose exec api pytest tests/ -v
```

The test suite uses a real PostgreSQL test database (no mocks for DB), with LLM calls mocked via `unittest.mock`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ Complete | Core pipeline: extension → ingest → match → alert → deliver |
| Phase 2 | Planned | Network map, trending topics, weekly intelligence brief |
| Phase 3 | Planned | Full relationship memory, CRM sync, account-level scoring |
| Phase 4 | Planned | White-label API, enterprise, predictive conversion scoring |

---

## License

MIT
