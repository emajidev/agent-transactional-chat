import json
import logging
import time
from typing import Any, Callable

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.configuration.config import settings

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """Consumidor de RabbitMQ para procesar mensajes"""

    def __init__(
        self,
        message_handler: Callable[[dict[str, Any]], None],
        queue_name: str | None = None,
        max_reconnect_attempts: int = 5,
        reconnect_delay: int = 5,
    ):
        """
        Inicializa el consumidor de RabbitMQ

        Args:
            message_handler: Función que procesa los mensajes recibidos.
                Recibe un diccionario con los datos del mensaje.
            queue_name: Nombre de la cola a consumir. Si es None, usa RABBITMQ_TRANSFER_QUEUE
            max_reconnect_attempts: Número máximo de intentos de reconexión
            reconnect_delay: Segundos de espera entre intentos de reconexión
        """
        self.message_handler = message_handler
        self.queue_name = queue_name or settings.RABBITMQ_TRANSFER_QUEUE
        self.connection = None
        self.channel = None
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self._should_reconnect = True
        self._consuming = False

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
                heartbeat=600,
                blocked_connection_timeout=300,
                connection_attempts=3,
                retry_delay=2,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declarar la cola para asegurar que existe (durable=True para persistencia)
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            # Configurar QoS para procesar un mensaje a la vez
            self.channel.basic_qos(prefetch_count=1)
            logger.info(f"Conexión a RabbitMQ establecida exitosamente para cola: {self.queue_name}")
        except AMQPConnectionError as e:
            logger.error(f"Error al conectar con RabbitMQ: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al conectar con RabbitMQ: {str(e)}")
            raise

    def _is_connection_closed(self) -> bool:
        """Verifica si la conexión está cerrada"""
        try:
            return self.connection is None or self.connection.is_closed
        except Exception:
            return True

    def _is_channel_closed(self) -> bool:
        """Verifica si el canal está cerrado"""
        try:
            return self.channel is None or self.channel.is_closed
        except Exception:
            return True

    def _close_connections(self):
        """Cierra las conexiones existentes de forma segura"""
        try:
            if self.channel and not self._is_channel_closed():
                self.channel.stop_consuming()
        except Exception as e:
            logger.debug(f"Error al detener consumo del canal: {str(e)}")

        try:
            if self.connection and not self._is_connection_closed():
                self.connection.close()
        except Exception as e:
            logger.debug(f"Error al cerrar conexión: {str(e)}")

        self.channel = None
        self.connection = None

    def _reconnect(self):
        """Intenta reconectar a RabbitMQ"""
        attempt = 0
        while attempt < self.max_reconnect_attempts and self._should_reconnect:
            try:
                attempt += 1
                logger.info(f"Intento de reconexión {attempt}/{self.max_reconnect_attempts}")

                # Cerrar conexiones existentes
                self._close_connections()

                # Esperar antes de reconectar
                time.sleep(self.reconnect_delay)

                # Intentar conectar
                self._connect()

                # Si la conexión fue exitosa, reiniciar el consumo
                if self._consuming:
                    self._setup_consumer()

                logger.info("Reconexión exitosa")
                return
            except Exception as e:
                logger.error(f"Error en intento de reconexión {attempt}: {str(e)}")
                if attempt >= self.max_reconnect_attempts:
                    logger.error("Se alcanzó el número máximo de intentos de reconexión")
                    raise

    def _process_message(
        self, ch: pika.channel.Channel, method: pika.spec.Basic.Deliver, properties: pika.spec.BasicProperties, body: bytes
    ):
        """
        Procesa un mensaje recibido de RabbitMQ

        Args:
            ch: Canal de RabbitMQ
            method: Método de entrega
            properties: Propiedades del mensaje
            body: Cuerpo del mensaje (bytes)
        """
        transaction_id = None
        try:
            # Decodificar el mensaje JSON
            message_data = json.loads(body.decode("utf-8"))
            transaction_id = message_data.get("transaction_id", "unknown")

            # Print cuando se recibe el mensaje
            logger.info(
                f"Mensaje recibido de RabbitMQ (cola: {self.queue_name}): transaction_id={transaction_id}, "
                f"conversation_id={message_data.get('conversation_id')}"
            )

            # Procesar el mensaje usando el handler
            self.message_handler(message_data)

            # Confirmar que el mensaje fue procesado exitosamente
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Mensaje procesado exitosamente: transaction_id={transaction_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar mensaje JSON: {str(e)}. Body: {body[:200]}")
            # Rechazar el mensaje y no reintentarlo (mensaje malformado)
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as nack_error:
                logger.error(f"Error al rechazar mensaje: {str(nack_error)}")
        except ValueError as e:
            # Errores de validación - no reintentar
            logger.error(f"Error de validación al procesar mensaje {transaction_id}: {str(e)}")
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as nack_error:
                logger.error(f"Error al rechazar mensaje: {str(nack_error)}")
        except Exception as e:
            logger.error(f"Error al procesar mensaje {transaction_id}: {str(e)}", exc_info=True)
            # Rechazar el mensaje y reintentarlo (error transitorio)
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except Exception as nack_error:
                logger.error(f"Error al rechazar mensaje: {str(nack_error)}")
                # Si no podemos rechazar, intentar reconectar
                if self._should_reconnect:
                    self._reconnect()

    def _setup_consumer(self):
        """Configura el consumidor en el canal"""
        if self.channel and not self.channel.is_closed:
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self._process_message,
            )

    def start_consuming(self):
        """Inicia el consumo de mensajes de la cola"""
        self._should_reconnect = True
        try:
            self._connect()
            self._setup_consumer()
            self._consuming = True

            logger.info(f"Esperando mensajes en la cola '{self.queue_name}'. Para salir presiona CTRL+C")

            # Iniciar consumo con manejo de errores
            while self._should_reconnect:
                try:
                    # Verificar que la conexión y el canal estén activos antes de consumir
                    if self._is_connection_closed() or self._is_channel_closed():
                        logger.warning("Conexión o canal cerrado, intentando reconectar...")
                        if self._should_reconnect:
                            self._reconnect()
                            continue
                        else:
                            break

                    self.channel.start_consuming()
                except KeyboardInterrupt:
                    logger.info("Deteniendo consumidor por interrupción del usuario...")
                    self._should_reconnect = False
                    break
                except (AMQPConnectionError, AMQPChannelError, ConnectionResetError, OSError) as e:
                    logger.warning(f"Error de conexión con RabbitMQ: {str(e)}")
                    if self._should_reconnect:
                        self._reconnect()
                    else:
                        raise
                except Exception as e:
                    # Verificar si es un error de conexión
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ["connection", "closed", "broken", "reset"]):
                        logger.warning(f"Error de conexión detectado: {str(e)}")
                        if self._should_reconnect:
                            self._reconnect()
                        else:
                            raise
                    else:
                        logger.error(f"Error inesperado en el consumidor: {str(e)}", exc_info=True)
                        if self._should_reconnect:
                            time.sleep(self.reconnect_delay)
                            # Verificar si necesitamos reconectar
                            if self._is_connection_closed() or self._is_channel_closed():
                                self._reconnect()
                        else:
                            raise

        except KeyboardInterrupt:
            logger.info("Deteniendo consumidor...")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error fatal en el consumidor: {str(e)}", exc_info=True)
            self._consuming = False
            raise

    def stop_consuming(self):
        """Detiene el consumo de mensajes"""
        self._should_reconnect = False
        self._consuming = False
        self._close_connections()
        logger.info("Consumidor detenido")

