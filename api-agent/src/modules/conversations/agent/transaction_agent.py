import logging
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from openai import PermissionDeniedError, RateLimitError
from sqlalchemy.orm import Session

from src.configuration.config import settings
from src.common.rabbitmq_service import get_rabbitmq_service
from src.common.redis_service import get_redis_service
from src.modules.conversations.agent.agent_state import AgentState
from src.modules.conversations.utils.validators import (
    extract_amount,
    extract_phone_number,
    is_transfer_related,
    validate_amount,
    validate_phone_number,
)

SPANISH_LANGUAGE_ENFORCEMENT = "Responde EXCLUSIVAMENTE en ESPAÑOL."
DENY_WORDS = ["no", "cancelar", "cancel", "nope"]

logger = logging.getLogger(__name__)

class TransactionAgent:
    def __init__(self, openai_api_key: str | None = None, db: Session | None = None):
        api_key = openai_api_key or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        # Configurar parámetros del LLM
        llm_kwargs = {
            "model": settings.OPENAI_MODEL,
            "temperature": 1.0,
            "api_key": api_key,
        }
        
        # Si hay una URL base configurada (para proxy o servicios compatibles), usarla
        if settings.OPENAI_BASE_URL:
            llm_kwargs["base_url"] = settings.OPENAI_BASE_URL

        self.llm = ChatOpenAI(**llm_kwargs)
        self.redis_service = get_redis_service()
        self.db = db
        self.graph = self._build_graph()

    @staticmethod
    def _get_last_user_message(messages: list[dict[str, Any]]) -> str | None:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None

    def _get_user_balance(self, user_id: str | None) -> tuple[float | None, str]:
        """Obtiene el saldo y moneda del usuario desde la base de datos."""
        if not self.db or not user_id:
            return None, "COP"
        
        try:
            from src.modules.auth.entities.user_entity import UserEntity
            
            # Convertir user_id a int si es string
            user_id_int = int(user_id) if isinstance(user_id, str) else user_id
            user = self.db.query(UserEntity).filter(UserEntity.id == user_id_int).first()
            
            if user:
                balance = user.balance if user.balance is not None else 0.0
                currency = user.currency if user.currency else "COP"
                return balance, currency
        except Exception as e:
            logger.error(f"Error al obtener saldo del usuario {user_id}: {str(e)}", exc_info=True)
        
        return None, "COP"

    @staticmethod
    def _is_balance_query(message: str) -> bool:
        """Verifica si el mensaje es una consulta de saldo."""
        if not message:
            return False
        
        message_lower = message.lower().strip()
        
        # Palabras clave para consulta de saldo
        balance_keywords = [
            "saldo",
            "balance",
            "cuánto tengo",
            "cuanto tengo",
            "cuánto dinero tengo",
            "cuanto dinero tengo",
            "cuánto tengo disponible",
            "cuanto tengo disponible",
            "mi saldo",
            "ver saldo",
            "consultar saldo",
            "cuánto es mi saldo",
            "cuanto es mi saldo",
            "dime mi saldo",
            "muéstrame mi saldo",
            "muestrame mi saldo",
            "quiero saber mi saldo",
            "cuánto tengo en mi cuenta",
            "cuanto tengo en mi cuenta",
        ]
        
        return any(keyword in message_lower for keyword in balance_keywords)

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("process_message", self._process_message)
        workflow.add_node("extract_info", self._extract_info)
        workflow.add_node("check_confirmation", self._check_confirmation)
        workflow.add_node("execute_transaction", self._execute_transaction)

        workflow.set_entry_point("process_message")

        workflow.add_conditional_edges(
            "process_message",
            self._should_check_confirmation,
            {"check_confirmation": "check_confirmation", "continue": "extract_info"},
        )
        
        workflow.add_conditional_edges(
            "check_confirmation",
            self._is_confirmed,
            {"yes": "execute_transaction", "no": END, "waiting": END},
        )
        
        workflow.add_conditional_edges(
            "extract_info",
            self._after_extraction,
            {"need_confirmation": "check_confirmation", "continue": END},
        )
        
        workflow.add_edge("execute_transaction", END)

        return workflow.compile()

    def _should_check_confirmation(self, state: AgentState) -> str:
        confirmation_pending = state.get("confirmation_pending", False)
        last_user_message = self._get_last_user_message(state.get("messages", []))
        
        if confirmation_pending:
            return "check_confirmation"
        
        if state.get("recipient_phone") and state.get("amount") and last_user_message:
            if last_user_message.strip().lower() == "confirmo":
                return "check_confirmation"
        
        return "continue"

    def _process_message(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_user_message = self._get_last_user_message(messages)
        
        # Si hay confirmación pendiente, no procesar con LLM
        if state.get("confirmation_pending", False):
            return state

        # Verificar si es una consulta de saldo
        if last_user_message and self._is_balance_query(last_user_message):
            user_id = state.get("user_id")
            balance, currency = self._get_user_balance(user_id)
            
            if balance is not None:
                response = f"Tu saldo actual es ${balance:,.0f} {currency}."
            else:
                response = "No pude obtener tu saldo en este momento. Por favor, intenta más tarde."
            
            return {
                "messages": [*messages, {"role": "assistant", "content": response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }

        # Validar si es sobre transferencias
        if last_user_message and not is_transfer_related(last_user_message):
            response = "Solo puedo ayudarte con transferencias de dinero y consultas de saldo. ¿Te gustaría hacer una transferencia o consultar tu saldo?"
            return {
                "messages": [*messages, {"role": "assistant", "content": response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }

        # Procesar con LLM
        system_prompt = self._get_system_prompt(state)
        conversation_messages = [
            SystemMessage(content=SPANISH_LANGUAGE_ENFORCEMENT),
            SystemMessage(content=system_prompt),
        ]

        for msg in messages[-10:]:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                conversation_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                conversation_messages.append(AIMessage(content=content))

        try:
            response = self.llm.invoke(conversation_messages)
        except RateLimitError as e:
            error_msg = str(e)
            logger.error(f"Rate limit de OpenAI alcanzado: {error_msg}")
            error_response = (
                "Lo siento, el servicio de IA está temporalmente sobrecargado debido a muchas solicitudes. "
                "Por favor, espera unos minutos e intenta de nuevo. "
                "Mientras tanto, puedes consultar tu saldo escribiendo 'saldo' o 'cuánto tengo'."
            )
            return {
                "messages": [*messages, {"role": "assistant", "content": error_response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }
        except PermissionDeniedError as e:
            error_msg = str(e)
            if "unsupported_country_region_territory" in error_msg or "Country, region, or territory not supported" in error_msg:
                logger.error("OpenAI no está disponible en esta región. Configura OPENAI_BASE_URL con un proxy o servicio compatible.")
                error_response = (
                    "Lo siento, hay un problema de configuración con el servicio de IA. "
                    "Por favor, contacta al administrador del sistema."
                )
            else:
                logger.error(f"Error de permisos de OpenAI: {error_msg}")
                error_response = "Lo siento, hubo un error al procesar tu mensaje. Por favor, intenta de nuevo."
            
            return {
                "messages": [*messages, {"role": "assistant", "content": error_response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }
        except Exception as e:
            logger.error(f"Error al invocar LLM: {str(e)}", exc_info=True)
            error_response = "Lo siento, hubo un error al procesar tu mensaje. Por favor, intenta de nuevo."
            return {
                "messages": [*messages, {"role": "assistant", "content": error_response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }

        return {
            "messages": [*messages, {"role": "assistant", "content": response.content}],
            **{k: v for k, v in state.items() if k != "messages"}
        }

    def _get_system_prompt(self, state: AgentState) -> str:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        confirmation_pending = state.get("confirmation_pending", False)
        
        # Obtener saldo del usuario
        user_id = state.get("user_id")
        balance, currency = self._get_user_balance(user_id)
        balance_info = ""
        if balance is not None:
            balance_info = f"Tu saldo actual es ${balance:,.0f} {currency}."

        prompt = """Eres un asistente amigable para transferencias de dinero y consultas de saldo.

INSTRUCCIONES:
- Sé natural y conversacional
- Ayuda con transferencias de dinero
- También puedes ayudar a los usuarios a consultar su saldo cuando lo soliciten
- Recopila teléfono (10 dígitos) y monto (positivo) para transferencias
- Solo solicita confirmación cuando tengas AMBOS datos (teléfono y monto)
- SIEMPRE menciona el saldo actual del usuario cuando tengas ambos datos (teléfono y monto)

CONSULTAS DE SALDO:
- Si el usuario pregunta por su saldo, el sistema lo mostrará automáticamente
- Puedes mencionar que pueden consultar su saldo en cualquier momento

CUANDO TENGAS AMBOS DATOS PARA TRANSFERENCIA:
- Menciona el saldo actual del usuario
- Pide EXPLÍCITAMENTE que escriba "confirmo"
- Ejemplo: "Tu saldo actual es $X. Para transferir $Y al teléfono Z, escribe CONFIRMO"
- No uses otras variaciones"""

        if confirmation_pending and recipient_phone and amount:
            if balance_info:
                prompt += f"\n\n[Contexto: {balance_info} Esperando que el usuario escriba 'confirmo' para transferir ${amount:,.0f} {currency} al {recipient_phone}]"
            else:
                prompt += f"\n\n[Contexto: Esperando que el usuario escriba 'confirmo' para transferir ${amount:,.0f} COP al {recipient_phone}]"
        elif recipient_phone and amount:
            if balance_info:
                prompt += f"\n\n[Contexto CRÍTICO: {balance_info} Tienes teléfono {recipient_phone} y monto ${amount:,.0f} {currency}. DEBES mencionar el saldo y pedir confirmación explícita]"
            else:
                prompt += f"\n\n[Contexto CRÍTICO: Tienes teléfono {recipient_phone} y monto ${amount:,.0f} COP. DEBES pedir confirmación explícita]"
        elif recipient_phone:
            prompt += f"\n[Contexto: Tienes teléfono {recipient_phone}. Necesitas el monto]"
        elif amount:
            prompt += f"\n[Contexto: Tienes monto ${amount:,.0f} COP. Necesitas el teléfono]"
        else:
            prompt += "\n[Contexto: Saluda amablemente y pregunta cómo puedes ayudar con transferencias]"

        return prompt

    def _extract_info(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_user_message = self._get_last_user_message(messages)
        
        if not last_user_message:
            return {}

        updates = {}
        
        # Extraer teléfono
        if not state.get("recipient_phone"):
            phone = extract_phone_number(last_user_message)
            if phone:
                updates["recipient_phone"] = phone

        # Extraer monto
        if not state.get("amount"):
            amount = extract_amount(last_user_message)
            if amount:
                updates["amount"] = amount

        # Validar datos extraídos
        if updates.get("recipient_phone"):
            is_valid, _ = validate_phone_number(updates["recipient_phone"])
            if not is_valid:
                updates["recipient_phone"] = None

        if updates.get("amount"):
            is_valid, validated_amount, _ = validate_amount(str(updates["amount"]))
            if is_valid:
                updates["amount"] = validated_amount
            else:
                updates["amount"] = None

        return updates

    def _after_extraction(self, state: AgentState) -> str:
        if state.get("recipient_phone") and state.get("amount"):
            return "need_confirmation"
        return "continue"

    def _check_confirmation(self, state: AgentState) -> dict[str, Any]:
        # Si tenemos datos pero no se ha pedido confirmación, pedirla
        if state.get("recipient_phone") and state.get("amount") and not state.get("confirmation_pending"):
            messages = state.get("messages", [])
            last_assistant_message = None
            
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    last_assistant_message = msg.get("content", "")
                    break
            
            if not last_assistant_message or "confirmo" not in last_assistant_message.lower():
                system_prompt = self._get_system_prompt(state)
                conversation_messages = [
                    SystemMessage(content=SPANISH_LANGUAGE_ENFORCEMENT),
                    SystemMessage(content=system_prompt),
                ]

                for msg in messages[-10:]:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role == "user":
                        conversation_messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        conversation_messages.append(AIMessage(content=content))

                try:
                    response = self.llm.invoke(conversation_messages)
                except RateLimitError as e:
                    error_msg = str(e)
                    logger.error(f"Rate limit de OpenAI alcanzado: {error_msg}")
                    error_response = (
                        "Lo siento, el servicio de IA está temporalmente sobrecargado debido a muchas solicitudes. "
                        "Por favor, espera unos minutos e intenta de nuevo. "
                        "Mientras tanto, puedes consultar tu saldo escribiendo 'saldo' o 'cuánto tengo'."
                    )
                    return {
                        "messages": [*messages, {"role": "assistant", "content": error_response}],
                        "recipient_phone": state.get("recipient_phone"),
                        "amount": state.get("amount"),
                        "confirmation_pending": False,
                        "currency": state.get("currency", "COP"),
                        "transaction_id": state.get("transaction_id"),
                        "user_id": state.get("user_id"),
                        "conversation_id": state.get("conversation_id"),
                    }
                except PermissionDeniedError as e:
                    error_msg = str(e)
                    if "unsupported_country_region_territory" in error_msg or "Country, region, or territory not supported" in error_msg:
                        logger.error("OpenAI no está disponible en esta región. Configura OPENAI_BASE_URL con un proxy o servicio compatible.")
                        error_response = (
                            "Lo siento, hay un problema de configuración con el servicio de IA. "
                            "Por favor, contacta al administrador del sistema."
                        )
                    else:
                        logger.error(f"Error de permisos de OpenAI: {error_msg}")
                        error_response = "Lo siento, hubo un error al procesar tu mensaje. Por favor, intenta de nuevo."
                    
                    return {
                        "messages": [*messages, {"role": "assistant", "content": error_response}],
                        "recipient_phone": state.get("recipient_phone"),
                        "amount": state.get("amount"),
                        "confirmation_pending": False,
                        "currency": state.get("currency", "COP"),
                        "transaction_id": state.get("transaction_id"),
                        "user_id": state.get("user_id"),
                        "conversation_id": state.get("conversation_id"),
                    }
                except Exception as e:
                    logger.error(f"Error al invocar LLM: {str(e)}", exc_info=True)
                    error_response = "Lo siento, hubo un error al procesar tu mensaje. Por favor, intenta de nuevo."
                    return {
                        "messages": [*messages, {"role": "assistant", "content": error_response}],
                        "recipient_phone": state.get("recipient_phone"),
                        "amount": state.get("amount"),
                        "confirmation_pending": False,
                        "currency": state.get("currency", "COP"),
                        "transaction_id": state.get("transaction_id"),
                        "user_id": state.get("user_id"),
                        "conversation_id": state.get("conversation_id"),
                    }
                
                return {
                    "messages": [*messages, {"role": "assistant", "content": response.content}],
                    "recipient_phone": state.get("recipient_phone"),
                    "amount": state.get("amount"),
                    "confirmation_pending": True,
                    "currency": state.get("currency", "COP"),
                    "transaction_id": state.get("transaction_id"),
                    "user_id": state.get("user_id"),
                    "conversation_id": state.get("conversation_id"),
                }
        
        return state

    def _is_confirmed(self, state: AgentState) -> str:
        last_user_message = self._get_last_user_message(state.get("messages", []))
        
        if not last_user_message:
            return "waiting"

        cleaned_message = last_user_message.strip().lower()

        if cleaned_message == "confirmo":
            return "yes"
        
        if any(word in cleaned_message for word in DENY_WORDS):
            return "no"

        return "waiting"

    def _execute_transaction(self, state: AgentState) -> dict[str, Any]:
        print(f"[_execute_transaction] Ejecutando transferencia")
        transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        messages = state.get("messages", [])

        if not recipient_phone or not amount:
            error_message = "Necesito tanto el número de teléfono como el monto para ejecutar la transferencia."
            return {
                "messages": [*messages, {"role": "assistant", "content": error_message}],
                "confirmation_pending": False,
                **{k: v for k, v in state.items() if k not in ["messages", "confirmation_pending"]}
            }

        # Obtener saldo actual antes de la transferencia
        user_id = state.get("user_id")
        balance_before, currency = self._get_user_balance(user_id)
        
        # Enviar a RabbitMQ
        try:
            transfer_data = {
                "transaction_id": transaction_id,
                "recipient_phone": recipient_phone,
                "amount": amount,
                "currency": state.get("currency", "COP"),
            }
            
            if state.get("conversation_id"):
                transfer_data["conversation_id"] = str(state.get("conversation_id"))
            if state.get("user_id"):
                transfer_data["user_id"] = state.get("user_id")

            print(f"Enviando transferencia a RabbitMQ: {transfer_data}")
            get_rabbitmq_service().send_transfer(transfer_data)
            
            # Mensaje temporal mientras se procesa la transferencia
            # El mensaje real llegará a través de RabbitMQ cuando se procese
            success_message = (
                f"Tu solicitud de transferencia ha sido enviada (ID: {transaction_id}). "
                f"Procesando transferencia de ${amount:,.0f} {currency} al {recipient_phone}..."
            )
            
        except Exception:
            success_message = f"Tu solicitud ha sido registrada (ID: {transaction_id}), pero hubo un problema al enviarla."

        return {
            "messages": [*messages, {"role": "assistant", "content": success_message}],
            "recipient_phone": None,
            "amount": None,
            "confirmation_pending": False,
            "transaction_id": transaction_id,
            "user_id": state.get("user_id"),
            "conversation_id": state.get("conversation_id"),
        }

    def process(
        self, user_message: str, conversation_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        conversation_state = conversation_state or {}

        initial_state: AgentState = {
            "messages": [
                *conversation_state.get("messages", []),
                {"role": "user", "content": user_message},
            ],
            "recipient_phone": conversation_state.get("recipient_phone"),
            "amount": conversation_state.get("amount"),
            "currency": conversation_state.get("currency", "COP"),
            "confirmation_pending": conversation_state.get("confirmation_pending", False),
            "transaction_id": conversation_state.get("transaction_id"),
            "user_id": conversation_state.get("user_id"),
            "conversation_id": conversation_state.get("conversation_id"),
        }

        final_state = self.graph.invoke(initial_state)
        messages = final_state.get("messages", [])

        # Obtener el último mensaje del asistente
        last_assistant_message = None
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_assistant_message = msg.get("content", "")
                break

        return {
            "response": last_assistant_message or "Lo siento, no pude procesar tu mensaje.",
            "state": {
                "recipient_phone": final_state.get("recipient_phone"),
                "amount": final_state.get("amount"),
                "currency": final_state.get("currency", "COP"),
                "confirmation_pending": final_state.get("confirmation_pending", False),
                "transaction_id": final_state.get("transaction_id"),
                "messages": messages[-10:],
            },
        }