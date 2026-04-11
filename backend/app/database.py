from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

_engine = None
_session_local = None

def _get_engine():
    global _engine
    if _engine is None:
        from app.config import get_settings
        _engine = create_async_engine(get_settings().database_url, echo=False)
    return _engine

def _get_session_local():
    global _session_local
    if _session_local is None:
        _session_local = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_local

async def get_db() -> AsyncSession:
    async with _get_session_local()() as session:
        yield session
