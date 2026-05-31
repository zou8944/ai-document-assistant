"""add categorized_at to documents and regenerate_readme task type

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c1
Create Date: 2026-05-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add categorized_at column to documents table
    op.add_column(
        'documents',
        sa.Column('categorized_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Expand task type constraint to include regenerate_readme
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        "type IN ('ingest_files', 'ingest_urls', 'reindex_collection', 'regenerate_readme')"
    )


def downgrade() -> None:
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        "type IN ('ingest_files', 'ingest_urls', 'reindex_collection')"
    )
    op.drop_column('documents', 'categorized_at')
