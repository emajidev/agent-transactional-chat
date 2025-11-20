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

    is_transfer_related,

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

        # Validar si es sobre transferencias
        if last_user_message and not is_transfer_related(last_user_message):
            response = "Solo puedo ayudarte con transferencias de dinero. ¿Te gustaría hacer una transferencia?"
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

        response = self.llm.invoke(conversation_messages)

        return {
            "messages": [*messages, {"role": "assistant", "content": response.content}],
            **{k: v for k, v in state.items() if k != "messages"}
        }

    def _get_system_prompt(self, state: AgentState) -> str:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        confirmation_pending = state.get("confirmation_pending", False)

        prompt = """Eres un asistente amigable para transferencias de dinero.
                    INSTRUCCIONES:
                    - Sé natural y conversacional
                    - Ayuda con transferencias de dinero
                    - Recopila teléfono (10 dígitos) y monto (positivo)
                    - Solo solicita confirmación cuando tengas AMBOS datos

                    CUANDO TENGAS AMBOS DATOS:
                    - Pide EXPLÍCITAMENTE que escriba "confirmo"
                    - Ejemplo: "Para proceder, escribe CONFIRMO"
                    - No uses otras variaciones"""

        if confirmation_pending and recipient_phone and amount:
            prompt += f"\n\n[Contexto: Esperando que el usuario escriba 'confirmo' para transferir ${amount:,.0f} COP al {recipient_phone}]"
        elif recipient_phone and amount:
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
        conversation_id = state.get("conversation_id")
        user_id = state.get("user_id")
        
        if not last_user_message:
            return {}
        
        extraction_prompt = f"""Analiza el siguiente mensaje del usuario y extrae SOLO los datos que se solicitan.
                                Mensaje: "{last_user_message}"
                                INSTRUCCIONES:
                                - Si el mensaje contiene un número de teléfono (10 dígitos, puede empezar con 0), extráelo en el campo "recipient_phone"
                                - Si el mensaje contiene un monto de dinero (número positivo), extráelo en el campo "amount"
                                - Si no encuentras un dato, usa null para ese campo
                                - El teléfono debe tener exactamente 10 dígitos
                                - El monto debe ser un número positivo
                                Responde ÚNICAMENTE con un JSON válido en este formato:
                                {{
                                    "recipient_phone": "número_de_teléfono_o_null",
                                    "amount": número_o_null
                                }}
                                Ejemplo si el mensaje es "04140220846 enviar 100":
                                {{
                                    "recipient_phone": "04140220846",
                                    "amount": 100
                                }}
                                Ejemplo si el mensaje es "quiero transferir 50000":
                                {{
                                    "recipient_phone": null,
                                    "amount": 50000
                                }}
                                Responde SOLO con el JSON, sin texto adicional."""

        conversation_messages = [
            SystemMessage(content=SPANISH_LANGUAGE_ENFORCEMENT),
            SystemMessage(content=extraction_prompt),
        ]
            
        response = self.llm.invoke(conversation_messages)
        response_content = response.content.strip()
        
        # Limpiar la respuesta si tiene markdown code blocks
        if response_content.startswith("```"):
            # Remover markdown code blocks
            lines = response_content.split('\n')
            response_content = '\n'.join([line for line in lines if not line.startswith('```')])
        
        # Parsear JSON
        extracted_data = json.loads(response_content)
        redis_key = f"conversation:{conversation_id}"
        
        redis_data = {
            "recipient_phone": extracted_data.get("recipient_phone"),
            "amount": extracted_data.get("amount"),
            "conversation_id": conversation_id,
            "user_id": user_id,
        }
        if(extracted_data.get("recipient_phone") is not None and extracted_data.get("amount") is not None):
            self.redis_service.set(redis_key, redis_data)
        return extracted_data

        

    def _after_extraction(self, state: AgentState) -> str:
        if state.get("recipient_phone") and state.get("amount"):
            return "need_confirmation"
        return "continue"

    def _check_confirmation(self, state: AgentState) -> dict[str, Any]:
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

                response = self.llm.invoke(conversation_messages)
                
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
                "conversation_id": state.get("conversation_id"),
                "user_id": state.get("user_id"),
            }
            
            if state.get("conversation_id"):
                transfer_data["conversation_id"] = str(state.get("conversation_id"))
            if state.get("user_id"):
                transfer_data["user_id"] = state.get("user_id")

            get_rabbitmq_service().send_transfer(transfer_data)
                        # No mostrar éxito inmediatamente - el resultado real vendrá en la respuesta asíncrona
            success_message = f"Tu solicitud de transferencia de ${amount:,.0f} COP al {recipient_phone} está siendo procesada. ID: {transaction_id}. Te notificaré cuando se complete."
            
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
                "user_id": final_state.get("user_id"),
                "conversation_id": final_state.get("conversation_id"),
                "messages": messages[-10:],
            },
        }