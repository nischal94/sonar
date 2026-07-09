# Sonar Phase 2.6 — Fit × Intent Hybrid Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Ready to execute (design approved — see `docs/phase-2-6/design.md`)
**Date:** 2026-04-20 (written end-of-session-9)
**Supersedes:** Narrow "threshold calibration" framing from issue #106

**Goal:** Replace Sonar's single-axis post-similarity matching (`combined_score`) with a two-axis hybrid that multiplies a per-connection **fit_score** (is this author a buyer?) by a per-post **intent_score** (does this post show intent?). Fix the Lipi Mittal / NotifyVisitors class of failure proven by the session-8 calibration evidence.

**Architecture:** For each connection, compute `fit_score = cos(ICP, connection) - λ·cos(seller_mirror, connection)` where ICP and seller-mirror are LLM-extracted from the workspace URL/doc/text. For each post, compute `intent_score` from relevance + timing (relationship removed — moves to dashboard filter). Combine multiplicatively: `final_score = fit_score × intent_score`. Ship behind `workspace.use_hybrid_scoring` feature flag; existing workspaces stay on the old scorer until explicitly flipped.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic + pgvector + OpenAI (`text-embedding-3-small` + `gpt-5.4-mini`) + Celery + pytest. Frontend: React 18 + TypeScript + Vite + React Router v6.

---

## Pre-flight for every task

Every backend command runs inside the `api` container. Reminders:

```bash
docker compose up -d postgres redis api                 # stack up
docker compose exec -T api alembic upgrade head         # latest migrations
docker compose exec -T api pytest -q                    # baseline: all 136 pass
```

Never `cd backend && uv run ...` — the host has no `uv`/Python.

Branch discipline: each task is its own feature branch + PR, per Sonar's CLAUDE.md "Complex changes" rule. Branch prefix `feat/phase-2-6-<slice>`. Dispatch `superpowers:code-reviewer` before opening every PR; wait for approval before merging. No exceptions.

---

## File Structure

New files:

```
backend/alembic/versions/
  008_connection_fit_score.py             # ADD fit_score to connections
  009_workspace_use_hybrid_scoring.py     # ADD use_hybrid_scoring flag
  010_icp_and_seller_mirror.py            # ADD icp, seller_mirror, their embeddings

backend/app/prompts/
  extract_icp_and_seller_mirror.py        # Single dual-output prompt

backend/app/services/
  fit_scorer.py                           # compute_fit_score, compute_intent_score, compute_hybrid_score

backend/scripts/
  backfill_fit_scores.py                  # One-shot per-workspace fit_score backfill

backend/tests/
  test_migration_008_009_010.py           # Migration round-trip test
  test_extract_icp_prompt.py              # Prompt module unit test
  test_fit_scorer.py                      # Fit scorer unit tests
  test_profile_extract_icp.py             # /profile/extract integration test (ICP path)
  test_pipeline_hybrid_scoring.py         # Pipeline branch integration test
  test_backfill_fit_scores.py             # Backfill script integration test
  test_calibrate_hybrid.py                # analyze-hybrid subcommand unit test
```

Modified files:

```
backend/app/models/workspace.py           # +use_hybrid_scoring, +icp, +seller_mirror, +embeddings
backend/app/models/connection.py          # +fit_score
backend/app/services/profile_extractor.py # Extract & persist ICP + seller_mirror
backend/app/routers/profile.py            # Return icp/seller_mirror in response
backend/app/workers/pipeline.py           # Branch on use_hybrid_scoring
backend/scripts/calibrate_matching.py     # +analyze-hybrid subcommand w/ λ sweep
frontend/src/pages/SignalConfig.tsx       # +ICP review step (insert as step 3; renumber)
```

---

## Task 1: Migrations 008+009+010 + ORM model updates

Adds all three schema additions in one PR. They're independent and all additive, so one migration-bundle PR avoids three back-to-back review cycles for trivial DDL.

**Files:**
- Create: `backend/alembic/versions/008_connection_fit_score.py`
- Create: `backend/alembic/versions/009_workspace_use_hybrid_scoring.py`
- Create: `backend/alembic/versions/010_icp_and_seller_mirror.py`
- Modify: `backend/app/models/connection.py` — add `fit_score` column
- Modify: `backend/app/models/workspace.py` — add `use_hybrid_scoring` to Workspace, add `icp`/`seller_mirror`/`icp_embedding`/`seller_mirror_embedding` to CapabilityProfileVersion
- Test: `backend/tests/test_migration_008_009_010.py`

Branch: `feat/phase-2-6-migrations`

- [ ] **Step 1: Write the failing round-trip migration test**

Create `backend/tests/test_migration_008_009_010.py`:

```python
"""Round-trip test: head → 007 → head works without errors and preserves row counts."""
import pytest
from sqlalchemy import text
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_cfg() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg


def test_migrations_008_009_010_round_trip(alembic_cfg: Config):
    """Upgrade to head, downgrade to 007, upgrade to head. Should not error."""
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "007")
    command.upgrade(alembic_cfg, "head")


def test_new_columns_present_after_upgrade(alembic_cfg: Config, sync_engine):
    """After head, the 6 new columns exist with correct types and defaults."""
    command.upgrade(alembic_cfg, "head")
    with sync_engine.connect() as conn:
        # Migration 008
        row = conn.execute(text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name='connections' AND column_name='fit_score'"
        )).fetchone()
        assert row is not None, "connections.fit_score missing"
        assert row.data_type == "real"
        assert row.is_nullable == "YES"

        # Migration 009
        row = conn.execute(text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name='workspaces' AND column_name='use_hybrid_scoring'"
        )).fetchone()
        assert row is not None, "workspaces.use_hybrid_scoring missing"
        assert row.data_type == "boolean"
        assert row.is_nullable == "NO"
        assert "false" in (row.column_default or "").lower()

        # Migration 010
        for col in ("icp", "seller_mirror", "icp_embedding", "seller_mirror_embedding"):
            row = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='capability_profile_versions' AND column_name='{col}'"
            )).fetchone()
            assert row is not None, f"capability_profile_versions.{col} missing"
```

Note: `sync_engine` fixture may not exist yet. If it doesn't, add it to `conftest.py`:

```python
@pytest.fixture
def sync_engine():
    """Synchronous engine for DDL introspection. Separate from the async test engine."""
    from sqlalchemy import create_engine
    from app.config import get_settings
    url = get_settings().database_url.replace("+asyncpg", "")
    engine = create_engine(url)
    yield engine
    engine.dispose()
```

- [ ] **Step 2: Run the test — it must fail**

```bash
docker compose exec -T api pytest tests/test_migration_008_009_010.py -v
```

Expected: FAIL — migrations 008/009/010 don't exist yet. Error mentions "Can't locate revision 008" or similar.

- [ ] **Step 3: Write migration 008**

Create `backend/alembic/versions/008_connection_fit_score.py`:

```python
"""Add fit_score to connections (Phase 2.6).

Revision ID: 008
Revises: 007
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connections",
        sa.Column("fit_score", sa.REAL(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connections", "fit_score")
```

- [ ] **Step 4: Write migration 009**

Create `backend/alembic/versions/009_workspace_use_hybrid_scoring.py`:

```python
"""Add use_hybrid_scoring flag to workspaces (Phase 2.6).

Revision ID: 009
Revises: 008
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "use_hybrid_scoring",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "use_hybrid_scoring")
```

- [ ] **Step 5: Write migration 010**

Create `backend/alembic/versions/010_icp_and_seller_mirror.py`:

```python
"""Add icp, seller_mirror, and their embeddings to capability_profile_versions (Phase 2.6).

Revision ID: 010
Revises: 009
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("capability_profile_versions", sa.Column("icp", sa.Text(), nullable=True))
    op.add_column("capability_profile_versions", sa.Column("seller_mirror", sa.Text(), nullable=True))
    op.add_column("capability_profile_versions", sa.Column("icp_embedding", Vector(1536), nullable=True))
    op.add_column("capability_profile_versions", sa.Column("seller_mirror_embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    op.drop_column("capability_profile_versions", "seller_mirror_embedding")
    op.drop_column("capability_profile_versions", "icp_embedding")
    op.drop_column("capability_profile_versions", "seller_mirror")
    op.drop_column("capability_profile_versions", "icp")
```

- [ ] **Step 6: Update Connection ORM model**

Modify `backend/app/models/connection.py` — add to the Connection class (place next to `relationship_score`):

```python
    fit_score = Column(Float, nullable=True)
```

- [ ] **Step 7: Update Workspace ORM model**

Modify `backend/app/models/workspace.py` — add to the Workspace class (place next to `matching_threshold`):

```python
    use_hybrid_scoring = Column(Boolean, nullable=False, default=False, server_default="false")
```

And add to the CapabilityProfileVersion class (place after `anti_keywords`):

```python
    icp = Column(Text, nullable=True)
    seller_mirror = Column(Text, nullable=True)
    icp_embedding = Column(Vector(1536), nullable=True)
    seller_mirror_embedding = Column(Vector(1536), nullable=True)
```

Confirm imports in the file — `Vector` should already be imported for the existing `embedding` column. If not:

```python
from pgvector.sqlalchemy import Vector
```

- [ ] **Step 8: Run the migration round-trip test — must pass**

```bash
docker compose exec -T api alembic downgrade base    # fresh start
docker compose exec -T api pytest tests/test_migration_008_009_010.py -v
```

Expected: 2 passed. If the round-trip fails with "relation already exists," the downgrade path is missing a column.

- [ ] **Step 9: Run the full test suite — must pass (regression check)**

```bash
docker compose exec -T api pytest -q
```

Expected: 136 + 2 new = 138 passed (or same "5 passing pre-existing failures" baseline from CLAUDE.md).

- [ ] **Step 10: Verify manually via psql**

```bash
docker compose exec -T postgres psql -U sonar -d sonar -c "\d connections"
docker compose exec -T postgres psql -U sonar -d sonar -c "\d workspaces"
docker compose exec -T postgres psql -U sonar -d sonar -c "\d capability_profile_versions"
```

Each should list the new columns.

- [ ] **Step 11: Dispatch `superpowers:code-reviewer`**

Open a review request against the branch diff. Spec compliance check: migrations match design §4.2 "Schema changes (three non-breaking migrations)." Code quality check: ORM models mirror migrations, no accidental defaults, no broken relationships.

- [ ] **Step 12: Commit and open PR**

```bash
git checkout -b feat/phase-2-6-migrations
git add backend/alembic/versions/008_connection_fit_score.py \
        backend/alembic/versions/009_workspace_use_hybrid_scoring.py \
        backend/alembic/versions/010_icp_and_seller_mirror.py \
        backend/app/models/connection.py \
        backend/app/models/workspace.py \
        backend/tests/test_migration_008_009_010.py \
        backend/tests/conftest.py
git commit -m "feat(db): add Phase 2.6 migrations 008/009/010 + ORM updates

- connections.fit_score REAL NULL
- workspaces.use_hybrid_scoring BOOLEAN NOT NULL DEFAULT FALSE
- capability_profile_versions.icp TEXT NULL + embedding
- capability_profile_versions.seller_mirror TEXT NULL + embedding

All additive. Existing rows keep current behavior until explicitly flipped.
Part of Phase 2.6 — see docs/phase-2-6/design.md §4.2."
git push -u origin feat/phase-2-6-migrations
gh pr create --title "feat(db): Phase 2.6 migrations 008/009/010" \
             --body "$(cat <<'EOF'
## Summary
Schema additions for Phase 2.6 Fit × Intent hybrid scoring:
- Migration 008 — `connections.fit_score REAL NULL`
- Migration 009 — `workspaces.use_hybrid_scoring BOOLEAN DEFAULT FALSE`
- Migration 010 — `capability_profile_versions.{icp, seller_mirror, icp_embedding, seller_mirror_embedding}`

All three are additive with safe defaults. Zero breaking changes; every existing workspace continues running the existing scorer until explicitly flipped via the flag.

## Test plan
- [x] Round-trip test (head → 007 → head) passes
- [x] New-column introspection test passes
- [x] Full backend suite still green
- [ ] Reviewer verifies `upgrade()` / `downgrade()` symmetry
EOF
)"
```

---

## Task 2: ICP + seller_mirror prompt module

A single dual-output prompt module, following the `propose_signals.py` pattern. Lives under `app/prompts/` with its own `PROMPT_VERSION` so changes are auditable.

**Files:**
- Create: `backend/app/prompts/extract_icp_and_seller_mirror.py`
- Test: `backend/tests/test_extract_icp_prompt.py`

Branch: `feat/phase-2-6-icp-prompt`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_extract_icp_prompt.py`:

```python
"""Prompt module: structure + schema validation.

This file does NOT test LLM output quality (that's for calibration), only that
the prompt module is well-formed: version set, system prompt static, user
message builder interpolates the right inputs, schema validates realistic JSON.
"""
import json
import pytest
from jsonschema import validate, ValidationError

from app.prompts import extract_icp_and_seller_mirror as mod


def test_prompt_version_is_semver_like():
    assert isinstance(mod.PROMPT_VERSION, str)
    assert mod.PROMPT_VERSION.startswith("v")


def test_system_prompt_is_static_and_nonempty():
    assert isinstance(mod.SYSTEM_PROMPT, str)
    assert len(mod.SYSTEM_PROMPT) > 100
    # Must not contain user-controlled placeholders
    assert "{" not in mod.SYSTEM_PROMPT
    assert "}" not in mod.SYSTEM_PROMPT


def test_build_user_message_interpolates_source_text():
    source = "We sell CDP tooling for D2C brands."
    msg = mod.build_user_message(source_text=source)
    assert source in msg


def test_build_user_message_rejects_empty():
    with pytest.raises(ValueError):
        mod.build_user_message(source_text="")


def test_response_schema_validates_well_formed_output():
    sample = {
        "icp": "Marketing, growth, or e-commerce leaders at D2C or direct-to-consumer brands generating >$1M ARR. Not employees of martech SaaS vendors or competing agencies.",
        "seller_mirror": "Founders, CEOs, CPOs, and sales directors at CDP / marketing-automation / customer-engagement SaaS companies. People whose LinkedIn headlines name-drop their own product.",
    }
    validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)


def test_response_schema_rejects_missing_field():
    sample = {"icp": "..."}  # missing seller_mirror
    with pytest.raises(ValidationError):
        validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)


def test_response_schema_rejects_short_fields():
    sample = {"icp": "short", "seller_mirror": "also short"}
    with pytest.raises(ValidationError):
        validate(instance=sample, schema=mod.RESPONSE_JSON_SCHEMA)
```

- [ ] **Step 2: Run the test — must fail**

```bash
docker compose exec -T api pytest tests/test_extract_icp_prompt.py -v
```

Expected: FAIL — `ModuleNotFoundError: extract_icp_and_seller_mirror`.

- [ ] **Step 3: Write the prompt module**

Create `backend/app/prompts/extract_icp_and_seller_mirror.py`:

```python
"""Extract ICP paragraph + seller-mirror paragraph from a workspace's source text.

Single dual-output prompt per design §3.2 and §8. Outputs are consumed by
profile_extractor to persist icp / seller_mirror text + embeddings on
capability_profile_versions.

PROMPT_VERSION: bump on every content change. Logged alongside every call.
"""

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are a B2B sales intelligence analyst. Given a company's
self-description (from their website, a sales playbook, or a typed summary),
your job is to produce two paragraphs that describe (a) who that company's
buyers are and (b) what OTHER companies that sell the SAME capability look
like on LinkedIn.

Rules for the ICP paragraph:
1. Name the buyer's role, seniority, and company shape (industry, stage, size).
2. Phrase contrastively — explicitly name who the buyer is NOT. Example: "Not
   employees of martech SaaS vendors or competing agencies."
3. Written in plain English. No bullet lists, no headers. One dense paragraph.
4. 50-120 words.

Rules for the seller-mirror paragraph:
1. Describe what other SELLERS of this same capability look like on LinkedIn.
   Who would a competitor's founder, CEO, CPO, or sales director look like?
2. Focus on linguistic tells in LinkedIn headlines — product name-drops,
   stage signals ("Series B", "YC W22"), role words ("CEO", "Founder",
   "Head of Sales at X").
3. This paragraph is SUBTRACTED from the ICP signal during scoring, so
   precision matters: describe the seller-shape as specifically as you can.
4. 50-120 words.

Return strict JSON with exactly two keys: icp and seller_mirror. No other keys,
no prose outside the JSON."""


def build_user_message(source_text: str) -> str:
    """Compose the user turn. This is the only place user input is interpolated.

    Raises ValueError if source_text is empty or whitespace-only.
    """
    if not source_text or not source_text.strip():
        raise ValueError("source_text must be non-empty")
    return (
        "Here is the company's self-description. Produce the ICP and seller-mirror "
        "paragraphs per the rules.\n\n"
        "---\n"
        f"{source_text.strip()}\n"
        "---"
    )


RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "icp": {
            "type": "string",
            "minLength": 80,
            "maxLength": 1200,
        },
        "seller_mirror": {
            "type": "string",
            "minLength": 80,
            "maxLength": 1200,
        },
    },
    "required": ["icp", "seller_mirror"],
    "additionalProperties": False,
}
```

- [ ] **Step 4: Run the test — must pass**

```bash
docker compose exec -T api pytest tests/test_extract_icp_prompt.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run full suite — must still pass**

```bash
docker compose exec -T api pytest -q
```

- [ ] **Step 6: Dispatch `superpowers:code-reviewer`**

Spec compliance: matches design §3.2 "ICP paragraph: contrastive phrasing" + "Seller-mirror paragraph: linguistic mirror." Code quality: no user-input interpolation into SYSTEM_PROMPT, schema has `additionalProperties: false`, min/max bounds reasonable.

- [ ] **Step 7: Commit + PR**

```bash
git checkout -b feat/phase-2-6-icp-prompt
git add backend/app/prompts/extract_icp_and_seller_mirror.py \
        backend/tests/test_extract_icp_prompt.py
git commit -m "feat(prompts): add extract_icp_and_seller_mirror prompt module

Single dual-output prompt producing an ICP paragraph + seller-mirror
paragraph from a workspace's source text. Consumed by profile_extractor
(Task 4) to populate capability_profile_versions.icp and .seller_mirror.

PROMPT_VERSION=v1. Contrastive ICP phrasing + explicit seller-shape
description per design §3.2."
git push -u origin feat/phase-2-6-icp-prompt
gh pr create --title "feat(prompts): ICP + seller-mirror extraction prompt" \
             --body "$(cat <<'EOF'
## Summary
- New prompt module: `app/prompts/extract_icp_and_seller_mirror.py`
- Dual-output: `{ icp, seller_mirror }` JSON
- Follows the `propose_signals.py` convention (PROMPT_VERSION, static SYSTEM_PROMPT, `build_user_message()` only place user input is interpolated, `RESPONSE_JSON_SCHEMA` for validation)

## Test plan
- [x] 6 unit tests pass (version set, system prompt static, user builder validates, schema validates well-formed output and rejects malformed)
- [x] Full suite still green
EOF
)"
```

---

## Task 3: Fit scorer service

Pure-function scoring module. No DB, no LLM. Easy to test. Defines `compute_fit_score`, `compute_intent_score`, `compute_hybrid_score`.

Key implementation decision: **floor `fit_score` at 0.0**. If `cos(icp) - λ·cos(mirror)` goes negative (connection looks more like a seller than a buyer), clamp to 0. Multiplying a negative fit by a positive intent would give negative final_score and invert ordering — not the intended behavior. Flooring at 0 means anti-ICP connections get `final_score = 0` (correct suppression).

**Files:**
- Create: `backend/app/services/fit_scorer.py`
- Test: `backend/tests/test_fit_scorer.py`

Branch: `feat/phase-2-6-fit-scorer`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_fit_scorer.py`:

```python
"""Unit tests for fit_scorer — pure math, no DB, no LLM."""
from datetime import datetime, timedelta, timezone
import math

import pytest

from app.services.fit_scorer import (
    cosine_similarity,
    compute_fit_score,
    compute_intent_score,
    compute_hybrid_score,
)


# ---------- cosine_similarity ----------

def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert math.isclose(cosine_similarity(v, v), 1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_cosine_similarity_opposite_vectors():
    assert math.isclose(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)


def test_cosine_similarity_zero_vector_returns_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# ---------- compute_fit_score ----------

def test_fit_score_pure_icp_match_no_seller_signal():
    # ICP matches perfectly; seller signal absent
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [1.0, 0.0, 0.0]  # perfect ICP, zero seller
    fit = compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.3)
    assert math.isclose(fit, 1.0, abs_tol=1e-6)


def test_fit_score_pure_seller_match_floored_at_zero():
    # Connection is a perfect seller mirror, nothing like ICP
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.0, 1.0, 0.0]  # perfect mirror → raw = 0 - 0.3*1 = -0.3
    fit = compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.3)
    assert fit == 0.0, "negative raw fit must floor at 0"


def test_fit_score_lambda_zero_equals_raw_icp_cosine():
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.8, 0.6, 0.0]
    expected = cosine_similarity(icp_emb, conn_emb)  # 0.8
    assert math.isclose(
        compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=0.0),
        expected, abs_tol=1e-6,
    )


def test_fit_score_lambda_one_subtracts_full_mirror_term():
    icp_emb = [1.0, 0.0, 0.0]
    mirror_emb = [0.0, 1.0, 0.0]
    conn_emb = [0.8, 0.6, 0.0]
    # raw = 0.8 - 1.0*0.6 = 0.2
    assert math.isclose(
        compute_fit_score(icp_emb, mirror_emb, conn_emb, lambda_=1.0),
        0.2, abs_tol=1e-6,
    )


def test_fit_score_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        compute_fit_score([1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0], lambda_=0.3)


def test_fit_score_negative_lambda_raises():
    with pytest.raises(ValueError):
        compute_fit_score([1.0], [0.5], [1.0], lambda_=-0.1)


# ---------- compute_intent_score ----------

def test_intent_score_fresh_post_full_relevance():
    now = datetime.now(timezone.utc)
    score = compute_intent_score(relevance_score=1.0, posted_at=now)
    assert math.isclose(score, 1.0, abs_tol=1e-3)  # 0.7*1 + 0.3*1 = 1


def test_intent_score_stale_post_timing_decayed_to_zero():
    then = datetime.now(timezone.utc) - timedelta(hours=48)
    score = compute_intent_score(relevance_score=1.0, posted_at=then)
    # relevance 1 * 0.7 + timing 0 * 0.3 = 0.7
    assert math.isclose(score, 0.7, abs_tol=1e-3)


def test_intent_score_mid_decay():
    then = datetime.now(timezone.utc) - timedelta(hours=12)
    score = compute_intent_score(relevance_score=0.5, posted_at=then)
    # relevance 0.5 * 0.7 + timing 0.5 * 0.3 = 0.35 + 0.15 = 0.5
    assert math.isclose(score, 0.5, abs_tol=1e-2)


def test_intent_score_clamped_to_unit_interval():
    now = datetime.now(timezone.utc)
    assert 0.0 <= compute_intent_score(relevance_score=0.0, posted_at=now) <= 1.0
    assert 0.0 <= compute_intent_score(relevance_score=1.5, posted_at=now) <= 1.0


# ---------- compute_hybrid_score ----------

def test_hybrid_score_multiplies_fit_and_intent():
    assert math.isclose(compute_hybrid_score(fit_score=0.4, intent_score=0.9), 0.36)


def test_hybrid_score_zero_fit_suppresses():
    """The Lipi Mittal fix: low fit zeros out regardless of intent."""
    assert compute_hybrid_score(fit_score=0.0, intent_score=0.95) == 0.0


def test_hybrid_score_zero_intent_suppresses():
    assert compute_hybrid_score(fit_score=0.8, intent_score=0.0) == 0.0


def test_hybrid_score_clamps_to_unit_interval():
    assert compute_hybrid_score(fit_score=1.0, intent_score=1.0) == 1.0
```

- [ ] **Step 2: Run tests — must fail**

```bash
docker compose exec -T api pytest tests/test_fit_scorer.py -v
```

Expected: FAIL — `ModuleNotFoundError: app.services.fit_scorer`.

- [ ] **Step 3: Write the fit_scorer module**

Create `backend/app/services/fit_scorer.py`:

```python
"""Fit × Intent hybrid scoring — Phase 2.6.

Pure functions. No DB, no LLM, no async. Import-safe from workers and scripts.

Design reference: docs/phase-2-6/design.md §3.2, §3.5.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero."""
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def compute_fit_score(
    icp_embedding: Sequence[float],
    seller_mirror_embedding: Sequence[float],
    connection_embedding: Sequence[float],
    lambda_: float,
) -> float:
    """fit_score = max(0, cos(ICP, conn) - λ·cos(seller_mirror, conn)).

    Floored at 0: anti-ICP connections (raw < 0) get suppressed to 0, not
    ranked negatively. Multiplying a negative fit by a positive intent
    would invert ordering — not the intended behavior.

    Raises ValueError on negative lambda_ or mismatched dimensions.
    """
    if lambda_ < 0:
        raise ValueError(f"lambda_ must be non-negative, got {lambda_}")
    if not (len(icp_embedding) == len(seller_mirror_embedding) == len(connection_embedding)):
        raise ValueError("all three embeddings must share dimension")

    icp_cos = cosine_similarity(icp_embedding, connection_embedding)
    mirror_cos = cosine_similarity(seller_mirror_embedding, connection_embedding)
    raw = icp_cos - lambda_ * mirror_cos
    return max(0.0, raw)


def compute_intent_score(
    relevance_score: float,
    posted_at: datetime,
    *,
    now: datetime | None = None,
) -> float:
    """intent_score = 0.7·relevance + 0.3·timing. No relationship axis.

    Relationship moves to the dashboard degree filter per design §3.5.
    Timing decays linearly to 0 over 24 hours.
    """
    now = now or datetime.now(timezone.utc)
    # Ensure posted_at is timezone-aware
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    hours_old = max(0.0, (now - posted_at).total_seconds() / 3600.0)
    timing = max(0.0, 1.0 - hours_old / 24.0)
    relevance = max(0.0, min(1.0, relevance_score))
    return max(0.0, min(1.0, 0.7 * relevance + 0.3 * timing))


def compute_hybrid_score(fit_score: float, intent_score: float) -> float:
    """final_score = fit_score × intent_score, clamped to [0, 1]."""
    return max(0.0, min(1.0, fit_score * intent_score))
```

- [ ] **Step 4: Run tests — must pass**

```bash
docker compose exec -T api pytest tests/test_fit_scorer.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Run full suite — must stay green**

```bash
docker compose exec -T api pytest -q
```

- [ ] **Step 6: Dispatch `superpowers:code-reviewer`**

Spec compliance: formula matches design §3.2, flooring decision is explicit. Code quality: pure functions, input validation, docstrings point at the design doc.

- [ ] **Step 7: Commit + PR**

```bash
git checkout -b feat/phase-2-6-fit-scorer
git add backend/app/services/fit_scorer.py backend/tests/test_fit_scorer.py
git commit -m "feat(scoring): add fit_scorer service for Phase 2.6 hybrid scoring

Pure functions implementing the Fit × Intent math from design §3.2 + §3.5:

- compute_fit_score = max(0, cos(ICP, conn) - λ·cos(mirror, conn))
- compute_intent_score = 0.7·relevance + 0.3·timing (no relationship axis)
- compute_hybrid_score = fit × intent, clamped [0, 1]

Flooring fit_score at 0 handles the negative-raw-fit case: anti-ICP
connections suppress to 0 rather than ranking negatively.

15 unit tests. No DB, no LLM, no async."
git push -u origin feat/phase-2-6-fit-scorer
gh pr create --title "feat(scoring): Phase 2.6 fit_scorer service" \
             --body "$(cat <<'EOF'
## Summary
Pure-function scoring module for Phase 2.6. Consumed by the pipeline branch
(Task 5) and the backfill script (Task 6).

Key design decision made in implementation: **floor `fit_score` at 0**. Design
§3.2 doesn't explicitly specify behavior when `cos(ICP) - λ·cos(mirror)` goes
negative. I chose clamp-to-zero because:
- Multiplying negative fit by positive intent inverts ordering (wrong)
- Anti-ICP connections should suppress to 0, not rank negatively
- Calibration sweeps over λ will never produce a legitimate negative final_score

Flagging in the PR so reviewer can agree/overrule before this locks in.

## Test plan
- [x] 15 unit tests cover cosine edge cases, lambda bounds, intent timing decay, hybrid combine + clamp
- [x] Full suite green
EOF
)"
```

---

## Task 4: Extend profile_extractor + `/profile/extract` endpoint

Add ICP + seller_mirror extraction to the existing capability-profile extraction flow. Persist both text fields + both embeddings on `capability_profile_versions`. Extend the response model so the frontend can display them.

**Files:**
- Modify: `backend/app/services/profile_extractor.py` — add ICP + seller_mirror extraction
- Modify: `backend/app/routers/profile.py` — extend response model, pass embeddings through
- Test: `backend/tests/test_profile_extract_icp.py`

Branch: `feat/phase-2-6-profile-extract-icp`

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/test_profile_extract_icp.py`:

```python
"""Integration test: POST /profile/extract persists ICP + seller_mirror."""
import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.workspace import CapabilityProfileVersion, Workspace


class _FakeLLMForICP:
    """Returns capability JSON first, then ICP+mirror JSON."""
    def __init__(self):
        self.calls = []

    async def complete(self, prompt, model=None, *, system=None, max_tokens=2048):
        self.calls.append(("complete", system, prompt[:60]))
        if "sales intelligence analyst" in (system or "").lower():
            # ICP prompt
            return json.dumps({
                "icp": "Marketing and growth leaders at D2C brands. Not competing martech vendors or agency employees. Must own a budget for outbound tooling.",
                "seller_mirror": "Founders, CEOs, CPOs at CDP or marketing-automation SaaS companies. LinkedIn headlines typically name-drop the product and include Series A/B signals.",
            })
        # Capability prompt (existing path)
        return json.dumps({
            "company_name": "Acme CDP",
            "capability_summary": "We sell a CDP for D2C brands.",
            "signal_keywords": ["customer data", "cdp migration"],
        })


class _FakeEmbedding:
    async def embed(self, text: str) -> list[float]:
        # Deterministic fake embedding keyed by first char, so we can distinguish
        # ICP / seller_mirror / capability in assertions
        seed = ord(text[0]) if text else 0
        return [float((seed + i) % 10) / 10.0 for i in range(1536)]


@pytest.mark.asyncio
async def test_profile_extract_persists_icp_and_seller_mirror(
    client: AsyncClient,
    db_session,
    auth_headers,
    workspace_id,
):
    from app.main import app
    from app.services.embedding import get_embedding_provider
    from app.services.llm import get_llm_client

    fake_llm = _FakeLLMForICP()
    fake_emb = _FakeEmbedding()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb

    try:
        resp = await client.post(
            "/profile/extract",
            json={"text": "Acme CDP sells customer-data tooling to D2C brands."},
            headers=auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
        app.dependency_overrides.pop(get_embedding_provider, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["icp"].startswith("Marketing")
    assert body["seller_mirror"].startswith("Founders")

    row = (await db_session.execute(
        select(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == workspace_id)
        .where(CapabilityProfileVersion.is_active.is_(True))
    )).scalar_one()

    assert row.icp is not None and "D2C" in row.icp
    assert row.seller_mirror is not None and "CDP" in row.seller_mirror
    assert row.icp_embedding is not None
    assert len(list(row.icp_embedding)) == 1536
    assert row.seller_mirror_embedding is not None
    assert len(list(row.seller_mirror_embedding)) == 1536
```

`auth_headers` and `workspace_id` fixtures do not exist in conftest.py yet. Add both to `backend/tests/conftest.py` (verified absent; no duplication risk). Use the simpler "override `get_current_user`" pattern instead of minting a real JWT — it's cheaper, avoids hashing a test password, and works for any test that needs an authenticated request:

```python
@pytest_asyncio.fixture
async def workspace_id(db_session):
    """Create a test workspace and return its UUID."""
    from app.models.workspace import Workspace
    ws = Workspace(name="Test WS", plan_tier="starter")
    db_session.add(ws)
    await db_session.flush()
    return ws.id


@pytest_asyncio.fixture
async def auth_headers(workspace_id, db_session):
    """Install a dependency override for get_current_user that returns a fake
    User bound to `workspace_id`, and return an empty headers dict.

    Tests do: `await client.post('/x', json=..., headers=auth_headers)`.
    The override is cleared by the `client` fixture's `app.dependency_overrides.clear()`
    at teardown, so no leak between tests.
    """
    from app.main import app
    from app.routers.auth import get_current_user
    from app.models.user import User

    user = User(
        email="test@example.com",
        password_hash="x",  # not used — auth is overridden
        workspace_id=workspace_id,
    )
    db_session.add(user)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    return {}  # empty dict; override handles auth, no Bearer token needed
```

- [ ] **Step 2: Run test — must fail**

```bash
docker compose exec -T api pytest tests/test_profile_extract_icp.py -v
```

Expected: FAIL — response model doesn't include `icp` / `seller_mirror`, extractor doesn't call the new prompt, DB row doesn't populate the new columns.

- [ ] **Step 3: Extend profile_extractor service**

Modify `backend/app/services/profile_extractor.py`. Append a new top-level coroutine `extract_icp_and_seller_mirror` (keep the existing `extract_capability_profile` unchanged):

```python
import json
from app.prompts import extract_icp_and_seller_mirror as icp_prompt


async def extract_icp_and_seller_mirror(
    *,
    source_text: str,
    llm_override=None,
) -> tuple[str, str]:
    """Call the ICP+seller_mirror prompt. Returns (icp, seller_mirror) strings.

    Parse JSON, minimal schema check. Raises ValueError on malformed output.
    """
    from app.services.llm import get_llm_client
    llm = llm_override or get_llm_client()
    user_msg = icp_prompt.build_user_message(source_text=source_text)

    raw = await llm.complete(
        prompt=user_msg,
        system=icp_prompt.SYSTEM_PROMPT,
        model="gpt-5.4-mini",  # matches OPENAI_MODEL_EXPENSIVE
        max_tokens=1200,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"[profile_extractor] ICP prompt returned non-JSON: {e}. Raw: {raw[:200]}"
        )
    if "icp" not in parsed or "seller_mirror" not in parsed:
        raise ValueError(
            f"[profile_extractor] ICP response missing required keys. Got: {list(parsed.keys())}"
        )
    return parsed["icp"], parsed["seller_mirror"]
```

- [ ] **Step 4: Extend `/profile/extract` router**

The existing handler in `backend/app/routers/profile.py` uses the **ORM construct + flush + parameterized UPDATE for embedding** pattern. We follow the same pattern for the two new embeddings. Exact variable names from the file (verified by reading it): the extracted object is `profile`, the ORM instance is `version`, the version number is `version_number`, the capability embedding is `embedding`.

**4a. Extend the response model:**

Replace:

```python
class ProfileExtractResponse(BaseModel):
    company_name: str
    capability_summary: str
    signal_keywords: list[str]
    version: int
```

with:

```python
class ProfileExtractResponse(BaseModel):
    company_name: str
    capability_summary: str
    signal_keywords: list[str]
    version: int
    icp: str
    seller_mirror: str
```

**4b. Extract ICP + seller_mirror after the capability call, embed both.**

In the handler, right after the existing `embedding = await emb.embed(profile.capability_summary)` line, insert:

```python
    from app.services.profile_extractor import extract_icp_and_seller_mirror

    # Source text for ICP extraction: prefer the user-provided text; if only a
    # URL was given, the capability summary itself is a faithful summary of
    # what the crawler found and is a reasonable substitute.
    icp_source_text = body.text or profile.capability_summary
    icp_text, seller_mirror_text = await extract_icp_and_seller_mirror(
        source_text=icp_source_text,
        llm_override=llm,
    )
    icp_embedding = await emb.embed(icp_text)
    seller_mirror_embedding = await emb.embed(seller_mirror_text)
```

**4c. Pass icp/seller_mirror text into the ORM constructor.**

Replace:

```python
    version = CapabilityProfileVersion(
        workspace_id=current_user.workspace_id,
        version=version_number,
        raw_text=profile.capability_summary,
        source="url" if body.url else "document",
        signal_keywords=profile.signal_keywords,
        anti_keywords=profile.anti_keywords,
        is_active=True,
    )
```

with:

```python
    version = CapabilityProfileVersion(
        workspace_id=current_user.workspace_id,
        version=version_number,
        raw_text=profile.capability_summary,
        source="url" if body.url else "document",
        signal_keywords=profile.signal_keywords,
        anti_keywords=profile.anti_keywords,
        icp=icp_text,
        seller_mirror=seller_mirror_text,
        is_active=True,
    )
```

**4d. After the existing `await db.flush()` line, replace the single-embedding UPDATE with a three-embedding UPDATE.**

Replace:

```python
    await db.execute(
        text("UPDATE capability_profile_versions SET embedding = :emb WHERE id = :id"),
        {"emb": str(embedding), "id": str(version.id)}
    )
```

with:

```python
    await db.execute(
        text(
            "UPDATE capability_profile_versions "
            "SET embedding = :emb, "
            "    icp_embedding = :icp_emb, "
            "    seller_mirror_embedding = :mirror_emb "
            "WHERE id = :id"
        ),
        {
            "emb": str(embedding),
            "icp_emb": str(icp_embedding),
            "mirror_emb": str(seller_mirror_embedding),
            "id": str(version.id),
        },
    )
```

**4e. Extend the response construction:**

Replace:

```python
    return ProfileExtractResponse(
        company_name=profile.company_name,
        capability_summary=profile.capability_summary,
        signal_keywords=profile.signal_keywords,
        version=version_number,
    )
```

with:

```python
    return ProfileExtractResponse(
        company_name=profile.company_name,
        capability_summary=profile.capability_summary,
        signal_keywords=profile.signal_keywords,
        version=version_number,
        icp=icp_text,
        seller_mirror=seller_mirror_text,
    )
```

- [ ] **Step 5: Run the integration test — must pass**

```bash
docker compose exec -T api pytest tests/test_profile_extract_icp.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Full suite regression — must stay green**

```bash
docker compose exec -T api pytest -q
```

The existing `/profile/extract` tests must still pass — adding ICP fields should not break the capability-extraction path.

- [ ] **Step 7: Dispatch `superpowers:code-reviewer`**

Security-sensitive check: `source_text` flows into the ICP prompt's user message only (never the system prompt). `icp_text` / `seller_mirror_text` are treated as untrusted LLM output — parsed as JSON, schema-validated, never interpolated into shell or SQL. Confirm parameterized SQL used for the INSERT.

- [ ] **Step 8: Commit + PR**

```bash
git checkout -b feat/phase-2-6-profile-extract-icp
git add backend/app/services/profile_extractor.py \
        backend/app/routers/profile.py \
        backend/tests/test_profile_extract_icp.py \
        backend/tests/conftest.py  # if fixtures added
git commit -m "feat(profile): extract + persist ICP and seller_mirror

POST /profile/extract now calls the ICP+seller_mirror prompt alongside
capability extraction and persists both text fields + their embeddings
on capability_profile_versions. Response model extended with icp and
seller_mirror strings so the wizard (Task 7) can show them.

Part of Phase 2.6 — see docs/phase-2-6/design.md §4.3 + §8 step 2."
git push -u origin feat/phase-2-6-profile-extract-icp
gh pr create --title "feat(profile): persist ICP + seller_mirror on extract" \
             --body "..."
```

---

## Task 5: Pipeline branch on `use_hybrid_scoring`

Modify `app/workers/pipeline.py` so that workspaces with the flag flipped score via the hybrid path, while others continue on the existing `compute_combined_score`.

**Files:**
- Modify: `backend/app/workers/pipeline.py` — add hybrid branch
- Test: `backend/tests/test_pipeline_hybrid_scoring.py`

Branch: `feat/phase-2-6-pipeline-branch`

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/test_pipeline_hybrid_scoring.py`:

```python
"""Pipeline branches on workspace.use_hybrid_scoring.

Case A: flag=False → existing compute_combined_score path; post stored with
relationship/timing/combined scores, no fit_score.

Case B: flag=True → hybrid path; post's combined_score = fit_score * intent_score
(where fit_score comes from connection.fit_score and intent_score from
relevance + timing), connection.fit_score is populated if null.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.connection import Connection
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.post import Post


@pytest.mark.asyncio
async def test_pipeline_legacy_path_when_flag_false(db_session, pipeline_setup):
    """flag=False: uses compute_combined_score (existing behavior)."""
    workspace_id, post_id, connection_id = await pipeline_setup(use_hybrid=False)

    from app.workers.pipeline import _run_pipeline
    await _run_pipeline(post_id, workspace_id)

    post = (await db_session.execute(
        select(Post).where(Post.id == post_id)
    )).scalar_one()
    conn = (await db_session.execute(
        select(Connection).where(Connection.id == connection_id)
    )).scalar_one()

    assert post.combined_score is not None
    assert post.relationship_score is not None
    # Legacy path does not populate fit_score on the connection
    assert conn.fit_score is None


@pytest.mark.asyncio
async def test_pipeline_hybrid_path_when_flag_true(db_session, pipeline_setup):
    """flag=True: uses compute_hybrid_score. Stores fit_score on the connection."""
    workspace_id, post_id, connection_id = pipeline_setup(use_hybrid=True)

    from app.workers.pipeline import _run_pipeline
    await _run_pipeline(post_id, workspace_id)

    post = (await db_session.execute(
        select(Post).where(Post.id == post_id)
    )).scalar_one()
    conn = (await db_session.execute(
        select(Connection).where(Connection.id == connection_id)
    )).scalar_one()

    # Hybrid path: combined_score = fit * intent
    assert post.combined_score is not None
    assert 0.0 <= post.combined_score <= 1.0
    assert conn.fit_score is not None
    assert 0.0 <= conn.fit_score <= 1.0
```

Add a `pipeline_setup` factory fixture to `backend/tests/conftest.py`:

```python
@pytest_asyncio.fixture
async def pipeline_setup(db_session):
    """Factory: returns an async callable that creates a workspace + user +
    capability profile (with ICP/seller_mirror embeddings) + connection + post.
    Returns (workspace_id, post_id, connection_id)."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from sqlalchemy import text as sql_text

    async def _factory(*, use_hybrid: bool):
        from app.models.workspace import Workspace, CapabilityProfileVersion
        from app.models.user import User
        from app.models.connection import Connection
        from app.models.post import Post

        ws = Workspace(
            name="PipelineTestWS",
            plan_tier="starter",
            matching_threshold=0.1,  # low so scores pass through
            use_hybrid_scoring=use_hybrid,
        )
        db_session.add(ws)
        await db_session.flush()

        user = User(email=f"u-{uuid4()}@test", password_hash="x", workspace_id=ws.id)
        db_session.add(user)

        profile = CapabilityProfileVersion(
            workspace_id=ws.id,
            version=1,
            raw_text="Test capability: customer data platform for D2C brands.",
            source="text",
            signal_keywords=["cdp"],
            anti_keywords=[],
            icp="Marketing and growth leaders at D2C brands with >$1M ARR. Not competing martech vendors.",
            seller_mirror="Founders, CEOs, CPOs at martech SaaS companies.",
            is_active=True,
        )
        db_session.add(profile)
        await db_session.flush()

        # Populate the three pgvector columns via parameterized SQL.
        fake_emb = "[" + ",".join(["0.1"] * 1536) + "]"
        await db_session.execute(
            sql_text(
                "UPDATE capability_profile_versions "
                "SET embedding = CAST(:e AS vector), "
                "    icp_embedding = CAST(:e AS vector), "
                "    seller_mirror_embedding = CAST(:e AS vector) "
                "WHERE id = :id"
            ),
            {"e": fake_emb, "id": str(profile.id)},
        )

        conn = Connection(
            workspace_id=ws.id,
            user_id=user.id,
            linkedin_id=f"li-{uuid4()}",
            name="Test Buyer",
            headline="Head of Growth at Acme D2C",
            company="Acme D2C",
            degree=2,
        )
        db_session.add(conn)
        await db_session.flush()

        post = Post(
            workspace_id=ws.id,
            connection_id=conn.id,
            linkedin_post_id=f"p-{uuid4()}",
            content="Looking at customer data tooling for our D2C stack.",
            posted_at=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
        )
        db_session.add(post)
        await db_session.flush()

        # Populate post embedding.
        await db_session.execute(
            sql_text("UPDATE posts SET embedding = CAST(:e AS vector) WHERE id = :id"),
            {"e": fake_emb, "id": str(post.id)},
        )
        await db_session.commit()

        return ws.id, post.id, conn.id

    return _factory
```

Note: Since `Post` and `Connection` have required fields like `linkedin_post_id` and `linkedin_id` with unique constraints, the UUID suffixes above prevent collisions across tests. If existing model columns have additional required fields, add them here — the Post / Connection / User constructors above mirror their current shapes (2026-04-20). Verify against `app/models/post.py` and `app/models/connection.py` at implementation time.

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T api pytest tests/test_pipeline_hybrid_scoring.py -v
```

Expected: FAIL — hybrid branch doesn't exist yet.

- [ ] **Step 3: Modify pipeline.py**

Verified shape: pipeline.py imports everything inside `_run_pipeline` (local imports). The embedding provider is `embedding_provider` (module-level lazy singleton, imported at line 61). The `profile` variable already holds the active `CapabilityProfileVersion` (loaded at line 84), so the hybrid path can read `profile.icp_embedding` and `profile.seller_mirror_embedding` directly without a second query. `ScoringResult` is a dataclass from `app.services.scorer` with a `priority: Priority` enum field.

**3a. Extend the imports inside `_run_pipeline`**. Locate the block at lines 50–68 and add to it:

```python
    from app.services.scorer import compute_combined_score, ScoringResult, Priority
    from app.services.fit_scorer import compute_fit_score, compute_intent_score, compute_hybrid_score
```

(The existing file already has `from app.services.scorer import compute_combined_score` — replace that line with the extended import above.)

**3b. Replace the scoring block** at lines 202–208. Currently:

```python
        scoring = compute_combined_score(
            relevance_score=relevance_score,
            connection=connection,
            posted_at=post.posted_at or post.ingested_at,
            weights=workspace.scoring_weights,
            keyword_match_strength=keyword_match_strength,
        )
```

Replace with:

```python
        if workspace.use_hybrid_scoring and profile.icp_embedding is not None and profile.seller_mirror_embedding is not None:
            # Hybrid path. Populate connection.fit_score on first encounter.
            if connection.fit_score is None:
                text_for_embed = f"{connection.headline or ''} {connection.company or ''}".strip()
                if text_for_embed:
                    conn_emb = await embedding_provider.embed(text_for_embed)
                    # profile.icp_embedding and .seller_mirror_embedding come back as
                    # pgvector objects; cast via list() so the fit_scorer sees Sequence[float].
                    connection.fit_score = compute_fit_score(
                        icp_embedding=list(profile.icp_embedding),
                        seller_mirror_embedding=list(profile.seller_mirror_embedding),
                        connection_embedding=conn_emb,
                        lambda_=0.3,  # hardcoded; replace with workspace.hybrid_lambda after Task 9 calibration
                    )
                else:
                    connection.fit_score = 0.0
                await db.flush()

            intent = compute_intent_score(
                relevance_score=relevance_score,
                posted_at=post.posted_at or post.ingested_at,
            )
            final = compute_hybrid_score(
                fit_score=connection.fit_score,
                intent_score=intent,
            )

            # Derive priority from the hybrid final score using the same
            # thresholds as legacy scoring (0.80 high, 0.55 medium).
            if final >= 0.80:
                priority = Priority.HIGH
            elif final >= 0.55:
                priority = Priority.MEDIUM
            else:
                priority = Priority.LOW

            # Timing is already folded into `intent`; surface the raw component
            # for the legacy DB columns so dashboards/debugging still work.
            posted = post.posted_at or post.ingested_at
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            hours_old = max(0.0, (datetime.now(timezone.utc) - posted).total_seconds() / 3600.0)
            timing_component = max(0.0, 1.0 - hours_old / 24.0)

            scoring = ScoringResult(
                relevance_score=relevance_score,
                relationship_score=0.0,  # not used in hybrid; degree filter lives on dashboard
                timing_score=timing_component,
                combined_score=final,
                priority=priority,
            )
        else:
            if workspace.use_hybrid_scoring:
                logger.warning(
                    "[pipeline] use_hybrid_scoring=True but ICP/seller_mirror embeddings missing "
                    "for workspace_id=%s profile_id=%s — falling back to legacy scorer. "
                    "Run /profile/extract then scripts/backfill_fit_scores.py to populate.",
                    workspace_id, profile.id,
                )
            scoring = compute_combined_score(
                relevance_score=relevance_score,
                connection=connection,
                posted_at=post.posted_at or post.ingested_at,
                weights=workspace.scoring_weights,
                keyword_match_strength=keyword_match_strength,
            )
```

**Notes:**
- `datetime` and `timezone` are already imported inside `_run_pipeline` (line 52).
- `Priority.HIGH/MEDIUM/LOW` — verify the exact enum casing by opening `app/services/scorer.py`. If the enum uses lowercase (`Priority.high`), use that instead. The existing pipeline uses `scoring.priority.value` at line 294, so it is an enum — only the case of the members needs verification at implementation time.
- **Lambda is hardcoded at 0.3** for this task. If Task 9 calibration finds a non-0.3 optimum, open a follow-up task to add `workspaces.hybrid_lambda REAL DEFAULT 0.3` via migration 011 and read it here.
- No new top-of-file imports needed; everything is inside `_run_pipeline`.

- [ ] **Step 4: Run integration test — must pass**

```bash
docker compose exec -T api pytest tests/test_pipeline_hybrid_scoring.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Full suite — must stay green**

```bash
docker compose exec -T api pytest -q
```

- [ ] **Step 6: Dispatch `superpowers:code-reviewer`**

Spec compliance: branch per design §3.7. Code quality: fallback on missing ICP embeddings (warn, use legacy — not hard-fail). Lambda is hardcoded with a TODO pointer to Task 9.

- [ ] **Step 7: Commit + PR**

```bash
git checkout -b feat/phase-2-6-pipeline-branch
git add backend/app/workers/pipeline.py backend/tests/test_pipeline_hybrid_scoring.py
git commit -m "feat(pipeline): branch scoring path on workspace.use_hybrid_scoring

When the flag is True, pipeline scores via compute_hybrid_score (fit × intent)
instead of compute_combined_score. Fit is computed on first encounter of each
connection and cached on connection.fit_score.

Lambda hardcoded at 0.3; replace with workspace.hybrid_lambda column after
calibration (Task 9) picks the per-workspace optimum.

Fallback: if use_hybrid_scoring=True but the workspace lacks ICP/seller_mirror
embeddings (e.g., flag flipped before Task 4 ran against it), log a warning
and fall through to the legacy scorer rather than hard-failing."
git push -u origin feat/phase-2-6-pipeline-branch
gh pr create --title "feat(pipeline): hybrid scoring branch on use_hybrid_scoring flag" --body "..."
```

---

## Task 6: `backfill_fit_scores.py` one-shot script

Populate `connection.fit_score` for every connection in a workspace, so that when the flag flips, the pipeline doesn't pay the per-connection embedding cost on first encounter.

**Files:**
- Create: `backend/scripts/backfill_fit_scores.py`
- Test: `backend/tests/test_backfill_fit_scores.py`

Branch: `feat/phase-2-6-backfill-fit`

- [ ] **Step 1a: Add the fixtures to conftest.py**

```python
@pytest_asyncio.fixture
async def workspace_with_icp(db_session):
    """Workspace + active CapabilityProfileVersion with icp/seller_mirror embeddings populated.
    Returns the workspace_id (UUID)."""
    from uuid import uuid4
    from sqlalchemy import text as sql_text
    from app.models.workspace import Workspace, CapabilityProfileVersion
    from app.models.user import User

    ws = Workspace(name="BackfillTest", plan_tier="starter", use_hybrid_scoring=True)
    db_session.add(ws)
    await db_session.flush()

    user = User(email=f"u-{uuid4()}@test", password_hash="x", workspace_id=ws.id)
    db_session.add(user)

    profile = CapabilityProfileVersion(
        workspace_id=ws.id, version=1,
        raw_text="...", source="text",
        signal_keywords=[], anti_keywords=[],
        icp="ICP text.", seller_mirror="Seller mirror text.",
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()

    fake_emb = "[" + ",".join(["0.1"] * 1536) + "]"
    await db_session.execute(
        sql_text(
            "UPDATE capability_profile_versions "
            "SET embedding = CAST(:e AS vector), "
            "    icp_embedding = CAST(:e AS vector), "
            "    seller_mirror_embedding = CAST(:e AS vector) "
            "WHERE id = :id"
        ),
        {"e": fake_emb, "id": str(profile.id)},
    )
    # Stash user_id on the workspace object for the connection fixtures below.
    ws._test_user_id = user.id
    await db_session.commit()
    return ws.id


async def _add_connection(db, workspace_id, user_id, *, headline: str, company: str, fit_score=None):
    from uuid import uuid4
    from app.models.connection import Connection
    conn = Connection(
        workspace_id=workspace_id,
        user_id=user_id,
        linkedin_id=f"li-{uuid4()}",
        name="N",
        headline=headline,
        company=company,
        degree=2,
        fit_score=fit_score,
    )
    db.add(conn)
    await db.flush()
    return conn.id


@pytest_asyncio.fixture
async def seeded_connections(db_session, workspace_with_icp):
    """3 connections in the workspace, all with fit_score=None."""
    from sqlalchemy import select
    from app.models.workspace import Workspace
    ws = (await db_session.execute(
        select(Workspace).where(Workspace.id == workspace_with_icp)
    )).scalar_one()
    ids = []
    for h, c in [
        ("Head of Growth at Acme D2C", "Acme D2C"),
        ("CMO", "Retail Co"),
        ("VP Marketing", "BrandX"),
    ]:
        ids.append(await _add_connection(db_session, ws.id, ws._test_user_id, headline=h, company=c))
    await db_session.commit()
    return ids


@pytest_asyncio.fixture
async def seeded_connections_mixed(db_session, workspace_with_icp):
    """Mixed: 2 connections without fit_score + 1 with fit_score=0.5 pre-populated."""
    from sqlalchemy import select
    from app.models.workspace import Workspace
    ws = (await db_session.execute(
        select(Workspace).where(Workspace.id == workspace_with_icp)
    )).scalar_one()
    ids = [
        await _add_connection(db_session, ws.id, ws._test_user_id, headline="CMO", company="X", fit_score=None),
        await _add_connection(db_session, ws.id, ws._test_user_id, headline="VP Growth", company="Y", fit_score=None),
        await _add_connection(db_session, ws.id, ws._test_user_id, headline="Founder", company="Z", fit_score=0.5),
    ]
    await db_session.commit()
    return ids
```

- [ ] **Step 1b: Write the failing test**

Create `backend/tests/test_backfill_fit_scores.py`:

```python
"""Integration test: backfill script populates fit_score for every connection."""
import pytest
from sqlalchemy import select

from app.models.connection import Connection


@pytest.mark.asyncio
async def test_backfill_populates_fit_score_for_all_connections(
    db_session, workspace_with_icp, seeded_connections,
):
    from scripts.backfill_fit_scores import run

    # Override the embedding provider to avoid real OpenAI calls.
    from app.services import embedding as emb_mod
    class _FakeProvider:
        async def embed(self, text: str) -> list[float]:
            return [0.2] * 1536
    emb_mod._provider = _FakeProvider()

    summary = await run(db_session, workspace_id=workspace_with_icp)

    assert summary["updated"] == 3
    conns = (await db_session.execute(
        select(Connection).where(Connection.workspace_id == workspace_with_icp)
    )).scalars().all()
    for c in conns:
        assert c.fit_score is not None
        assert 0.0 <= c.fit_score <= 1.0


@pytest.mark.asyncio
async def test_backfill_skips_connections_with_existing_fit_score(
    db_session, workspace_with_icp, seeded_connections_mixed,
):
    """Default mode skips connections that already have a fit_score."""
    from scripts.backfill_fit_scores import run
    from app.services import embedding as emb_mod
    class _FakeProvider:
        async def embed(self, text: str) -> list[float]:
            return [0.2] * 1536
    emb_mod._provider = _FakeProvider()

    summary = await run(db_session, workspace_id=workspace_with_icp, recompute_all=False)
    assert summary["updated"] == 2  # the two with fit_score=None
```

Note: the `_reset_provider_singletons` autouse fixture in conftest clears `emb_mod._provider` at teardown, so the fake set here doesn't leak between tests.

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T api pytest tests/test_backfill_fit_scores.py -v
```

Expected: FAIL — script doesn't exist.

- [ ] **Step 3: Write the backfill script**

Create `backend/scripts/backfill_fit_scores.py`:

```python
"""One-shot script: populate connection.fit_score for a workspace.

Loads the active CapabilityProfileVersion for the workspace (must have
icp_embedding + seller_mirror_embedding). For each connection in the workspace:
  1. Embed headline + company.
  2. Compute fit_score via fit_scorer.
  3. Persist.

Usage inside api container:
  python scripts/backfill_fit_scores.py --workspace-id <uuid>
  python scripts/backfill_fit_scores.py --workspace-id <uuid> --recompute-all

The --recompute-all flag forces re-embed of every connection, overwriting any
existing fit_score. Useful after an ICP change.
"""
import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.connection import Connection
from app.models.workspace import CapabilityProfileVersion
from app.services.embedding import get_embedding_provider
from app.services.fit_scorer import compute_fit_score


async def run(db, workspace_id: UUID, *, recompute_all: bool = False, lambda_: float = 0.3) -> dict:
    profile = (await db.execute(
        select(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == workspace_id)
        .where(CapabilityProfileVersion.is_active.is_(True))
    )).scalar_one_or_none()
    if profile is None:
        raise RuntimeError(f"No active capability_profile_version for workspace {workspace_id}")
    if profile.icp_embedding is None or profile.seller_mirror_embedding is None:
        raise RuntimeError(
            f"Workspace {workspace_id} active profile has no ICP/seller_mirror embeddings. "
            "Run /profile/extract first."
        )

    emb = get_embedding_provider()

    q = select(Connection).where(Connection.workspace_id == workspace_id)
    if not recompute_all:
        q = q.where(Connection.fit_score.is_(None))
    connections = (await db.execute(q)).scalars().all()

    icp_emb = list(profile.icp_embedding)
    mirror_emb = list(profile.seller_mirror_embedding)

    updated = 0
    skipped_empty = 0
    for conn in connections:
        text = f"{conn.headline or ''} {conn.company or ''}".strip()
        if not text:
            conn.fit_score = 0.0
            skipped_empty += 1
            continue
        conn_emb = await emb.embed(text)
        conn.fit_score = compute_fit_score(
            icp_embedding=icp_emb,
            seller_mirror_embedding=mirror_emb,
            connection_embedding=conn_emb,
            lambda_=lambda_,
        )
        updated += 1

    await db.commit()
    return {"updated": updated, "skipped_empty": skipped_empty, "total": len(connections)}


async def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--recompute-all", action="store_true")
    parser.add_argument("--lambda", type=float, default=0.3, dest="lambda_",
                        help="Subtractive weight on seller_mirror term (default 0.3)")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        summary = await run(
            db,
            workspace_id=args.workspace_id,
            recompute_all=args.recompute_all,
            lambda_=args.lambda_,
        )
        print(f"[backfill_fit_scores] {summary}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
```

- [ ] **Step 4: Run tests — must pass**

```bash
docker compose exec -T api pytest tests/test_backfill_fit_scores.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Full suite — green**

```bash
docker compose exec -T api pytest -q
```

- [ ] **Step 6: Smoke test the CLI entry point**

```bash
docker compose exec -T api python scripts/backfill_fit_scores.py --help
```

Expected: argparse help output with --workspace-id, --recompute-all, --lambda.

- [ ] **Step 7: Review + commit + PR**

```bash
git checkout -b feat/phase-2-6-backfill-fit
git add backend/scripts/backfill_fit_scores.py backend/tests/test_backfill_fit_scores.py
git commit -m "feat(scripts): one-shot backfill_fit_scores.py for Phase 2.6

Populates connection.fit_score for every connection in a workspace by
embedding headline+company and applying the fit_score formula against
the workspace's active ICP + seller_mirror embeddings.

Idempotent (skips non-null fit_scores by default). Use --recompute-all
after an ICP change to invalidate the cache."
git push -u origin feat/phase-2-6-backfill-fit
gh pr create --title "feat(scripts): backfill_fit_scores.py" --body "..."
```

---

## Task 7: Wizard frontend — ICP review step

Insert a new review step into `SignalConfig.tsx` so the user sees the extracted ICP + seller_mirror before signals are generated. Lets them edit either paragraph inline.

**Per Sonar's CLAUDE.md:** no automated integration tests on the frontend. Verify via `docker compose up -d frontend` + manual browser walkthrough. Human signoff before merging.

**Files:**
- Modify: `frontend/src/pages/SignalConfig.tsx` — add new Step 3 (ICP review), shift 3→4, 4→5, 5→6

Branch: `feat/phase-2-6-wizard-icp-review`

- [ ] **Step 1: Read the current SignalConfig.tsx structure**

```bash
cat frontend/src/pages/SignalConfig.tsx | head -50
```

Confirm current `Step = 1 | 2 | 3 | 4 | 5` layout.

- [ ] **Step 2: Extend the Step union type and state**

Change:

```typescript
type Step = 1 | 2 | 3 | 4 | 5;
```

to:

```typescript
type Step = 1 | 2 | 3 | 4 | 5 | 6;
```

Add ICP state:

```typescript
const [icp, setIcp] = useState<string>("");
const [sellerMirror, setSellerMirror] = useState<string>("");
const [icpEdited, setIcpEdited] = useState<boolean>(false);
```

- [ ] **Step 3: Split step 2's "Generating signals..." into two**

Currently step 3 is "Generating signals...". We repurpose: step 3 becomes "Reviewing your ICP", and the signal-proposal step moves to 4.

After the user submits `whatYouSell` + optional `icp`, call `/profile/extract` FIRST to get the ICP + seller_mirror text. Populate state. Render step 3 as a review screen:

```tsx
{step === 3 && (
  <section>
    <h2>Review who we think your buyers are</h2>
    <p className="text-sm text-gray-600">
      Before we generate signals, confirm the buyer persona and seller
      persona we'll be comparing connections against. Edit anything that
      looks off.
    </p>

    <label className="block mt-4">
      <span className="font-medium">Your ideal buyer (ICP)</span>
      <textarea
        className="w-full mt-1 p-2 border rounded"
        rows={6}
        value={icp}
        onChange={(e) => { setIcp(e.target.value); setIcpEdited(true); }}
      />
    </label>

    <label className="block mt-4">
      <span className="font-medium">Seller-mirror (subtracted during scoring)</span>
      <p className="text-xs text-gray-500 mb-1">
        What OTHER sellers of your capability look like on LinkedIn.
        We subtract this signal so competing vendors don't rank as buyers.
      </p>
      <textarea
        className="w-full mt-1 p-2 border rounded"
        rows={6}
        value={sellerMirror}
        onChange={(e) => setSellerMirror(e.target.value)}
      />
    </label>

    <div className="mt-6 flex gap-2">
      <button onClick={() => setStep(2)}>← Back</button>
      <button
        className="btn-primary"
        onClick={async () => {
          if (icpEdited) {
            // Persist edits back to the server
            await apiClient.post("/profile/update-icp", { icp, seller_mirror: sellerMirror });
          }
          setStep(4);  // move to signal generation
        }}
      >
        Looks right — generate signals
      </button>
    </div>
  </section>
)}
```

Shift the existing step 3, 4, 5 blocks to `step === 4`, `step === 5`, `step === 6`.

- [ ] **Step 4: Modify the "call /profile/extract" handler**

Where the wizard currently POSTs to `/profile/extract` (likely in step 2's submit handler), update the response handling to set the new state:

```typescript
const resp = await apiClient.post("/profile/extract", { text: whatYouSell });
setIcp(resp.data.icp);
setSellerMirror(resp.data.seller_mirror);
setStep(3);  // go to ICP review BEFORE signal generation
```

- [ ] **Step 5: Add a backend endpoint for the edit path (optional but recommended)**

If `/profile/update-icp` doesn't exist, either:
- (a) skip the persist-on-edit behavior for now and track as a follow-up issue
- (b) add a small endpoint in `app/routers/profile.py`:

```python
@router.post("/update-icp")
async def update_icp(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    emb: EmbeddingProvider = Depends(get_embedding_provider),
):
    """Update the active capability_profile_version's ICP and/or seller_mirror.
    Re-embed whichever fields are provided."""
    icp = body.get("icp")
    seller_mirror = body.get("seller_mirror")
    if not icp and not seller_mirror:
        raise HTTPException(400, "must provide icp and/or seller_mirror")

    update_fields = {}
    if icp:
        update_fields["icp"] = icp
        update_fields["icp_embedding"] = await emb.embed(icp)
    if seller_mirror:
        update_fields["seller_mirror"] = seller_mirror
        update_fields["seller_mirror_embedding"] = await emb.embed(seller_mirror)

    await db.execute(
        update(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
        .where(CapabilityProfileVersion.is_active.is_(True))
        .values(**update_fields)
    )
    await db.commit()
    return {"ok": True}
```

Add a test for it. If skipping, open a GitHub issue: "Wire wizard ICP edits back to /profile/update-icp."

**Recommendation:** include the endpoint in this task (it's ~20 lines + a test).

- [ ] **Step 6: Manual browser walkthrough (required — no automated tests)**

```bash
docker compose up -d --build frontend
open http://localhost:5173/signals/setup
```

Walk through:
1. Enter "What do you sell?" text → submit
2. Verify ICP + seller_mirror text appears, editable
3. Edit each; click "Looks right — generate signals"
4. Confirm signal generation completes
5. Click through to step 5 (accept/reject signals) and step 6 (ready to save)
6. Check browser devtools network tab: `/profile/extract` returned icp/seller_mirror fields; `/profile/update-icp` fired on edit.

Take a screenshot of the new step 3 for the PR body.

- [ ] **Step 7: Commit + PR**

```bash
git checkout -b feat/phase-2-6-wizard-icp-review
git add frontend/src/pages/SignalConfig.tsx \
        backend/app/routers/profile.py \
        backend/tests/test_profile_update_icp.py
git commit -m "feat(wizard): add ICP review step before signal generation

New step 3 in the wizard shows the extracted ICP + seller_mirror text
to the user. They can edit either paragraph; edits re-embed via a new
POST /profile/update-icp endpoint.

Per Phase 2.6 design §3.1 tier-2/3 ICP customization + §7 risk-2 mitigation."
git push -u origin feat/phase-2-6-wizard-icp-review
gh pr create --title "feat(wizard): ICP review step + /profile/update-icp endpoint" --body "..."
```

---

## Task 8: Calibration — `analyze-hybrid` subcommand with λ sweep

Extend `backend/scripts/calibrate_matching.py` with a new subcommand that:
- Reads the existing labeled dataset (same 30-post dogfood set from PR #114)
- For each λ in a sweep: computes per-connection fit_score, per-post intent_score, `final_score = fit * intent`
- Reports P@5, Recall, top-5 competitor count at each λ
- Picks the winning λ per the DoD (§3.8): P@5 ≥ 0.6, Recall ≥ 0.5, zero competitor posts in top-5

**Files:**
- Modify: `backend/scripts/calibrate_matching.py` — add `analyze-hybrid` subcommand + helpers
- Test: `backend/tests/test_calibrate_hybrid.py`

Branch: `feat/phase-2-6-calibrate-hybrid`

The existing `calibrate_matching.py` already exposes `parse_labels(labels_path: Path) -> dict[str, bool]` at module scope (no refactor needed). The existing labeling format tracks only `is_match` per post — it does NOT have an `is_competitor` flag. Two ways to surface competitor leakage:
- **(a)** Accept a `--competitors` flag pointing at a file of known competitor LinkedIn IDs or connection UUIDs; auto-count.
- **(b)** Print top-5 posts with author headline/company so the user eyeballs competitor leakage.

This task implements **both**: auto-count if `--competitors` is provided, always print top-5 for visual verification.

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/test_calibrate_hybrid.py`:

```python
"""Unit tests for the metrics helpers used by analyze-hybrid."""
import pytest

from scripts.calibrate_matching import (
    precision_at_k,
    recall_at_k,
    competitor_count_in_top_k,
)


def test_precision_at_5_mixed_ranking():
    # 3 of top-5 are true matches → 0.6
    # Each item is (score, is_match, is_competitor).
    ranked = [
        (0.9, True, False), (0.8, False, False), (0.7, True, False),
        (0.6, True, False), (0.5, False, False), (0.4, True, False),
    ]
    assert precision_at_k(ranked, k=5) == 0.6


def test_precision_at_5_fewer_than_k():
    ranked = [(0.9, True, False), (0.8, True, False)]
    assert precision_at_k(ranked, k=5) == 1.0  # 2/2


def test_recall_half_caught():
    ranked = [
        (0.9, True, False), (0.8, False, False), (0.7, True, False),
        (0.6, False, False), (0.5, True, False), (0.4, True, False),
    ]
    # top-5 has 3 true matches; total true matches = 4 → 3/4 = 0.75
    assert recall_at_k(ranked, k=5) == 0.75


def test_competitor_count_in_top_5():
    ranked = [
        (0.9, True, False),   (0.85, False, True),   (0.8, False, True),
        (0.7, True, False),   (0.6, False, False),
    ]
    assert competitor_count_in_top_k(ranked, k=5) == 2


def test_competitor_count_zero_when_none_flagged():
    ranked = [(0.9, True, False)] * 5
    assert competitor_count_in_top_k(ranked, k=5) == 0
```

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T api pytest tests/test_calibrate_hybrid.py -v
```

Expected: FAIL — helpers don't exist.

- [ ] **Step 3: Extend calibrate_matching.py**

In `backend/scripts/calibrate_matching.py`, add these top-level helpers below `compute_metrics_at_threshold`:

```python
def precision_at_k(ranked: list[tuple[float, bool, bool]], k: int = 5) -> float:
    """ranked: list of (score, is_match, is_competitor) sorted by score desc.
    Returns matches_in_top_k / len(top_k)."""
    top = ranked[:k]
    if not top:
        return 0.0
    matches = sum(1 for _score, is_match, _comp in top if is_match)
    return matches / len(top)


def recall_at_k(ranked: list[tuple[float, bool, bool]], k: int = 5) -> float:
    """Recall at k against all true matches in the dataset (not just top-k)."""
    total_true = sum(1 for _score, is_match, _comp in ranked if is_match)
    if total_true == 0:
        return 0.0
    top_true = sum(1 for _score, is_match, _comp in ranked[:k] if is_match)
    return top_true / total_true


def competitor_count_in_top_k(ranked: list[tuple[float, bool, bool]], k: int = 5) -> int:
    """Count competitor-flagged posts in top-k."""
    return sum(1 for _score, _is_match, is_comp in ranked[:k] if is_comp)


def load_competitor_set(competitors_path: Path | None) -> set[str]:
    """Load a set of connection UUID strings from a newline-separated file.
    Returns empty set if path is None. Ignores blank lines and # comments."""
    if competitors_path is None:
        return set()
    out: set[str] = set()
    for line in competitors_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lower())
    return out
```

Add the subcommand registration in `main()` after the existing `analyze` parser:

```python
    hy = subparsers.add_parser("analyze-hybrid", help="Sweep λ for Phase 2.6 hybrid scoring")
    hy.add_argument("--workspace-id", type=UUID, required=True)
    hy.add_argument("--labels", type=Path, required=True,
                    help="Labeled dataset file (same format as the existing analyze input)")
    hy.add_argument("--lambdas", type=str, default="0.0,0.1,0.2,0.3,0.5,0.7,1.0",
                    help="Comma-separated λ values to sweep")
    hy.add_argument("--competitors", type=Path, default=None,
                    help="Optional: file with newline-separated connection UUIDs known to be competitors. "
                         "If provided, analyzer reports top-5 competitor leakage automatically.")
```

Dispatch it inside `main()`:

```python
    elif args.cmd == "analyze-hybrid":
        asyncio.run(cmd_analyze_hybrid(args))
```

Add the command handler at module scope:

```python
async def cmd_analyze_hybrid(args) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.config import get_settings
    from app.models.workspace import CapabilityProfileVersion
    from app.models.connection import Connection
    from app.models.post import Post
    from app.services.fit_scorer import (
        compute_fit_score,
        compute_intent_score,
        compute_hybrid_score,
        cosine_similarity,
    )
    from app.services.embedding import embedding_provider

    labels_map = parse_labels(args.labels)   # {post_id: is_match}
    if not labels_map:
        print(f"[calibrate-hybrid] no labels parsed from {args.labels}")
        sys.exit(1)

    lambdas = [float(x) for x in args.lambdas.split(",")]
    competitor_ids = load_competitor_set(args.competitors)

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        profile = (await db.execute(
            select(CapabilityProfileVersion)
            .where(CapabilityProfileVersion.workspace_id == args.workspace_id)
            .where(CapabilityProfileVersion.is_active.is_(True))
        )).scalar_one_or_none()
        if profile is None:
            print(f"[calibrate-hybrid] no active capability_profile_version for {args.workspace_id}")
            sys.exit(1)
        if profile.icp_embedding is None or profile.seller_mirror_embedding is None:
            print("[calibrate-hybrid] active profile has no ICP/seller_mirror embeddings. "
                  "Run /profile/extract first.")
            sys.exit(1)

        icp_emb = list(profile.icp_embedding)
        mirror_emb = list(profile.seller_mirror_embedding)
        cap_emb = list(profile.embedding) if profile.embedding is not None else None

        # Fetch each labeled post joined with its connection + embedding text.
        post_rows = (await db.execute(
            select(Post, Connection)
            .join(Connection, Post.connection_id == Connection.id)
            .where(Post.id.in_([UUID(pid) for pid in labels_map.keys()]))
        )).all()

        # Fetch post embeddings via raw SQL (pgvector cast to text, then json-parse).
        import json
        from sqlalchemy import text as sql_text
        post_emb_rows = (await db.execute(
            sql_text("SELECT id::text, embedding::text FROM posts WHERE id = ANY(:ids)"),
            {"ids": list(labels_map.keys())},
        )).all()
        post_embs = {
            pid: json.loads(emb_str) if emb_str else None
            for pid, emb_str in post_emb_rows
        }

        # Embed each connection's headline+company exactly once.
        conn_embs: dict[str, list[float]] = {}
        for _post, conn in post_rows:
            cid = str(conn.id)
            if cid in conn_embs:
                continue
            text_for_embed = f"{conn.headline or ''} {conn.company or ''}".strip()
            conn_embs[cid] = await embedding_provider.embed(text_for_embed) if text_for_embed else [0.0] * 1536

        print(f"\n{'λ':>5} | {'P@5':>5} | {'R@5':>5} | {'comp@5':>6} | DoD?")
        print("-" * 45)

        best_lambda = None
        for lam in lambdas:
            ranked: list[tuple[float, bool, bool]] = []
            top5_preview: list[tuple[float, str, str, str]] = []  # (score, post_id, headline, company)

            for post, conn in post_rows:
                pid = str(post.id)
                if pid not in labels_map:
                    continue
                post_emb = post_embs.get(pid)
                if post_emb is None or cap_emb is None:
                    continue
                fit = compute_fit_score(
                    icp_embedding=icp_emb,
                    seller_mirror_embedding=mirror_emb,
                    connection_embedding=conn_embs[str(conn.id)],
                    lambda_=lam,
                )
                relevance = cosine_similarity(cap_emb, post_emb)
                intent = compute_intent_score(
                    relevance_score=relevance,
                    posted_at=post.posted_at or post.ingested_at,
                )
                final = compute_hybrid_score(fit, intent)

                is_match = labels_map[pid]
                is_competitor = str(conn.id).lower() in competitor_ids
                ranked.append((final, is_match, is_competitor))
                top5_preview.append((final, pid, conn.headline or "", conn.company or ""))

            ranked.sort(key=lambda x: -x[0])
            top5_preview.sort(key=lambda x: -x[0])

            p5 = precision_at_k(ranked, k=5)
            r5 = recall_at_k(ranked, k=5)
            comp5 = competitor_count_in_top_k(ranked, k=5)
            dod = "YES" if (p5 >= 0.6 and r5 >= 0.5 and comp5 == 0) else "no"
            print(f"{lam:>5.2f} | {p5:>5.2f} | {r5:>5.2f} | {comp5:>6d} | {dod}")

            if dod == "YES" and best_lambda is None:
                best_lambda = lam
                # Show top-5 for visual competitor check at the winning λ
                print(f"\n  top-5 at λ={lam}:")
                for score, pid, headline, company in top5_preview[:5]:
                    print(f"    {score:.3f}  {pid}  {headline[:60]}  @ {company[:40]}")

        if best_lambda is None:
            print("\n[calibrate-hybrid] no λ satisfied DoD (P@5 ≥ 0.6, R@5 ≥ 0.5, zero top-5 competitors).")
            print("See design.md §5 step 8 for diagnostic paths.")

    await engine.dispose()
```

- [ ] **Step 4: Tests pass**

```bash
docker compose exec -T api pytest tests/test_calibrate_hybrid.py -v
docker compose exec -T api pytest -q
```

- [ ] **Step 5: Smoke test the CLI**

```bash
docker compose exec -T api python scripts/calibrate_matching.py analyze-hybrid --help
```

- [ ] **Step 6: Review + commit + PR**

```bash
git checkout -b feat/phase-2-6-calibrate-hybrid
git add backend/scripts/calibrate_matching.py backend/tests/test_calibrate_hybrid.py
git commit -m "feat(eval): analyze-hybrid subcommand with λ sweep

Extends calibrate_matching.py with an analyze-hybrid subcommand that
evaluates the Phase 2.6 hybrid scoring model across a λ sweep. For each
λ, computes P@5, Recall, and top-5 competitor count against the labeled
dogfood dataset. Surfaces the DoD (P@5≥0.6, Recall≥0.5, zero competitors
in top-5 per design §3.8).

Also factors out parse_labels_file() so the existing analyze command and
the new analyze-hybrid command share the same parser."
git push -u origin feat/phase-2-6-calibrate-hybrid
gh pr create --title "feat(eval): hybrid λ sweep in calibrate_matching.py" --body "..."
```

---

## Task 9: Operational — calibration run, flip flag, retire legacy scorer

**Not a code task.** No TDD steps. This is the go/no-go step that either ships Phase 2.6 or surfaces a design gap.

### Sequence

- [ ] **Step 1: Extract ICP + seller_mirror for Dwao workspace via POST /profile/extract**

```bash
# Run through the wizard at /signals/setup, or POST directly:
curl -X POST http://localhost:8000/profile/extract \
  -H "Authorization: Bearer $DWAO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://dwao.in"}'
```

Verify the returned ICP + seller_mirror look reasonable. Iterate via `/profile/update-icp` if they don't.

- [ ] **Step 2: Backfill fit_scores for Dwao**

```bash
docker compose exec -T api python scripts/backfill_fit_scores.py \
  --workspace-id $DWAO_WORKSPACE_ID
```

- [ ] **Step 3: Run analyze-hybrid against the Session-8 labeled dataset**

```bash
docker compose exec -T api python scripts/calibrate_matching.py analyze-hybrid \
  --workspace-id $DWAO_WORKSPACE_ID \
  --labels eval/calibration/dogfood-martech-labeled.md \
  --lambdas 0.0,0.1,0.2,0.3,0.5,0.7,1.0
```

Record the output in `eval/calibration/phase-2-6-findings-dwao.md`.

- [ ] **Step 4: Repeat for CleverTap**

Extract CleverTap's ICP from `https://clevertap.com`. Re-label the same 30 posts under the CleverTap lens (~15 min). Run analyze-hybrid against the relabeled set. Record findings.

- [ ] **Step 5: Pick a winning λ**

Pick the λ that satisfies DoD on BOTH workspaces, maximizing P@5 subject to Recall ≥ 0.5 and zero top-5 competitors. Document in `eval/calibration/phase-2-6-lambda-decision.md`.

- [ ] **Step 6: If DoD passes — flip the flag**

```sql
-- Inside psql:
UPDATE workspaces SET use_hybrid_scoring = TRUE WHERE id = '<DWAO_WORKSPACE_ID>';
```

Optionally add a `hybrid_lambda REAL DEFAULT 0.3` column (migration 011) if the winning λ differs from 0.3; otherwise the hardcoded default covers it.

- [ ] **Step 7: Monitor for 2 weeks**

Watch the `/dashboard` output. Compare against the session-8 calibration baseline. If top-5 posts still contain competitor leakage, revert the flag and revisit.

- [ ] **Step 8: If stable — retire legacy `compute_combined_score`**

After 2 weeks stable, open a branch `chore/retire-combined-score`:
- Remove `compute_combined_score` from `scorer.py`
- Remove the `else` branch in `pipeline.py` — hybrid becomes the only path
- Require all new workspaces to have ICP/seller_mirror extracted before first pipeline run
- Default `workspaces.use_hybrid_scoring` to `TRUE` via migration 011

- [ ] **Step 9: If DoD fails — diagnose per design §5 step 8**

Likely fixes (in order of design preference):
1. **Encoder asymmetry** — upgrade embedding to `text-embedding-3-large` (Plan B per design §3.4). New migration to widen embedding columns from 1536 to 3072 dimensions; re-embed everything.
2. **Weak ICP extraction** — tighten the prompt in `extract_icp_and_seller_mirror.py`, bump PROMPT_VERSION. Re-run Dwao extract → backfill → analyze-hybrid.
3. **λ sweep finds no usable value** — indicates seller-mirror isn't discriminating. Try a fresh prompt (different framing) or switch to an asymmetric retrieval model (BGE / E5) as a Phase 2.7 slice.

Open a GitHub issue for whichever fix is indicated; do not ship hybrid behind the flag until DoD passes.

---

## After every task: update session log + TODO.md

Each merged task gets a terse entry appended to TODO.md's Session log (newest first, 3-5 bullets). Both TODO.md and TODO.html must be updated together per the memory scar about asymmetric edits.

At session end, rewrite TODO.md's Next Session Action Plan per the CLAUDE.md rule.

---

## Self-review of this plan (done — see below)

**Spec coverage vs. design §8:**
- §8.1 (migrations + models) → Task 1 ✅
- §8.2 (prompt module + extended /profile/extract) → Tasks 2 + 4 ✅
- §8.3 (fit_scorer) → Task 3 ✅
- §8.4 (backfill script) → Task 6 ✅
- §8.5 (pipeline branch) → Task 5 ✅
- §8.6 (wizard updates) → Task 7 ✅
- §8.7 (calibration run) → Task 8 (tooling) + Task 9 (operational run) ✅
- §8.8 (flip flag, retire legacy) → Task 9 steps 6-8 ✅
- §8.9 (if DoD fails) → Task 9 step 9 ✅

**Placeholder scan:** All tasks have executable code. Task 9 steps are operational by design — concrete commands, no "TBD".

**Type consistency check:**
- `compute_fit_score` signature in Task 3 matches usages in Tasks 5 + 6 + 8 ✅
- `CapabilityProfileVersion.icp_embedding` defined in Task 1, read in Tasks 4 + 5 + 6 + 8 ✅
- `workspace.use_hybrid_scoring` column defined in Task 1, read in Task 5 ✅
- `connection.fit_score` column defined in Task 1, read/written in Tasks 5 + 6 ✅

**Known design ambiguities surfaced:**
- Fit score flooring at 0 (Task 3 PR body flags for reviewer confirmation)
- Lambda storage: hardcoded 0.3 in Task 5; migration 011 deferred to post-calibration
- `/profile/update-icp` endpoint included in Task 7 rather than split out

**Open questions for reviewer:**
- Should the edge case "hybrid flag True but ICP embeddings missing" hard-fail or fall through to legacy? Task 5 chose fall-through-with-warning.
- Should `compute_intent_score` use the existing `scorer.py` timing decay helper if one exists, to avoid drift? Task 3 re-implements it inline; consolidation is a cleanup opportunity after hybrid ships.
