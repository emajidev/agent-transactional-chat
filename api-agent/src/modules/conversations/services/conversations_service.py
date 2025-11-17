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
from src.modules.conversations.services.agent_service import AgentService


class ConversationsService:
    def __init__(self, db: Session, openai_api_key: str | None = None):
        self.repository = ConversationRepository(db)
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
        )
