import logging
from typing import Any

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from src.common.redis_service import get_redis_service
from src.modules.conversations.agent.transaction_agent import TransactionAgent
from src.modules.conversations.repositories.conversation_repository import ConversationRepository
from src.modules.conversations.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, db: Session, openai_api_key: str | None = None):
        self.agent = TransactionAgent(openai_api_key)
        self.repository = ConversationRepository(db)
        self.message_repository = MessageRepository(db)
        self.redis_service = get_redis_service()
        self._context_cache: dict[int, dict[str, Any]] = {}  # Fallback en memoria

    def get_conversation_context(self, conversation_id: int) -> dict[str, Any]:
        # Intentar obtener de Redis primero
        redis_key = f"conversation:{conversation_id}"
        cached_context = self.redis_service.get(redis_key)
        if cached_context:
            logger.debug(f"Contexto cargado desde Redis para conversación {conversation_id}")
            # Actualizar caché en memoria como fallback
            self._context_cache[conversation_id] = cached_context
            return cached_context

        # Si está en caché en memoria, devolverlo
        if conversation_id in self._context_cache:
            return self._context_cache[conversation_id]

        # Cargar conversación desde BD para obtener el estado
        conversation = self.repository.get_by_id(conversation_id)
        
        # Intentar cargar mensajes desde la base de datos
        messages = []
        try:
            db_messages = self.message_repository.get_by_conversation_id(
                conversation_id=conversation_id, limit=100
            )
            # Convertir mensajes de BD al formato esperado
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in db_messages
            ]
        except ProgrammingError as e:
            # Si la tabla no existe, loguear el error y continuar con mensajes vacíos
            if "does not exist" in str(e) or "relation" in str(e).lower():
                logger.warning(
                    f"La tabla 'messages' no existe. "
                    f"Por favor ejecuta la migración: alembic upgrade head. "
                    f"Error: {str(e)}"
                )
            else:
                # Re-lanzar si es otro tipo de error de programación
                raise
        except Exception as e:
            # Para otros errores, loguear y continuar con mensajes vacíos
            logger.error(f"Error al cargar mensajes desde BD: {str(e)}")

        # Cargar el estado desde la conversación en BD
        # Usar getattr con valores por defecto para manejar campos que pueden no existir
        recipient_phone = getattr(conversation, "recipient_phone", None) if conversation else None
        amount = getattr(conversation, "amount", None) if conversation else None
        currency = getattr(conversation, "currency", "COP") if conversation else "COP"
        confirmation_pending = getattr(conversation, "confirmation_pending", False) if conversation else False
        transaction_id = getattr(conversation, "transaction_id", None) if conversation else None
        user_id = getattr(conversation, "user_id", None) if conversation else None
        
        context = {
            "recipient_phone": recipient_phone,
            "amount": amount,
            "currency": currency,
            "confirmation_pending": confirmation_pending,
            "transaction_id": transaction_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": messages,
        }
        
        logger.debug(
            f"Cargando contexto de conversación {conversation_id} - "
            f"Teléfono: {recipient_phone}, Monto: {amount}, "
            f"Confirmación pendiente: {confirmation_pending}, "
            f"Mensajes: {len(messages)}"
        )

        # Guardar en caché (Redis y memoria)
        self._context_cache[conversation_id] = context
        
        # Guardar teléfono, monto, conversation_id y user_id en Redis
        redis_key = f"conversation:{conversation_id}"
        redis_data = {
            "recipient_phone": recipient_phone,
            "amount": amount,
            "conversation_id": conversation_id,
            "user_id": user_id,
        }
        self.redis_service.set(redis_key, redis_data)

        return context

    def save_conversation_context(self, conversation_id: int, context: dict[str, Any]):
        # Guardar en caché en memoria como fallback (con todo el contexto)
        self._context_cache[conversation_id] = context
        
        # Guardar teléfono, monto, conversation_id y user_id en Redis
        redis_key = f"conversation:{conversation_id}"
        redis_data = {
            "recipient_phone": context.get("recipient_phone"),
            "amount": context.get("amount"),
            "conversation_id": conversation_id,
            "user_id": context.get("user_id"),
        }
        self.redis_service.set(redis_key, redis_data)
        
        # Guardar el estado en la base de datos
        try:
            from src.modules.conversations.dtos.conversation import ConversationUpdate
            
            update_data = ConversationUpdate(
                recipient_phone=context.get("recipient_phone"),
                amount=context.get("amount"),
                currency=context.get("currency", "COP"),
                confirmation_pending=context.get("confirmation_pending", False),
                transaction_id=context.get("transaction_id"),
            )
            self.repository.update(conversation_id, update_data)
            logger.debug(f"Estado guardado en BD y Redis para conversación {conversation_id}")
        except Exception as e:
            logger.error(f"Error al guardar el estado de la conversación en BD: {str(e)}")

    def process_message(
        self, user_message: str, conversation_id: int, _user_id: str
    ) -> dict[str, Any]:
        conversation_state = self.get_conversation_context(conversation_id)
        # Agregar user_id y conversation_id al estado de la conversación
        conversation_state["user_id"] = _user_id
        conversation_state["conversation_id"] = conversation_id

        result = self.agent.process(user_message, conversation_state)

        self.save_conversation_context(conversation_id, result["state"])

        return {
            "response": result["response"],
            "conversation_id": conversation_id,
            "state": result["state"],
        }
