from typing import Optional, Dict, Any, List
from src.common.repositories import BaseRepository
from src.common.resilience import retry_db_operation
from src.modules.transactions.entities import Transaction
from src.modules.transactions.dtos.transaction import TransactionCreate, TransactionUpdate
from src.common.enums.transaction_status import TransactionStatus


class TransactionRepository(BaseRepository[Transaction]):
    
    model = Transaction
    
    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        # El filtrado por deleted_at se hace automáticamente en _build_query
        return (
            self.session.query(Transaction)
            .filter(Transaction.id == transaction_id)
            .filter(Transaction.deleted_at.is_(None))
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Transaction]:
        # El filtrado por deleted_at se hace automáticamente en _build_query del BaseRepository
        return super().get_all(skip=skip, limit=limit, filters=filters)

    def create(self, transaction_data: TransactionCreate) -> Transaction:
        # Convertir el enum a su valor antes de crear la entidad
        # Usar model_dump con mode='python' para obtener valores nativos
        data = transaction_data.model_dump(mode='python')
        # Asegurar que el status sea el valor del enum (string)
        if 'status' in data:
            if isinstance(data['status'], TransactionStatus):
                data['status'] = data['status'].value
            elif isinstance(data['status'], str):
                # Si ya es string, verificar que sea válido
                data['status'] = data['status'].lower()
        db_transaction = Transaction(**data)
        return super().create(db_transaction)
    
    def update(self, transaction_id: int, transaction_data: TransactionUpdate) -> Optional[Transaction]:
        db_transaction = self.get_by_id(transaction_id)
        if not db_transaction:
            return None
        
        # Convertir el enum a su valor antes de actualizar
        update_data = transaction_data.model_dump(exclude_unset=True, mode='python')
        if 'status' in update_data:
            if isinstance(update_data['status'], TransactionStatus):
                update_data['status'] = update_data['status'].value
            elif isinstance(update_data['status'], str):
                update_data['status'] = update_data['status'].lower()
        return super().update(db_transaction, update_data)
    
    def delete(self, transaction_id: int) -> bool:
        """
        Elimina una transacción (soft delete).
        El listener de SQLAlchemy interceptará el DELETE y establecerá deleted_at automáticamente.
        """
        db_transaction = self.get_by_id(transaction_id)
        if not db_transaction:
            return False
        
        # El listener de SQLAlchemy manejará el soft delete automáticamente
        # Solo necesitamos llamar a session.delete y el listener convertirá en UPDATE
        super().delete(db_transaction)
        return True

