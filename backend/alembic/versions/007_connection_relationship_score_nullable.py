"""connections.relationship_score — make nullable, drop 0.5 default

The previous schema forced every new connection to relationship_score=0.5.
The scorer treats non-NULL values as 'already measured', so the 0.5 default
silently overrode the degree-based fallback (1st=0.9, 2nd=0.6, 3rd=0.3).
Every live post scored with relationship_score=0.5 regardless of degree.

Fix: make the column nullable. Callers that know the value (e.g. the
backfill endpoint, which knows degree=1) set it explicitly; otherwise
NULL lets the scorer fall back correctly. See issue #105.

Data backfill (UPDATE ... WHERE relationship_score = 0.5) is intentionally
NOT in this migration — it would silently overwrite any legitimately-measured
0.5 values. Operators should run the backfill manually (see issue #105 PR).

Revision ID: 007
Revises: 006
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "connections",
        "relationship_score",
        existing_type=sa.Float(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE connections SET relationship_score = 0.5 WHERE relationship_score IS NULL"
    )
    op.alter_column(
        "connections",
        "relationship_score",
        existing_type=sa.Float(),
        nullable=False,
        server_default="0.5",
    )
