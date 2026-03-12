"""add_sessions_table_and_token_version

Revision ID: c7d8e9f0a1b2
Revises: 876ce331ae0b
Create Date: 2026-03-11 18:40:00.000000

Changes:
- Creates `sessions` table for multi-device login tracking
- Adds `token_version` column to `users` (for access token revocation)
- Drops `refresh_token_jti` column from `users` (replaced by sessions table)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "876ce331ae0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=43), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("device_name", sa.String(length=200), nullable=True),
        sa.Column("browser", sa.String(length=100), nullable=True),
        sa.Column("os", sa.String(length=100), nullable=True),
        sa.Column("is_mobile", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("GETUTCDATE()"),
            nullable=True,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("GETUTCDATE()"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_id", "sessions", ["id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_jti", "sessions", ["jti"], unique=True)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    # 2. Add token_version to users (default 0)
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # 3. Drop the now-replaced refresh_token_jti column
    op.drop_column("users", "refresh_token_jti")


def downgrade() -> None:
    """Downgrade schema."""

    # Restore refresh_token_jti
    op.add_column(
        "users",
        sa.Column("refresh_token_jti", sa.String(length=43), nullable=True),
    )

    # Remove token_version
    op.drop_column("users", "token_version")

    # Drop sessions table and its indexes
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_jti", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_id", table_name="sessions")
    op.drop_table("sessions")
