"""merge categorize heads

Revision ID: 19d22996ad8c
Revises: e5f6a7b8c9d0, g9b3c2d4e5f6
Create Date: 2026-06-05 10:53:08.562822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19d22996ad8c'
down_revision: Union[str, Sequence[str], None] = ('e5f6a7b8c9d0', 'g9b3c2d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
