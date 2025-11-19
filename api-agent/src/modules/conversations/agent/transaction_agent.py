import uuid
import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

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

class TransactionAgent:
    def __init__(self, openai_api_key: str | None = None):
        api_key = openai_api_key or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        self.llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=1.0, api_key=api_key)
        self.redis_service = get_redis_service()
        self.graph = self._build_graph()

    @staticmethod
    def _get_last_user_message(messages: list[dict[str, Any]]) -> str | None:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None

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
        last_user_message = self._get_last_user_message(state.get("messages", []))
        confirmation_pending = state.get("confirmation_pending", False)
        
        # Si hay confirmación pendiente, ir a verificar
        if confirmation_pending:
            return "check_confirmation"
        
        # Solo permitir confirmación si tenemos ambos datos válidos
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        
        if recipient_phone and amount and last_user_message:
            # Solo considerar "confirmo" si realmente tenemos datos completos
            if last_user_message.strip().lower() == "confirmo":
                return "check_confirmation"
        
        return "continue"

    def _process_message(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_user_message = self._get_last_user_message(messages)
        
        # Si hay confirmación pendiente, no procesar con LLM
        if state.get("confirmation_pending", False):
            return state

        # Si ya tenemos ambos datos, ir directamente a confirmación
        if state.get("recipient_phone") and state.get("amount"):
            return state

        # Validar si es sobre transferencias
        if last_user_message and not is_transfer_related(last_user_message):
            response = "Solo puedo ayudarte con transferencias de dinero. ¿Te gustaría hacer una transferencia?"
            return {
                "messages": [*messages, {"role": "assistant", "content": response}],
                **{k: v for k, v in state.items() if k != "messages"}
            }

        # Determinar qué información necesitamos
        needs_phone = not state.get("recipient_phone")
        needs_amount = not state.get("amount")
        
        system_prompt = self._get_directed_prompt(needs_phone, needs_amount, state)
        
        # Procesar con LLM
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

        response = self.llm.invoke(conversation_messages)

        return {
            "messages": [*messages, {"role": "assistant", "content": response.content}],
            **{k: v for k, v in state.items() if k != "messages"}
        }

    def _get_directed_prompt(self, needs_phone: bool, needs_amount: bool, state: AgentState) -> str:
        base_prompt = self._get_system_prompt(state)
        
        if needs_phone and not needs_amount:
            return base_prompt + "\n\n[ENFOQUE: Solicitar específicamente el NÚMERO DE TELÉFONO del destinatario (10 dígitos)]"
        elif needs_amount and not needs_phone:
            return base_prompt + "\n\n[ENFOQUE: Solicitar específicamente el MONTO de la transferencia]"
        elif needs_phone and needs_amount:
            return base_prompt + "\n\n[ENFOQUE: Solicitar el NÚMERO DE TELÉFONO primero]"
        else:
            return base_prompt

    def _get_system_prompt(self, state: AgentState) -> str:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        confirmation_pending = state.get("confirmation_pending", False)

        prompt = """Eres un asistente especializado en transferencias de dinero.

REGLAS ESTRICTAS:
1. NUNCA asumas información que no te han proporcionado
2. SOLICITA UN DATO A LA VEZ
3. VERIFICA que tienes ambos datos antes de pedir confirmación
4. ESPERA a que el usuario proporcione cada dato explícitamente

FLUJO OBLIGATORIO:
- Paso 1: Si no tienes teléfono, SOLICITA solo el número (10 dígitos)
- Paso 2: Si tienes teléfono pero no monto, SOLICITA solo el monto
- Paso 3: Solo cuando tengas AMBOS, pide confirmación

NUNCA saltes pasos o asumas datos."""

        if confirmation_pending and recipient_phone and amount:
            prompt += f"\n\n[ESTADO: Esperando confirmación para transferir ${amount:,.0f} COP al {recipient_phone}. Usuario debe escribir 'confirmo']"
        elif recipient_phone and not amount:
            prompt += f"\n[ESTADO: Tengo teléfono {recipient_phone}. NECESITO SOLICITAR EL MONTO]"
        elif amount and not recipient_phone:
            prompt += f"\n[ESTADO: Tengo monto ${amount:,.0f} COP. NECESITO SOLICITAR EL TELÉFONO]"
        elif recipient_phone and amount:
            prompt += f"\n[ESTADO CRÍTICO: Tengo ambos datos. DEBO PEDIR CONFIRMACIÓN explícita]"
        else:
            prompt += "\n[ESTADO: Iniciando conversación. SOLICITAR TELÉFONO del destinatario]"

        return prompt

    def _extract_info(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_user_message = self._get_last_user_message(messages)
        
        if not last_user_message:
            return {}

        updates = {}
        current_phone = state.get("recipient_phone")
        current_amount = state.get("amount")
        
        # Solo extraer teléfono si no lo tenemos
        if not current_phone:
            phone = extract_phone_number(last_user_message)
            if phone:
                is_valid, _ = validate_phone_number(phone)
                if is_valid:
                    updates["recipient_phone"] = phone
                else:
                    # Si extrajeron un teléfono inválido, limpiarlo
                    updates["recipient_phone"] = None

        # Solo extraer monto si no lo tenemos
        if not current_amount:
            amount = extract_amount(last_user_message)
            if amount:
                is_valid, validated_amount, _ = validate_amount(str(amount))
                if is_valid:
                    updates["amount"] = validated_amount
                else:
                    updates["amount"] = None

        return updates

    def _after_extraction(self, state: AgentState) -> str:
        # Solo pasar a confirmación si tenemos ambos datos válidos
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        
        if recipient_phone and amount:
            # Validar que ambos datos son válidos
            is_phone_valid, _ = validate_phone_number(recipient_phone)
            is_amount_valid, _, _ = validate_amount(str(amount))
            
            if is_phone_valid and is_amount_valid:
                return "need_confirmation"
        
        return "continue"

    def _check_confirmation(self, state: AgentState) -> dict[str, Any]:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        confirmation_pending = state.get("confirmation_pending", False)
        
        # Validar que tenemos datos completos antes de pedir confirmación
        if not recipient_phone or not amount:
            return {
                "confirmation_pending": False,
                **state
            }
        
        # Si tenemos datos pero no se ha pedido confirmación, pedirla
        if not confirmation_pending:
            messages = state.get("messages", [])
            
            confirmation_message = (
                f"✅ **Resumen de transferencia:**\n"
                f"• Destinatario: {recipient_phone}\n"
                f"• Monto: ${amount:,.0f} COP\n\n"
                f"Para proceder con la transferencia, escribe exactamente: **CONFIRMO**"
            )
            
            return {
                "messages": [*messages, {"role": "assistant", "content": confirmation_message}],
                "recipient_phone": recipient_phone,
                "amount": amount,
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

            get_rabbitmq_service().send_transfer(transfer_data)
            
            success_message = f"¡Transferencia exitosa! Se enviaron ${amount:,.0f} COP al {recipient_phone}. ID: {transaction_id}"
            
        except Exception:
            success_message = f"Tu solicitud ha sido registrada (ID: {transaction_id}), pero hubo un problema al procesarla."

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
        
        # Log del estado actual para debugging
        print(f"Estado actual: phone={conversation_state.get('recipient_phone')}, "
              f"amount={conversation_state.get('amount')}, "
              f"confirmation_pending={conversation_state.get('confirmation_pending')}")

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