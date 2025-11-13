from typing import List, Optional
from sqlalchemy.orm import Session
from src.modules.transactions.repositories.transaction_repository import TransactionRepository
from src.modules.transactions.dtos.transaction import TransactionCreate, TransactionUpdate, TransactionResponse
class TransactionsService:
    
    def __init__(self, db: Session):
        self.repository = TransactionRepository(db)
    
    def get_transaction(self, transaction_id: int) -> Optional[TransactionResponse]:
        transaction = self.repository.get_by_id(transaction_id)
        if not transaction:
            return None
        return TransactionResponse.model_validate(transaction)
    
    def get_transactions(self, skip: int = 0, limit: int = 100) -> List[TransactionResponse]:
        transactions = self.repository.get_all(skip=skip, limit=limit)
        return [TransactionResponse.model_validate(t) for t in transactions]
    
    def create_transaction(self, transaction_data: TransactionCreate) -> TransactionResponse:
        transaction = self.repository.create(transaction_data)
        return TransactionResponse.model_validate(transaction)
    
    def update_transaction(
        self, 
        transaction_id: int, 
        transaction_data: TransactionUpdate
    ) -> Optional[TransactionResponse]:
        transaction = self.repository.update(transaction_id, transaction_data)
        if not transaction:
            return None
        return TransactionResponse.model_validate(transaction)
    
    def delete_transaction(self, transaction_id: int) -> bool:
        return self.repository.delete(transaction_id)

