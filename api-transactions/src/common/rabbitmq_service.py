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
            # Declarar las colas para asegurar que existen
            self.channel.queue_declare(queue=settings.RABBITMQ_TRANSFER_QUEUE, durable=True)
            self.channel.queue_declare(queue=settings.RABBITMQ_RESPONSE_QUEUE, durable=True)
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

    def send_response(self, response_data: dict[str, Any]) -> bool:
        """
        Envía un mensaje de respuesta a RabbitMQ

        Args:
            response_data: Diccionario con los datos de la respuesta
                - transaction_id: ID de la transacción
                - conversation_id: ID de la conversación
                - status: Estado de la transacción (success/failed)
                - message: Mensaje de respuesta
                - balance_after: Saldo después de la transferencia (opcional)
                - currency: Moneda (opcional)
                - error_message: Mensaje de error (opcional)

        Returns:
            True si el mensaje se envió exitosamente, False en caso contrario
        """
        try:
            self._ensure_connection()

            transaction_id = response_data.get("transaction_id")
            conversation_id = response_data.get("conversation_id")
            status = response_data.get("status")
            
            logger.info(
                f"Enviando mensaje de respuesta a la cola RabbitMQ - Cola: {settings.RABBITMQ_RESPONSE_QUEUE}, "
                f"Transaction ID: {transaction_id}, Conversation ID: {conversation_id}, Status: {status}"
            )

            message_body = json.dumps(response_data, ensure_ascii=False)
            self.channel.basic_publish(
                exchange="",
                routing_key=settings.RABBITMQ_RESPONSE_QUEUE,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Hace el mensaje persistente
                ),
            )
            logger.info(
                f"Mensaje de respuesta enviado exitosamente: transaction_id={transaction_id}, status={status}"
            )
            return True
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Error de conexión al enviar respuesta a RabbitMQ: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al enviar respuesta a RabbitMQ: {str(e)}", exc_info=True)
            return False

