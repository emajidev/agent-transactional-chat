"""Add conversation state fields

Revision ID: 003
Revises: 002
Create Date: 2024-01-17 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '003'
down_revision: str | None = '002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('conversations')]

    if 'recipient_phone' not in existing_columns:
        op.add_column('conversations', sa.Column('recipient_phone', sa.String(length=20), nullable=True))
    
    if 'amount' not in existing_columns:
        op.add_column('conversations', sa.Column('amount', sa.Float(), nullable=True))
    
    if 'currency' not in existing_columns:
        op.add_column('conversations', sa.Column('currency', sa.String(length=10), nullable=True, server_default='COP'))
    
    if 'confirmation_pending' not in existing_columns:
        op.add_column('conversations', sa.Column('confirmation_pending', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    
    if 'transaction_id' not in existing_columns:
        op.add_column('conversations', sa.Column('transaction_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'transaction_id')
    op.drop_column('conversations', 'confirmation_pending')
    op.drop_column('conversations', 'currency')
    op.drop_column('conversations', 'amount')
    op.drop_column('conversations', 'recipient_phone')

