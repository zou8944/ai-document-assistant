"""add categorize_mode and generate_readme to collections, recategorize task type

Revision ID: g9b3c2d4e5f6
Revises: f8a2c1e3b9d4
Create Date: 2026-06-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g9b3c2d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f8a2c1e3b9d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add categorize_mode column to collections table
    op.add_column(
        'collections',
        sa.Column('categorize_mode', sa.String(20), nullable=False, server_default='ai')
    )

    # Add generate_readme column to collections table
    op.add_column(
        'collections',
        sa.Column('generate_readme', sa.Boolean(), nullable=False, server_default='1')
    )

    # Expand task type constraint to include recategorize
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        "type IN ('ingest_files', 'ingest_urls', 'reindex_collection', 'regenerate_readme', 'recategorize')"
    )


def downgrade() -> None:
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        "type IN ('ingest_files', 'ingest_urls', 'reindex_collection', 'regenerate_readme')"
    )
    op.drop_column('collections', 'generate_readme')
    op.drop_column('collections', 'categorize_mode')
