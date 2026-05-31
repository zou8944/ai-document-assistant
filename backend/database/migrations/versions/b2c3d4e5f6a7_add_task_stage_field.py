"""add task stage field

Revision ID: b2c3d4e5f6a7
Revises: 66913a4200a7
Create Date: 2026-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '66913a4200a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stage column to tasks table
    op.add_column(
        'tasks',
        sa.Column('stage', sa.String(50), nullable=True, comment='Current processing stage')
    )


def downgrade() -> None:
    op.drop_column('tasks', 'stage')
