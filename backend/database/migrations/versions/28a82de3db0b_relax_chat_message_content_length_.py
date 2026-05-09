"""relax_chat_message_content_length_constraint

Revision ID: 28a82de3db0b
Revises: c2d4e6f8a0b1
Create Date: 2026-05-09 12:17:04.720175

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '28a82de3db0b'
down_revision: Union[str, Sequence[str], None] = 'c2d4e6f8a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('chk_message_content_length', 'chat_messages', type_='check')
    op.create_check_constraint(
        'chk_message_content_length',
        'chat_messages',
        "length(content) >= 0"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('chk_message_content_length', 'chat_messages', type_='check')
    op.create_check_constraint(
        'chk_message_content_length',
        'chat_messages',
        "length(content) > 0"
    )
