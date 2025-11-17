import os
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.configuration.config import settings
from src.modules.conversations.agent.agent_state import AgentState
from src.modules.conversations.utils.validators import (
    extract_amount,
    extract_phone_number,
    is_transfer_related,
    validate_amount,
    validate_phone_number,
)


class TransactionAgent:
    def __init__(self, openai_api_key: str | None = None):
        api_key = openai_api_key or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured. Set it in environment variables.")

        self.llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=1.0, api_key=api_key)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("process_message", self._process_message)
        workflow.add_node("extract_info", self._extract_info)
        workflow.add_node("validate_info", self._validate_info)
        workflow.add_node("request_confirmation", self._request_confirmation)
        workflow.add_node("execute_transaction", self._execute_transaction)
        workflow.add_node("handle_error", self._handle_error)

        workflow.set_entry_point("process_message")

        workflow.add_edge("process_message", "extract_info")
        workflow.add_edge("extract_info", "validate_info")
        workflow.add_conditional_edges(
            "validate_info",
            self._should_request_confirmation,
            {"confirm": "request_confirmation", "error": "handle_error", "continue": END},
        )
        workflow.add_conditional_edges(
            "request_confirmation",
            self._is_confirmed,
            {"yes": "execute_transaction", "no": END, "waiting": END},
        )
        workflow.add_edge("execute_transaction", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _process_message(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        
        # Obtener el último mensaje del usuario
        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        # Validar si el mensaje está relacionado con transferencias de dinero
        # Pasamos el contexto de la conversación para ser más flexible con preguntas de seguimiento
        if last_user_message and not is_transfer_related(last_user_message, conversation_context=messages):
            # Si no está relacionado, responder que solo puede ayudar con transferencias
            out_of_context_response = (
                "Lo siento, solo puedo ayudarte con transferencias de dinero. "
                "Puedo ayudarte a enviar dinero a otro número de teléfono. "
                "¿Te gustaría hacer una transferencia?"
            )
            new_messages = [*messages, {"role": "assistant", "content": out_of_context_response}]
            return {"messages": new_messages, "error": None}

        system_prompt = self._get_system_prompt(state)
        conversation_messages = [SystemMessage(content=system_prompt)]

        # Incluir todo el historial disponible para máximo contexto (hasta 20 mensajes)
        # Esto permite que el LLM vea toda la conversación y responda de manera más contextual
        for msg in messages[-20:]:
            if msg.get("role") == "user":
                conversation_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                conversation_messages.append(AIMessage(content=msg.get("content", "")))

        response = self.llm.invoke(conversation_messages)

        new_messages = [*messages, {"role": "assistant", "content": response.content}]

        return {"messages": new_messages, "error": None}

    def _get_system_prompt(self, state: AgentState) -> str:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        confirmation_pending = state.get("confirmation_pending", False)
        messages = state.get("messages", [])

        # Determinar el contexto de la conversación
        user_messages = [m for m in messages if m.get("role") == "user"]
        is_first_message = len(user_messages) <= 1
        conversation_length = len(messages)

        prompt = """You are a friendly, warm, and natural conversational assistant specialized in helping users with money transfers.
                    
                    CRITICAL INSTRUCTIONS:
                    - Be EXTREMELY natural and conversational. Write as if you're talking to a friend.
                    - NEVER repeat the same phrases or responses. Always vary your wording significantly.
                    - Use detailed, expressive language. Be descriptive and engaging.
                    - Read the full conversation history and respond contextually to what the user actually said.
                    - Adapt your tone and style based on the conversation flow.
                    - If the user asks about unrelated topics (science, history, etc.), politely redirect to money transfers.
                    - Be flexible with questions about the transfer process, steps, or instructions.
                    
                    Your role is to help users transfer money. You need to collect:
                    - Recipient's phone number (10 digits)
                    - Amount to transfer (must be positive)
                    - User confirmation before executing
                    
                    Be natural, detailed, and engaging in every response. Show personality and warmth.
                    Never use robotic or repetitive language. Always respond as a real person would."""

        # Agregar contexto del estado de manera muy sutil y natural
        if confirmation_pending:
            prompt += f"\n\n[Context: You have phone {recipient_phone} and amount ${amount:,.0f} COP. Waiting for confirmation.]"
        elif recipient_phone and amount:
            prompt += f"\n[Context: Phone {recipient_phone} and ${amount:,.0f} COP collected.]"
        elif recipient_phone:
            prompt += f"\n[Context: Phone {recipient_phone} collected. Need amount.]"
        else:
            if is_first_message:
                prompt += "\n[Context: First message. Start naturally.]"
            else:
                prompt += "\n[Context: Need to collect phone number. Continue conversation naturally.]"

        return prompt

    def _extract_info(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {}

        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        if not last_user_message:
            return {}

        updates = {}

        if not state.get("recipient_phone"):
            phone = extract_phone_number(last_user_message)
            if phone:
                updates["recipient_phone"] = phone

        if not state.get("amount"):
            amount = extract_amount(last_user_message)
            if amount:
                updates["amount"] = amount

        return updates

    def _validate_info(self, state: AgentState) -> dict[str, Any]:
        recipient_phone = state.get("recipient_phone")
        amount = state.get("amount")
        updates = {}
        error = None

        if recipient_phone:
            is_valid, error_msg = validate_phone_number(recipient_phone)
            if not is_valid:
                error = error_msg
                updates["recipient_phone"] = None

        if amount:
            is_valid, validated_amount, error_msg = validate_amount(str(amount))
            if not is_valid:
                error = error_msg
                updates["amount"] = None
            else:
                updates["amount"] = validated_amount

        if error:
            updates["error"] = error
            return updates

        if recipient_phone and amount:
            updates["confirmation_pending"] = True

        return updates

    def _should_request_confirmation(self, state: AgentState) -> str:
        if state.get("error"):
            return "error"

        if (
            state.get("confirmation_pending")
            and state.get("recipient_phone")
            and state.get("amount")
        ):
            return "confirm"

        return "continue"

    def _request_confirmation(self, _state: AgentState) -> dict[str, Any]:
        return {"confirmation_pending": True}

    def _is_confirmed(self, state: AgentState) -> str:
        messages = state.get("messages", [])
        confirmation_pending = state.get("confirmation_pending", False)

        if not confirmation_pending:
            return "continue"

        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "").lower()
                break

        if not last_user_message:
            return "waiting"

        confirm_words = [
            "sí",
            "si",
            "yes",
            "confirmo",
            "confirmar",
            "correcto",
            "ok",
            "okay",
            "de acuerdo",
            "confirm",
        ]
        deny_words = ["no", "cancelar", "cancel", "nope"]

        if any(word in last_user_message for word in confirm_words):
            return "yes"
        elif any(word in last_user_message for word in deny_words):
            return "no"

        return "waiting"

    def _execute_transaction(self, state: AgentState) -> dict[str, Any]:
        transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

        messages = state.get("messages", [])
        success_message = (
            f"Transaction completed successfully. Your transaction ID is: {transaction_id}"
        )

        return {
            "messages": [*messages, {"role": "assistant", "content": success_message}],
            "transaction_id": transaction_id,
            "confirmation_pending": False,
        }

    def _handle_error(self, state: AgentState) -> dict[str, Any]:
        error = state.get("error", "An error occurred")
        messages = state.get("messages", [])

        error_message = f"Sorry, {error.lower()}. Please try again."

        return {
            "messages": [*messages, {"role": "assistant", "content": error_message}],
            "error": None,
        }

    def process(
        self, user_message: str, conversation_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if conversation_state is None:
            conversation_state = {}

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
            "error": None,
        }

        final_state = self.graph.invoke(initial_state)

        messages = final_state.get("messages", [])
        last_assistant_message = None
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_assistant_message = msg.get("content", "")
                break

        return {
            "response": last_assistant_message or "Sorry, I couldn't process your message.",
            "state": {
                "recipient_phone": final_state.get("recipient_phone"),
                "amount": final_state.get("amount"),
                "currency": final_state.get("currency", "COP"),
                "confirmation_pending": final_state.get("confirmation_pending", False),
                "transaction_id": final_state.get("transaction_id"),
                "messages": messages[-10:],
            },
        }
