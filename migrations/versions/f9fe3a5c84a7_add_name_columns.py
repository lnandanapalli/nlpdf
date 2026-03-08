"""add_name_columns

Revision ID: f9fe3a5c84a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-08 09:02:20.067590

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f9fe3a5c84a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add first_name and last_name columns to users table."""
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    """Remove name columns."""
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
