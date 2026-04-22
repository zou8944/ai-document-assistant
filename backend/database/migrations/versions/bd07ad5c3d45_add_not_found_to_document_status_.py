"""add_not_found_to_document_status_constraint

Revision ID: bd07ad5c3d45
Revises: 96473d89b63b
Create Date: 2026-04-22 21:59:20.834964

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bd07ad5c3d45'
down_revision: Union[str, Sequence[str], None] = '96473d89b63b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('chk_document_status', 'documents', type_='check')
    op.create_check_constraint(
        'chk_document_status',
        'documents',
        "status IN ('pending', 'processing', 'indexed', 'failed', 'not_found')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('chk_document_status', 'documents', type_='check')
    op.create_check_constraint(
        'chk_document_status',
        'documents',
        "status IN ('pending', 'processing', 'indexed', 'failed')"
    )
