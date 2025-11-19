from sqlalchemy import Column, ForeignKey, Integer, String, Text

from src.common.entities.base import BaseEntity


class MessageEntity(BaseEntity):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' o 'assistant'
    content = Column(Text, nullable=False)

    def __repr__(self):
        return (
            f"<Message(id={self.id}, conversation_id={self.conversation_id}, "
            f"role='{self.role}', content='{self.content[:50]}...')>"
        )

