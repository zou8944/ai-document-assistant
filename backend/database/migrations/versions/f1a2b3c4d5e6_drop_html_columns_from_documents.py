"""drop html_content and clean_html columns from documents

Revision ID: f1a2b3c4d5e6
Revises: 19d22996ad8c
Create Date: 2026-06-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '19d22996ad8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop html_content and clean_html columns from documents."""
    op.drop_column('documents', 'html_content')
    op.drop_column('documents', 'clean_html')


def downgrade() -> None:
    """Re-add html_content and clean_html columns to documents."""
    op.add_column('documents', sa.Column('html_content', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('clean_html', sa.Text(), nullable=True))
