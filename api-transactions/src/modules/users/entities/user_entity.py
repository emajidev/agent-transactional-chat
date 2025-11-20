from sqlalchemy import Column, Float, Integer, String

from src.common.entities.base import BaseEntity


class UserEntity(BaseEntity):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    balance = Column(Float, nullable=True, default=0.0)
    currency = Column(String(10), nullable=True, default="COP")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}', balance={self.balance} {self.currency})>"



