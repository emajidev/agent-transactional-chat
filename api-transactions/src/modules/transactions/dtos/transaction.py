from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from src.common.enums.transaction_status import TransactionStatus


class TransactionBase(BaseModel):
    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    transaction_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    recipient_phone: str = Field(
        ...,
        min_length=1,
        max_length=32,
    )
    amount: float = Field(
        ...,
        gt=0,
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
    )
    status: TransactionStatus = Field(
        ...,
    )
    error_message: Optional[str] = Field(
        None,
        max_length=255,
    )


class TransactionCreate(TransactionBase):    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_123",
                "transaction_id": "txn_456",
                "recipient_phone": "+1234567890",
                "amount": 150.50,
                "currency": "USD",
                "status": "pending",
                "error_message": None
            }
        }


class TransactionUpdate(BaseModel):
    conversation_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
    )
    transaction_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
    )
    recipient_phone: Optional[str] = Field(
        None,
        min_length=1,
        max_length=32,
    )
    amount: Optional[float] = Field(
        None,
        gt=0,
    )
    currency: Optional[str] = Field(
        None,
        min_length=3,
        max_length=3,
    )
    status: Optional[TransactionStatus] = Field(
        None,
    )
    error_message: Optional[str] = Field(
        None,
        max_length=255,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "error_message": None
            }
        }


class TransactionResponse(TransactionBase):
    id: int = Field(...)
    created_at: datetime = Field(...)
    updated_at: Optional[datetime] = Field(None)
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "conversation_id": "conv_123",
                "transaction_id": "txn_456",
                "recipient_phone": "+1234567890",
                "amount": 150.50,
                "currency": "USD",
                "status": "completed",
                "error_message": None,
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T11:00:00"
            }
        }

