from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy import text as sa_text

from alembic import context
from src.configuration.config import Base, get_engine, settings

config = context.config


def ensure_tables_exist():
    """Create tables and enums if they don't exist before running migrations."""
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(sa_text("""
                DO $$ BEGIN
                    CREATE TYPE conversationstatus AS ENUM ('active', 'completed', 'abandoned');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            connection.commit()
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Could not create tables automatically: {e}")
        print("Continuing with migrations...")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    ensure_tables_exist()

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
