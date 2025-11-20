import logging
import threading
import time
from typing import Any

from src.common.enums.transaction_status import TransactionStatus
from src.common.rabbitmq_consumer import RabbitMQConsumer
from src.common.rabbitmq_service import RabbitMQService
from src.configuration.config import get_session
from src.modules.transactions.dtos.transaction import TransactionCreate, TransactionUpdate
from src.modules.transactions.services.transactions_service import TransactionsService
from src.modules.users.entities.user_entity import UserEntity

logger = logging.getLogger(__name__)


class TransferConsumerService:
    """Servicio para procesar mensajes de transferencias desde RabbitMQ"""

    def __init__(self):
        self.consumer_thread = None
        self.consumer = None
        self.rabbitmq_service = RabbitMQService()

    def _validate_message(self, message_data: dict[str, Any]) -> tuple[bool, list[str]]:
        errors = []
        
        # Validar campos requeridos
        required_fields = {
            "transaction_id": str,
            "conversation_id": str,
            "recipient_phone": str,
            "amount": (int, float),
            "user_id": int,
        }
        
        for field, expected_type in required_fields.items():
            if field not in message_data or message_data[field] is None:
                errors.append(f"Campo requerido faltante: {field}")
            elif not isinstance(message_data[field], expected_type):
                errors.append(f"Campo '{field}' tiene tipo incorrecto. Esperado: {expected_type}, Recibido: {type(message_data[field])}")
        
        # Validaciones específicas
        if "amount" in message_data and message_data["amount"] is not None:
            try:
                amount = float(message_data["amount"])
                if amount <= 0:
                    errors.append("El monto debe ser mayor a 0")
            except (ValueError, TypeError):
                errors.append(f"El monto '{message_data['amount']}' no es un número válido")
        
        if "recipient_phone" in message_data and message_data["recipient_phone"] is not None:
            phone = str(message_data["recipient_phone"]).strip()
            if len(phone) == 0 or len(phone) > 32:
                errors.append(f"El número de teléfono debe tener entre 1 y 32 caracteres. Recibido: {len(phone)} caracteres")
        
        if "transaction_id" in message_data and message_data["transaction_id"] is not None:
            tx_id = str(message_data["transaction_id"]).strip()
            if len(tx_id) == 0 or len(tx_id) > 255:
                errors.append(f"El transaction_id debe tener entre 1 y 255 caracteres. Recibido: {len(tx_id)} caracteres")
        
        if "conversation_id" in message_data and message_data["conversation_id"] is not None:
            conv_id = str(message_data["conversation_id"]).strip()
            if len(conv_id) == 0 or len(conv_id) > 255:
                errors.append(f"El conversation_id debe tener entre 1 y 255 caracteres. Recibido: {len(conv_id)} caracteres")
        
        if "user_id" in message_data and message_data["user_id"] is not None:
            user_id = int(message_data["user_id"])
            if user_id <= 0:
                errors.append(f"El user_id debe ser mayor a 0. Recibido: {user_id}")
        
        return len(errors) == 0, errors

    def _process_message(self, message_data: dict[str, Any]):
        transaction_id = message_data.get("transaction_id", "unknown")
        conversation_id = message_data.get("conversation_id", "unknown")
        amount = message_data.get("amount", "N/A")
        user_id = message_data.get("user_id", "N/A")
        
        # Print cuando se inicia el procesamiento
        logger.info(f"Iniciando procesamiento de transferencia: transaction_id={transaction_id}, conversation_id={conversation_id}, amount={amount} {currency}")
        
        db = None
        
        try:
            # Validar el mensaje ANTES de crear la sesión de BD
            is_valid, errors = self._validate_message(message_data)
            if not is_valid:
                error_msg = "; ".join(errors)
                logger.error(
                    f"Validación fallida para transaction_id={transaction_id}: {error_msg}. "
                    f"Mensaje completo: {message_data}"
                )
                raise ValueError(f"Validación fallida: {error_msg}")

            # Preparar datos normalizados antes de crear la sesión
            amount = float(message_data["amount"])
            user_id = message_data.get("user_id")

            # Crear la transacción DTO antes de crear la sesión
            transaction_create = TransactionCreate(
                conversation_id=str(message_data["conversation_id"]).strip(),
                transaction_id=str(message_data["transaction_id"]).strip(),
                recipient_phone=str(message_data["recipient_phone"]).strip(),
                amount=amount,
                status=TransactionStatus.PENDING,
                error_message=None,
            )

            # Intentar crear la transacción con reintentos
            # Cada intento crea una nueva sesión para evitar problemas con sesiones en estado inválido
            max_retries = 3
            user = None
            
            for attempt in range(1, max_retries + 1):
                db = None
                try:
                    # Crear una nueva sesión de base de datos para cada intento
                    db = get_session()
                    
                    # Verificar y descontar saldo del usuario si user_id está presente
                    if user_id:
                        try:
                            # Convertir user_id a int si es string
                            user_id_int = int(user_id) if isinstance(user_id, str) else user_id
                            user = db.query(UserEntity).filter(UserEntity.id == user_id_int).first()
                            
                            if not user:
                                error_msg = f"Usuario con ID {user_id} no encontrado"
                                logger.error(f"Error de validación: {error_msg}")
                                transaction_create.status = TransactionStatus.FAILED
                                transaction_create.error_message = error_msg
                                # Crear la transacción con estado FAILED
                                transactions_service = TransactionsService(db)
                                transaction = transactions_service.create_transaction(transaction_create)
                                db.commit()
                                
                                # Enviar respuesta de error
                                try:
                                    response_data = {
                                        "transaction_id": transaction_id,
                                        "conversation_id": str(conversation_id),
                                        "status": "failed",
                                        "message": f"Error al procesar la transferencia: {error_msg}",
                                        "error_message": error_msg,
                                    }
                                    if user_id:
                                        response_data["user_id"] = user_id
                                    self.rabbitmq_service.send_response(response_data)
                                except Exception as response_error:
                                    logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
                                
                                raise ValueError(error_msg)
                            
                            # Verificar que las monedas coincidan
                            user_currency = user.currency or "COP"
                            if user_currency != currency:
                                error_msg = f"No puedes transferir en {currency}. Tu cuenta está en {user_currency}."
                                logger.error(f"Error de validación: {error_msg}")
                                transaction_create.status = TransactionStatus.FAILED
                                transaction_create.error_message = error_msg
                                transactions_service = TransactionsService(db)
                                transaction = transactions_service.create_transaction(transaction_create)
                                db.commit()
                                
                                # Enviar respuesta de error
                                try:
                                    response_data = {
                                        "transaction_id": transaction_id,
                                        "conversation_id": str(conversation_id),
                                        "status": "failed",
                                        "message": f"Error al procesar la transferencia: {error_msg}",
                                        "error_message": error_msg,
                                    }
                                    if user_id:
                                        response_data["user_id"] = user_id
                                    self.rabbitmq_service.send_response(response_data)
                                except Exception as response_error:
                                    logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
                                
                                raise ValueError(error_msg)
                            
                            # Verificar saldo suficiente (solo validación, no descontar aún)
                            user_balance = user.balance or 0.0
                            if user_balance < amount:
                                error_msg = (
                                    f"Saldo insuficiente. Saldo actual: ${user_balance:,.0f} {user_currency}, "
                                    f"Monto solicitado: ${amount:,.0f} {currency}."
                                )
                                logger.error(f"Error de validación: {error_msg}")
                                transaction_create.status = TransactionStatus.FAILED
                                transaction_create.error_message = error_msg
                                # Crear la transacción con estado FAILED
                                transactions_service = TransactionsService(db)
                                transaction = transactions_service.create_transaction(transaction_create)
                                db.commit()
                                
                                # Enviar respuesta de error
                                try:
                                    response_data = {
                                        "transaction_id": transaction_id,
                                        "conversation_id": str(conversation_id),
                                        "status": "failed",
                                        "message": f"Error al procesar la transferencia: {error_msg}",
                                        "error_message": error_msg,
                                    }
                                    if user_id:
                                        response_data["user_id"] = user_id
                                    self.rabbitmq_service.send_response(response_data)
                                except Exception as response_error:
                                    logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
                                
                                raise ValueError(error_msg)
                            
                        except ValueError:
                            # Re-lanzar errores de validación sin reintentar
                            raise
                        except Exception as user_error:
                            logger.error(f"Error al verificar/descontar saldo: {str(user_error)}", exc_info=True)
                            db.rollback()
                            raise ValueError(f"Error al procesar saldo del usuario: {str(user_error)}")
                    
                    # Crear el servicio de transacciones con la sesión
                    transactions_service = TransactionsService(db)

                    # Guardar la transacción en la base de datos con estado PENDING
                    transaction = transactions_service.create_transaction(transaction_create)
                    
                    # Si hay usuario, restar el balance y actualizar estado a COMPLETED
                    if user_id and user:
                        # Descontar el saldo cuando se complete la transferencia
                        original_balance = user.balance or 0.0
                        user.balance = original_balance - amount
                        db.flush()  # Flush para asegurar que el cambio se refleje antes de commit
                        
                        logger.info(
                            f"Saldo descontado para usuario {user_id}: "
                            f"Saldo anterior: ${original_balance:,.0f}, "
                            f"Monto transferido: ${amount:,.0f}, "
                            f"Nuevo saldo: ${user.balance:,.0f} {user.currency or currency}"
                        )
                        
                        # Actualizar el estado de la transacción a COMPLETED
                        transaction_update = TransactionUpdate(status=TransactionStatus.COMPLETED)
                        updated_transaction = transactions_service.update_transaction(transaction.id, transaction_update)
                        if not updated_transaction:
                            raise ValueError(f"No se pudo actualizar la transacción {transaction.id} a estado COMPLETED")
                        transaction = updated_transaction
                    
                    # Hacer commit de todo (transacción, balance actualizado, estado COMPLETED)
                    db.commit()
                    
                    # Obtener saldo después de la transferencia
                    balance_after = None
                    currency_after = currency
                    if user:
                        balance_after = user.balance
                        currency_after = user.currency or currency
                    
                    # Enviar respuesta de éxito
                    response_data = {
                        "transaction_id": transaction_id,
                        "conversation_id": str(conversation_id),
                        "status": "success",
                        "message": f"¡Transferencia exitosa! Se enviaron ${amount:,.0f} {currency} al {message_data.get('recipient_phone')}.",
                        "balance_after": balance_after,
                        "currency": currency_after,
                    }
                    if user_id:
                        response_data["user_id"] = user_id
                    
                    self.rabbitmq_service.send_response(response_data)
                    
                    # Print cuando se procesa exitosamente
                    print(f"[TransferConsumer] ✅ Transacción procesada y guardada - id={transaction.id}, transaction_id={transaction.transaction_id}, amount={transaction.amount} {transaction.currency}")
                    logger.info(
                        f"Transacción creada exitosamente: id={transaction.id}, "
                        f"transaction_id={transaction.transaction_id}, amount={transaction.amount} {transaction.currency}"
                    )
                    # Éxito, salir del loop de reintentos
                    break
                    
                except ValueError as validation_error:
                    # Errores de validación (saldo insuficiente, etc.) - no reintentar
                    # El saldo ya fue revertido o no se descontó
                    if db:
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        finally:
                            try:
                                db.close()
                            except Exception:
                                pass
                    raise validation_error
                except Exception as db_error:
                    # Si ya descontamos el saldo, revertirlo
                    if db and user_id and user:
                        try:
                            # Recargar el usuario para obtener el balance original
                            db.refresh(user)
                            db.rollback()
                            logger.info(f"Saldo revertido para usuario {user_id} después de error en BD")
                        except Exception as rollback_error:
                            logger.error(f"Error al revertir saldo: {str(rollback_error)}", exc_info=True)
                            try:
                                db.rollback()
                            except Exception:
                                pass
                    
                    # Asegurar rollback en caso de cualquier error de BD
                    if db:
                        try:
                            db.rollback()
                        except Exception as rollback_error:
                            logger.debug(
                                f"Error al hacer rollback (intento {attempt}): {str(rollback_error)}"
                            )
                        finally:
                            try:
                                db.close()
                            except Exception:
                                pass
                    
                    # Si es el último intento, re-lanzar el error
                    if attempt >= max_retries:
                        logger.error(
                            f"Error después de {max_retries} intentos para transaction_id={transaction_id}: {str(db_error)}"
                        )
                        # Intentar crear la transacción con estado FAILED
                        try:
                            db = get_session()
                            transaction_create.status = TransactionStatus.FAILED
                            transaction_create.error_message = f"Error al procesar: {str(db_error)}"
                            transactions_service = TransactionsService(db)
                            transactions_service.create_transaction(transaction_create)
                            db.commit()
                            db.close()
                            
                            # Enviar respuesta de error
                            try:
                                response_data = {
                                    "transaction_id": transaction_id,
                                    "conversation_id": str(conversation_id),
                                    "status": "failed",
                                    "message": f"Error al procesar la transferencia: {str(db_error)}",
                                    "error_message": str(db_error),
                                }
                                if message_data.get("user_id"):
                                    response_data["user_id"] = message_data.get("user_id")
                                self.rabbitmq_service.send_response(response_data)
                            except Exception as response_error:
                                logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
                        except Exception as create_error:
                            logger.error(f"Error al crear transacción fallida: {str(create_error)}")
                        raise db_error
                    
                    # Log del intento fallido
                    logger.warning(
                        f"Intento {attempt}/{max_retries} fallido para transaction_id={transaction_id}: {str(db_error)}. Reintentando..."
                    )
                    # Pequeña espera antes de reintentar
                    time.sleep(0.5 * attempt)  # Backoff simple
                    
                    # Limpiar la referencia a db para el siguiente intento
                    db = None
                    user = None

        except ValueError as e:
            # Errores de validación - no reintentar
            error_message = str(e)
            logger.error(
                f"Error de validación al procesar transferencia transaction_id={transaction_id}: {error_message}"
            )
            logger.debug(f"Datos del mensaje: {message_data}")
            
            # Enviar respuesta de error
            try:
                response_data = {
                    "transaction_id": transaction_id,
                    "conversation_id": str(conversation_id),
                    "status": "failed",
                    "message": f"Error al procesar la transferencia: {error_message}",
                    "error_message": error_message,
                }
                if message_data.get("user_id"):
                    response_data["user_id"] = message_data.get("user_id")
                self.rabbitmq_service.send_response(response_data)
            except Exception as response_error:
                logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
            
            # No hay sesión de BD en este caso, solo re-lanzar
            raise
        except Exception as e:
            # Errores inesperados - pueden reintentarse
            error_message = str(e)
            logger.error(
                f"Error inesperado al procesar transferencia transaction_id={transaction_id}: {error_message}",
                exc_info=True,
            )
            logger.debug(f"Datos del mensaje: {message_data}")
            
            # Enviar respuesta de error solo si es el último intento o error no recuperable
            try:
                response_data = {
                    "transaction_id": transaction_id,
                    "conversation_id": str(conversation_id),
                    "status": "failed",
                    "message": f"Error al procesar la transferencia: {error_message}",
                    "error_message": error_message,
                }
                if message_data.get("user_id"):
                    response_data["user_id"] = message_data.get("user_id")
                self.rabbitmq_service.send_response(response_data)
            except Exception as response_error:
                logger.error(f"Error al enviar respuesta de error: {str(response_error)}")
            
            # Re-lanzar para que el consumidor reintente
            raise
        finally:
            # Cerrar la sesión de forma segura si aún existe
            # (puede que ya se haya cerrado en el loop de reintentos)
            if db:
                try:
                    # Verificar si la sesión está en un estado válido antes de cerrar
                    if hasattr(db, 'is_active') and db.is_active:
                        try:
                            db.rollback()
                        except Exception:
                            pass  # Ignorar errores de rollback al cerrar
                    db.close()
                except Exception as close_error:
                    logger.debug(
                        f"Error al cerrar sesión de BD para transaction_id={transaction_id}: {str(close_error)}"
                    )

    def _run_consumer(self):
        """Ejecuta el consumidor en un thread separado"""
        try:
            self.consumer = RabbitMQConsumer(self._process_message)
            self.consumer.start_consuming()
        except Exception as e:
            logger.error(f"Error en el consumidor de RabbitMQ: {str(e)}", exc_info=True)

    def start(self):
        """Inicia el consumidor en un thread separado"""
        if self.consumer_thread is None or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self._run_consumer, daemon=True)
            self.consumer_thread.start()
            logger.info("Consumidor de RabbitMQ iniciado en thread separado")

    def stop(self):
        """Detiene el consumidor"""
        if self.consumer:
            try:
                self.consumer.stop_consuming()
                logger.info("Consumidor de RabbitMQ detenido")
            except Exception as e:
                logger.error(f"Error al detener consumidor: {str(e)}")

