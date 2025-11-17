from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker


class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., description="Database connection URL")
    APP_NAME: str = "Agent API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 3000
    API_KEY: str = Field(default="", description="API Key for authentication (deprecated, use JWT)")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key for AI agent")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model to use for AI agent")
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production", description="Secret key for JWT tokens"
    )

    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# Database
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None

Base = declarative_base()


def get_engine() -> Engine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=settings.DEBUG)
    return _engine


def get_session() -> Session:
    global _SessionFactory  # noqa: PLW0603
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory()


def get_db():
    db = get_session()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger("uvicorn.error")
        logger.error(f"Error en get_db: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()
