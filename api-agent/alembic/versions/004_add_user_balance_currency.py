"""Add balance and currency to users table

Revision ID: 004
Revises: 003
Create Date: 2024-01-18 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '004'
down_revision: str | None = '003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]

    if 'balance' not in existing_columns:
        op.add_column('users', sa.Column('balance', sa.Float(), nullable=True, server_default='0.0'))
    
    if 'currency' not in existing_columns:
        op.add_column('users', sa.Column('currency', sa.String(length=10), nullable=True, server_default='COP'))
    
    # Actualizar usuarios existentes para que tengan valores por defecto si son None
    op.execute(
        sa.text("""
            UPDATE users 
            SET balance = 0.0 
            WHERE balance IS NULL
        """)
    )
    
    op.execute(
        sa.text("""
            UPDATE users 
            SET currency = 'COP' 
            WHERE currency IS NULL
        """)
    )
    
    # Asignar 10000 COP al usuario admin
    op.execute(
        sa.text("""
            UPDATE users 
            SET balance = 10000.0, currency = 'COP'
            WHERE username = 'admin'
        """)
    )


def downgrade() -> None:
    op.drop_column('users', 'currency')
    op.drop_column('users', 'balance')

