"""Create tickets table.

Revision ID: 20260813_0001
Revises:
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ticket_status = sa.Enum("open", "in_progress", "closed", name="ticket_status")
    priority = sa.Enum("P1", "P2", "P3", "P4", name="ticket_priority")

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("user_category", sa.String(length=100), nullable=True),
        sa.Column("final_category", sa.String(length=100), nullable=True),
        sa.Column("ai_priority", priority, nullable=True),
        sa.Column("final_priority", priority, nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("status", ticket_status, server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_status_created_at", "tickets", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_status_created_at", table_name="tickets")
    op.drop_table("tickets")
    sa.Enum(name="ticket_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticket_priority").drop(op.get_bind(), checkfirst=True)
