from typing import Any

from sqlalchemy.orm import Session

from src.modules.conversations.agent.transaction_agent import TransactionAgent
from src.modules.conversations.repositories.conversation_repository import ConversationRepository


class AgentService:
    def __init__(self, db: Session, openai_api_key: str | None = None):
        self.agent = TransactionAgent(openai_api_key)
        self.repository = ConversationRepository(db)
        self._context_cache: dict[int, dict[str, Any]] = {}

    def get_conversation_context(self, conversation_id: int) -> dict[str, Any]:
        if conversation_id in self._context_cache:
            return self._context_cache[conversation_id]

        return {
            "recipient_phone": None,
            "amount": None,
            "currency": "COP",
            "confirmation_pending": False,
            "transaction_id": None,
            "messages": [],
        }

    def save_conversation_context(self, conversation_id: int, context: dict[str, Any]):
        self._context_cache[conversation_id] = context

    def process_message(
        self, user_message: str, conversation_id: int, _user_id: str
    ) -> dict[str, Any]:
        conversation_state = self.get_conversation_context(conversation_id)

        result = self.agent.process(user_message, conversation_state)

        self.save_conversation_context(conversation_id, result["state"])

        return {
            "response": result["response"],
            "conversation_id": conversation_id,
            "state": result["state"],
        }
