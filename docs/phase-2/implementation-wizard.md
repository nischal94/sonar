# Sonar Phase 2 — Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Signal Configuration Wizard — a first-time-user flow at `/signals/setup` that turns a free-form "what you sell" description into 8–10 embedded buying signals, with day-one telemetry so every proposal call is logged for future prompt iteration.

**Architecture:** Two new backend endpoints (`POST /workspace/signals/propose`, `POST /workspace/signals/confirm`) backed by a new `propose_signals` prompt module, a new `signal_proposal_events` telemetry table, and a project-wide bump of the OpenAI "expensive tier" from `gpt-4o-mini` to `gpt-5.4-mini`. Single React page `SignalConfig.tsx` with a step-state machine drives the UX. Structural CI gate on prompt output shape (not semantic quality — real-world telemetry is the quality signal).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, Postgres + pgvector, OpenAI SDK v2.x (`gpt-5.4-mini`, `text-embedding-3-small`), slowapi (already wired in via PR #61), React 18 + Vite + TypeScript, pytest + pytest-asyncio.

---

## Scope

**In scope:**
- Project-wide LLM "expensive tier" bump: `gpt-4o-mini` → `gpt-5.4-mini` (single routing layer preserved)
- Alembic migration 003 — `signal_proposal_events` telemetry table
- `SignalProposalEvent` ORM model + unit test
- New `app/prompts/` package + `propose_signals.py` module (first entry under this convention, per `sonar/CLAUDE.md` "Prompts are code" rule)
- Pydantic schemas for propose/confirm request+response
- `POST /workspace/signals/propose` endpoint (LLM call, no DB write, emits partial telemetry event)
- `POST /workspace/signals/confirm` endpoint (persists signals with embeddings, completes telemetry event, marks capability profile active)
- Rate limit on `/propose` via existing slowapi setup
- Structural CI test against live LLM (asserts shape, not quality)
- End-to-end integration test (register → propose → confirm → assert persisted + telemetry logged)
- Frontend `SignalConfig.tsx` + `/signals/setup` route + `Onboarding.tsx` redirect
- `sonar/CLAUDE.md` updates — LLM routing rule + `app/prompts/` convention note

**Out of scope (follow-up plans):**
- `/signals` ongoing management page + CRUD endpoints (Signal Management slice)
- `POST /workspace/signals/from-discovery` (depends on Ring 3 — Discovery slice)
- Offline LLM eval harness with golden datasets (later plan, seeded from `signal_proposal_events`)
- A/B testing rail for prompt iteration (later plan)

**Key design decisions already locked** (see `docs/phase-2/wizard-decisions.md` for rationale):
1. Scope Option B — wizard-only, no management UI in this plan
2. LLM Option A1 — bump project standard to `gpt-5.4-mini`, migrate `context_generator.py` in the same plan
3. Validation Option D — hybrid: ship telemetry + structural CI gate + prompt versioning now; dataset-based evals derived from production later

---

## File Structure

### New files
- `backend/alembic/versions/003_signal_proposal_events.py` — telemetry table migration
- `backend/app/models/signal_proposal_event.py` — `SignalProposalEvent` ORM model
- `backend/app/prompts/__init__.py` — empty package marker
- `backend/app/prompts/propose_signals.py` — prompt templates + `PROMPT_VERSION` + JSON schema
- `backend/app/schemas/wizard.py` — Pydantic request/response for propose + confirm
- `backend/app/routers/signals.py` — new router: `POST /workspace/signals/propose`, `POST /workspace/signals/confirm`
- `backend/tests/test_signal_proposal_event_model.py`
- `backend/tests/test_propose_signals_prompt.py` — unit tests on the prompt module (not LLM)
- `backend/tests/test_propose_signals_shape.py` — structural CI gate against live LLM
- `backend/tests/test_wizard_flow.py` — end-to-end integration
- `frontend/src/pages/SignalConfig.tsx` — 5-step wizard component

### Modified files
- `backend/app/config.py` — add `OPENAI_MODEL_EXPENSIVE = "gpt-5.4-mini"` module-level constant (Task 1)
- `backend/app/services/llm.py` — import the constant, change `_LazyOpenAI.complete` default (Task 1)
- `backend/app/services/context_generator.py` — import the constant, remove hardcoded `gpt-4o-mini` / `gpt-4o` references (Task 1)
- `backend/app/models/__init__.py` — import `SignalProposalEvent` so metadata registry sees it (Task 3)
- `backend/app/main.py` — register `signals_router` (Task 6)
- `frontend/src/App.tsx` — add `/signals/setup` route (Task 11)
- `frontend/src/pages/Onboarding.tsx` — redirect new users to `/signals/setup` (Task 11)
- `CLAUDE.md` — LLM routing rule update + `app/prompts/` convention note (Task 12)

Each file has one clear responsibility: the prompt module owns prompt strings + version; the router owns HTTP shape; the schemas own validation; the model owns persistence; the frontend page owns step UX.

---

## Test Strategy Note for Implementers

- Backend tests run with `docker compose exec -T api pytest`. A single test: `docker compose exec -T api pytest tests/test_signal_proposal_event_model.py -v`. Every command runs inside the `api` container which already has `uv` and every dep installed. Do NOT install anything on the host.
- Postgres + pgvector must be running: `docker compose up -d postgres redis api` from the repo root if not already up.
- Fixtures in `backend/tests/conftest.py` provide `db_session`, `test_engine`, and `client` (the `AsyncClient` + dependency overrides). The `client` fixture also calls `limiter.reset()` before yielding (PR #61) — rate-limit state is isolated per test.
- For tests that need to mock the LLM, use FastAPI `Depends()` overrides via `app.dependency_overrides` rather than `unittest.mock.patch()` on module globals. This is the hard-won pattern from issues #6 and #11 — see "Lessons Learned — Python test mocking" in `sonar/CLAUDE.md`. Any new LLM-calling endpoint in this plan must accept its LLM provider via `Depends(get_llm_client)` so tests can override cleanly.
- The structural CI gate in Task 9 hits the REAL OpenAI API (with the env-configured key) — it's the only test in this plan that does so. All other tests mock the LLM.
- Follow `test_*` function naming consistent with existing tests.
- Each new ORM model must be imported from `backend/app/models/__init__.py` so SQLAlchemy metadata sees it before `create_all` runs in tests.

---

## Task 1: Project-wide LLM model constant + migration

**Files:**
- Modify: `backend/app/config.py` — add module-level constant below the `Settings` class
- Modify: `backend/app/services/llm.py` — import + use constant in the OpenAI provider's `complete()` default
- Modify: `backend/app/services/context_generator.py` — replace any hardcoded `"gpt-4o-mini"` or `"gpt-4o"` references with the constant
- Test: `backend/tests/test_llm_model_constant.py` (new)

- [ ] **Step 1: Grep the codebase to see every current reference**

Run: `grep -rn "gpt-4o" backend/app/ backend/tests/ 2>&1`
Note every file that comes back — each one is a site that either (a) needs migrating to the new constant, or (b) is a test asserting the old model name and will need updating.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_llm_model_constant.py`:

```python
from app.config import OPENAI_MODEL_EXPENSIVE


def test_expensive_tier_is_gpt_5_4_mini():
    """Project-wide LLM expensive tier is gpt-5.4-mini as of the Phase 2
    Wizard slice. Context: sonar/CLAUDE.md routing rule + wizard-decisions.md
    §2. If you're changing this, update the routing rule in CLAUDE.md and
    every caller that imports the constant."""
    assert OPENAI_MODEL_EXPENSIVE == "gpt-5.4-mini"


def test_context_generator_uses_constant():
    """context_generator must not hardcode model names — use the constant
    so a single edit updates every caller at once."""
    import app.services.context_generator as cg
    import inspect
    source = inspect.getsource(cg)
    assert "gpt-4o" not in source, (
        "context_generator.py still hardcodes 'gpt-4o' — migrate to "
        "OPENAI_MODEL_EXPENSIVE from app.config"
    )
```

- [ ] **Step 3: Run the test — verify it fails**

Run: `docker compose exec -T api pytest tests/test_llm_model_constant.py -v`
Expected: both tests FAIL — `OPENAI_MODEL_EXPENSIVE` doesn't exist yet, and `context_generator.py` still references `gpt-4o*`.

- [ ] **Step 4: Add the constant**

Edit `backend/app/config.py` — add a module-level constant AFTER the `get_settings()` function:

```python
# Project-wide LLM routing constants. Keep in lockstep with sonar/CLAUDE.md
# "LLM and agent discipline" routing rules. Single source of truth — every
# caller imports from here, no hardcoding model names at call sites.
OPENAI_MODEL_EXPENSIVE = "gpt-5.4-mini"
```

- [ ] **Step 5: Migrate llm.py**

Edit `backend/app/services/llm.py`:
- Add at the top: `from app.config import OPENAI_MODEL_EXPENSIVE`
- Change the `_LazyOpenAI.complete` default from `model: str = "gpt-4o"` to `model: str = OPENAI_MODEL_EXPENSIVE`
- Change the `OpenAILLMProvider.complete` default likewise

The `GroqLLMProvider` stays on `llama-3.3-70b-versatile` — that's the "cheap tier," separate from the "expensive tier" bump.

- [ ] **Step 6: Migrate context_generator.py**

Edit `backend/app/services/context_generator.py`:
- Add at the top: `from app.config import OPENAI_MODEL_EXPENSIVE`
- Replace every occurrence of `"gpt-4o-mini"` or `"gpt-4o"` in OpenAI calls with `OPENAI_MODEL_EXPENSIVE`
- Do NOT change any Groq/Llama references — those are the cheap tier, different model

- [ ] **Step 7: Run the full test suite — verify no regressions**

Run: `docker compose exec -T api pytest -q`
Expected: 55/55 pass + 2 new tests pass = 57/57 total. If any existing test asserts the old model name, update it to import + assert the constant.

- [ ] **Step 8: Commit**

```bash
git add backend/app/config.py backend/app/services/llm.py backend/app/services/context_generator.py backend/tests/test_llm_model_constant.py
git commit -m "chore(llm): bump expensive tier to gpt-5.4-mini" -m "Adds OPENAI_MODEL_EXPENSIVE constant in app/config.py and migrates llm.py + context_generator.py to import it. Single routing layer preserved. Sonar/CLAUDE.md routing rule updated in Task 12 of this plan."
```

---

## Task 2: Alembic migration 003 — signal_proposal_events table

**Files:**
- Create: `backend/alembic/versions/003_signal_proposal_events.py`

- [ ] **Step 1: Verify the current migration head**

Run: `docker compose exec -T api alembic current`
Expected: output ends with `002_phase2_foundation (head)` (or whatever Foundation's migration was named). The new migration will set `down_revision` to this.

- [ ] **Step 2: Create the migration file**

Create `backend/alembic/versions/003_signal_proposal_events.py`:

```python
"""signal_proposal_events — telemetry for wizard LLM calls

Revision ID: 003_signal_proposal_events
Revises: 002_phase2_foundation
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_signal_proposal_events"
down_revision = "002_phase2_foundation"  # VERIFY against `alembic current` in Step 1
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_proposal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("what_you_sell", sa.Text(), nullable=False),
        sa.Column("icp", sa.Text(), nullable=True),
        sa.Column("proposed", postgresql.JSONB(), nullable=False),
        sa.Column("accepted_ids", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("edited_pairs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rejected_ids", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("user_added", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_signal_proposal_events_workspace_created", "signal_proposal_events", ["workspace_id", sa.text("created_at DESC")])
    op.create_index("ix_signal_proposal_events_version_completed", "signal_proposal_events", ["prompt_version", sa.text("completed_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_signal_proposal_events_version_completed", table_name="signal_proposal_events")
    op.drop_index("ix_signal_proposal_events_workspace_created", table_name="signal_proposal_events")
    op.drop_table("signal_proposal_events")
```

- [ ] **Step 3: Run the migration + verify both directions**

Run:
```bash
docker compose exec -T api alembic upgrade head
docker compose exec -T postgres psql -U sonar -d sonar -c "\d signal_proposal_events"
docker compose exec -T api alembic downgrade -1
docker compose exec -T postgres psql -U sonar -d sonar -c "\d signal_proposal_events"
docker compose exec -T api alembic upgrade head
```
Expected: first `\d` shows the full table. `downgrade -1` drops it (second `\d` returns "Did not find any relation"). Final `upgrade head` restores it.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/003_signal_proposal_events.py
git commit -m "feat(db): migration 003 — signal_proposal_events table" -m "Day-one telemetry for Wizard LLM calls. Stores user input, LLM proposal, and user's accepted/edited/rejected/added breakdown per wizard completion. Seed data for later offline eval harness. Indexed on (workspace_id, created_at DESC) and (prompt_version, completed_at DESC) for time-series and v1→v2 comparison queries."
```

---

## Task 3: SignalProposalEvent ORM model + test

**Files:**
- Create: `backend/app/models/signal_proposal_event.py`
- Modify: `backend/app/models/__init__.py` (add import)
- Create: `backend/tests/test_signal_proposal_event_model.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_signal_proposal_event_model.py`:

```python
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_signal_proposal_event_persists_all_fields(db_session):
    workspace = Workspace(name="Test Agency")
    db_session.add(workspace)
    await db_session.flush()

    event = SignalProposalEvent(
        workspace_id=workspace.id,
        prompt_version="v1",
        what_you_sell="Fractional CTO services for Series A-B SaaS",
        icp="CEOs and VPs Eng at 20-50 person startups",
        proposed=[
            {"phrase": "struggling to hire senior engineers", "example_post": "We've been interviewing for 4 months.", "intent_strength": 0.82},
        ],
        accepted_ids=["0"],
        edited_pairs=[],
        rejected_ids=[],
        user_added=[],
    )
    db_session.add(event)
    await db_session.commit()

    result = await db_session.execute(select(SignalProposalEvent).where(SignalProposalEvent.id == event.id))
    loaded = result.scalar_one()
    assert loaded.prompt_version == "v1"
    assert loaded.what_you_sell.startswith("Fractional CTO")
    assert loaded.icp is not None
    assert loaded.proposed[0]["phrase"] == "struggling to hire senior engineers"
    assert loaded.accepted_ids == ["0"]
    assert loaded.completed_at is None  # not yet completed
    assert loaded.created_at is not None


@pytest.mark.asyncio
async def test_signal_proposal_event_allows_null_icp_and_empty_arrays(db_session):
    """ICP is optional (design.md §4.1 Step 2). Arrays default to empty."""
    workspace = Workspace(name="Test Agency 2")
    db_session.add(workspace)
    await db_session.flush()

    event = SignalProposalEvent(
        workspace_id=workspace.id,
        prompt_version="v1",
        what_you_sell="Something",
        icp=None,
        proposed=[],
    )
    db_session.add(event)
    await db_session.commit()
    assert event.icp is None
    assert event.accepted_ids == []
    assert event.rejected_ids == []
    assert event.user_added == []
```

- [ ] **Step 2: Run it — verify it fails**

Run: `docker compose exec -T api pytest tests/test_signal_proposal_event_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.signal_proposal_event'`.

- [ ] **Step 3: Create the ORM model**

Create `backend/app/models/signal_proposal_event.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import TIMESTAMP, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class SignalProposalEvent(Base):
    """Telemetry row written once per wizard run. See `docs/phase-2/wizard-decisions.md` §3a
    for the schema rationale. `/propose` inserts with most fields populated + `completed_at=NULL`;
    `/confirm` updates the same row with the acceptance breakdown and sets `completed_at`."""
    __tablename__ = "signal_proposal_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    what_you_sell: Mapped[str] = mapped_column(Text, nullable=False)
    icp: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed: Mapped[list] = mapped_column(JSONB, nullable=False)
    accepted_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    edited_pairs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rejected_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    user_added: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

- [ ] **Step 4: Register in the metadata index**

Edit `backend/app/models/__init__.py` — add line (order alphabetical with existing):

```python
from app.models.signal_proposal_event import SignalProposalEvent  # noqa: F401
```

Without this, `Base.metadata.create_all` in tests won't build the table.

- [ ] **Step 5: Run the test — verify it passes**

Run: `docker compose exec -T api pytest tests/test_signal_proposal_event_model.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Run full suite for regressions**

Run: `docker compose exec -T api pytest -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/signal_proposal_event.py backend/app/models/__init__.py backend/tests/test_signal_proposal_event_model.py
git commit -m "feat(models): SignalProposalEvent ORM for wizard telemetry" -m "Persisting inputs, LLM proposal, and user's acceptance breakdown per wizard run. Companion to migration 003. Null completed_at distinguishes partial (/propose called) from completed (/confirm called) events."
```

---

## Task 4: Prompt module `app/prompts/propose_signals.py`

**Files:**
- Create: `backend/app/prompts/__init__.py` (empty marker)
- Create: `backend/app/prompts/propose_signals.py`
- Create: `backend/tests/test_propose_signals_prompt.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_propose_signals_prompt.py`:

```python
import json
from app.prompts.propose_signals import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_message,
    RESPONSE_JSON_SCHEMA,
)


def test_prompt_version_is_v1():
    """Locks the initial version. Bump when prompt content changes."""
    assert PROMPT_VERSION == "v1"


def test_system_prompt_is_static_and_does_not_interpolate_user_input():
    """Per sonar/CLAUDE.md 'Prompt injection defense is mandatory':
    user-controlled input goes in the user message position only. If the
    system prompt is an f-string with {...} placeholders, that's a bug."""
    assert "{" not in SYSTEM_PROMPT or "{{" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT looks like it contains interpolation placeholders — "
        "user input belongs in build_user_message, not in the system prompt."
    )


def test_build_user_message_includes_what_you_sell():
    msg = build_user_message(what_you_sell="Fractional CTO services", icp=None)
    assert "Fractional CTO services" in msg


def test_build_user_message_includes_icp_when_provided():
    msg = build_user_message(
        what_you_sell="Fractional CTO services",
        icp="CEOs at 20-50 person startups",
    )
    assert "CEOs at 20-50 person startups" in msg


def test_build_user_message_handles_null_icp_gracefully():
    msg = build_user_message(what_you_sell="X", icp=None)
    assert isinstance(msg, str) and len(msg) > 0


def test_response_schema_enforces_signal_shape():
    """Schema must require phrase, example_post, intent_strength per signal;
    signals array must have 8–10 items to meet design.md §4.1 Step 3."""
    schema = RESPONSE_JSON_SCHEMA
    assert schema["type"] == "object"
    signals = schema["properties"]["signals"]
    assert signals["type"] == "array"
    assert signals["minItems"] == 8
    assert signals["maxItems"] == 10
    item_props = signals["items"]["properties"]
    assert "phrase" in item_props
    assert "example_post" in item_props
    assert "intent_strength" in item_props
    assert item_props["intent_strength"]["minimum"] == 0
    assert item_props["intent_strength"]["maximum"] == 1
    # strict mode requirements
    assert signals["items"]["additionalProperties"] is False
    assert set(signals["items"]["required"]) == {"phrase", "example_post", "intent_strength"}
```

- [ ] **Step 2: Run it — verify failure**

Run: `docker compose exec -T api pytest tests/test_propose_signals_prompt.py -v`
Expected: all FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Create the package marker**

Create empty `backend/app/prompts/__init__.py`.

- [ ] **Step 4: Create the prompt module**

Create `backend/app/prompts/propose_signals.py`:

```python
"""Wizard prompt — turns user's 'what you sell' + 'ICP' into 8–10 embedded buying signals.

See docs/phase-2/design.md §4.1 and docs/phase-2/wizard-decisions.md §3c for rationale.
Rules (sonar/CLAUDE.md 'LLM and agent discipline'):
  - Static system prompt, user input only in the user-message position (no f-strings in system)
  - JSON-schema-validated output via OpenAI Structured Outputs, strict mode
  - PROMPT_VERSION bumped on EVERY content change, logged with every call for v1→v2 comparison
"""
from __future__ import annotations

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "You are a sales intelligence analyst helping the user define buying signals "
    "for their product. A buying signal is a short phrase a prospect might post on "
    "LinkedIn that indicates they are experiencing the problem the user's product "
    "solves, or are actively evaluating solutions like it.\n"
    "\n"
    "Given the user's description of what they sell and their ICP, produce 8–10 "
    "distinct buying signals. For each signal, write:\n"
    "  - phrase: a short human-readable label (3–10 words) in the prospect's voice\n"
    "  - example_post: a realistic LinkedIn post excerpt (1–3 sentences) that this signal would match\n"
    "  - intent_strength: your confidence (0.0–1.0) that a post matching this phrase indicates real buying intent\n"
    "\n"
    "Signals must be distinct from each other (no near-duplicates) and specific to what the user sells. "
    "Avoid generic pain phrases that apply to any business."
)


def build_user_message(what_you_sell: str, icp: str | None) -> str:
    """Compose the user message from the wizard inputs.
    NEVER interpolate user input into SYSTEM_PROMPT. Only here."""
    lines = [f"What I sell: {what_you_sell}"]
    if icp:
        lines.append(f"My ICP: {icp}")
    lines.append("Produce 8–10 buying signals now, matching the schema you were given.")
    return "\n".join(lines)


RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "minItems": 8,
            "maxItems": 10,
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string", "minLength": 3, "maxLength": 120},
                    "example_post": {"type": "string", "minLength": 10, "maxLength": 500},
                    "intent_strength": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["phrase", "example_post", "intent_strength"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["signals"],
    "additionalProperties": False,
}
```

- [ ] **Step 5: Run the test — verify pass**

Run: `docker compose exec -T api pytest tests/test_propose_signals_prompt.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts/__init__.py backend/app/prompts/propose_signals.py backend/tests/test_propose_signals_prompt.py
git commit -m "feat(prompts): propose_signals prompt module + v1" -m "First entry under backend/app/prompts/ (new convention per sonar/CLAUDE.md 'Prompts are code'). Exports PROMPT_VERSION, SYSTEM_PROMPT, build_user_message(), and RESPONSE_JSON_SCHEMA for OpenAI Structured Outputs. Unit-tested for injection safety (no interpolation in system prompt) and schema enforcement (exactly 8–10 signals, strict mode)."
```

---

## Task 5: Wizard Pydantic schemas

**Files:**
- Create: `backend/app/schemas/wizard.py`
- Create: `backend/tests/test_wizard_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_wizard_schemas.py`:

```python
import pytest
from pydantic import ValidationError
from app.schemas.wizard import (
    ProposeSignalsRequest,
    ProposedSignal,
    ProposeSignalsResponse,
    ConfirmSignalsRequest,
    ConfirmedSignal,
    ConfirmSignalsResponse,
)


def test_propose_request_requires_what_you_sell():
    with pytest.raises(ValidationError):
        ProposeSignalsRequest(icp="x")


def test_propose_request_icp_is_optional():
    req = ProposeSignalsRequest(what_you_sell="Fractional CTO services")
    assert req.icp is None


def test_proposed_signal_intent_strength_bounds():
    with pytest.raises(ValidationError):
        ProposedSignal(phrase="x", example_post="y", intent_strength=1.5)
    with pytest.raises(ValidationError):
        ProposedSignal(phrase="x", example_post="y", intent_strength=-0.1)
    # 0 and 1 inclusive should work
    ProposedSignal(phrase="x", example_post="y", intent_strength=0)
    ProposedSignal(phrase="x", example_post="y", intent_strength=1)


def test_confirm_request_accepts_empty_lists():
    req = ConfirmSignalsRequest(
        proposal_event_id="00000000-0000-0000-0000-000000000000",
        accepted=[],
        edited=[],
        rejected=[],
        user_added=[],
    )
    assert req.accepted == []


def test_confirmed_signal_shape():
    sig = ConfirmedSignal(phrase="x", example_post="y", intent_strength=0.5)
    assert sig.phrase == "x"
```

- [ ] **Step 2: Run — verify failure**

Run: `docker compose exec -T api pytest tests/test_wizard_schemas.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Create the schemas**

Create `backend/app/schemas/wizard.py`:

```python
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


class ProposeSignalsRequest(BaseModel):
    what_you_sell: str = Field(min_length=5, max_length=2000)
    icp: str | None = Field(default=None, max_length=1000)


class ProposedSignal(BaseModel):
    phrase: str = Field(min_length=3, max_length=120)
    example_post: str = Field(min_length=10, max_length=500)
    intent_strength: float = Field(ge=0, le=1)


class ProposeSignalsResponse(BaseModel):
    proposal_event_id: UUID
    prompt_version: str
    signals: list[ProposedSignal]


class EditedPair(BaseModel):
    proposed_idx: int = Field(ge=0)
    final_phrase: str = Field(min_length=3, max_length=120)
    final_example_post: str = Field(min_length=10, max_length=500)
    final_intent_strength: float = Field(ge=0, le=1)


class ConfirmedSignal(BaseModel):
    """Final shape sent by the frontend — post-edit or user-added."""
    phrase: str = Field(min_length=3, max_length=120)
    example_post: str = Field(min_length=10, max_length=500)
    intent_strength: float = Field(ge=0, le=1)


class ConfirmSignalsRequest(BaseModel):
    proposal_event_id: UUID
    accepted: list[int] = Field(default_factory=list)   # indices into proposal's signals array
    edited: list[EditedPair] = Field(default_factory=list)
    rejected: list[int] = Field(default_factory=list)
    user_added: list[ConfirmedSignal] = Field(default_factory=list)


class ConfirmSignalsResponse(BaseModel):
    signal_ids: list[UUID]
    profile_active: bool
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_wizard_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/wizard.py backend/tests/test_wizard_schemas.py
git commit -m "feat(schemas): Pydantic request/response for wizard endpoints" -m "Defines ProposeSignalsRequest/Response, ConfirmSignalsRequest/Response, ProposedSignal/ConfirmedSignal, EditedPair. Used by /propose and /confirm routers in Tasks 6-7."
```

---

## Task 6: `POST /workspace/signals/propose` endpoint

**Files:**
- Create: `backend/app/routers/signals.py`
- Modify: `backend/app/main.py` (register new router)
- Create: `backend/tests/test_propose_endpoint.py`

- [ ] **Step 1: Write the failing test (LLM mocked via Depends override)**

Create `backend/tests/test_propose_endpoint.py`:

```python
import pytest
import json
from uuid import UUID
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.models.signal_proposal_event import SignalProposalEvent


class FakeLLM:
    """Test double. Returns a fixed 8-signal JSON payload."""
    def __init__(self, payload: str | None = None):
        self.payload = payload or json.dumps({
            "signals": [
                {"phrase": f"phrase {i}", "example_post": f"example post {i} body", "intent_strength": 0.5}
                for i in range(8)
            ]
        })
        self.calls = 0

    async def complete(self, prompt: str, model: str) -> str:
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_propose_returns_8_signals_and_logs_partial_telemetry(client, db_session):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake

    # Register a workspace + login to get a JWT
    await client.post("/workspace/register", json={
        "workspace_name": "WS", "email": "a@a.com", "password": "pw1234567890",
    })
    tok = (await client.post("/auth/token", data={"username": "a@a.com", "password": "pw1234567890"})).json()["access_token"]

    resp = await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "Fractional CTO services", "icp": "CEOs at small startups"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["signals"]) == 8
    assert body["prompt_version"] == "v1"
    proposal_event_id = UUID(body["proposal_event_id"])

    # Telemetry row is written with completed_at still NULL
    result = await db_session.execute(
        select(SignalProposalEvent).where(SignalProposalEvent.id == proposal_event_id)
    )
    row = result.scalar_one()
    assert row.prompt_version == "v1"
    assert row.what_you_sell.startswith("Fractional CTO")
    assert row.icp == "CEOs at small startups"
    assert len(row.proposed) == 8
    assert row.completed_at is None
    assert fake.calls == 1

    app.dependency_overrides.pop(get_llm_client, None)


@pytest.mark.asyncio
async def test_propose_rejects_unauthenticated(client):
    resp = await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "x"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_propose_validates_minimum_input_length(client, db_session):
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    await client.post("/workspace/register", json={"workspace_name": "W", "email": "b@b.com", "password": "pw1234567890"})
    tok = (await client.post("/auth/token", data={"username": "b@b.com", "password": "pw1234567890"})).json()["access_token"]
    # 'hi' is 2 chars, below min_length=5
    resp = await client.post(
        "/workspace/signals/propose",
        json={"what_you_sell": "hi"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 422
    app.dependency_overrides.pop(get_llm_client, None)
```

- [ ] **Step 2: Run — verify fail (endpoint doesn't exist)**

Run: `docker compose exec -T api pytest tests/test_propose_endpoint.py -v`
Expected: all FAIL with 404 or import errors.

- [ ] **Step 3: Create the router**

Create `backend/app/routers/signals.py`:

```python
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.user import User
from app.routers.auth import get_current_user
from app.rate_limit import limiter
from app.schemas.wizard import (
    ProposeSignalsRequest,
    ProposedSignal,
    ProposeSignalsResponse,
)
from app.services.llm import get_llm_client, LLMProvider
from app.config import OPENAI_MODEL_EXPENSIVE
from app.prompts.propose_signals import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_message,
    RESPONSE_JSON_SCHEMA,
)

router = APIRouter(prefix="/workspace/signals", tags=["signals"])


def _strip_markdown_fence(raw: str) -> str:
    """Reuse the fence-strip pattern from context_generator.py — some models
    wrap JSON output in ```json ... ``` despite Structured Outputs."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


@router.post("/propose", response_model=ProposeSignalsResponse)
@limiter.limit("3/minute")
async def propose_signals(
    request: Request,  # required by @limiter.limit
    body: ProposeSignalsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_client),
):
    user_msg = build_user_message(body.what_you_sell, body.icp)
    # Compose the prompt for the existing `complete(prompt, model)` signature.
    # Two-part prompt delimited by role markers so the system/user separation is preserved.
    prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{user_msg}"
    raw = await llm.complete(prompt, model=OPENAI_MODEL_EXPENSIVE)
    try:
        payload = json.loads(_strip_markdown_fence(raw))
        signals_raw = payload["signals"]
        signals = [ProposedSignal(**s) for s in signals_raw]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f"LLM output parse failed: {exc}")

    event = SignalProposalEvent(
        workspace_id=current_user.workspace_id,
        prompt_version=PROMPT_VERSION,
        what_you_sell=body.what_you_sell,
        icp=body.icp,
        proposed=[s.model_dump() for s in signals],
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return ProposeSignalsResponse(
        proposal_event_id=event.id,
        prompt_version=PROMPT_VERSION,
        signals=signals,
    )
```

- [ ] **Step 4: Register the router in main.py**

Edit `backend/app/main.py`:
- Add import near other router imports: `from app.routers.signals import router as signals_router`
- Add `app.include_router(signals_router)` near the other `include_router` calls

- [ ] **Step 5: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_propose_endpoint.py -v`
Expected: all PASS.

- [ ] **Step 6: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/signals.py backend/app/main.py backend/tests/test_propose_endpoint.py
git commit -m "feat(wizard): POST /workspace/signals/propose endpoint" -m "Calls LLM via injected get_llm_client dependency (Depends — override pattern per sonar/CLAUDE.md Python test mocking rule, avoids the issue-#6/#11 import-binding trap). Writes partial SignalProposalEvent row with completed_at=NULL. Rate-limited to 3/minute per IP. No DB writes to the signals table — confirm does that."
```

---

## Task 7: `POST /workspace/signals/confirm` endpoint

**Files:**
- Modify: `backend/app/routers/signals.py` (add confirm handler)
- Create: `backend/tests/test_confirm_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_confirm_endpoint.py`:

```python
import pytest
import json
from uuid import UUID
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.signal import Signal


class FakeLLM:
    async def complete(self, prompt: str, model: str) -> str:
        return json.dumps({
            "signals": [
                {"phrase": f"phrase {i}", "example_post": f"ex {i} body here", "intent_strength": 0.5}
                for i in range(8)
            ]
        })


class FakeEmbed:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_confirm_persists_accepted_and_user_added_signals(client, db_session):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post("/workspace/register", json={"workspace_name": "W", "email": "c@c.com", "password": "pw1234567890"})
    tok = (await client.post("/auth/token", data={"username": "c@c.com", "password": "pw1234567890"})).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    propose = (await client.post("/workspace/signals/propose", json={"what_you_sell": "X services"}, headers=hdrs)).json()
    event_id = propose["proposal_event_id"]

    resp = await client.post(
        "/workspace/signals/confirm",
        json={
            "proposal_event_id": event_id,
            "accepted": [0, 1, 2],
            "edited": [{"proposed_idx": 3, "final_phrase": "my edit", "final_example_post": "post body", "final_intent_strength": 0.7}],
            "rejected": [4, 5, 6, 7],
            "user_added": [{"phrase": "custom one", "example_post": "body body", "intent_strength": 0.8}],
        },
        headers=hdrs,
    )
    assert resp.status_code == 200
    body = resp.json()
    # 3 accepted + 1 edited + 1 user_added = 5 signals persisted
    assert len(body["signal_ids"]) == 5
    assert body["profile_active"] is True

    # Telemetry event is marked completed
    result = await db_session.execute(
        select(SignalProposalEvent).where(SignalProposalEvent.id == UUID(event_id))
    )
    row = result.scalar_one()
    assert row.completed_at is not None
    assert row.accepted_ids == ["0", "1", "2"]
    assert row.rejected_ids == ["4", "5", "6", "7"]
    assert len(row.edited_pairs) == 1
    assert len(row.user_added) == 1

    # Signal rows exist with embeddings populated
    sig_result = await db_session.execute(select(Signal))
    sigs = sig_result.scalars().all()
    assert len(sigs) == 5
    assert all(s.embedding is not None and len(list(s.embedding)) == 1536 for s in sigs)

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.mark.asyncio
async def test_confirm_rejects_mismatched_workspace(client, db_session):
    """A user in one workspace cannot confirm another workspace's proposal."""
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post("/workspace/register", json={"workspace_name": "A", "email": "d@d.com", "password": "pw1234567890"})
    tokA = (await client.post("/auth/token", data={"username": "d@d.com", "password": "pw1234567890"})).json()["access_token"]
    proposeA = (await client.post("/workspace/signals/propose", json={"what_you_sell": "X"}, headers={"Authorization": f"Bearer {tokA}"})).json()

    await client.post("/workspace/register", json={"workspace_name": "B", "email": "e@e.com", "password": "pw1234567890"})
    tokB = (await client.post("/auth/token", data={"username": "e@e.com", "password": "pw1234567890"})).json()["access_token"]

    resp = await client.post(
        "/workspace/signals/confirm",
        json={"proposal_event_id": proposeA["proposal_event_id"], "accepted": [0]},
        headers={"Authorization": f"Bearer {tokB}"},
    )
    assert resp.status_code == 404

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
```

- [ ] **Step 2: Run — verify fail**

Run: `docker compose exec -T api pytest tests/test_confirm_endpoint.py -v`
Expected: FAIL (endpoint not found).

- [ ] **Step 3: Add confirm handler to the router**

Edit `backend/app/routers/signals.py` — append below the `propose_signals` function:

```python
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.signal import Signal
from app.schemas.wizard import (
    ConfirmSignalsRequest,
    ConfirmSignalsResponse,
)
from app.services.embedding import get_embedding_provider, EmbeddingProvider


@router.post("/confirm", response_model=ConfirmSignalsResponse)
async def confirm_signals(
    body: ConfirmSignalsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embed: EmbeddingProvider = Depends(get_embedding_provider),
):
    # Look up the telemetry event — must belong to the caller's workspace.
    result = await db.execute(
        select(SignalProposalEvent).where(
            SignalProposalEvent.id == body.proposal_event_id,
            SignalProposalEvent.workspace_id == current_user.workspace_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Proposal event not found for this workspace")

    # Resolve final signal list from the three buckets (accepted / edited / user_added).
    # Rejected are just recorded; they don't produce signal rows.
    final_signals: list[dict] = []
    proposed = event.proposed  # list[dict] with the original LLM output

    for idx in body.accepted:
        if 0 <= idx < len(proposed):
            final_signals.append(proposed[idx])

    for pair in body.edited:
        final_signals.append({
            "phrase": pair.final_phrase,
            "example_post": pair.final_example_post,
            "intent_strength": pair.final_intent_strength,
        })

    for sig in body.user_added:
        final_signals.append(sig.model_dump())

    # Embed each confirmed signal's phrase and persist.
    signal_ids: list = []
    for s in final_signals:
        vector = await embed.embed(s["phrase"])
        row = Signal(
            workspace_id=current_user.workspace_id,
            phrase=s["phrase"],
            example_post=s["example_post"],
            intent_strength=s["intent_strength"],
            embedding=vector,
            enabled=True,
        )
        db.add(row)
        await db.flush()
        signal_ids.append(row.id)

    # Mark the telemetry event complete.
    event.accepted_ids = [str(i) for i in body.accepted]
    event.edited_pairs = [p.model_dump() for p in body.edited]
    event.rejected_ids = [str(i) for i in body.rejected]
    event.user_added = [s.model_dump() for s in body.user_added]
    event.completed_at = datetime.now(timezone.utc)

    await db.commit()

    # NOTE: marking the capability profile active is a placeholder until the
    # capability-profile-versions flow is extended. For the wizard-only scope,
    # profile_active=True is returned unconditionally once signals are persisted.
    # If the capability profile model has an activation step, wire it here.
    return ConfirmSignalsResponse(signal_ids=signal_ids, profile_active=True)
```

- [ ] **Step 4: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_confirm_endpoint.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/signals.py backend/tests/test_confirm_endpoint.py
git commit -m "feat(wizard): POST /workspace/signals/confirm endpoint" -m "Resolves final signal list from accepted/edited/user_added buckets, embeds each phrase via injected get_embedding_provider dependency, persists Signal rows, completes the SignalProposalEvent telemetry row. Workspace-scoped authorization — rejects 404 if the event belongs to a different workspace. Rejected indices are recorded on the telemetry row but don't produce signal rows."
```

---

## Task 8: End-to-end integration test

**Files:**
- Create: `backend/tests/test_wizard_flow.py`

- [ ] **Step 1: Write the full end-to-end test**

Create `backend/tests/test_wizard_flow.py`:

```python
import pytest
import json
from sqlalchemy import select
from app.main import app
from app.services.llm import get_llm_client
from app.services.embedding import get_embedding_provider
from app.models.signal import Signal
from app.models.signal_proposal_event import SignalProposalEvent


class FakeLLM:
    async def complete(self, prompt: str, model: str) -> str:
        return json.dumps({
            "signals": [
                {"phrase": f"signal {i}", "example_post": f"post body {i} here", "intent_strength": 0.5 + i * 0.01}
                for i in range(9)
            ]
        })


class FakeEmbed:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_happy_path_register_propose_confirm(client, db_session):
    """End-to-end: a new user registers, logs in, calls propose, confirms all
    9 proposed signals verbatim, and ends up with 9 Signal rows + 1 completed
    SignalProposalEvent."""
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbed()

    await client.post("/workspace/register", json={
        "workspace_name": "Happy Path Agency",
        "email": "happy@path.com",
        "password": "testpassword1234",
    })
    tok = (await client.post("/auth/token", data={"username": "happy@path.com", "password": "testpassword1234"})).json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    propose = (await client.post("/workspace/signals/propose", json={
        "what_you_sell": "Fractional CTO services for Series A-B SaaS startups",
        "icp": "CEOs and VPs Eng at 20-50 person startups",
    }, headers=hdrs)).json()
    assert len(propose["signals"]) == 9

    confirm = (await client.post("/workspace/signals/confirm", json={
        "proposal_event_id": propose["proposal_event_id"],
        "accepted": list(range(9)),
    }, headers=hdrs)).json()
    assert len(confirm["signal_ids"]) == 9
    assert confirm["profile_active"] is True

    sigs = (await db_session.execute(select(Signal))).scalars().all()
    assert len(sigs) == 9
    assert all(s.enabled for s in sigs)
    assert all(s.embedding is not None for s in sigs)

    ev_result = await db_session.execute(select(SignalProposalEvent))
    ev = ev_result.scalar_one()
    assert ev.completed_at is not None
    assert ev.prompt_version == "v1"

    app.dependency_overrides.pop(get_llm_client, None)
    app.dependency_overrides.pop(get_embedding_provider, None)
```

- [ ] **Step 2: Run — verify pass**

Run: `docker compose exec -T api pytest tests/test_wizard_flow.py -v`
Expected: PASS (Tasks 1–7 already built everything needed).

- [ ] **Step 3: Run full suite**

Run: `docker compose exec -T api pytest -q`
Expected: all green, count increased by 1.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_wizard_flow.py
git commit -m "test(wizard): end-to-end integration test (register → propose → confirm)" -m "Asserts the full happy path produces the expected Signal rows, embeddings, and completed telemetry event. Mocks LLM + embedding providers via Depends override (per sonar/CLAUDE.md Python test mocking rule)."
```

---

## Task 9: Structural CI gate — real LLM against fixed inputs

**Files:**
- Create: `backend/tests/test_propose_signals_shape.py`

This is the ONE test in the plan that hits the real OpenAI API. It's the structural gate from `wizard-decisions.md §3b` — runs the real prompt against 3 fixed inputs and asserts output shape (valid JSON, 8–10 signals, required fields, intent_strength in [0,1], no duplicates). It does NOT assert semantic quality — that's what production telemetry is for.

- [ ] **Step 1: Write the test**

Create `backend/tests/test_propose_signals_shape.py`:

```python
"""Structural CI gate for the propose_signals prompt.

Hits the REAL OpenAI API. Runs the prompt against 3 fixed inputs and
asserts output SHAPE, not semantic quality:
  - Valid JSON
  - signals array has length 8-10
  - Each signal has phrase (non-empty), example_post (non-empty), intent_strength in [0,1]
  - No duplicate phrases

Gated by OPENAI_API_KEY being a real key, not the placeholder. Skipped otherwise
so CI on a fork (no secret) doesn't fail.
"""
import json
import os
import pytest
from app.config import OPENAI_MODEL_EXPENSIVE, get_settings
from app.prompts.propose_signals import (
    SYSTEM_PROMPT, build_user_message, RESPONSE_JSON_SCHEMA,
)
from app.services.llm import OpenAILLMProvider

SANITY_INPUTS = [
    {
        "what_you_sell": "Fractional CTO services for Series A-B SaaS startups",
        "icp": "CEOs and VPs Eng at 20-50 person startups",
    },
    {
        "what_you_sell": "AI copywriting tool for e-commerce product descriptions",
        "icp": "DTC brand founders running on Shopify",
    },
    {
        "what_you_sell": "B2B data enrichment API for sales teams",
        "icp": None,
    },
]


def _has_real_openai_key() -> bool:
    key = get_settings().openai_api_key
    return bool(key) and not key.startswith("placeholder-") and key.startswith("sk-")


@pytest.mark.asyncio
@pytest.mark.skipif(not _has_real_openai_key(), reason="real OPENAI_API_KEY required")
@pytest.mark.parametrize("inputs", SANITY_INPUTS)
async def test_propose_signals_prompt_produces_valid_shape(inputs):
    """Does NOT assert quality — asserts shape. Quality is measured via
    production acceptance rate, not here. See docs/phase-2/wizard-decisions.md §3b."""
    provider = OpenAILLMProvider()
    user_msg = build_user_message(inputs["what_you_sell"], inputs["icp"])
    prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{user_msg}"
    raw = await provider.complete(prompt, model=OPENAI_MODEL_EXPENSIVE)

    # Strip markdown fence if present
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
    payload = json.loads(s.strip())

    assert "signals" in payload
    signals = payload["signals"]
    assert 8 <= len(signals) <= 10, f"expected 8-10 signals, got {len(signals)}"

    phrases_seen = set()
    for i, sig in enumerate(signals):
        assert "phrase" in sig and isinstance(sig["phrase"], str) and len(sig["phrase"]) > 0
        assert "example_post" in sig and isinstance(sig["example_post"], str) and len(sig["example_post"]) > 0
        assert "intent_strength" in sig
        strength = sig["intent_strength"]
        assert isinstance(strength, (int, float)) and 0 <= strength <= 1
        normalized = sig["phrase"].strip().lower()
        assert normalized not in phrases_seen, f"duplicate phrase at index {i}: {sig['phrase']}"
        phrases_seen.add(normalized)
```

- [ ] **Step 2: Run it (skipped locally if no real key; real CI runs it)**

Run: `docker compose exec -T api pytest tests/test_propose_signals_shape.py -v`
If the local `.env` has a placeholder OpenAI key, all three parameters skip with the reason "real OPENAI_API_KEY required". That's expected and correct.

If you have a real key locally and want to run once to verify, set it in `.env` temporarily and re-run. Expected: 3/3 PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_propose_signals_shape.py
git commit -m "test(wizard): structural CI gate for propose_signals prompt" -m "Hits real OpenAI API with 3 fixed sanity inputs; asserts output shape only (valid JSON, 8-10 signals, required fields, intent_strength bounds, no duplicate phrases). Does NOT judge semantic quality — that is what production telemetry via signal_proposal_events measures. Skipped when OPENAI_API_KEY is the placeholder, so fork CI doesn't fail."
```

---

## Task 10: Frontend SignalConfig.tsx — 5-step wizard

**Files:**
- Create: `frontend/src/pages/SignalConfig.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/pages/SignalConfig.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

interface ProposedSignal {
  phrase: string;
  example_post: string;
  intent_strength: number;
}

interface SignalSelection {
  proposed: ProposedSignal;
  status: "accepted" | "edited" | "rejected";
  edited?: ProposedSignal;
}

type Step = 1 | 2 | 3 | 4 | 5;

export function SignalConfig() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [whatYouSell, setWhatYouSell] = useState("");
  const [icp, setIcp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposalEventId, setProposalEventId] = useState<string | null>(null);
  const [selections, setSelections] = useState<SignalSelection[]>([]);
  const [userAdded, setUserAdded] = useState<ProposedSignal[]>([]);

  const token = () => localStorage.getItem("access_token") || "";
  const authHeaders = () => ({ Authorization: `Bearer ${token()}` });

  const handlePropose = async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await axios.post("/workspace/signals/propose",
        { what_you_sell: whatYouSell, icp: icp || null },
        { headers: authHeaders() });
      setProposalEventId(data.proposal_event_id);
      setSelections(data.signals.map((s: ProposedSignal) => ({ proposed: s, status: "accepted" as const })));
      setStep(4);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to generate signals. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = (idx: number, status: SignalSelection["status"]) => {
    const next = [...selections];
    next[idx] = { ...next[idx], status };
    setSelections(next);
  };

  const updateEdit = (idx: number, field: keyof ProposedSignal, value: string | number) => {
    const next = [...selections];
    const current = next[idx].edited || { ...next[idx].proposed };
    next[idx] = { ...next[idx], status: "edited", edited: { ...current, [field]: value } };
    setSelections(next);
  };

  const handleConfirm = async () => {
    if (!proposalEventId) return;
    setLoading(true); setError(null);
    const accepted: number[] = [];
    const edited: any[] = [];
    const rejected: number[] = [];
    selections.forEach((s, idx) => {
      if (s.status === "accepted") accepted.push(idx);
      else if (s.status === "edited" && s.edited) edited.push({
        proposed_idx: idx,
        final_phrase: s.edited.phrase,
        final_example_post: s.edited.example_post,
        final_intent_strength: s.edited.intent_strength,
      });
      else if (s.status === "rejected") rejected.push(idx);
    });
    try {
      await axios.post("/workspace/signals/confirm",
        { proposal_event_id: proposalEventId, accepted, edited, rejected, user_added: userAdded },
        { headers: authHeaders() });
      navigate("/dashboard");
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to save signals.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="mb-6 text-sm text-gray-500">Step {step} of 5</div>

      {step === 1 && (
        <section>
          <h1 className="text-2xl font-semibold mb-3">What do you sell?</h1>
          <p className="text-gray-600 mb-4">In one or two sentences. Example: "Fractional CTO services for Series A-B SaaS startups with small engineering teams."</p>
          <textarea className="w-full border rounded p-3 min-h-32" value={whatYouSell} onChange={e => setWhatYouSell(e.target.value)} />
          <button className="mt-4 bg-black text-white rounded px-4 py-2 disabled:opacity-50" disabled={whatYouSell.trim().length < 5} onClick={() => setStep(2)}>Next</button>
        </section>
      )}

      {step === 2 && (
        <section>
          <h1 className="text-2xl font-semibold mb-3">Who's your ICP? (optional)</h1>
          <p className="text-gray-600 mb-4">Who are the people you sell to? Example: "CEOs and VPs Eng at 20-50 person startups."</p>
          <input className="w-full border rounded p-3" value={icp} onChange={e => setIcp(e.target.value)} />
          <div className="mt-4 flex gap-2">
            <button className="border rounded px-4 py-2" onClick={() => setStep(1)}>Back</button>
            <button className="bg-black text-white rounded px-4 py-2" onClick={() => setStep(3)}>Next</button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section>
          <h1 className="text-2xl font-semibold mb-3">Generating signals...</h1>
          <p className="text-gray-600 mb-4">This takes a few seconds.</p>
          {!loading && !proposalEventId && (
            <button className="bg-black text-white rounded px-4 py-2" onClick={handlePropose}>Generate</button>
          )}
          {loading && <div>Thinking...</div>}
          {error && <div className="text-red-600 mt-3">{error} <button className="underline" onClick={handlePropose}>Retry</button></div>}
        </section>
      )}

      {step === 4 && (
        <section>
          <h1 className="text-2xl font-semibold mb-3">Review your signals</h1>
          <p className="text-gray-600 mb-4">Accept, edit, or reject each one. Add your own if anything's missing.</p>
          {selections.map((sel, idx) => (
            <div key={idx} className="border rounded p-4 mb-3">
              <div className="flex gap-2 items-start">
                <input
                  className="flex-1 font-medium"
                  value={sel.edited?.phrase ?? sel.proposed.phrase}
                  onChange={e => updateEdit(idx, "phrase", e.target.value)}
                />
              </div>
              <div className="text-sm text-gray-500 mt-1 italic">"{sel.proposed.example_post}"</div>
              <div className="mt-2 flex gap-2">
                <button onClick={() => updateStatus(idx, "accepted")} className={`text-sm px-3 py-1 rounded ${sel.status === "accepted" ? "bg-green-100" : "border"}`}>Accept</button>
                <button onClick={() => updateStatus(idx, "rejected")} className={`text-sm px-3 py-1 rounded ${sel.status === "rejected" ? "bg-red-100" : "border"}`}>Reject</button>
              </div>
            </div>
          ))}
          <div className="mt-4 flex gap-2">
            <button className="border rounded px-4 py-2" onClick={() => setStep(3)}>Back</button>
            <button className="bg-black text-white rounded px-4 py-2" onClick={() => setStep(5)}>Next</button>
          </div>
        </section>
      )}

      {step === 5 && (
        <section>
          <h1 className="text-2xl font-semibold mb-3">Ready to save?</h1>
          <p className="text-gray-600 mb-4">
            {selections.filter(s => s.status !== "rejected").length + userAdded.length} signal(s) will be saved.
          </p>
          {error && <div className="text-red-600 mb-3">{error}</div>}
          <div className="flex gap-2">
            <button className="border rounded px-4 py-2" onClick={() => setStep(4)}>Back</button>
            <button className="bg-black text-white rounded px-4 py-2 disabled:opacity-50" disabled={loading} onClick={handleConfirm}>
              {loading ? "Saving..." : "Save and open dashboard"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

export default SignalConfig;
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds. Fix any TypeScript errors inline.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SignalConfig.tsx
git commit -m "feat(frontend): SignalConfig wizard page — 5 steps, single component" -m "Step-state machine inside one <SignalConfig/> component per wizard-decisions.md §4 (no multi-step routing). Calls POST /workspace/signals/propose then /confirm, then navigates to /dashboard. Uses localStorage JWT token for Authorization header."
```

---

## Task 11: Frontend routing + Onboarding redirect

**Files:**
- Modify: `frontend/src/App.tsx` — add `/signals/setup` route
- Modify: `frontend/src/pages/Onboarding.tsx` — redirect first-time users

- [ ] **Step 1: Read the current files to understand pattern**

Run: `cat frontend/src/App.tsx frontend/src/pages/Onboarding.tsx`
Note the routing library style, auth guard pattern, and how `Onboarding.tsx` currently routes new users.

- [ ] **Step 2: Add the `/signals/setup` route**

Edit `frontend/src/App.tsx`:
- Import the new page: `import SignalConfig from "./pages/SignalConfig";`
- Add route inside the authenticated routes group:

```tsx
<Route path="/signals/setup" element={<SignalConfig />} />
```

- [ ] **Step 3: Update Onboarding.tsx**

Edit `frontend/src/pages/Onboarding.tsx`:
- On first successful login/register, navigate to `/signals/setup` instead of whatever the previous destination was
- Preserve the existing auth-token-store logic; only change the navigate destination

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Smoke test in browser (manual)**

Run: `docker compose up -d frontend && open http://localhost:5173/register`
Register a new user → should land on `/signals/setup` → wizard step 1 visible.

(Full manual testing against real LLM is deferred to the structural CI test + real user observation per wizard-decisions.md §3.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/Onboarding.tsx
git commit -m "feat(frontend): /signals/setup route + onboarding redirect" -m "New users land on the wizard after registration/first login. Existing users with signals already configured are unaffected — they hit existing routes."
```

---

## Task 12: CLAUDE.md updates — routing rule + prompts convention

**Files:**
- Modify: `CLAUDE.md` (project-root file, not `sonar/CLAUDE.md` — same file)

- [ ] **Step 1: Find the LLM routing section**

Run: `grep -n "gpt-4o-mini\|HIGH priority\|expensive tier\|routing layer" CLAUDE.md`
Note every line — each is a candidate for update.

- [ ] **Step 2: Update the LLM routing rule**

Edit `CLAUDE.md`:
- Replace every reference to `gpt-4o-mini` in the routing rule with `gpt-5.4-mini`
- Add a brief note: *"Upgraded from `gpt-4o-mini` on 2026-04-17 as part of the Wizard slice. Single routing layer preserved via `OPENAI_MODEL_EXPENSIVE` constant in `app/config.py`. To bump again, edit the constant and update this rule in lockstep."*

- [ ] **Step 3: Add the `app/prompts/` convention note**

Add a new short subsection under "LLM and agent discipline":

```markdown
- **Prompts live in `app/prompts/<name>.py`.** Each prompt module exports `PROMPT_VERSION: str`, a static `SYSTEM_PROMPT`, a `build_user_message(...)` function that composes the user turn (the ONLY place user input is interpolated), and a `RESPONSE_JSON_SCHEMA` for Structured Outputs. Every call to the prompt logs `PROMPT_VERSION` alongside the call. Bump the version on every content change. First entry under this convention: `app/prompts/propose_signals.py` (Wizard slice, 2026-04-17).
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): LLM tier = gpt-5.4-mini, add app/prompts/ convention" -m "Reflects the Wizard-slice decisions: project-wide expensive-tier bump from gpt-4o-mini to gpt-5.4-mini (via OPENAI_MODEL_EXPENSIVE constant — single routing layer preserved), and the new app/prompts/<name>.py convention with PROMPT_VERSION + static SYSTEM_PROMPT + build_user_message + RESPONSE_JSON_SCHEMA."
```

---

## Self-Review Notes

Applied inline before saving this plan:

**Spec coverage check:** Every sub-requirement of design.md §4.1 and wizard-decisions.md §1–6 maps to a task — scope (Task 6 + 7 cover the two endpoints, Task 10/11 cover the `/signals/setup` frontend), model bump (Task 1), telemetry (Tasks 2–3 + emission in Tasks 6–7), structural CI gate (Task 9), prompt versioning (Task 4 + logged in Task 6). Out-of-scope items (management endpoints, offline eval harness, A/B rail) are explicitly flagged in the Scope section and will live in follow-up plans.

**Placeholder scan:** No TBDs or vague "add error handling" steps. Every code block is complete and runnable. The one `NOTE` in Task 7 about `profile_active` is flagged as a scope boundary, not a placeholder — the capability-profile-activation step is an intentionally minimal stub until the profile-versions flow is extended in a later slice.

**Type consistency:** `ProposedSignal` shape is the same across Tasks 4 (prompt schema), 5 (Pydantic), 6 (router response), 7 (consumed in confirm), 8 (integration test), 10 (frontend TypeScript). `SignalProposalEvent` field names match across the migration (Task 2), ORM model (Task 3), router telemetry writes (Tasks 6–7), and tests.

**Scope check:** ~12 tasks — matches the target. Single slice, no sub-projects needed.

---

## Open Questions (to resolve during execution, not blocking start)

- Rate-limit value for `/propose` — starting at 3/minute; tune if OpenAI latency + real user behavior say otherwise.
- Exact capability-profile activation logic — Task 7 returns `profile_active=True` unconditionally on signal save. If the profile-versions model has an activation step, Task 7's handler should wire it.
- Whether the structural CI test should run on every PR or only on prompt/endpoint changes — currently every PR (simpler). Revisit if cost becomes noticeable.
- Error-handling UX for LLM failures in the frontend — Task 10 has a Retry button and generic error message. Tune after real-world observation.
