# Sonar — Product Design Specification
**Version:** 1.0  
**Date:** 2026-04-07  
**Status:** Approved for implementation planning  

---

## Table of Contents

1. [Product Vision & Core Thesis](#1-product-vision--core-thesis)
2. [System Architecture](#2-system-architecture)
3. [Data Model](#3-data-model)
4. [Chrome Extension Design](#4-chrome-extension-design)
5. [Matching Engine & AI Layer](#5-matching-engine--ai-layer)
6. [Alert Generation & Delivery Layer](#6-alert-generation--delivery-layer)
7. [Phased Roadmap & Success Metrics](#7-phased-roadmap--success-metrics)

---

## 1. Product Vision & Core Thesis

### What Sonar Is

Sonar is the relationship intelligence OS for B2B revenue teams. It monitors your LinkedIn network in real-time, detects intent signals the moment they surface, and delivers prioritized alerts with AI-crafted outreach — so you spend zero time finding opportunities and 100% of your time closing them. The longer you use Sonar, the smarter it gets: learning your network, your capabilities, and what signals actually convert for your specific business.

### The Problem

Agency owners and B2B founders scroll LinkedIn daily. They see posts from connections that signal a need for their services — someone struggling with AI integration, evaluating a new tool, posting about a pain point. But the moment passes. Crafting a relevant outreach feels like work. By the time they act, the window is closed and a competitor has moved in.

### The Core Value Loop

```
You describe what you do (URL / About Us doc)
        ↓
Sonar learns your capability profile
        ↓
Chrome extension monitors your LinkedIn network's posts
        ↓
AI matches posts against your capability profile
        ↓
You get a real-time alert: who posted, what they said,
why it's relevant, what to say
        ↓
You reach out manually — warm, timely, relevant
        ↓
Deal starts
```

### What Makes Sonar Different

Every existing tool (Trigify, Octolens, Intently) monitors the public LinkedIn feed — millions of strangers posting publicly. Sonar monitors *your* network — people who already have a degree of connection to you. A warm signal from someone who knows you is worth 10x a cold signal from a stranger.

The Chrome extension running in the user's own authenticated LinkedIn session is the technical unlock — accessing their own data, legally, without dependency on LinkedIn's restricted API.

### The Full Product Vision (3-Year)

| Horizon | What Sonar Does |
|---|---|
| Today (Phase 1) | Detects intent signals from your LinkedIn network. Alerts you instantly with AI outreach draft. |
| 6 months (Phase 2) | Builds a living map of your network. Surfaces trending topics. Proactively identifies re-engagement windows. Delivers weekly intelligence brief. |
| 12 months (Phase 3) | Full relationship memory — tracks every outreach, outcome, and conversation. CRM sync. Account-level scoring. |
| 18 months (Phase 4) | Relationship intelligence OS. White-labeled for agencies. API for enterprise. Predictive scoring based on historical conversion data. |

### Who It's For

- **Agencies** (digital, AI, data, Martech) monitoring for service opportunities
- **Product companies** watching for pain points their product solves
- **Founders** doing hands-on sales via their personal LinkedIn network
- **Any B2B company** where relationship-driven outreach is the primary sales motion

### The North Star Metric

**Time to first wow moment** — elapsed time between a user installing Sonar and receiving their first alert that leads to a real outreach conversation.

**Target: under 24 hours from onboarding.**

---

## 2. System Architecture

### Architecture Principle

Modular event-driven. Each concern is a separate service connected by an event queue. A scraping failure doesn't kill alert delivery. The matching engine scales independently of the ingestion layer. Every component is replaceable without affecting others.

### Full System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                           │
│  Chrome Extension (primary)      React Dashboard             │
│  • LinkedIn feed sync            • Alert feed + priority      │
│  • Connection graph capture      • Relationship map           │
│  • Interaction history           • Network pulse insights     │
│  • Background sync (alarms API)  • Opportunity board         │
│                                  • Outreach history           │
└───────────────┬──────────────────────────┬───────────────────┘
                │ HTTPS (encrypted)        │ HTTPS
                ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI)                        │
│  /ingest · /profile · /alerts · /feedback · /workspace       │
│  /connections · /trends · /opportunities · /brief            │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    EVENT QUEUE (Redis)                        │
│  post.received → enrich → score → generate → deliver         │
└──────┬─────────────┬──────────────┬───────────────┬──────────┘
       │             │              │               │
       ▼             ▼              ▼               ▼
┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐
│ENRICHMENT│  │ 3-DIM     │  │  ALERT   │  │   DELIVERY     │
│WORKER    │  │ SCORING   │  │GENERATOR │  │   ROUTER       │
│          │  │ ENGINE    │  │          │  │                │
│• Company │  │           │  │• Context │  │• Slack         │
│  data    │  │• Relevance│  │  card    │  │• Email         │
│• Funding │  │• Relation-│  │• 2 draft │  │• WhatsApp      │
│• Tech    │  │  ship     │  │  variants│  │• Telegram      │
│  stack   │  │• Timing   │  │• Priority│  │• Priority      │
│• News    │  │           │  │  level   │  │  routing       │
└──────────┘  └───────────┘  └──────────┘  └────────────────┘
       │             │              │
       ▼             ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│                      DATA LAYER                               │
│  PostgreSQL                      pgvector                     │
│  • workspaces                    • capability_embeddings      │
│  • users                         • post_embeddings            │
│  • connection_profiles           • relationship_vectors       │
│  • posts (raw + processed)       • topic_clusters            │
│  • enrichment_cache                                          │
│  • alerts + priority scores                                   │
│  • outreach_history                                          │
│  • feedback + adjustments                                     │
│  • relationship_graph                                         │
│  • opportunity_windows                                        │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              SCHEDULED INTELLIGENCE JOBS (Celery Beat)        │
│  • Network Pulse Engine   — proactive opportunity surfacing   │
│  • Relationship Scorer    — updates connection strength daily │
│  • Feedback Trainer       — adjusts matching per workspace    │
│  • Enrichment Refresher   — keeps company data fresh         │
│  • Brief Generator        — Monday 8am weekly brief          │
│  • Public Post Poller     — fallback for non-extension users  │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   EXTERNAL PROVIDERS                          │
│  Apify (public fallback)    Proxycurl (enrichment)           │
│  Groq + Llama 3.3 (matching/scoring — free tier)            │
│  GPT-4o mini (outreach draft generation)                     │
│  OpenAI text-embedding-3-small (embeddings)                  │
│  SendGrid (email)   Twilio (WhatsApp)   Telegram Bot API     │
└──────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| Chrome Extension | JavaScript, Manifest V3, Chrome Alarms API |
| Backend API | Python 3.12, FastAPI |
| Job Queue | Celery + Redis |
| Database | PostgreSQL 16 + pgvector extension |
| Embeddings | OpenAI text-embedding-3-small (1536 dims) |
| Matching LLM | Groq + Llama 3.3 70B (free tier) |
| Drafting LLM | GPT-4o mini |
| Onboarding LLM | GPT-4o (one-time, high quality) |
| Frontend | React 18 + TypeScript + Vite |
| Email | SendGrid |
| WhatsApp | Twilio WhatsApp Business API |
| Dev Environment | Docker Compose (fully local) |
| Production | Railway or Render (Phase 1), AWS (Phase 3+) |

### Provider Abstraction

All external providers are abstracted behind interfaces. Swapping Proxycurl for Coresignal, or Groq for Anthropic, requires only a config change — no application code changes.

```python
# All providers implement the same interface
class LinkedInDataProvider(Protocol):
    async def get_public_posts(self, query: str, limit: int) -> list[Post]: ...

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

class LLMProvider(Protocol):
    async def complete(self, prompt: str, model: str) -> str: ...
```

---

## 3. Data Model

### Design Principle

Collect everything from day one, even if not surfaced in the UI yet. Every post, every topic signal, every outreach outcome stored permanently. The data collected in Phase 1 becomes the moat in Phase 2.

### Core Tables

#### workspaces
```sql
CREATE TABLE workspaces (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    plan_tier               TEXT NOT NULL DEFAULT 'starter',
    capability_profile      TEXT,
    matching_threshold      FLOAT NOT NULL DEFAULT 0.72,
    scoring_weights         JSONB DEFAULT '{"relevance":0.50,"relationship":0.30,"timing":0.20}',
    onboarding_url          TEXT,
    onboarding_doc_path     TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### capability_profile_versions
```sql
CREATE TABLE capability_profile_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    version             INT NOT NULL,
    raw_text            TEXT NOT NULL,
    embedding           VECTOR(1536),
    source              TEXT NOT NULL, -- 'url' | 'document' | 'manual'
    signal_keywords     TEXT[],
    anti_keywords       TEXT[],
    is_active           BOOLEAN NOT NULL DEFAULT true,
    performance_score   FLOAT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### users
```sql
CREATE TABLE users (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL REFERENCES workspaces(id),
    email                   TEXT NOT NULL UNIQUE,
    role                    TEXT NOT NULL DEFAULT 'member', -- 'owner' | 'member'
    linkedin_profile_url    TEXT,
    delivery_channels       JSONB DEFAULT '{}',
    alert_rate_limits       JSONB DEFAULT '{"high":10,"medium":5,"low":2}',
    quiet_hours             JSONB DEFAULT '{}',
    extension_installed     BOOLEAN NOT NULL DEFAULT false,
    extension_last_sync     TIMESTAMPTZ,
    timezone                TEXT NOT NULL DEFAULT 'UTC',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### connections
```sql
CREATE TABLE connections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    user_id             UUID NOT NULL REFERENCES users(id),
    linkedin_id         TEXT NOT NULL,
    name                TEXT NOT NULL,
    headline            TEXT,
    profile_url         TEXT,
    company             TEXT,
    seniority           TEXT,
    degree              INT NOT NULL, -- 1, 2, or 3
    relationship_score  FLOAT NOT NULL DEFAULT 0.5,
    has_interacted      BOOLEAN NOT NULL DEFAULT false,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at      TIMESTAMPTZ,
    enriched_at         TIMESTAMPTZ,
    enrichment_data     JSONB DEFAULT '{}',
    topic_interests     TEXT[],
    UNIQUE(workspace_id, linkedin_id)
);
```

#### posts
```sql
CREATE TABLE posts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    connection_id       UUID REFERENCES connections(id),
    linkedin_post_id    TEXT NOT NULL,
    content             TEXT NOT NULL,
    post_type           TEXT NOT NULL, -- 'post' | 'comment' | 'article' | 'job_posting'
    source              TEXT NOT NULL, -- 'extension' | 'public_fallback'
    posted_at           TIMESTAMPTZ,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding           VECTOR(1536),
    relevance_score     FLOAT,
    relationship_score  FLOAT,
    timing_score        FLOAT,
    combined_score      FLOAT,
    matched             BOOLEAN NOT NULL DEFAULT false,
    processed_at        TIMESTAMPTZ,
    extraction_version  TEXT,  -- Chrome extension version that captured this post
    UNIQUE(workspace_id, linkedin_post_id)
);
```

#### alerts
```sql
CREATE TABLE alerts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    post_id             UUID NOT NULL REFERENCES posts(id),
    connection_id       UUID NOT NULL REFERENCES connections(id),
    relevance_score     FLOAT NOT NULL,
    relationship_score  FLOAT NOT NULL,
    timing_score        FLOAT NOT NULL,
    combined_score      FLOAT NOT NULL,
    priority            TEXT NOT NULL, -- 'high' | 'medium' | 'low'
    match_reason        TEXT,
    outreach_draft_a    TEXT, -- Direct style
    outreach_draft_b    TEXT, -- Question-led style
    opportunity_type    TEXT, -- 'service_need' | 'product_pain' | 'hiring_signal' | etc.
    urgency_reason      TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    delivered_at        TIMESTAMPTZ,
    seen_at             TIMESTAMPTZ,
    feedback            TEXT, -- 'positive' | 'negative' | null
    feedback_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### outreach_history
```sql
CREATE TABLE outreach_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id),
    alert_id        UUID NOT NULL REFERENCES alerts(id),
    connection_id   UUID NOT NULL REFERENCES connections(id),
    message_sent    TEXT,
    outcome         TEXT, -- 'no_reply' | 'replied' | 'meeting_booked' | 'deal_opened' | null
    notes           TEXT,
    contacted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Network Intelligence Tables

#### connection_topic_signals
```sql
CREATE TABLE connection_topic_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id       UUID NOT NULL REFERENCES connections(id),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    topic               TEXT NOT NULL,
    topic_embedding     VECTOR(1536),
    signal_strength     FLOAT NOT NULL DEFAULT 0.5,
    trend               TEXT NOT NULL DEFAULT 'stable', -- 'rising' | 'stable' | 'falling'
    post_count          INT NOT NULL DEFAULT 1,
    first_detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_detected_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### network_trends
```sql
CREATE TABLE network_trends (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    topic               TEXT NOT NULL,
    topic_embedding     VECTOR(1536),
    connection_count    INT NOT NULL DEFAULT 1,
    velocity            FLOAT NOT NULL DEFAULT 0.0,
    status              TEXT NOT NULL DEFAULT 'emerging', -- 'emerging' | 'peaking' | 'declining'
    peak_date           DATE,
    first_detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### opportunity_windows
```sql
CREATE TABLE opportunity_windows (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    connection_id       UUID NOT NULL REFERENCES connections(id),
    trigger_post_ids    UUID[] NOT NULL,
    topic               TEXT NOT NULL,
    opportunity_type    TEXT NOT NULL,
    confidence_score    FLOAT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open',
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL,
    acted_at            TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ
);
```

#### competitive_signals
```sql
CREATE TABLE competitive_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    post_id             UUID NOT NULL REFERENCES posts(id),
    connection_id       UUID NOT NULL REFERENCES connections(id),
    competitor_name     TEXT NOT NULL,
    mention_type        TEXT NOT NULL, -- 'positive' | 'negative' | 'evaluating' | 'switched_to' | 'switched_from'
    context             TEXT,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### relationship_graph
```sql
CREATE TABLE relationship_graph (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL REFERENCES workspaces(id),
    source_connection_id    UUID NOT NULL REFERENCES connections(id),
    target_connection_id    UUID NOT NULL REFERENCES connections(id),
    edge_type               TEXT NOT NULL,
    strength                FLOAT NOT NULL DEFAULT 0.5,
    last_updated            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### signal_effectiveness
```sql
CREATE TABLE signal_effectiveness (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    alert_id            UUID NOT NULL REFERENCES alerts(id),
    predicted_score     FLOAT NOT NULL,
    user_rated          TEXT, -- 'relevant' | 'not_relevant' | null
    outreach_sent       BOOLEAN NOT NULL DEFAULT false,
    outreach_outcome    TEXT,
    revenue_attributed  DECIMAL(10,2),
    effectiveness_score FLOAT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### feedback_adjustments
```sql
CREATE TABLE feedback_adjustments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id),
    alert_id            UUID NOT NULL REFERENCES alerts(id),
    old_threshold       FLOAT NOT NULL,
    new_threshold       FLOAT NOT NULL,
    positive_rate       FLOAT NOT NULL,
    adjustment_reason   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### The 3-Dimension Score Formula

```python
# Weights tunable per workspace (stored in workspaces.scoring_weights)
DEFAULT_WEIGHTS = {
    "relevance":    0.50,
    "relationship": 0.30,
    "timing":       0.20
}

# Degree base scores
DEGREE_BASE = {1: 0.90, 2: 0.60, 3: 0.30}

# Timing decay: post loses urgency linearly over 24 hours
timing_score = max(0.0, 1.0 - (hours_since_posted / 24))

combined_score = (
    relevance_score    * weights["relevance"] +
    relationship_score * weights["relationship"] +
    timing_score       * weights["timing"]
)

# Priority bucketing
HIGH   = combined_score >= 0.80
MEDIUM = combined_score >= 0.55
LOW    = combined_score < 0.55
```

---

## 4. Chrome Extension Design

### Core Mechanic

The extension runs silently in Chrome. When the user opens LinkedIn, it reads their feed DOM, extracts posts with author metadata (including degree of connection), and sends an encrypted batch to the Sonar backend. No login required beyond the user's own LinkedIn session. No LinkedIn API dependency.

### Architecture (Manifest V3)

```
sonar-extension/
├── manifest.json               — permissions, service worker registration
├── background/
│   └── service-worker.js       — alarm scheduling, API communication
├── content/
│   └── linkedin-scraper.js     — DOM reading, post extraction
├── popup/
│   ├── popup.html              — sync status, signal count, settings link
│   └── popup.js
├── utils/
│   ├── extractor.js            — DOM parsing, high-water mark logic
│   ├── api-client.js           — encrypted HTTPS communication
│   └── storage.js              — local deduplication cache
└── icons/
```

### Permissions (Minimum Footprint)

```json
{
  "manifest_version": 3,
  "permissions": ["activeTab", "storage", "alarms"],
  "host_permissions": ["https://www.linkedin.com/*"],
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'"
  }
}
```

No "read all websites" permission. LinkedIn only.

### Post Payload Schema

```javascript
{
  linkedin_post_id: "urn:li:activity:123456789",  // deduplication key
  author: {
    name: "John Smith",
    headline: "VP Marketing at Acme Corp",
    profile_url: "https://linkedin.com/in/johnsmith",
    linkedin_id: "johnsmith123",
    degree: 1  // LinkedIn shows this directly in feed DOM
  },
  content: "We've been evaluating AI agent platforms...",
  post_type: "post",  // 'post' | 'comment' | 'share'
  posted_at: "2026-04-07T08:32:00Z",
  engagement: { likes: 47, comments: 12 },
  extraction_version: "1.2.0",  // for DOM change detection
  captured_at: "2026-04-07T09:15:00Z"
}
```

### Sync Strategy

```
TRIGGER: Chrome alarm fires every 30min (±randomized jitter)
  OR: User navigates to linkedin.com

CHECK: Has it been > 30 minutes since last sync? If no, skip.

SCROLL: Scroll LinkedIn feed incrementally
  — Stop when high-water mark post ID is encountered
  — Never re-process already-seen posts
  — Randomize scroll speed (800-1400ms between scrolls)
  — Randomize pause duration (1.2-3.8s between batches)

DEDUPLICATE: Check local storage cache — skip known post IDs

BATCH: Bundle new posts (max 50 per batch)

ENCRYPT + SEND: POST /api/ingest with JWT auth

UPDATE: High-water mark + last_sync timestamp

BADGE: Show signal count on extension icon
```

### Resilience Strategy

- DOM selectors stored as configurable constants — patchable without full extension update
- `extraction_version` field on every payload — sudden quality drop = LinkedIn UI change detected
- Graceful degradation: if selector fails, log error and continue with partial data
- Backend monitors extraction quality per version — alerts engineering team on drop

### Security

```
• All data encrypted in transit (TLS 1.3)
• Extension authenticates via rotating JWT (stored in chrome.storage.local)
• No LinkedIn session tokens, cookies, or passwords ever transmitted
• Per-workspace AES-256 encryption at rest
• Auth token auto-rotates every 7 days
• Extension source code auditable (open source or third-party audited)
```

### Sync Randomization (Account Safety)

```javascript
// Never sync at exactly the same interval
const jitter = Math.random() * 360 - 180;  // ±3 minutes
const nextSyncMinutes = 30 + jitter;

// Never scroll at machine speed
const scrollDelay = 800 + Math.random() * 600;  // 800-1400ms
const batchPause  = 1200 + Math.random() * 2600; // 1.2-3.8s
```

### Fallback Path (Non-Extension Users)

Public Post Poller (Celery Beat) pulls from Apify LinkedIn scrapers on an hourly schedule. Posts processed through identical matching pipeline but scored lower by default (no degree data available). Alerts tagged "Public signal — connection status unknown." Creates natural upgrade incentive toward Pro tier.

### Onboarding UX

```
Step 1: Install extension from Chrome Web Store
Step 2: Click icon → "Connect to Sonar" → OAuth with Sonar account
Step 3: "Open LinkedIn to start your first sync"
Step 4: Extension auto-scrolls feed silently
Step 5: Badge: "47 posts captured. Processing signals..."
Step 6: First alert arrives within minutes
```

Target: first alert delivered within 2 hours of extension install.

---

## 5. Matching Engine & AI Layer

### Pipeline Overview

```
Raw Post
    ↓
Stage 1: Keyword Pre-Filter     — eliminates ~70% of posts (free)
    ↓
Stage 2: Embedding Generation   — post text → 1536-dim vector ($0.00002/1K tokens)
    ↓
Stage 3: Semantic Similarity    — cosine similarity vs capability embedding
    ↓ (threshold: workspace.matching_threshold, default 0.72)
Stage 4: Enrichment             — company data, funding, tech stack (cached 7 days)
    ↓
Stage 5: 3-Dimension Scoring    — relevance + relationship + timing → combined_score
    ↓ (minimum combined_score: 0.45)
Stage 6: Context Generation     — match reason + 2 outreach draft variants
    ↓
Stage 7: Alert Creation         — priority bucketed, queued for delivery
```

### Stage 1: Keyword Pre-Filter

```python
def keyword_prefilter(content: str, workspace: Workspace) -> bool:
    content_lower = content.lower()
    
    # Hard blocklist — skip entirely
    blocklist = [
        "happy birthday", "congratulations", "work anniversary",
        "excited to announce my new role", "open to work",
        "pleased to share", "thrilled to announce"
    ]
    if any(term in content_lower for term in blocklist):
        return False
    
    # Signal keywords — auto-generated from capability profile at onboarding
    if not any(kw.lower() in content_lower for kw in workspace.signal_keywords):
        return False
    
    return True
```

### Stage 3: Semantic Similarity (pgvector)

```sql
-- Fast in-database cosine similarity
SELECT 
    p.id,
    1 - (p.embedding <=> cpv.embedding) AS relevance_score
FROM posts p
CROSS JOIN capability_profile_versions cpv
WHERE cpv.workspace_id = $1 
  AND cpv.is_active = true
  AND p.id = $2;
```

### Stage 5: 3-Dimension Scoring

```python
def compute_combined_score(
    relevance_score: float,
    connection: Connection,
    post: Post,
    workspace: Workspace
) -> ScoringResult:

    # Relationship score — base by degree, boosted by interaction history
    degree_base = {1: 0.90, 2: 0.60, 3: 0.30}
    relationship_score = connection.relationship_score or degree_base.get(connection.degree, 0.15)
    if connection.has_interacted:
        relationship_score = min(1.0, relationship_score + 0.15)

    # Timing decay — linear over 24 hours
    hours_old = (datetime.now(UTC) - post.posted_at).total_seconds() / 3600
    timing_score = max(0.0, 1.0 - (hours_old / 24))

    # Weighted combination
    weights = workspace.scoring_weights or DEFAULT_WEIGHTS
    combined = (
        relevance_score    * weights["relevance"] +
        relationship_score * weights["relationship"] +
        timing_score       * weights["timing"]
    )

    priority = (
        Priority.HIGH   if combined >= 0.80 else
        Priority.MEDIUM if combined >= 0.55 else
        Priority.LOW
    )

    return ScoringResult(
        relevance_score=relevance_score,
        relationship_score=relationship_score,
        timing_score=timing_score,
        combined_score=combined,
        priority=priority
    )
```

### Stage 6: Context Generation

```python
CONTEXT_GENERATION_PROMPT = """
You are a B2B sales intelligence assistant for {company_name}.

COMPANY CAPABILITY PROFILE:
{capability_profile}

LINKEDIN POST:
Author: {author_name}, {author_headline} at {company}
Connection: {degree} degree
Company context: {enrichment_summary}
Post: {post_content}

Return JSON with:
1. match_reason: 2 sentences. Why is this relevant to the company's capabilities? Be specific.
2. outreach_draft_a: Direct style LinkedIn message. Max 4 sentences. Reference the specific post. No emojis, no "I hope this finds you well."
3. outreach_draft_b: Question-led style. Opens with a curious question about their situation.
4. opportunity_type: one of [service_need, product_pain, hiring_signal, funding_signal, competitive_mention, general_interest]
5. urgency_reason: One sentence on why timing matters for this signal.

Valid JSON only. No preamble.
"""

# Model routing by priority
async def generate_context(post: Post, workspace: Workspace) -> AlertContext:
    if post.priority == Priority.HIGH:
        model = "gpt-4o-mini"     # Best quality for high-value alerts
        provider = openai_client
    else:
        model = "llama-3.3-70b"  # Near-free for medium/low
        provider = groq_client
    
    response = await provider.complete(
        prompt=CONTEXT_GENERATION_PROMPT.format(...),
        model=model
    )
    return AlertContext(**json.loads(response))
```

### Capability Profile Extraction (Onboarding)

```python
PROFILE_EXTRACTION_PROMPT = """
Analyze this company's website/document to build a sales intelligence capability profile.

CONTENT: {content}

Return JSON:
1. company_name: string
2. company_description: 2-3 sentence summary
3. primary_services: list of specific services/products
4. target_customers: industries, roles, company sizes they serve
5. pain_points_solved: specific problems they solve
6. technologies_used: tech stack and platforms
7. signal_keywords: 20-30 keywords indicating a prospect needs this company
8. anti_keywords: 10-15 phrases indicating irrelevance
9. capability_summary: Dense 150-200 word paragraph covering all capabilities.
   Written to maximize semantic vector coverage — not marketing copy.

Valid JSON only.
"""
```

### Feedback Learning Loop

```python
async def process_feedback_adjustment(workspace_id: UUID, db: AsyncSession):
    recent = await db.get_recent_feedback(workspace_id, limit=50)
    if len(recent) < 10:
        return  # Not enough data yet
    
    positive_rate = sum(1 for f in recent if f.feedback == "positive") / len(recent)
    workspace = await db.get_workspace(workspace_id)
    old_threshold = workspace.matching_threshold

    if positive_rate < 0.40:
        # Too many irrelevant alerts — be more selective
        new_threshold = min(0.92, old_threshold + 0.02)
    elif positive_rate > 0.75:
        # High relevance rate — catch more signals
        new_threshold = max(0.55, old_threshold - 0.01)
    else:
        return

    await db.update_workspace_threshold(workspace_id, new_threshold)
    await db.log_feedback_adjustment(workspace_id, old_threshold, new_threshold, positive_rate)
```

### Cost Model at Scale

```
Per 1,000 posts processed:
  Stage 1 (keyword filter):        $0.00   pure Python
  Stage 2-3 (embeddings):          $0.02   text-embedding-3-small
  Stage 4 (enrichment):            $0.00   mostly cache hits
  Stage 5 (scoring):               $0.00   pure math
  Stage 6 (context — HIGH 15%):    $0.08   GPT-4o mini
  Stage 6 (context — MED/LOW 85%): $0.01   Groq free tier
  ─────────────────────────────────────────
  Total per 1,000 posts:           ~$0.11

At 10,000 posts/day (50 clients × 200 posts):
  Daily cost:   ~$1.10
  Monthly cost: ~$33
```

---

## 6. Alert Generation & Delivery Layer

### Alert Payload (All Channels)

Every alert carries:
- Connection: name, role, company, degree, relationship score
- Post: content (truncated to 400 chars), posted timestamp
- Scores: relevance, relationship, timing, combined (as visual bars)
- Match reason: 2-sentence LLM explanation
- Outreach Draft A: Direct style
- Outreach Draft B: Question-led style
- Opportunity type and urgency reason
- Action buttons: View on LinkedIn · Mark Acted · Not Relevant

### Delivery Router

```python
class DeliveryRouter:
    async def deliver(self, alert: Alert, workspace: Workspace):
        channels = workspace.delivery_config
        tasks = []
        
        for channel, config in channels.items():
            # Each channel has configurable minimum priority threshold
            if alert.priority_value >= config.min_priority_value:
                tasks.append(self.send_to_channel(channel, alert, config))
        
        # Fire all channels in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
```

### Channel Implementations

**Slack:** Rich block kit formatting with priority color coding, score bars, both draft variants, and interactive buttons (Acted / Not Relevant) that feed directly back to the learning loop via Slack webhooks.

**Telegram:** Markdown-formatted message with inline keyboard buttons. Clean, readable on mobile. Ideal for founders who live in Telegram.

**Email:**
- HIGH priority: immediate single-alert email
- MEDIUM/LOW: batched into hourly digest
- Subject line: `🔴 High Priority Signal: {Name} — {topic summary}`

**WhatsApp (Twilio):** Stripped-down format — essential signal + Draft A + short link. Pre-approved message template for Business API compliance.

### Alert Rate Limiting (Anti-Fatigue)

```python
DAILY_LIMITS = {
    Priority.HIGH:   10,
    Priority.MEDIUM: 5,
    Priority.LOW:    2
}
# HIGH alerts always delivered immediately — never suppressed
# MEDIUM/LOW queued to next day if daily limit exceeded
```

### Quiet Hours

User-configurable per channel. Example: WhatsApp quiet between 10pm-8am. Alerts queued and delivered at quiet hours end.

### The Weekly Intelligence Brief

Delivered every Monday at 8am in the user's configured timezone via all channels.

Sections:
1. **Emerging in your network** — topics trending this week with connection count and velocity
2. **Expiring opportunity windows** — open windows closing in 48 hours
3. **Re-engagement windows** — dormant connections with fresh relevant signals
4. **Untapped high-value connections** — high-degree connections never alerted on, now showing signals

### Alert Lifecycle

```
PENDING → DELIVERED → SEEN → ACTED (or DISMISSED)
                                    ↓
                            outreach_history created
                                    ↓
                            feedback processed
                                    ↓
                            signal_effectiveness updated
                                    ↓
                            matching threshold adjusted
```

### Delivery Reliability

```
• Retry: 3× with exponential backoff on delivery failure
• Dead letter queue: permanently failed alerts logged
• Deduplication key: same post cannot trigger duplicate alerts
• Delivery receipts: per-channel delivered/seen/acted tracking
• "Sonar is learning your preferences" confirmation on every feedback action
```

---

## 7. Phased Roadmap & Success Metrics

### Phase 1 — The Wedge (Months 1-3)

**Goal:** One user installs Sonar, gets a real signal, sends a real message, books a real meeting.

**Scope:**
- Full onboarding flow (URL/doc → capability profile → extension install)
- Chrome extension with incremental sync + randomized behavior
- Keyword pre-filter + semantic matching pipeline
- 3-dimension scoring engine
- Context generation with 2 outreach draft variants
- Delivery: Slack, email (immediate + digest), WhatsApp, Telegram
- Alert feedback (Acted / Not Relevant) with threshold adjustment
- React dashboard: alert feed, opportunity board, settings
- Public fallback via Apify for non-extension users

**Out of scope for Phase 1:**
- 2nd/3rd degree extended capture
- Weekly Intelligence Brief
- Network map / topic radar
- Multi-user team workspaces
- CRM integrations
- White-label
- Geographic/industry filters

**Success Metrics:**

| Metric | Target |
|---|---|
| Time to first alert | < 2 hours post-onboarding |
| Time to first wow moment | < 24 hours |
| Week 1 retention | > 80% |
| Month 1 retention | > 60% |
| Alert positive feedback rate | > 55% |
| Extension install rate | > 70% of signups |
| Alerts actioned per user per week | > 3 |

### Phase 2 — Network Depth & Intelligence (Months 4-7)

**Goal:** Make Sonar indispensable. Users can't imagine doing BD without it.

**Additions:**
- 2nd + 3rd degree post capture via extension
- Connection enrichment (Proxycurl company data)
- Relationship strength scoring (daily Celery Beat job)
- Weekly Intelligence Brief (Monday 8am)
- Network Pulse Engine (topic trend detection)
- Re-engagement surfacing
- Opportunity window expiry alerts
- Competitive signal detection
- Network map + topic radar in dashboard
- Relationship timeline per connection
- A/B outreach draft performance tracking
- Mobile-responsive dashboard
- Team workspaces (up to 5 seats)

**Success Metrics:**

| Metric | Target |
|---|---|
| Weekly brief open rate | > 65% |
| Re-engagement conversion | > 20% |
| Month 3 retention | > 70% |
| Meetings from Sonar per user per month | > 2 |
| NPS | > 50 |
| Starter → Pro upgrade rate | > 40% |

### Phase 3 — Platform & Scale (Months 8-14)

**Goal:** Become the intelligence layer B2B revenue teams can't operate without.

**Additions:**
- CRM: HubSpot → Pipedrive → Salesforce
- White-label (custom domain, branded emails, color themes)
- SSO (SAML/OIDC)
- GDPR DPAs + EU data residency
- Custom model fine-tuning per workspace
- Dedicated enterprise infrastructure + SLA
- Public API (pull alerts, push capability updates)
- Intent pattern recognition (multi-post signals)
- Account-level scoring (multiple signals from same company)
- Predictive scoring (historical conversion patterns)

**Success Metrics:**

| Metric | Target |
|---|---|
| ARR | $500K |
| Enterprise clients | > 10 |
| Agency white-label | > 20 |
| ARPU | > $250/month |
| Gross margin | > 80% |
| Monthly churn | < 3% |

### Pricing Tiers

| Tier | Price | Key Features |
|---|---|---|
| **Starter** | $79/mo | 1 user, public fallback only, 30 alerts/month, email only, 30-day retention |
| **Pro** | $199/mo | 1 user, Chrome extension (network-scoped), unlimited alerts, all channels, weekly brief, opportunity board, 90-day retention |
| **Team** | $499/mo | 5 users + 5 LinkedIn accounts, shared signal feed, alert assignment, team outreach history, 1-year retention |
| **Enterprise** | Custom ($1,500+/mo) | Unlimited seats, white-label, CRM, SSO, DPA, custom fine-tuning, dedicated infra, SLA, API |

The extension unlock (Starter → Pro) is the primary conversion lever. Users who see the quality difference between public fallback alerts and network-scoped alerts convert at high rates.

### Go-To-Market Sequencing

```
Month 1-2: Private beta (10 hand-picked users from founder's network)
           → Goal: 3 users book a meeting from a Sonar signal

Month 3:   Soft launch — ProductHunt + LinkedIn content
           → Goal: 50 paying users

Month 4-6: Agency focus — direct outreach, case studies, partner program
           → Goal: 200 paying users, $20K MRR

Month 7+:  Scale — content marketing, SEO, paid acquisition
           → Goal: $100K MRR by month 12
```

The go-to-market channel is LinkedIn itself. The founder uses Sonar to find prospects on LinkedIn, reaches out with Sonar-drafted messages, converts them into Sonar customers. The product sells itself through its own use case.

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn blocks extension | Medium | High | Public fallback always live; randomized sync; legal review pre-launch |
| LinkedIn DOM changes | High | Medium | Extraction version monitoring; 24hr patch target |
| Data breach | Low | Critical | Per-workspace encryption; secrets manager; pen testing |
| Alert fatigue → churn | Medium | High | Rate limits; quiet hours; threshold auto-adjustment |
| LLM cost spike | Low | Medium | Model routing; cost alerts; fallback models |
| Competitor copies approach | Medium | Medium | Network data compounds — history can't be replicated |

---

## Appendix: Key Design Decisions

### Why Chrome Extension Over LinkedIn API
LinkedIn's official API does not expose the network feed or connections' posts. The Chrome extension running in the user's own authenticated session is the only technically viable path to network-scoped real-time intelligence. The user accesses their own data — legally defensible under GDPR Article 20 (data portability).

### Why Python FastAPI Over Next.js
The matching engine is the product's core. It requires vector embeddings, semantic similarity computation, LLM orchestration, and async job processing. The Python ecosystem (sentence-transformers, pgvector, LangChain, Celery) is the native home of these workloads. Node.js is not.

### Why Store Everything From Day One
The competitive moat deepens with data history. Relationship timelines, topic evolution, signal effectiveness by type — none of this can be reconstructed retroactively. Storing all posts and signals from day one costs very little (text is cheap) and pays compounding returns from Phase 2 onward.

### Why Two Outreach Draft Variants
Users have different communication styles. Some prefer direct; some prefer curious questions. Offering both increases the probability that the user sends something — reducing the friction between "signal detected" and "message sent" is the single highest-leverage UX decision in the product.

### Why Public Fallback
Not all users will install the Chrome extension. Keeping them on a lower-quality public signal experience preserves their value as paying customers while creating a constant demonstration of what they're missing — a natural upgrade nudge built into the product experience.
