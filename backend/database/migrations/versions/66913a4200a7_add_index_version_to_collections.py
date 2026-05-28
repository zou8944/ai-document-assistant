"""add index_version to collections

Revision ID: 66913a4200a7
Revises: 66913a4199a7
Create Date: 2026-05-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66913a4200a7'
down_revision: Union[str, Sequence[str], None] = '66913a4199a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('collections', sa.Column('index_version', sa.String(100), nullable=True))
    # Expand task type constraint to include reindex_collection
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        sa.text("type IN ('ingest_files', 'ingest_urls', 'reindex_collection')")
    )


def downgrade() -> None:
    op.drop_constraint('chk_task_type', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_type',
        'tasks',
        sa.text("type IN ('ingest_files', 'ingest_urls')")
    )
    op.drop_column('collections', 'index_version')
