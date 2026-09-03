"""Add structured rejection reasons and search evaluation runs.

Revision ID: 20260830_0008
Revises: 20260830_0007
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0008"
down_revision: str | None = "20260830_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    rejection_category = sa.Enum(
        "EVIDENCE_MISMATCH",
        "ALREADY_TRIED",
        "RISK_OR_INCOMPLETE",
        "OTHER",
        name="solution_rejection_category",
    )
    rejection_category.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "ticket_solution_reviews",
        sa.Column("rejection_category", rejection_category),
    )
    op.create_table(
        "search_evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("dataset_version", sa.String(length=50), nullable=False),
        sa.Column("query_count", sa.Integer(), nullable=False),
        sa.Column("recall_at_5", sa.Float(), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_evaluation_runs_created",
        "search_evaluation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_search_evaluation_runs_created", table_name="search_evaluation_runs")
    op.drop_table("search_evaluation_runs")
    op.drop_column("ticket_solution_reviews", "rejection_category")
    sa.Enum(name="solution_rejection_category").drop(op.get_bind(), checkfirst=True)
