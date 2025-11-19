from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from src.common.entities.base import BaseEntity
from src.common.enums.conversation_status import ConversationStatus


class ConversationEntity(BaseEntity):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    # Usar el enum de PostgreSQL con valores explícitos
    status = Column(
        PG_ENUM(
            ConversationStatus,
            name="conversationstatus",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    # Campos para guardar el estado de la conversación
    # Estos campos pueden no existir en la tabla si la migración no se ha ejecutado
    # Por eso no tienen valores por defecto a nivel de Python
    recipient_phone = Column(String(20), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True)  # Sin default para evitar que SQLAlchemy lo inserte si no existe
    confirmation_pending = Column(Boolean, nullable=True)  # Sin default para evitar que SQLAlchemy lo inserte si no existe
    transaction_id = Column(String(255), nullable=True)

    def __repr__(self):
        return (
            f"<Conversation(id={self.id}, user_id='{self.user_id}', status='{self.status.value}')>"
        )


