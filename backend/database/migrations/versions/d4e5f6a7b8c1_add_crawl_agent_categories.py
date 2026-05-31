"""add crawl and agent setting categories

Revision ID: d4e5f6a7b8c1
Revises: c3d4e5f6a7b8
Create Date: 2026-01-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c1'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('chk_settings_category', 'settings', type_='check')
    op.create_check_constraint(
        'chk_settings_category',
        'settings',
        "category IN ('general', 'llm', 'embedding', 'paths', 'crawler', "
        "'credentials', 'business', 'system', 'crawl', 'agent')"
    )


def downgrade() -> None:
    op.drop_constraint('chk_settings_category', 'settings', type_='check')
    op.create_check_constraint(
        'chk_settings_category',
        'settings',
        "category IN ('general', 'llm', 'embedding', 'paths', 'crawler', "
        "'credentials', 'business', 'system')"
    )
