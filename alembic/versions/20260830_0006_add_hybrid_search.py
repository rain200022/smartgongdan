"""Add knowledge and pgvector-backed hybrid search fields.

Revision ID: 20260830_0006
Revises: 20260827_0005
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "20260830_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("subcategory", sa.String(length=100), nullable=False),
        sa.Column("embedding", Vector(dim=128), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_code", "knowledge", ["code"], unique=True)
    op.create_index(
        "ix_knowledge_active_category",
        "knowledge",
        ["is_active", "category"],
    )

    op.add_column("tickets", sa.Column("external_reference", sa.String(length=50)))
    op.add_column("tickets", sa.Column("search_embedding", Vector(dim=128)))
    op.add_column("tickets", sa.Column("search_embedding_model", sa.String(length=200)))
    op.create_unique_constraint(
        "uq_tickets_external_reference",
        "tickets",
        ["external_reference"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tickets_external_reference", "tickets", type_="unique")
    op.drop_column("tickets", "search_embedding_model")
    op.drop_column("tickets", "search_embedding")
    op.drop_column("tickets", "external_reference")
    op.drop_index("ix_knowledge_active_category", table_name="knowledge")
    op.drop_index("ix_knowledge_code", table_name="knowledge")
    op.drop_table("knowledge")
