"""Add missing FK constraint on connections.user_id → users.id

Revision ID: 003
Revises: 002
Create Date: 2026-04-12

The `connections.user_id` column has been NOT NULL since 001 but the
DB-level FK was never declared. The ORM (Connection.user_id) also did
not declare ForeignKey(...) until PR #13. This migration closes the gap.

Uses the two-phase `NOT VALID` + `VALIDATE CONSTRAINT` pattern so this
is safe to run against a large production `connections` table without
holding ACCESS EXCLUSIVE during the full-table validation scan:

  Phase 1 — ADD CONSTRAINT ... NOT VALID
    Takes ACCESS EXCLUSIVE only briefly (catalog update). New and updated
    rows are immediately enforced.

  Phase 2 — VALIDATE CONSTRAINT
    Takes only SHARE UPDATE EXCLUSIVE, which does not block reads or
    writes on `connections`. Scans existing rows; fails loudly if any
    orphan row is found.

ON DELETE RESTRICT is explicit, matching the ORM side in connection.py:
a user cannot be deleted while connections they scraped still reference
them — higher-level application logic decides what to do with a user's
connections when removing the user (reassign / soft-delete / archive).

A pre-flight orphan check emits a clear error with a repair query if any
`connections.user_id` points at a missing user, so operators get better
context than a raw Postgres FK-violation error.
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Pre-flight: detect orphan user_id rows before attempting the constraint,
    # so the error message tells the operator exactly how to find and repair them.
    conn = op.get_bind()
    orphan_count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM connections c "
            "LEFT JOIN users u ON c.user_id = u.id "
            "WHERE u.id IS NULL"
        )
    ).scalar()
    if orphan_count:
        # nosec B608 — f-string contains a static SQL hint inside an error
        # message; not executed. orphan_count is an int from a COUNT(*) query.
        raise RuntimeError(
            f"[migration 003] Cannot add connections_user_id_fkey: "
            f"{orphan_count} orphan row(s) in `connections` reference a non-existent "
            f"user. Inspect with: SELECT c.id, c.user_id FROM connections c "
            f"LEFT JOIN users u ON c.user_id = u.id WHERE u.id IS NULL; "
            f"then delete or repair before re-running this migration."
        )

    # Phase 1: add the FK without scanning existing rows.
    op.execute(
        "ALTER TABLE connections "
        "ADD CONSTRAINT connections_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) "
        "ON DELETE RESTRICT NOT VALID"
    )
    # Phase 2: validate existing rows without blocking reads/writes.
    op.execute(
        "ALTER TABLE connections VALIDATE CONSTRAINT connections_user_id_fkey"
    )


def downgrade():
    op.drop_constraint(
        "connections_user_id_fkey",
        "connections",
        type_="foreignkey",
    )
