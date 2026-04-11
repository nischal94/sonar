import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import get_settings


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
