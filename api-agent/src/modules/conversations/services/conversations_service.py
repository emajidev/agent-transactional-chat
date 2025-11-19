import logging

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from src.common.enums.conversation_status import ConversationStatus
from src.modules.conversations.dtos.conversation import (
    ChatMessage,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from src.modules.conversations.repositories.conversation_repository import ConversationRepository
from src.modules.conversations.repositories.message_repository import MessageRepository
from src.modules.conversations.services.agent_service import AgentService

logger = logging.getLogger(__name__)


class ConversationsService:
    def __init__(self, db: Session, openai_api_key: str | None = None):
        self.repository = ConversationRepository(db)
        self.message_repository = MessageRepository(db)
        self.agent_service = AgentService(db, openai_api_key)

    def get_conversation(self, conversation_id: int) -> ConversationResponse | None:
        conversation = self.repository.get_by_id(conversation_id)
        if not conversation:
            return None
        return ConversationResponse.model_validate(conversation)

    def get_conversations(self, skip: int = 0, limit: int = 100) -> list[ConversationResponse]:
        conversations = self.repository.get_all(skip=skip, limit=limit)
        return [ConversationResponse.model_validate(c) for c in conversations]

    def create_conversation(self, conversation_data: ConversationCreate) -> ConversationResponse:
        conversation = self.repository.create(conversation_data)
        return ConversationResponse.model_validate(conversation)

    def update_conversation(
        self, conversation_id: int, conversation_data: ConversationUpdate
    ) -> ConversationResponse | None:
        conversation = self.repository.update(conversation_id, conversation_data)
        if not conversation:
            return None
        return ConversationResponse.model_validate(conversation)

    def delete_conversation(self, conversation_id: int) -> bool:
        return self.repository.delete(conversation_id)

    def process_chat_message(self, chat_message: ChatMessage, user_id: str) -> ChatResponse:
        conversation = None

        if chat_message.conversation_id:
            conversation = self.repository.get_by_id(chat_message.conversation_id)
            if not conversation:
                conversation = None

        if not conversation:
            conversation_data = ConversationCreate(
                user_id=user_id, status=ConversationStatus.ACTIVE
            )
            conversation = self.repository.create(conversation_data)
        elif conversation.status in [ConversationStatus.COMPLETED, ConversationStatus.ABANDONED]:
            update_data = ConversationUpdate(status=ConversationStatus.ACTIVE)
            conversation = self.repository.update(conversation.id, update_data)

        agent_result = self.agent_service.process_message(
            user_message=chat_message.message, conversation_id=conversation.id, _user_id=user_id
        )

        # Guardar mensajes en la base de datos
        messages = agent_result["state"].get("messages", [])
        if messages:
            try:
                # Obtener los mensajes existentes en BD para comparar
                existing_messages = self.message_repository.get_by_conversation_id(
                    conversation_id=conversation.id, limit=100
                )
                existing_content_set = {
                    (m.role, m.content) for m in existing_messages
                }
                
                # Guardar solo los mensajes nuevos (los últimos 2: usuario y asistente)
                new_messages = messages[-2:] if len(messages) >= 2 else messages
                for msg in new_messages:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role and content:
                        # Solo guardar si no existe un mensaje idéntico
                        if (role, content) not in existing_content_set:
                            self.message_repository.create_message(
                                conversation_id=conversation.id,
                                role=role,
                                content=content,
                            )
                            # Agregar a la lista de existentes para evitar duplicados en la misma ejecución
                            existing_content_set.add((role, content))
            except ProgrammingError as e:
                # Si la tabla no existe, loguear el error pero continuar
                if "does not exist" in str(e) or "relation" in str(e).lower():
                    logger.warning(
                        f"La tabla 'messages' no existe. "
                        f"Por favor ejecuta la migración: alembic upgrade head. "
                        f"Los mensajes no se guardarán hasta que se ejecute la migración. "
                        f"Error: {str(e)}"
                    )
                else:
                    # Re-lanzar si es otro tipo de error de programación
                    raise
            except Exception as e:
                # Para otros errores, loguear pero continuar
                logger.error(f"Error al guardar mensajes en BD: {str(e)}")

        if agent_result["state"].get("transaction_id"):
            update_data = ConversationUpdate(status=ConversationStatus.COMPLETED)
            self.repository.update(conversation.id, update_data)
            conversation_status = ConversationStatus.COMPLETED
        else:
            conversation_status = ConversationStatus(conversation.status)

        return ChatResponse(
            conversation_id=conversation.id,
            response=agent_result["response"],
            status=conversation_status,
            state=agent_result.get("state"),
        )
