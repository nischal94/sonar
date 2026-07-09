import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import get_settings


@pytest.fixture
def sync_engine():
    """Synchronous engine for DDL introspection. Separate from the async test engine."""
    url = get_settings().database_url.replace("+asyncpg", "")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_provider_singletons():
    """Clear lazy provider caches after each test so a real client populated
    by one test cannot leak into another (would cause spooky action at a
    distance — e.g. a test that forgets to mock silently benefits from a
    prior test's real client). Closes issue #22."""
    yield
    from app.services import embedding, llm

    embedding._provider = None
    llm._openai = None
    llm._groq = None


# NOTE: rate-limiter reset is handled inside the `client` fixture below,
# NOT as a separate autouse fixture. An autouse fixture's ordering relative
# to `client` is non-deterministic (both are function-scoped), which would
# make this test: client-setup → limiter-reset vs limiter-reset → client-setup.
# If the limiter is never reset before a test that happens to be the 6th call
# in a run, it flakes with a spurious 429. Resetting inside `client` setup
# guarantees the ordering.

# Note: no user-defined `event_loop` fixture.
# pytest-asyncio 1.x supplies a function-scoped event loop by default,
# which is what `test_engine` (function-scoped) expects. A previous
# session-scoped override of `event_loop` was silently ignored by
# pytest-asyncio 1.x (DeprecationWarning) but would break under 2.x;
# it was removed as part of the Phase 2 Foundation pre-merge cleanup.
# Configured via `pyproject.toml [tool.pytest.ini_options]`.


@pytest_asyncio.fixture
async def test_engine():
    # Swap only the trailing database name (not any earlier "/sonar" in credentials/host)
    base_url = get_settings().database_url
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    engine = create_async_engine(test_db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Reset slowapi counters per-test — ASGITransport reuses one client IP,
    # so without this any test hitting a rate-limited endpoint accumulates
    # counters that would leak into subsequent tests.
    from app.rate_limit import limiter

    limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


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

        user = User(
            email=f"u-{uuid4()}@test",
            hashed_password="x",
            workspace_id=ws.id,
        )
        db_session.add(user)
        await db_session.flush()

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
            post_type="post",
            source="extension",
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

    user = User(email=f"u-{uuid4()}@test", hashed_password="x", workspace_id=ws.id)
    db_session.add(user)

    profile = CapabilityProfileVersion(
        workspace_id=ws.id,
        version=1,
        raw_text="...",
        source="text",
        signal_keywords=[],
        anti_keywords=[],
        icp="ICP text.",
        seller_mirror="Seller mirror text.",
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
    # Capture user_id before commit expires the ORM instance.
    user_id = user.id
    await db_session.commit()
    # Stash user_id on a plain object so connection fixtures can reference it
    # without re-fetching. This is a test-only pattern; production code never
    # touches _test_user_id.
    import types

    result = types.SimpleNamespace(id=ws.id, _test_user_id=user_id)
    return result


async def _add_connection(
    db, workspace_id, user_id, *, headline: str, company: str, fit_score=None
):
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
    ids = []
    for h, c in [
        ("Head of Growth at Acme D2C", "Acme D2C"),
        ("CMO", "Retail Co"),
        ("VP Marketing", "BrandX"),
    ]:
        ids.append(
            await _add_connection(
                db_session,
                workspace_with_icp.id,
                workspace_with_icp._test_user_id,
                headline=h,
                company=c,
            )
        )
    await db_session.commit()
    return ids


@pytest_asyncio.fixture
async def seeded_connections_mixed(db_session, workspace_with_icp):
    """Mixed: 2 connections without fit_score + 1 with fit_score=0.5 pre-populated."""
    ids = [
        await _add_connection(
            db_session,
            workspace_with_icp.id,
            workspace_with_icp._test_user_id,
            headline="CMO",
            company="X",
            fit_score=None,
        ),
        await _add_connection(
            db_session,
            workspace_with_icp.id,
            workspace_with_icp._test_user_id,
            headline="VP Growth",
            company="Y",
            fit_score=None,
        ),
        await _add_connection(
            db_session,
            workspace_with_icp.id,
            workspace_with_icp._test_user_id,
            headline="Founder",
            company="Z",
            fit_score=0.5,
        ),
    ]
    await db_session.commit()
    return ids


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
        hashed_password="x",  # not used — auth is overridden
        workspace_id=workspace_id,
    )
    db_session.add(user)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    return {}  # empty dict; override handles auth, no Bearer token needed
