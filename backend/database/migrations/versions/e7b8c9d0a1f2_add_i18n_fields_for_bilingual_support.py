"""add i18n fields for bilingual support

Revision ID: e7b8c9d0a1f2
Revises: bd07ad5c3d45
Create Date: 2026-04-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b8c9d0a1f2'
down_revision: Union[str, Sequence[str], None] = 'bd07ad5c3d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Collection i18n fields
    op.add_column('collections', sa.Column('readme_content_zh', sa.Text(), nullable=True))
    op.add_column('collections', sa.Column('categories_json_zh', sa.Text(), nullable=True))
    op.add_column('collections', sa.Column('source_language', sa.String(length=10), nullable=True))

    # Document i18n fields
    op.add_column('documents', sa.Column('name_translated', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'name_translated')
    op.drop_column('collections', 'source_language')
    op.drop_column('collections', 'categories_json_zh')
    op.drop_column('collections', 'readme_content_zh')
