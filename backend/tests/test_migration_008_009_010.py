"""Round-trip test: head → 007 → head works without errors and preserves row counts."""

import pytest
from sqlalchemy import text
from alembic import command
from alembic.config import Config

from app.config import get_settings


@pytest.fixture
def alembic_cfg() -> Config:
    """Alembic config pinned to the isolated sonar_test database.

    Without the explicit sqlalchemy.url override, alembic.ini's default
    points at the main sonar database. Running this test against a live
    dev stack would destructively downgrade the dev schema mid-run.
    """
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    base_url = get_settings().database_url.replace("+asyncpg", "")
    test_db_url = base_url.rsplit("/", 1)[0] + "/sonar_test"
    cfg.set_main_option("sqlalchemy.url", test_db_url)
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
        # Migration 008 — fit_score. sa.Float() maps to Postgres double precision,
        # matching the neighbour relationship_score column on the same table.
        row = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name='connections' AND column_name='fit_score'"
            )
        ).fetchone()
        assert row is not None, "connections.fit_score missing"
        assert row.data_type == "double precision"
        assert row.is_nullable == "YES"

        # Migration 009 — use_hybrid_scoring.
        row = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name='workspaces' AND column_name='use_hybrid_scoring'"
            )
        ).fetchone()
        assert row is not None, "workspaces.use_hybrid_scoring missing"
        assert row.data_type == "boolean"
        assert row.is_nullable == "NO"
        assert "false" in (row.column_default or "").lower()

        # Migration 010 — text columns. Bindparam (not f-string) per the
        # project's "parameterized SQL always" rule, even in test code.
        for col in ("icp", "seller_mirror"):
            row = conn.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name='capability_profile_versions' "
                    "AND column_name=:c"
                ),
                {"c": col},
            ).fetchone()
            assert row is not None, f"capability_profile_versions.{col} missing"
            assert row.data_type == "text"

        # Migration 010 — pgvector columns. Postgres reports
        # data_type='USER-DEFINED' for extension types; we assert the
        # specific udt_name='vector' so a future regression (dropped
        # pgvector extension, swapped type) would fail loudly.
        for col in ("icp_embedding", "seller_mirror_embedding"):
            row = conn.execute(
                text(
                    "SELECT column_name, udt_name FROM information_schema.columns "
                    "WHERE table_name='capability_profile_versions' "
                    "AND column_name=:c"
                ),
                {"c": col},
            ).fetchone()
            assert row is not None, f"capability_profile_versions.{col} missing"
            assert row.udt_name == "vector", f"{col} is not pgvector type"
