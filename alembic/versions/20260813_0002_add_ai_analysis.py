"""Add AI ticket analysis and judgment audit tables.

Revision ID: 20260813_0002
Revises: 20260813_0001
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0002"
down_revision: str | None = "20260813_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    judge_type = sa.Enum("USER", "AI", "ENGINEER", name="judge_type")

    op.create_table(
        "ticket_ai_analysis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=False),
        sa.Column("device", sa.String(length=200), nullable=True),
        sa.Column("symptom", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_actions", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_ai_analysis_ticket_created",
        "ticket_ai_analysis",
        ["ticket_id", "created_at"],
    )

    op.create_table(
        "ticket_judgments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("judge_type", judge_type, nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_judgments_ticket_created",
        "ticket_judgments",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_judgments_ticket_created", table_name="ticket_judgments")
    op.drop_table("ticket_judgments")
    op.drop_index("ix_ticket_ai_analysis_ticket_created", table_name="ticket_ai_analysis")
    op.drop_table("ticket_ai_analysis")
    sa.Enum(name="judge_type").drop(op.get_bind(), checkfirst=True)
