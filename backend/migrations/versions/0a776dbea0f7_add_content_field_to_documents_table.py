"""add content field to documents table

Revision ID: 0a776dbea0f7
Revises: 766923fa4157
Create Date: 2025-08-31 17:14:26.447377

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0a776dbea0f7'
down_revision: Union[str, Sequence[str], None] = '766923fa4157'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add content field to documents table
    op.add_column('documents', sa.Column('content', sa.Text(), server_default="", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove content field from documents table
    op.drop_column('documents', 'content')
