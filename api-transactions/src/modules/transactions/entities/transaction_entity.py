from sqlalchemy import Column, Integer, String, Float, Enum
from src.common.entities.base import BaseEntity
from src.common.enums.transaction_status import TransactionStatus


class TransactionEntity(BaseEntity):    
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), nullable=False)
    transaction_id = Column(String(255), nullable=False)
    recipient_phone = Column(String(32), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(Enum(TransactionStatus), nullable=False)
    error_message = Column(String(255), nullable=True)

    
    def __repr__(self):
        return f"<Transaction(id={self.id}, transaction_id='{self.transaction_id}', amount={self.amount}, status='{self.status.value}')>"

