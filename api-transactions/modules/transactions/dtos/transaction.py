from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from common.enums.transaction_type import TransactionType


class TransactionBase(BaseModel):
    """Schema base para transacciones."""
    description: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Descripción de la transacción",
        example="Compra en supermercado"
    )
    amount: float = Field(
        ...,
        gt=0,
        description="Monto de la transacción (debe ser mayor a 0)",
        example=150.50
    )
    transaction_type: TransactionType = Field(
        ...,
        description="Tipo de transacción (income o expense)"
    )


class TransactionCreate(TransactionBase):
    """Schema para crear una transacción."""
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Compra en supermercado",
                "amount": 150.50,
                "transaction_type": "expense"
            }
        }


class TransactionUpdate(BaseModel):
    """Schema para actualizar una transacción."""
    description: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Descripción de la transacción",
        example="Compra en supermercado"
    )
    amount: Optional[float] = Field(
        None,
        gt=0,
        description="Monto de la transacción (debe ser mayor a 0)",
        example=200.00
    )
    transaction_type: Optional[TransactionType] = Field(
        None,
        description="Tipo de transacción (income o expense)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Venta de productos",
                "amount": 500.00,
                "transaction_type": "income"
            }
        }


class TransactionResponse(TransactionBase):
    """Schema de respuesta para transacciones."""
    id: int = Field(..., description="ID único de la transacción", example=1)
    created_at: datetime = Field(..., description="Fecha y hora de creación", example="2024-01-15T10:30:00")
    updated_at: Optional[datetime] = Field(None, description="Fecha y hora de última actualización", example="2024-01-15T11:00:00")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "description": "Compra en supermercado",
                "amount": 150.50,
                "transaction_type": "expense",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T11:00:00"
            }
        }

