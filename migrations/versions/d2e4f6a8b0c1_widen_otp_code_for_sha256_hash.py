"""widen otp_code for sha256 hash

Revision ID: d2e4f6a8b0c1
Revises: 8ff52253da33
Create Date: 2026-03-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d2e4f6a8b0c1"
down_revision: Union[str, Sequence[str], None] = "8ff52253da33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen otp_code from 6 chars (plaintext) to 64 chars (SHA-256 hex digest)."""
    op.alter_column(
        "users",
        "otp_code",
        existing_type=sa.String(length=6),
        type_=sa.String(length=64),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert otp_code column back to 6 chars."""
    # Clear any hashed OTPs before shrinking the column
    op.execute("UPDATE users SET otp_code = NULL")
    op.alter_column(
        "users",
        "otp_code",
        existing_type=sa.String(length=64),
        type_=sa.String(length=6),
        existing_nullable=True,
    )
