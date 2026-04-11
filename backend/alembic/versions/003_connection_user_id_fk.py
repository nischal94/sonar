"""Add missing FK constraint on connections.user_id → users.id

Revision ID: 003
Revises: 002
Create Date: 2026-04-12

The `connections.user_id` column has been NOT NULL since 001 but the
DB-level FK was never declared. The ORM (Connection.user_id) also did
not declare ForeignKey(...) until PR #13. This migration closes the gap.

Per Sonar CLAUDE.md "expand / contract" guidance: this is a pure additive
constraint on an existing column. Any orphan rows in dev/prod must be
cleaned before running this migration. The constraint uses ON DELETE
RESTRICT (the default) because a user should not be deletable while
connections they scraped still reference them; higher-level logic
decides what to do with a user's connections when the user is removed.
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(
        "connections_user_id_fkey",
        "connections",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "connections_user_id_fkey",
        "connections",
        type_="foreignkey",
    )
