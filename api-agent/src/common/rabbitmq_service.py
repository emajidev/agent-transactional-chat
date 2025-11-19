import json
import logging
from typing import Any

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.configuration.config import settings

logger = logging.getLogger(__name__)


class RabbitMQService:
    """Servicio para enviar mensajes a RabbitMQ"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        """Establece conexión con RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
            )
            parameters = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                virtual_host=settings.RABBITMQ_VHOST,
                credentials=credentials,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            # Declarar la cola para asegurar que existe
            self.channel.queue_declare(queue=settings.RABBITMQ_TRANSFER_QUEUE, durable=True)
            logger.info("Conexión a RabbitMQ establecida exitosamente")
        except AMQPConnectionError as e:
            logger.error(f"Error al conectar con RabbitMQ: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al conectar con RabbitMQ: {str(e)}")
            raise

    def _ensure_connection(self):
        """Asegura que la conexión esté activa"""
        if self.connection is None or self.connection.is_closed:
            if self.channel is not None and not self.channel.is_closed:
                try:
                    self.channel.close()
                except Exception:
                    pass
            self._connect()

    def send_transfer(self, transfer_data: dict[str, Any]) -> bool:
        """
        Envía un mensaje de transferencia a RabbitMQ

        Args:
            transfer_data: Diccionario con los datos de la transferencia
                - transaction_id: ID de la transacción
                - recipient_phone: Número de teléfono del destinatario
                - amount: Monto de la transferencia
                - currency: Moneda (default: COP)
                - user_id: ID del usuario que realiza la transferencia (opcional)

        Returns:
            True si el mensaje se envió exitosamente, False en caso contrario
        """
        try:
            self._ensure_connection()

            transaction_id = transfer_data.get("transaction_id")
            recipient_phone = transfer_data.get("recipient_phone")
            amount = transfer_data.get("amount")
            currency = transfer_data.get("currency", "COP")
            user_id = transfer_data.get("user_id")
            conversation_id = transfer_data.get("conversation_id")
            
            logger.info(
                f"Enviando mensaje a la cola RabbitMQ - Cola: {settings.RABBITMQ_TRANSFER_QUEUE}, "
                f"Transaction ID: {transaction_id}, Recipient Phone: {recipient_phone}, "
                f"Amount: {amount} {currency}, User ID: {user_id}, Conversation ID: {conversation_id}"
            )

            message_body = json.dumps(transfer_data, ensure_ascii=False)
            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_TRANSFER_QUEUE,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Hace el mensaje persistente
                ),
            )
            logger.info(
                f"Mensaje enviado exitosamente a la cola RabbitMQ - Cola: {settings.RABBITMQ_TRANSFER_QUEUE}, "
                f"Transaction ID: {transaction_id}, Tamaño del mensaje: {len(message_body)} bytes"
            )
            return True
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Error al enviar mensaje a RabbitMQ: {str(e)}")
            # Intentar reconectar
            try:
                self._connect()
                # Reintentar el envío
                transaction_id = transfer_data.get("transaction_id")
                logger.info(
                    f"Reintentando envío de mensaje a la cola RabbitMQ después de reconexión - "
                    f"Transaction ID: {transaction_id}, Cola: {settings.RABBITMQ_TRANSFER_QUEUE}"
                )
                
                message_body = json.dumps(transfer_data, ensure_ascii=False)
                self.channel.basic_publish(
                    exchange="",
                    routing_key=settings.RABBITMQ_TRANSFER_QUEUE,
                    body=message_body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                logger.info(
                    f"Mensaje enviado exitosamente a la cola RabbitMQ después de reconexión - "
                    f"Cola: {settings.RABBITMQ_TRANSFER_QUEUE}, Transaction ID: {transaction_id}, "
                    f"Tamaño del mensaje: {len(message_body)} bytes"
                )
                return True
            except Exception as retry_error:
                logger.error(f"Error al reintentar envío a RabbitMQ: {str(retry_error)}")
                return False
        except Exception as e:
            logger.error(f"Error inesperado al enviar mensaje a RabbitMQ: {str(e)}")
            return False

    def close(self):
        """Cierra la conexión con RabbitMQ"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Conexión a RabbitMQ cerrada")
        except Exception as e:
            logger.error(f"Error al cerrar conexión con RabbitMQ: {str(e)}")


# Instancia global del servicio
_rabbitmq_service: RabbitMQService | None = None


def get_rabbitmq_service() -> RabbitMQService:
    """Obtiene la instancia global del servicio RabbitMQ"""
    global _rabbitmq_service
    if _rabbitmq_service is None:
        _rabbitmq_service = RabbitMQService()
    return _rabbitmq_service

