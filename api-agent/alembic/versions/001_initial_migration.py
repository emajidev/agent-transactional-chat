"""Initial migration with users and conversations

Revision ID: 001
Revises:
Create Date: 2024-01-15 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text("""
            DO $$ BEGIN
                CREATE TYPE conversationstatus AS ENUM ('active', 'completed', 'abandoned');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
    )

    conversation_status_enum = postgresql.ENUM(
        'active',
        'completed',
        'abandoned',
        name='conversationstatus',
        create_type=False
    )

    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    if 'conversations' not in existing_tables:
        op.create_table(
            'conversations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', conversation_status_enum, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)

    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        default_password = "admin123"
        password_hash = pwd_context.hash(default_password)
    except Exception:
        import bcrypt
        default_password = "admin123"
        password_hash = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    op.execute(
        sa.text("""
            INSERT INTO users (username, email, hashed_password, created_at)
            VALUES ('admin', 'admin@example.com', :password, now())
            ON CONFLICT (username) DO NOTHING
        """).bindparams(password=password_hash)
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_table('conversations')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')

    conversation_status_enum = postgresql.ENUM(
        'active',
        'completed',
        'abandoned',
        name='conversationstatus'
    )
    conversation_status_enum.drop(op.get_bind(), checkfirst=True)
