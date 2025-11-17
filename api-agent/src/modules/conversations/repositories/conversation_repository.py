from datetime import UTC, datetime
from typing import Any

from src.common.enums.conversation_status import ConversationStatus
from src.common.repositories import BaseRepository
from src.common.resilience import retry_db_operation
from src.modules.conversations.dtos.conversation import ConversationCreate, ConversationUpdate
from src.modules.conversations.entities import Conversation


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def get_by_id(self, conversation_id: int) -> Conversation | None:
        # El filtrado por deleted_at se hace automáticamente en _build_query
        return (
            self.session.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .filter(Conversation.deleted_at.is_(None))
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[Conversation]:
        # El filtrado por deleted_at se hace automáticamente en _build_query del BaseRepository
        return super().get_all(skip=skip, limit=limit, filters=filters)

    def create(self, conversation_data: ConversationCreate) -> Conversation:
        # Convertir el enum a su valor antes de crear la entidad
        # Usar model_dump con mode='python' para obtener valores nativos
        data = conversation_data.model_dump(mode="python", exclude_unset=True)

        # Establecer started_at si no se proporciona
        if "started_at" not in data:
            data["started_at"] = datetime.now(UTC)

        # Asegurar que el status sea el valor del enum (string)
        if "status" in data:
            if isinstance(data["status"], ConversationStatus):
                data["status"] = data["status"].value
            elif isinstance(data["status"], str):
                # Si ya es string, verificar que sea válido
                data["status"] = data["status"].lower()

        db_conversation = Conversation(**data)
        return super().create(db_conversation)

    def update(
        self, conversation_id: int, conversation_data: ConversationUpdate
    ) -> Conversation | None:
        db_conversation = self.get_by_id(conversation_id)
        if not db_conversation:
            return None

        # Convertir el enum a su valor antes de actualizar
        update_data = conversation_data.model_dump(exclude_unset=True, mode="python")
        if "status" in update_data:
            if isinstance(update_data["status"], ConversationStatus):
                update_data["status"] = update_data["status"].value
            elif isinstance(update_data["status"], str):
                update_data["status"] = update_data["status"].lower()
        return super().update(db_conversation, update_data)

    def delete(self, conversation_id: int) -> bool:
        """
        Elimina una conversación (soft delete).
        El listener de SQLAlchemy interceptará el DELETE y establecerá deleted_at automáticamente.
        """
        db_conversation = self.get_by_id(conversation_id)
        if not db_conversation:
            return False

        # El listener de SQLAlchemy manejará el soft delete automáticamente
        # Solo necesitamos llamar a session.delete y el listener convertirá en UPDATE
        super().delete(db_conversation)
        return True
