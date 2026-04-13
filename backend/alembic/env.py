from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
import app.models.workspace
import app.models.user
import app.models.connection
import app.models.post
import app.models.alert
import app.models.outreach
import app.models.feedback

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Let $DATABASE_URL override the hardcoded alembic.ini URL so CI and other
# environments don't need to match docker-compose's `postgres` service name.
# Alembic uses psycopg2 (sync); strip `+asyncpg` so the one env var can serve
# both the async app and sync migrations.
# NOTE: do not log _env_db_url — it contains the database password.
_env_db_url = os.environ.get("DATABASE_URL")
if _env_db_url:
    config.set_main_option(
        "sqlalchemy.url",
        _env_db_url.replace("postgresql+asyncpg://", "postgresql://"),
    )

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
