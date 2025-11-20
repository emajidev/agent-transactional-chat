import logging
import threading
from typing import Any

from src.configuration.config import get_session
from src.modules.conversations.repositories.conversation_repository import ConversationRepository
from src.modules.conversations.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class ResponseConsumerService:
    """Servicio para procesar mensajes de respuesta de transferencias desde RabbitMQ"""

    def __init__(self):
        self.consumer_thread = None
        self.consumer = None

    def _process_message(self, message_data: dict[str, Any]):
        """
        Procesa un mensaje de respuesta de transferencia recibido de RabbitMQ

        Args:
            message_data: Diccionario con los datos de la respuesta:
                - transaction_id: ID de la transacción
                - conversation_id: ID de la conversación
                - status: Estado de la transacción (success/failed)
                - message: Mensaje de respuesta
                - balance_after: Saldo después de la transferencia (opcional)
                - currency: Moneda (opcional)
                - error_message: Mensaje de error (opcional)
        """
        transaction_id = message_data.get("transaction_id", "unknown")
        conversation_id = message_data.get("conversation_id", "unknown")
        status = message_data.get("status", "unknown")
        
        logger.info(
            f"Respuesta de transferencia recibida: transaction_id={transaction_id}, "
            f"conversation_id={conversation_id}, status={status}"
        )
        
        db = None
        try:
            db = get_session()
            conversation_repo = ConversationRepository(db)
            message_repo = MessageRepository(db)
            
            # Convertir conversation_id a int
            try:
                conversation_id_int = int(conversation_id)
            except (ValueError, TypeError):
                logger.error(f"conversation_id inválido: {conversation_id}")
                return
            
            # Obtener la conversación
            conversation = conversation_repo.get_by_id(conversation_id_int)
            if not conversation:
                logger.warning(f"Conversación {conversation_id_int} no encontrada")
                return
            
            # Construir el mensaje de respuesta
            response_message = message_data.get("message", "")
            
            # Si hay saldo después, agregarlo al mensaje
            if status == "success" and message_data.get("balance_after") is not None:
                balance_after = message_data.get("balance_after")
                currency = message_data.get("currency", "COP")
                response_message += f"\n\nTu saldo después de la transferencia es ${balance_after:,.0f} {currency}."
            
            # Guardar el mensaje en la conversación
            try:
                message_repo.create_message(
                    conversation_id=conversation_id_int,
                    role="assistant",
                    content=response_message,
                )
                db.commit()
                logger.info(f"Mensaje de respuesta guardado en conversación {conversation_id_int}")
            except Exception as msg_error:
                logger.error(f"Error al guardar mensaje de respuesta: {str(msg_error)}", exc_info=True)
                db.rollback()
            
        except Exception as e:
            logger.error(
                f"Error al procesar respuesta de transferencia transaction_id={transaction_id}: {str(e)}",
                exc_info=True,
            )
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def _run_consumer(self):
        """Ejecuta el consumidor en un thread separado"""
        try:
            from src.configuration.config import settings
            from src.common.rabbitmq_consumer import RabbitMQConsumer

            # Crear un consumidor para la cola de respuestas
            self.consumer = RabbitMQConsumer(
                message_handler=self._process_message,
                queue_name=settings.RABBITMQ_RESPONSE_QUEUE,
            )
            self.consumer.start_consuming()

        except Exception as e:
            logger.error(f"Error en el consumidor de respuestas de RabbitMQ: {str(e)}", exc_info=True)

    def start(self):
        """Inicia el consumidor en un thread separado"""
        if self.consumer_thread is None or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self._run_consumer, daemon=True)
            self.consumer_thread.start()
            logger.info("Consumidor de respuestas de RabbitMQ iniciado en thread separado")

    def stop(self):
        """Detiene el consumidor"""
        if self.consumer:
            try:
                self.consumer.stop_consuming()
                logger.info("Consumidor de respuestas de RabbitMQ detenido")
            except Exception as e:
                logger.error(f"Error al detener consumidor de respuestas: {str(e)}")

