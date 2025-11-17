from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
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
    # Usar el enum de PostgreSQL con valores explícitos
    status = Column(
        PG_ENUM(TransactionStatus, name='transactionstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    error_message = Column(String(255), nullable=True)

    
    def __repr__(self):
        return f"<Transaction(id={self.id}, transaction_id='{self.transaction_id}', amount={self.amount}, status='{self.status.value}')>"

