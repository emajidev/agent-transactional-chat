"""
Script to initialize database: create tables if they don't exist before migrations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.configuration.config import Base, get_engine  # noqa: E402


def init_database():
    """Create all tables if they don't exist."""
    engine = get_engine()

    print("Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("Tables created/verified successfully!")


if __name__ == "__main__":
    init_database()
