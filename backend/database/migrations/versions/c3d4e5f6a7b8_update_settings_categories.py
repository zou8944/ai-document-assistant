"""update settings categories

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old constraint and add new one with expanded categories
    op.drop_constraint('chk_settings_category', 'settings', type_='check')
    op.create_check_constraint(
        'chk_settings_category',
        'settings',
        "category IN ('general', 'llm', 'embedding', 'paths', 'crawler', 'credentials', 'business', 'system')"
    )


def downgrade() -> None:
    op.drop_constraint('chk_settings_category', 'settings', type_='check')
    op.create_check_constraint(
        'chk_settings_category',
        'settings',
        "category IN ('general', 'llm', 'embedding', 'paths', 'crawler')"
    )
