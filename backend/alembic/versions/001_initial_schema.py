"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan_tier", sa.String(), nullable=False, server_default="starter"),
        sa.Column("capability_profile", sa.Text()),
        sa.Column("matching_threshold", sa.Float(), nullable=False, server_default="0.72"),
        sa.Column("scoring_weights", postgresql.JSONB(), server_default='{"relevance":0.50,"relationship":0.30,"timing":0.20}'),
        sa.Column("onboarding_url", sa.String()),
        sa.Column("onboarding_doc_path", sa.String()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("capability_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("anti_keywords", postgresql.ARRAY(sa.Text())),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("performance_score", sa.Float()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )
    op.execute("ALTER TABLE capability_profile_versions ADD COLUMN embedding vector(1536)")

    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("linkedin_profile_url", sa.String()),
        sa.Column("delivery_channels", postgresql.JSONB(), server_default="{}"),
        sa.Column("alert_rate_limits", postgresql.JSONB(), server_default='{"high":10,"medium":5,"low":2}'),
        sa.Column("quiet_hours", postgresql.JSONB(), server_default="{}"),
        sa.Column("extension_installed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extension_last_sync", postgresql.TIMESTAMPTZ()),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("linkedin_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("headline", sa.Text()),
        sa.Column("profile_url", sa.String()),
        sa.Column("company", sa.String()),
        sa.Column("seniority", sa.String()),
        sa.Column("degree", sa.Integer(), nullable=False),
        sa.Column("relationship_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("has_interacted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("first_seen_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_active_at", postgresql.TIMESTAMPTZ()),
        sa.Column("enriched_at", postgresql.TIMESTAMPTZ()),
        sa.Column("enrichment_data", postgresql.JSONB(), server_default="{}"),
        sa.Column("topic_interests", postgresql.ARRAY(sa.Text())),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "linkedin_id"),
    )

    op.create_table("posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True)),
        sa.Column("linkedin_post_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("posted_at", postgresql.TIMESTAMPTZ()),
        sa.Column("ingested_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("relationship_score", sa.Float()),
        sa.Column("timing_score", sa.Float()),
        sa.Column("combined_score", sa.Float()),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processed_at", postgresql.TIMESTAMPTZ()),
        sa.Column("extraction_version", sa.String()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.UniqueConstraint("workspace_id", "linkedin_post_id"),
    )
    op.execute("ALTER TABLE posts ADD COLUMN embedding vector(1536)")
    op.execute("CREATE INDEX posts_embedding_idx ON posts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    op.create_table("alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("relationship_score", sa.Float(), nullable=False),
        sa.Column("timing_score", sa.Float(), nullable=False),
        sa.Column("combined_score", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("match_reason", sa.Text()),
        sa.Column("outreach_draft_a", sa.Text()),
        sa.Column("outreach_draft_b", sa.Text()),
        sa.Column("opportunity_type", sa.String()),
        sa.Column("urgency_reason", sa.Text()),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("delivered_at", postgresql.TIMESTAMPTZ()),
        sa.Column("seen_at", postgresql.TIMESTAMPTZ()),
        sa.Column("feedback", sa.String()),
        sa.Column("feedback_at", postgresql.TIMESTAMPTZ()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"]),
    )

    op.create_table("outreach_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_sent", sa.Text()),
        sa.Column("outcome", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("contacted_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("feedback_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_threshold", sa.Float(), nullable=False),
        sa.Column("new_threshold", sa.Float(), nullable=False),
        sa.Column("positive_rate", sa.Float(), nullable=False),
        sa.Column("adjustment_reason", sa.String()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

    op.create_table("signal_effectiveness",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicted_score", sa.Float(), nullable=False),
        sa.Column("user_rated", sa.String()),
        sa.Column("outreach_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("outreach_outcome", sa.String()),
        sa.Column("revenue_attributed", sa.Numeric(10, 2)),
        sa.Column("effectiveness_score", sa.Float()),
        sa.Column("created_at", postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )

def downgrade():
    op.drop_table("signal_effectiveness")
    op.drop_table("feedback_adjustments")
    op.drop_table("outreach_history")
    op.drop_table("alerts")
    op.drop_table("posts")
    op.drop_table("connections")
    op.drop_table("users")
    op.drop_table("capability_profile_versions")
    op.drop_table("workspaces")
