from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from src.common.enums.conversation_status import ConversationStatus


class ConversationBase(BaseModel):
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    started_at: datetime = Field(
        ...,
    )
    ended_at: datetime | None = Field(
        None,
    )
    status: ConversationStatus = Field(
        ...,
    )


class ConversationCreate(BaseModel):
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    status: ConversationStatus = Field(
        default=ConversationStatus.ACTIVE,
    )

    class Config:
        json_schema_extra: ClassVar[dict] = {"example": {"user_id": "user_123", "status": "active"}}


class ConversationUpdate(BaseModel):
    user_id: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    started_at: datetime | None = Field(
        None,
    )
    ended_at: datetime | None = Field(
        None,
    )
    status: ConversationStatus | None = Field(
        None,
    )
    recipient_phone: str | None = Field(
        None,
        description="Número de teléfono del destinatario",
    )
    amount: float | None = Field(
        None,
        description="Monto a transferir",
    )
    currency: str | None = Field(
        None,
        description="Moneda (por defecto COP)",
    )
    confirmation_pending: bool | None = Field(
        None,
        description="Si hay una confirmación pendiente",
    )
    transaction_id: str | None = Field(
        None,
        description="ID de la transacción completada",
    )

    class Config:
        json_schema_extra: ClassVar[dict] = {"example": {"status": "completed", "ended_at": "2024-01-15T11:00:00"}}


class ConversationResponse(ConversationBase):
    id: int = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime | None = Field(None)

    class Config:
        from_attributes = True
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "id": 1,
                "user_id": "user_123",
                "started_at": "2024-01-15T10:30:00",
                "ended_at": None,
                "status": "active",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": None,
            }
        }


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Mensaje del chat")
    conversation_id: int | None = Field(
        None,
        description="ID de la conversación (opcional, se creará una nueva si no se proporciona)",
    )

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {"message": "Hola, ¿cómo puedo ayudarte?", "conversation_id": 1}
        }


class ChatResponse(BaseModel):
    conversation_id: int = Field(..., description="ID de la conversación")
    response: str = Field(..., description="Respuesta del agente")
    status: ConversationStatus = Field(..., description="Estado actual de la conversación")
    state: dict | None = Field(
        None,
        description="Estado de la conversación (teléfono, monto, confirmación pendiente, etc.)",
    )

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "conversation_id": 1,
                "response": "Hola, estoy aquí para ayudarte. ¿En qué puedo asistirte?",
                "status": "active",
                "state": {
                    "recipient_phone": None,
                    "amount": None,
                    "currency": "COP",
                    "confirmation_pending": False,
                    "transaction_id": None,
                },
            }
        }
