"""add indexes to documents table

Revision ID: b7d4e8f12a3c
Revises: f9fe3a5c84a7
Create Date: 2026-03-08
"""

from alembic import op

revision = "b7d4e8f12a3c"
down_revision = "f9fe3a5c84a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_documents_owner_id", table_name="documents")
