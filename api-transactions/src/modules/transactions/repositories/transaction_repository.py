from typing import List, Optional
from src.common.repositories import BaseRepository
from src.modules.transactions.entities.transaction import Transaction
from src.modules.transactions.dtos.transaction import TransactionCreate, TransactionUpdate


class TransactionRepository(BaseRepository[Transaction]):
    
    model = Transaction
    
    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        return self.session.query(Transaction).filter(Transaction.id == transaction_id).first()

    def create(self, transaction_data: TransactionCreate) -> Transaction:
        db_transaction = Transaction(**transaction_data.model_dump())
        return super().create(db_transaction)
    
    def update(self, transaction_id: int, transaction_data: TransactionUpdate) -> Optional[Transaction]:
        db_transaction = self.get_by_id(transaction_id)
        if not db_transaction:
            return None
        
        update_data = transaction_data.model_dump(exclude_unset=True)
        return super().update(db_transaction, update_data)
    
    def delete(self, transaction_id: int) -> bool:
        db_transaction = self.get_by_id(transaction_id)
        if not db_transaction:
            return False
        
        super().delete(db_transaction)
        return True

