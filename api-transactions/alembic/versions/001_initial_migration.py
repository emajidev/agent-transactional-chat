"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear el enum TransactionStatus
    transaction_status_enum = postgresql.ENUM(
        'pending',
        'completed',
        'failed',
        name='transactionstatus',
        create_type=True
    )
    transaction_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Crear la tabla transactions
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('transaction_id', sa.String(length=255), nullable=False),
        sa.Column('recipient_phone', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', transaction_status_enum, nullable=False),
        sa.Column('error_message', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)


def downgrade() -> None:
    # Eliminar índices
    op.drop_index(op.f('ix_transactions_id'), table_name='transactions')
    
    # Eliminar la tabla transactions
    op.drop_table('transactions')
    
    # Eliminar el enum TransactionStatus
    transaction_status_enum = postgresql.ENUM(
        'pending',
        'completed',
        'failed',
        name='transactionstatus'
    )
    transaction_status_enum.drop(op.get_bind(), checkfirst=True)

