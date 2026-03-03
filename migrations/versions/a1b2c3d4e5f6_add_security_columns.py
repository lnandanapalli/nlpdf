"""add_security_columns

Revision ID: a1b2c3d4e5f6
Revises: 876ce331ae0b
Create Date: 2026-03-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "876ce331ae0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OTP attempt tracking, account lockout, and refresh token rotation."""
    op.add_column(
        "users",
        sa.Column("otp_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("refresh_token_jti", sa.String(43), nullable=True),
    )


def downgrade() -> None:
    """Remove security columns."""
    op.drop_column("users", "refresh_token_jti")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "otp_attempts")
