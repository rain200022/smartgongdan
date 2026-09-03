"""Add AI and engineer classification evaluation records.

Revision ID: 20260820_0003
Revises: 20260813_0002
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0003"
down_revision: str | None = "20260813_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_classification_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("ai_judgment_id", sa.Integer(), nullable=False),
        sa.Column("engineer_judgment_id", sa.Integer(), nullable=False),
        sa.Column("category_agreement", sa.Boolean(), nullable=False),
        sa.Column("subcategory_agreement", sa.Boolean(), nullable=False),
        sa.Column("agreement", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ai_judgment_id"], ["ticket_judgments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["engineer_judgment_id"], ["ticket_judgments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engineer_judgment_id"),
    )
    op.create_index(
        "ix_ticket_classification_evaluations_ticket_created",
        "ticket_classification_evaluations",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_classification_evaluations_ticket_created",
        table_name="ticket_classification_evaluations",
    )
    op.drop_table("ticket_classification_evaluations")
