"""add sort_order to chats

Revision ID: 66913a4199a7
Revises: 28a82de3db0b
Create Date: 2026-05-17 11:01:34.269917

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '66913a4199a7'
down_revision: Union[str, Sequence[str], None] = '28a82de3db0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Add column with server_default so existing rows get a value
    op.add_column(
        'chats',
        sa.Column(
            'sort_order',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )

    # 2) Backfill sort_order using current UI ordering
    #    (last_message_at DESC NULLS LAST, updated_at DESC)
    bind = op.get_bind()
    chats_t = sa.table(
        'chats',
        sa.column('id', sa.String),
        sa.column('sort_order', sa.Integer),
        sa.column('last_message_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    ordered_ids = bind.execute(
        sa.select(chats_t.c.id).order_by(
            chats_t.c.last_message_at.desc().nullslast(),
            chats_t.c.updated_at.desc(),
        )
    ).scalars().all()
    for pos, chat_id in enumerate(ordered_ids):
        bind.execute(
            chats_t.update()
            .where(chats_t.c.id == chat_id)
            .values(sort_order=pos)
        )

    # 3) Create index for fast ordered listing
    op.create_index(
        'idx_chats_sort_order',
        'chats',
        ['sort_order'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_chats_sort_order', table_name='chats')
    op.drop_column('chats', 'sort_order')
