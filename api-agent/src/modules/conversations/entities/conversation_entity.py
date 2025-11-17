from sqlalchemy import Column, DateTime, Integer, String
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

    def __repr__(self):
        return (
            f"<Conversation(id={self.id}, user_id='{self.user_id}', status='{self.status.value}')>"
        )


