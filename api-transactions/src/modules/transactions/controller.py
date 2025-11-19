from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from src.common.repositories import get_db
from src.modules.transactions.services.transactions_service import TransactionsService
from src.modules.transactions.dtos.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva transacción",
    description="Crea una nueva transacción financiera. El monto debe ser mayor a 0 y la descripción es obligatoria.",
    responses={
        201: {
            "description": "Transacción creada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "description": "Compra en supermercado",
                        "amount": 150.50,
                        "transaction_type": "expense",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": None
                    }
                }
            }
        },
        422: {"description": "Error de validación de datos"}
    }
)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    """
    Crear una nueva transacción.
    
    - **description**: Descripción de la transacción (requerido, 1-255 caracteres)
    - **amount**: Monto de la transacción (requerido, debe ser mayor a 0)
    - **transaction_type**: Tipo de transacción - 'income' o 'expense' (requerido)
    """
    service = TransactionsService(db)
    return service.create_transaction(transaction)


@router.get(
    "/",
    response_model=List[TransactionResponse],
    summary="Obtener todas las transacciones",
    description="Obtiene una lista paginada de todas las transacciones. Utiliza los parámetros 'skip' y 'limit' para la paginación.",
    responses={
        200: {
            "description": "Lista de transacciones obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "description": "Compra en supermercado",
                            "amount": 150.50,
                            "transaction_type": "expense",
                            "created_at": "2024-01-15T10:30:00",
                            "updated_at": None
                        }
                    ]
                }
            }
        }
    }
)
def get_transactions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtener todas las transacciones con paginación.
    
    - **skip**: Número de registros a saltar (para paginación)
    - **limit**: Número máximo de registros a retornar (máximo 100)
    """
    service = TransactionsService(db)
    return service.get_transactions(skip=skip, limit=limit)


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Obtener una transacción por ID",
    description="Obtiene los detalles de una transacción específica mediante su ID.",
    responses={
        200: {
            "description": "Transacción encontrada",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "description": "Compra en supermercado",
                        "amount": 150.50,
                        "transaction_type": "expense",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": None
                    }
                }
            }
        },
        404: {"description": "Transacción no encontrada"}
    }
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener una transacción específica por su ID.
    
    - **transaction_id**: ID único de la transacción a buscar
    """
    service = TransactionsService(db)
    transaction = service.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción con ID {transaction_id} no encontrada"
        )
    return transaction


@router.put(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Actualizar una transacción",
    description="Actualiza una transacción existente. Todos los campos son opcionales, solo se actualizarán los campos proporcionados.",
    responses={
        200: {
            "description": "Transacción actualizada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "description": "Venta de productos",
                        "amount": 500.00,
                        "transaction_type": "income",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": "2024-01-15T11:00:00"
                    }
                }
            }
        },
        404: {"description": "Transacción no encontrada"},
        422: {"description": "Error de validación de datos"}
    }
)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar una transacción existente.
    
    - **transaction_id**: ID único de la transacción a actualizar
    - **description**: Nueva descripción (opcional)
    - **amount**: Nuevo monto (opcional, debe ser mayor a 0)
    - **transaction_type**: Nuevo tipo de transacción (opcional)
    """
    service = TransactionsService(db)
    updated_transaction = service.update_transaction(transaction_id, transaction)
    if not updated_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción con ID {transaction_id} no encontrada"
        )
    return updated_transaction


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una transacción",
    description="Elimina una transacción existente. Esta operación no se puede deshacer.",
    responses={
        204: {"description": "Transacción eliminada exitosamente"},
        404: {"description": "Transacción no encontrada"}
    }
)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar una transacción.
    
    - **transaction_id**: ID único de la transacción a eliminar
    
    **Nota**: Esta operación es permanente y no se puede deshacer.
    """
    service = TransactionsService(db)
    success = service.delete_transaction(transaction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción con ID {transaction_id} no encontrada"
        )
    return None

