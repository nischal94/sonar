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
        row = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name='connections' AND column_name='fit_score'"
            )
        ).fetchone()
        assert row is not None, "connections.fit_score missing"
        assert row.data_type == "real"
        assert row.is_nullable == "YES"

        # Migration 009
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

        # Migration 010
        for col in ("icp", "seller_mirror", "icp_embedding", "seller_mirror_embedding"):
            row = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name='capability_profile_versions' AND column_name='{col}'"
                )
            ).fetchone()
            assert row is not None, f"capability_profile_versions.{col} missing"
