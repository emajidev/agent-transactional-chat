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
    OPENAI_BASE_URL: str = Field(
        default="", description="OpenAI API base URL (optional, for proxy or compatible services)"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production", description="Secret key for JWT tokens"
    )
    RABBITMQ_HOST: str = Field(default="localhost", description="RabbitMQ host")
    RABBITMQ_PORT: int = Field(default=5672, description="RabbitMQ port")
    RABBITMQ_USER: str = Field(default="guest", description="RabbitMQ username")
    RABBITMQ_PASSWORD: str = Field(default="guest", description="RabbitMQ password")
    RABBITMQ_VHOST: str = Field(default="/", description="RabbitMQ virtual host")
    RABBITMQ_TRANSFER_QUEUE: str = Field(
        default="transfer_queue", description="RabbitMQ queue name for transfers"
    )
    RABBITMQ_RESPONSE_QUEUE: str = Field(
        default="transfer_response_queue", description="RabbitMQ queue name for transfer responses"
    )
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_PASSWORD: str = Field(default="", description="Redis password (empty if no auth)")
    REDIS_DB: int = Field(default=0, description="Redis database number")
    REDIS_TTL: int = Field(default=3600, description="Redis TTL in seconds for conversation cache (default 1 hour)")

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
