"""Add users, sessions, roles, and ticket ownership.

Revision ID: 20260820_0004
Revises: 20260820_0003
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0004"
down_revision: str | None = "20260820_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum("USER", "ENGINEER", "ADMIN", name="user_role")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user_expires", "auth_sessions", ["user_id", "expires_at"])
    op.add_column("tickets", sa.Column("requester_id", sa.Integer(), nullable=True))
    op.add_column("tickets", sa.Column("assigned_engineer_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tickets_requester_id_users",
        "tickets",
        "users",
        ["requester_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_tickets_assigned_engineer_id_users",
        "tickets",
        "users",
        ["assigned_engineer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tickets_requester_id", "tickets", ["requester_id"])
    op.create_index("ix_tickets_assigned_engineer_id", "tickets", ["assigned_engineer_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_assigned_engineer_id", table_name="tickets")
    op.drop_index("ix_tickets_requester_id", table_name="tickets")
    op.drop_constraint("fk_tickets_assigned_engineer_id_users", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_requester_id_users", "tickets", type_="foreignkey")
    op.drop_column("tickets", "assigned_engineer_id")
    op.drop_column("tickets", "requester_id")
    op.drop_index("ix_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    user_role.drop(op.get_bind(), checkfirst=True)
