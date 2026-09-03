"""Add rule-based priority facts and calculation results.

Revision ID: 20260827_0005
Revises: 20260820_0004
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260827_0005"
down_revision: str | None = "20260820_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

impact_level = postgresql.ENUM(
    "核心业务受影响",
    "业务功能受限",
    "个人工作受影响",
    "轻微影响",
    name="ticket_impact_level",
    create_type=False,
)
urgency_level = postgresql.ENUM("高", "中", "低", name="ticket_urgency_level", create_type=False)
affected_scope = postgresql.ENUM(
    "全公司",
    "多部门",
    "多用户",
    "单用户",
    name="ticket_affected_scope",
    create_type=False,
)
ticket_priority = postgresql.ENUM("P1", "P2", "P3", "P4", name="ticket_priority", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    impact_level.create(bind, checkfirst=True)
    urgency_level.create(bind, checkfirst=True)
    affected_scope.create(bind, checkfirst=True)

    op.add_column("ticket_ai_analysis", sa.Column("impact", impact_level, nullable=True))
    op.add_column("ticket_ai_analysis", sa.Column("urgency", urgency_level, nullable=True))
    op.add_column(
        "ticket_ai_analysis",
        sa.Column("affected_scope", affected_scope, nullable=True),
    )
    op.add_column("ticket_ai_analysis", sa.Column("impact_score", sa.Integer(), nullable=True))
    op.add_column("ticket_ai_analysis", sa.Column("urgency_score", sa.Integer(), nullable=True))
    op.add_column("ticket_ai_analysis", sa.Column("scope_score", sa.Integer(), nullable=True))
    op.add_column("ticket_ai_analysis", sa.Column("priority_score", sa.Float(), nullable=True))
    op.add_column(
        "ticket_ai_analysis",
        sa.Column("calculated_priority", ticket_priority, nullable=True),
    )
    op.create_check_constraint(
        "ck_ticket_ai_analysis_impact_score",
        "ticket_ai_analysis",
        "impact_score IS NULL OR impact_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_ticket_ai_analysis_urgency_score",
        "ticket_ai_analysis",
        "urgency_score IS NULL OR urgency_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_ticket_ai_analysis_scope_score",
        "ticket_ai_analysis",
        "scope_score IS NULL OR scope_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_ticket_ai_analysis_priority_score",
        "ticket_ai_analysis",
        "priority_score IS NULL OR priority_score BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ticket_ai_analysis_priority_score",
        "ticket_ai_analysis",
        type_="check",
    )
    op.drop_constraint(
        "ck_ticket_ai_analysis_scope_score",
        "ticket_ai_analysis",
        type_="check",
    )
    op.drop_constraint(
        "ck_ticket_ai_analysis_urgency_score",
        "ticket_ai_analysis",
        type_="check",
    )
    op.drop_constraint(
        "ck_ticket_ai_analysis_impact_score",
        "ticket_ai_analysis",
        type_="check",
    )
    op.drop_column("ticket_ai_analysis", "calculated_priority")
    op.drop_column("ticket_ai_analysis", "priority_score")
    op.drop_column("ticket_ai_analysis", "scope_score")
    op.drop_column("ticket_ai_analysis", "urgency_score")
    op.drop_column("ticket_ai_analysis", "impact_score")
    op.drop_column("ticket_ai_analysis", "affected_scope")
    op.drop_column("ticket_ai_analysis", "urgency")
    op.drop_column("ticket_ai_analysis", "impact")

    bind = op.get_bind()
    affected_scope.drop(bind, checkfirst=True)
    urgency_level.drop(bind, checkfirst=True)
    impact_level.drop(bind, checkfirst=True)
