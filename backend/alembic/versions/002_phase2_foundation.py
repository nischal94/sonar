"""Phase 2 foundation: signals, aggregation tables, post columns

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # ── signals ─────────────────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("example_post", sa.Text()),
        sa.Column("intent_strength", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("embedding", Vector(1536)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["profile_version_id"], ["capability_profile_versions.id"]),
    )
    op.execute(
        "CREATE INDEX signals_embedding_idx "
        "ON signals USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index(
        "signals_workspace_enabled_idx", "signals", ["workspace_id", "enabled"]
    )

    # ── person_signal_summary ───────────────────────────────────────────
    op.create_table(
        "person_signal_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("trend_direction", sa.String(), nullable=False, server_default="flat"),
        sa.Column("last_signal_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("recent_post_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recent_signal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"]),
        sa.ForeignKeyConstraint(["recent_post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["recent_signal_id"], ["signals.id"]),
        sa.UniqueConstraint("workspace_id", "connection_id"),
    )
    op.create_index(
        "person_signal_score_idx",
        "person_signal_summary",
        ["workspace_id", sa.text("aggregate_score DESC")],
    )

    # ── company_signal_summary ──────────────────────────────────────────
    op.create_table(
        "company_signal_summary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("active_signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "company_name"),
    )
    op.create_index(
        "company_signal_score_idx",
        "company_signal_summary",
        ["workspace_id", sa.text("aggregate_score DESC")],
    )

    # ── trends ──────────────────────────────────────────────────────────
    op.create_table(
        "trends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ring", sa.Integer(), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True)),
        sa.Column("cluster_label", sa.Text()),
        sa.Column("cluster_sample_posts", postgresql.JSONB()),
        sa.Column("this_week_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_week_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("velocity_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
    )
    op.create_index(
        "trends_workspace_ring_snapshot_idx",
        "trends",
        ["workspace_id", "ring", sa.text("snapshot_date DESC")],
    )

    # ── posts column additions ──────────────────────────────────────────
    op.add_column("posts", sa.Column("ring1_matches", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("ring2_matches", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("themes", postgresql.JSONB(), server_default="[]"))
    op.add_column("posts", sa.Column("engagement_counts", postgresql.JSONB(), server_default="{}"))

    # ── Phase 1 schema gap: posts.connection_id was missing its FK constraint.
    #    Design spec §5.1 says to roll this fix into the Phase 2 migration.
    op.create_foreign_key(
        "posts_connection_id_fkey",
        "posts",
        "connections",
        ["connection_id"],
        ["id"],
    )

    # ── connections column addition ─────────────────────────────────────
    op.add_column(
        "connections",
        sa.Column("mutual_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # ── workspaces column addition ──────────────────────────────────────
    op.add_column(
        "workspaces",
        sa.Column("backfill_used", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("workspaces", "backfill_used")
    op.drop_column("connections", "mutual_count")
    op.drop_constraint("posts_connection_id_fkey", "posts", type_="foreignkey")
    op.drop_column("posts", "engagement_counts")
    op.drop_column("posts", "themes")
    op.drop_column("posts", "ring2_matches")
    op.drop_column("posts", "ring1_matches")
    op.drop_index("trends_workspace_ring_snapshot_idx", "trends")
    op.drop_table("trends")
    op.drop_index("company_signal_score_idx", "company_signal_summary")
    op.drop_table("company_signal_summary")
    op.drop_index("person_signal_score_idx", "person_signal_summary")
    op.drop_table("person_signal_summary")
    op.drop_index("signals_workspace_enabled_idx", "signals")
    op.execute("DROP INDEX IF EXISTS signals_embedding_idx")
    op.drop_table("signals")
