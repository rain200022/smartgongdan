"""Add generated AI solutions and human review records.

Revision ID: 20260830_0007
Revises: 20260830_0006
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0007"
down_revision: str | None = "20260830_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    review_decision = sa.Enum("ADOPTED", "REJECTED", name="solution_review_decision")
    op.create_table(
        "ticket_ai_solutions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=False),
        sa.Column("possible_causes", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("referenced_cases", sa.JSON(), nullable=False),
        sa.Column("need_human", sa.Boolean(), nullable=False),
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
        "ix_ticket_ai_solutions_ticket_created",
        "ticket_ai_solutions",
        ["ticket_id", "created_at"],
    )
    op.create_table(
        "ticket_solution_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("solution_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("decision", review_decision, nullable=False),
        sa.Column("engineer_solution", sa.Text()),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["solution_id"], ["ticket_ai_solutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("solution_id"),
    )
    op.create_index(
        "ix_ticket_solution_reviews_ticket_created",
        "ticket_solution_reviews",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_solution_reviews_ticket_created",
        table_name="ticket_solution_reviews",
    )
    op.drop_table("ticket_solution_reviews")
    op.drop_index("ix_ticket_ai_solutions_ticket_created", table_name="ticket_ai_solutions")
    op.drop_table("ticket_ai_solutions")
    sa.Enum(name="solution_review_decision").drop(op.get_bind(), checkfirst=True)
