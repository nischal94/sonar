"""alerts.relationship_score — make nullable for hybrid scoring

In the legacy scoring path, relationship_score is a meaningful 0–1 value
derived from connection degree (1st=0.90, 2nd=0.60, 3rd=0.30) plus any
interaction boost.  It is written into the Alert row and surfaced in every
delivery formatter (Slack, Telegram, email).

In the Phase 2.6 hybrid scoring path (workspace.use_hybrid_scoring=True),
the relationship dimension is replaced by the Fit × Intent composite.
Network-degree filtering happens on the dashboard, not inside the scorer.
The hybrid pipeline sets scoring.relationship_score=0.0 as a placeholder,
and that 0.0 flows into the Alert row and renders as "Relationship: 0%" in
every delivery channel — which is misleading and looks broken.

Fix: make the column nullable.  The hybrid pipeline passes
relationship_score=None when constructing the Alert; the three delivery
formatters (slack.py, telegram.py, email.py) omit the field when it is
None.  Legacy workspaces are unaffected — they still receive a float value
and see the rendered percentage as before.

NULL in this column therefore means "this alert was scored via the hybrid
Fit × Intent path; the relationship axis does not apply."  A non-NULL value
means the legacy path ran and the percentage is meaningful.

See issue #120 for the full context.  Introduced in Phase 2.6 (PR #119).

Revision ID: 011
Revises: 010
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alerts",
        "relationship_score",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    # Back-fill NULLs with 0.0 before restoring the NOT NULL constraint.
    # Hybrid-mode alerts had no meaningful relationship score; 0.0 is the
    # least-bad sentinel for the legacy schema that requires a value.
    op.execute(
        "UPDATE alerts SET relationship_score = 0.0 WHERE relationship_score IS NULL"
    )
    op.alter_column(
        "alerts",
        "relationship_score",
        existing_type=sa.Float(),
        nullable=False,
    )
