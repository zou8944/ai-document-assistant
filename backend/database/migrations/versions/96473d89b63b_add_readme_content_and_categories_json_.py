"""add readme_content and categories_json to collections

Revision ID: 96473d89b63b
Revises: 3d9d149a244c
Create Date: 2026-04-15 19:11:58.007653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96473d89b63b'
down_revision: Union[str, Sequence[str], None] = '3d9d149a244c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collections', sa.Column('readme_content', sa.Text(), nullable=True))
    op.add_column('collections', sa.Column('categories_json', sa.Text(), nullable=True))
    op.drop_column('collections', 'sitemap_json')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('collections', sa.Column('sitemap_json', sa.Text(), nullable=True))
    op.drop_column('collections', 'categories_json')
    op.drop_column('collections', 'readme_content')
