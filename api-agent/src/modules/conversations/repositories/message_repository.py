from typing import Any

from src.common.repositories import BaseRepository
from src.common.resilience import retry_db_operation
from src.modules.conversations.entities import Message


class MessageRepository(BaseRepository[Message]):
    model = Message

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def get_by_conversation_id(
        self, conversation_id: int, skip: int = 0, limit: int = 100
    ) -> list[Message]:
        """Obtiene todos los mensajes de una conversación ordenados por fecha de creación."""
        return (
            self.session.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .filter(Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_message(
        self, conversation_id: int, role: str, content: str
    ) -> Message:
        """Crea un nuevo mensaje en la base de datos."""
        message_data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        db_message = Message(**message_data)
        return super().create(db_message)

    def create_messages(
        self, conversation_id: int, messages: list[dict[str, Any]]
    ) -> list[Message]:
        """Crea múltiples mensajes en la base de datos."""
        db_messages = []
        for msg in messages:
            message_data = {
                "conversation_id": conversation_id,
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            }
            db_message = Message(**message_data)
            db_messages.append(db_message)

        self.session.add_all(db_messages)
        self.session.commit()
        for db_message in db_messages:
            self.session.refresh(db_message)
        return db_messages

