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
