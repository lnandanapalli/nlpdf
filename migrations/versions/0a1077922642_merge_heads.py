"""merge heads

Revision ID: 0a1077922642
Revises: b7d4e8f12a3c, c7d8e9f0a1b2
Create Date: 2026-03-11 23:50:54.817498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a1077922642'
down_revision: Union[str, Sequence[str], None] = ('b7d4e8f12a3c', 'c7d8e9f0a1b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
