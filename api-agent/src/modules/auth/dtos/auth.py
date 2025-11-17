from typing import ClassVar

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, description="Nombre de usuario")
    email: EmailStr = Field(..., description="Correo electrónico")
    password: str = Field(..., min_length=6, max_length=100, description="Contraseña")

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "username": "usuario123",
                "email": "usuario@example.com",
                "password": "password123",
            }
        }


class UserLogin(BaseModel):
    username: str = Field(..., description="Nombre de usuario o email")
    password: str = Field(..., description="Contraseña")

    class Config:
        json_schema_extra: ClassVar[dict] = {"example": {"username": "admin", "password": "admin123"}}


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Token JWT de acceso")
    token_type: str = Field(default="bearer", description="Tipo de token")
    user_id: int = Field(..., description="ID del usuario")
    username: str = Field(..., description="Nombre de usuario")

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user_id": 1,
                "username": "usuario123",
            }
        }


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True
        json_schema_extra: ClassVar[dict] = {
            "example": {"id": 1, "username": "usuario123", "email": "usuario@example.com"}
        }
