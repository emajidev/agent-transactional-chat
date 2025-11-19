from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker


class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., description="Database connection URL")
    APP_NAME: str = "Transactions API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 3000
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
    RABBITMQ_MANAGEMENT_PORT: int = Field(
        default=15672, description="RabbitMQ management UI port"
    )
    
    class Config:
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignorar campos extra del .env que no están en el modelo


settings = Settings() 

# Database
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker[Session]] = None

Base = declarative_base()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )
    return _engine


def get_session() -> Session:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory()


def get_db():
    db = get_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()



