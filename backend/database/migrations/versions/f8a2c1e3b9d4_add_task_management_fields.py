"""add task management fields

Revision ID: f8a2c1e3b9d4
Revises: e7b8c9d0a1f2
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a2c1e3b9d4'
down_revision: Union[str, Sequence[str], None] = 'e7b8c9d0a1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_task_id to documents table
    op.add_column(
        'documents',
        sa.Column('source_task_id', sa.String(32), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('idx_documents_source_task_id', 'documents', ['source_task_id'])

    # Expand task status constraint to include 'stopped'
    op.drop_constraint('chk_task_status', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_status',
        'tasks',
        sa.text("status IN ('pending', 'processing', 'success', 'failed', 'stopped')")
    )


def downgrade() -> None:
    # Revert task status constraint
    op.drop_constraint('chk_task_status', 'tasks', type_='check')
    op.create_check_constraint(
        'chk_task_status',
        'tasks',
        sa.text("status IN ('pending', 'processing', 'success', 'failed')")
    )

    # Remove source_task_id from documents table
    op.drop_index('idx_documents_source_task_id', table_name='documents')
    op.drop_column('documents', 'source_task_id')
